#!/usr/bin/env node
/**
 * Daily check: clinical consults booked in the next 48h that have NO reachable
 * email recipient, so the reminder dispatcher will skip them.
 *
 * Exists because VP-17825 sat in production for ~6 months: reminder dispatch
 * drops participants without `calendar_owner_email` and, before the fix, did so
 * with no log and no audit row. Nobody complains about an email they never knew
 * was coming, so the only detection was a provider missing a Zoom call. 48h is
 * the lead time of the earliest reminder, so a hit here is still actionable.
 *
 * Read-only. Exit 1 when anything is unreachable OR when the check itself could
 * not run — a silent green is the failure mode this job exists to prevent.
 *
 * One exception, per Leo 2026-08-24: a consult whose attendees have no email
 * address anywhere in lis_core is NOT actionable — there is nothing to populate
 * (these are generic "Practice Admin" accounts whose contact rows hold
 * whitespace). Those are reported as a separate informational bucket and do not
 * raise the alert, so the alert keeps meaning "we lost an address we had".
 * The distinction is made against the authoritative GetCustomer RPC, never
 * assumed from the calendar row: an owner who DOES have an address but an empty
 * calendar row is the real defect and still alerts.
 */
const fs = require('fs');
const path = require('path');

const TRANSV2 = process.env.TRANSV2_DIR || '/Users/hung.l/src/LIS-transformer-v2';
const CLINICIAN_PRACTICE_ID = 150105;
const WINDOW_HOURS = Number(process.env.CONSULT_WINDOW_HOURS || 48);
const OUT_DIR = __dirname;

function loadPrisma() {
  require(path.join(TRANSV2, 'node_modules/dotenv')).config({ path: path.join(TRANSV2, '.env') });
  const { PrismaClient } = require(path.join(TRANSV2, 'node_modules/@prisma/client'));
  const url = process.env.DATABASE_URL_CALENDAR;
  if (!url || !/schema=calendar_prod/.test(url)) {
    throw new Error(`DATABASE_URL_CALENDAR missing or not pointed at calendar_prod: ${url ? 'wrong schema' : 'unset'}`);
  }
  return new PrismaClient({ datasources: { db: { url } } });
}

// ---------------------------------------------------------------------------
// Authoritative address lookup: lis.CustomerService.GetCustomer on the cloud
// mirror. Only called for consults already found unreachable (a handful a day),
// so the daily cost is negligible.
const CLOUD_RPC = process.env.CORE_RPC_CLOUD || '10.224.0.199:30276';
const DESCRIPTION_PREFERENCE = ['notification email', 'primary contact email'];
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

function pickCustomerEmail(contacts) {
  if (!contacts?.length) return null;
  const emails = contacts.filter(
    (c) => c.contact_type === 'email' && typeof c.contact_details === 'string' && c.contact_details.trim().length > 0,
  );
  if (!emails.length) return null;
  for (const preferred of DESCRIPTION_PREFERENCE) {
    const match = emails.find((c) => (c.contact_description || '').toLowerCase() === preferred);
    if (match) return match.contact_details.trim();
  }
  return emails[0].contact_details.trim();
}

async function customerLookup() {
  const grpc = require(path.join(TRANSV2, 'node_modules/@grpc/grpc-js'));
  const protoLoader = require(path.join(TRANSV2, 'node_modules/@grpc/proto-loader'));
  const axios = require(path.join(TRANSV2, 'node_modules/axios'));
  const crypto = require('crypto');

  const unquote = (v) => (v || '').trim().replace(/^'|'$/g, '');
  const params = new URLSearchParams();
  params.append('client_id', unquote(process.env.OAUTH2_CLIENT_ID));
  params.append('client_secret', unquote(process.env.OAUTH2_CLIENT_SECRET));
  params.append('grant_type', 'client_credentials');
  const tokenRes = await axios.post(unquote(process.env.OAUTH2_TOKEN_ENDPOINT), params.toString(), {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    timeout: 10000,
  });

  const metadata = new grpc.Metadata();
  metadata.set('authorization', `Bearer ${tokenRes.data.access_token}`);
  metadata.set('x-request-id', crypto.randomUUID());
  metadata.set('internal-user-id', 'consult-recipient-check');
  metadata.set('service-name', 'lis_frontend_service');

  const def = protoLoader.loadSync(path.join(TRANSV2, 'protos/lis_main.proto'), {
    keepCase: true, longs: String, enums: String, defaults: true, oneofs: true,
  });
  const client = new (grpc.loadPackageDefinition(def).lis.CustomerService)(
    CLOUD_RPC, grpc.credentials.createInsecure(),
  );

  const cache = new Map();
  return async function addressFor(customerId) {
    if (cache.has(customerId)) return cache.get(customerId);
    const result = await new Promise((resolve) => {
      client.GetCustomer({ customer_id: customerId, clinic_id: 0 }, metadata, { deadline: Date.now() + 20000 }, (err, res) => {
        if (err) return resolve({ status: 'lookup_failed', detail: err.details || err.message });
        const email = pickCustomerEmail(res?.customer_contact);
        if (email && EMAIL_RE.test(email)) return resolve({ status: 'has_address', email });
        resolve({ status: 'no_address' });
      });
    });
    cache.set(customerId, result);
    return result;
  };
}

async function main() {
  const prisma = loadPrisma();
  const now = new Date();

  const events = await prisma.v2_event.findMany({
    where: {
      practice_id: CLINICIAN_PRACTICE_ID,
      is_canceled: false,
      start_time: { gt: now, lt: new Date(now.getTime() + WINDOW_HOURS * 3600 * 1000) },
    },
    include: {
      v2_event_participant: {
        include: {
          v2_calendar: {
            select: { calendar_id: true, calendar_owner_id: true, calendar_owner_email: true, practice_id: true, role: true },
          },
        },
      },
    },
    orderBy: { start_time: 'asc' },
  });

  // Same predicate as reminder.service.ts dispatchEventReminder.
  //
  // Only events with a real attendee count. The clinical team blocks its own
  // calendar for OOO/admin notes ("OOO", "Block - Dental", "awaiting updated
  // times"); those carry a clinicadmin participant only, so the dispatcher
  // correctly sends nothing and there is no one to alert about. Alert on the
  // case that actually loses mail: an attendee exists and would be skipped.
  const unreachable = [];
  let internalBlocksSkipped = 0;
  for (const event of events) {
    const attendees = event.v2_event_participant.filter(
      (p) => !(p.v2_calendar?.practice_id === CLINICIAN_PRACTICE_ID && p.v2_calendar?.role === 'clinicadmin'),
    );
    if (attendees.length === 0) {
      internalBlocksSkipped++;
      continue;
    }
    const recipients = attendees.filter((p) => !!p.v2_calendar?.calendar_owner_email);
    const hasClinician = event.v2_event_participant.some((p) => p.v2_calendar?.role === 'clinicadmin');
    if (recipients.length === 0 || !hasClinician) {
      unreachable.push({
        event_id: Number(event.event_id),
        start_time: event.start_time.toISOString(),
        title: event.event_title,
        reason: recipients.length === 0 ? 'no attendee has calendar_owner_email' : 'no clinicadmin participant',
        calendars: attendees.map((p) => ({ calendar_id: p.v2_calendar?.calendar_id, owner: p.v2_calendar?.calendar_owner_id })),
      });
    }
  }

  // Split the unreachable set: an address that exists but never reached the
  // calendar row is our bug; an owner with no address anywhere is not.
  const actionable = [];
  const noAddressAnywhere = [];
  if (unreachable.length) {
    let addressFor;
    try {
      addressFor = await customerLookup();
    } catch (err) {
      // Cannot classify -> treat every hit as actionable. Never downgrade on doubt.
      addressFor = null;
      console.error(`address lookup unavailable (${err.message}); reporting every hit as actionable`);
    }
    for (const u of unreachable) {
      if (!addressFor || u.reason !== 'no attendee has calendar_owner_email') {
        actionable.push(u);
        continue;
      }
      const lookups = await Promise.all(u.calendars.map((c) => addressFor(Number(c.owner))));
      if (lookups.some((l) => l.status === 'lookup_failed')) {
        u.classification = 'lookup_failed';
        actionable.push(u);
      } else if (lookups.some((l) => l.status === 'has_address')) {
        u.classification = 'address_exists_but_calendar_empty';
        actionable.push(u);
      } else {
        u.classification = 'no_address_anywhere';
        noAddressAnywhere.push(u);
      }
    }
  }

  const stamp = now.toISOString().slice(0, 10);
  const lines = [
    `# Consult recipient check — ${stamp}`,
    '',
    `Window: next ${WINDOW_HOURS}h from ${now.toISOString()}`,
    `Consults scheduled: ${events.length} (internal clinical-team blocks skipped: ${internalBlocksSkipped})`,
    `**Unreachable and actionable: ${actionable.length}**`,
    `No address anywhere (informational, nothing to populate): ${noAddressAnywhere.length}`,
    '',
  ];
  if (actionable.length) {
    lines.push('| event | start | reason | calendars |', '|---|---|---|---|');
    for (const u of actionable) {
      lines.push(
        `| ${u.event_id} | ${u.start_time} | ${u.reason} | ${u.calendars.map((c) => `${c.calendar_id} (owner ${c.owner})`).join(', ')} |`,
      );
    }
    lines.push('', 'Fix: populate `calendar_owner_email` from the owner\'s LIS notification contact (VP-17825).');
  } else {
    lines.push('No consult is missing an address we actually hold.');
  }
  if (noAddressAnywhere.length) {
    lines.push('', '## No address anywhere — not actionable', '', '| event | start | calendars |', '|---|---|---|');
    for (const u of noAddressAnywhere) {
      lines.push(`| ${u.event_id} | ${u.start_time} | ${u.calendars.map((c) => `${c.calendar_id} (owner ${c.owner})`).join(', ')} |`);
    }
    lines.push('', 'GetCustomer returns no usable email contact for these owners — typically generic "Practice Admin" accounts whose contact rows hold whitespace. Reaching these attendees needs a human, not a data fix.');
  }
  fs.writeFileSync(path.join(OUT_DIR, `consult_recipient_${stamp}.md`), lines.join('\n') + '\n');

  console.log(
    `consults in next ${WINDOW_HOURS}h: ${events.length} (internal blocks skipped: ${internalBlocksSkipped}); ` +
      `actionable: ${actionable.length}; no address anywhere: ${noAddressAnywhere.length}`,
  );
  for (const u of actionable) console.log(`  ACTIONABLE event ${u.event_id} @ ${u.start_time} — ${u.classification || u.reason}`);
  for (const u of noAddressAnywhere) console.log(`  (info) event ${u.event_id} @ ${u.start_time} — no address exists for any attendee`);

  await prisma.$disconnect();
  process.exit(actionable.length ? 1 : 0);
}

main().catch((err) => {
  console.error(`CHECK FAILED (treat as unverified, not as clean): ${err.message}`);
  process.exit(1);
});
