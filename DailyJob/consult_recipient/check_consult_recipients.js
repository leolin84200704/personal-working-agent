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

  const stamp = now.toISOString().slice(0, 10);
  const lines = [
    `# Consult recipient check — ${stamp}`,
    '',
    `Window: next ${WINDOW_HOURS}h from ${now.toISOString()}`,
    `Consults scheduled: ${events.length} (internal clinical-team blocks skipped: ${internalBlocksSkipped})`,
    `**Unreachable: ${unreachable.length}**`,
    '',
  ];
  if (unreachable.length) {
    lines.push('| event | start | reason | calendars |', '|---|---|---|---|');
    for (const u of unreachable) {
      lines.push(
        `| ${u.event_id} | ${u.start_time} | ${u.reason} | ${u.calendars.map((c) => `${c.calendar_id} (owner ${c.owner})`).join(', ')} |`,
      );
    }
    lines.push('', 'Fix: populate `calendar_owner_email` from the owner\'s LIS notification contact (VP-17825).');
  } else {
    lines.push('All upcoming consults have a reachable recipient.');
  }
  fs.writeFileSync(path.join(OUT_DIR, `consult_recipient_${stamp}.md`), lines.join('\n') + '\n');

  console.log(
    `consults in next ${WINDOW_HOURS}h: ${events.length} (internal blocks skipped: ${internalBlocksSkipped}); unreachable: ${unreachable.length}`,
  );
  for (const u of unreachable) console.log(`  event ${u.event_id} @ ${u.start_time} — ${u.reason}`);

  await prisma.$disconnect();
  process.exit(unreachable.length ? 1 : 0);
}

main().catch((err) => {
  console.error(`CHECK FAILED (treat as unverified, not as clean): ${err.message}`);
  process.exit(1);
});
