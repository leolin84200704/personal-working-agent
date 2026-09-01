/**
 * VP-18030 staging E2E — run INSIDE the emr-v2 staging pod:
 *   node /tmp/vp18030-e2e.js
 * Mints an HS256 JWT from the pod's JWT_SECRET (payload must include userId —
 * JwtStrategy rejects otherwise) and exercises GET list mode on localhost.
 */
const crypto = require('crypto');
const http = require('http');

const SECRET = process.env.JWT_SECRET;
if (!SECRET) { console.error('no JWT_SECRET'); process.exit(1); }
const CUSTOMER = Number(process.env.E2E_CUSTOMER || 3194);
const OTHER_CUSTOMER = Number(process.env.E2E_OTHER_CUSTOMER || 999997);

const b64 = (o) => Buffer.from(JSON.stringify(o)).toString('base64url');
function mint(customerId) {
  const h = b64({ alg: 'HS256', typ: 'JWT' });
  const p = b64({ userId: 1, customer_id: customerId, iat: Math.floor(Date.now() / 1000), exp: Math.floor(Date.now() / 1000) + 3600 });
  const sig = crypto.createHmac('sha256', SECRET).update(`${h}.${p}`).digest('base64url');
  return `${h}.${p}.${sig}`;
}
const TOKEN = mint(CUSTOMER);

function get(path, token = TOKEN) {
  return new Promise((resolve, reject) => {
    const t0 = Date.now();
    const req = http.request({ host: 'localhost', port: 3000, path, method: 'GET', headers: { authorization: `Bearer ${token}` } }, (res) => {
      let body = '';
      res.on('data', (c) => (body += c));
      res.on('end', () => {
        let json = null; try { json = JSON.parse(body); } catch {}
        resolve({ status: res.statusCode, json, ms: Date.now() - t0, reqId: res.headers['x-request-id'] });
      });
    });
    req.on('error', reject);
    req.setTimeout(60000, () => req.destroy(new Error('timeout')));
    req.end();
  });
}

let pass = 0, fail = 0;
const ok = (name, cond, detail) => { if (cond) { pass++; console.log(`PASS ${name}`); } else { fail++; console.log(`FAIL ${name} :: ${detail}`); } };
const STATUSES = new Set(['placed','kit_shipped','kit_delivered','sample_in_transit','sample_received','analyzing','report_available','cancelled']);

(async () => {
  const B = '/api/v1/order-status';

  // 1. bare GET = clinic-wide list, envelope + defaults
  const r1 = await get(B);
  ok('1a bare GET 200', r1.status === 200, `${r1.status} ${JSON.stringify(r1.json).slice(0,200)}`);
  ok('1b envelope', r1.json && Array.isArray(r1.json.orders) && typeof r1.json.count === 'number' && r1.json.page === 1 && r1.json.perPage === 20, JSON.stringify(r1.json).slice(0,200));
  console.log(`   count=${r1.json?.count} latency=${r1.ms}ms rows=${r1.json?.orders?.length}`);
  if (r1.json?.orders?.length) console.log('   sample row:', JSON.stringify(r1.json.orders[0]));

  // 2. validation matrix
  const v = async (name, qs, code, httpStatus = 400) => {
    const r = await get(`${B}?${qs}`);
    ok(name, r.status === httpStatus && r.json?.error?.code === code, `${r.status} ${JSON.stringify(r.json?.error || r.json).slice(0,160)}`);
  };
  await v('2a unknown param', 'bogus=1', 'UNSUPPORTED_PARAMETER');
  await v('2b customerId rejected', 'customerId=999', 'UNSUPPORTED_PARAMETER');
  await v('2c mixed lookup+list', 'orderId=x&patientId=5', 'AMBIGUOUS_ORDER_IDENTIFIER');
  await v('2d bad patientId', 'patientId=abc', 'INVALID_FIELD_TYPE');
  await v('2e offsetless datetime', 'from=2026-08-01T10:00:00', 'INVALID_FIELD_TYPE');
  await v('2f empty window', 'from=2026-08-02&to=2026-08-01', 'INVALID_DATE_RANGE');
  await v('2g bad sortBy', 'sortBy=createdAt', 'INVALID_FIELD_TYPE');
  const rc = await get(`${B}?perPage=250`);
  ok('2h perPage clamps to 100', rc.status === 200 && rc.json?.perPage === 100, `${rc.status} perPage=${rc.json?.perPage}`);
  const rl = await get(`${B}?orderId=`);
  ok('2i blank lookup id still MISSING', rl.status === 400 && rl.json?.error?.code === 'MISSING_ORDER_IDENTIFIER', `${rl.status} ${rl.json?.error?.code}`);
  ok('2j request id present', !!r1.reqId, 'no x-request-id');

  // 3. pagination walk (perPage=2): no dup/miss across first pages, count stable
  const p1 = await get(`${B}?perPage=2&page=1`);
  const p2 = await get(`${B}?perPage=2&page=2`);
  const ids1 = (p1.json?.orders || []).map((o) => o.sampleId);
  const ids2 = (p2.json?.orders || []).map((o) => o.sampleId);
  ok('3a pages disjoint', ids1.every((id) => !ids2.includes(id)), `${ids1} vs ${ids2}`);
  ok('3b count stable', p1.json?.count === p2.json?.count && p1.json?.count === r1.json?.count, `${p1.json?.count}/${p2.json?.count}/${r1.json?.count}`);
  const beyond = await get(`${B}?page=99999`);
  ok('3c page past end = empty 200', beyond.status === 200 && beyond.json?.orders?.length === 0 && beyond.json?.count === r1.json?.count, `${beyond.status} ${beyond.json?.orders?.length}`);

  // 4. asc/desc reversal over full set (small sets on staging)
  const asc = await get(`${B}?sortOrder=asc&perPage=100`);
  const desc = await get(`${B}?sortOrder=desc&perPage=100`);
  if ((asc.json?.count ?? 0) <= 100) {
    const a = (asc.json?.orders || []).map((o) => o.sampleId);
    const d = (desc.json?.orders || []).map((o) => o.sampleId);
    ok('4a asc = reverse(desc)', JSON.stringify(a) === JSON.stringify([...d].reverse()), `${a} vs ${d}`);
  } else console.log('SKIP 4a (count>100)');

  // 5. row shape + status enum + channel split
  const rows = r1.json?.orders || [];
  ok('5a statuses valid', rows.every((o) => o.status === null || STATUSES.has(o.status)), JSON.stringify(rows.map((o) => o.status)));
  const api = rows.filter((o) => o.placerId != null);
  const portal = rows.filter((o) => o.placerId == null);
  console.log(`   channel split on page1: api=${api.length} portal=${portal.length}`);
  ok('5b api rows have accession or degraded-null shape', api.every((o) => 'accessionId' in o && 'testCodes' in o), JSON.stringify(api[0] || {}));
  if (portal.length) ok('5c portal rows: null orderId/placerId/testCodes + accession', portal.every((o) => o.orderId === null && o.testCodes === null), JSON.stringify(portal[0]));
  else console.log('NOTE 5c: no portal-channel rows for this customer on staging page1 — cross-channel proof needs a customer with both');
  const statusDist = {};
  rows.forEach((o) => { statusDist[o.status] = (statusDist[o.status] || 0) + 1; });
  console.log('   status distribution:', JSON.stringify(statusDist));

  // 6. half-open window boundary on a real row's orderedAt
  const anchor = rows.find((o) => o.orderedAt);
  if (anchor) {
    const t = anchor.orderedAt;
    const incl = await get(`${B}?from=${encodeURIComponent(t)}&perPage=100`);
    const has = (incl.json?.orders || []).some((o) => o.sampleId === anchor.sampleId);
    ok('6a from=t includes t', has, `anchor ${anchor.sampleId} orderedAt ${t} not in from=t result`);
    const excl = await get(`${B}?to=${encodeURIComponent(t)}&perPage=100`);
    const gone = !(excl.json?.orders || []).some((o) => o.sampleId === anchor.sampleId);
    ok('6b to=t excludes t', gone, `anchor ${anchor.sampleId} still present with to=t`);
  } else console.log('SKIP 6 (no row with orderedAt)');

  // 7. patientId path
  const anyPatient = rows.find((o) => o.patientId != null);
  if (anyPatient) {
    const rp = await get(`${B}?patientId=${anyPatient.patientId}`);
    ok('7a patient list 200', rp.status === 200 && (rp.json?.orders || []).length >= 1, `${rp.status} ${rp.json?.count}`);
    ok('7b all rows this patient (or null pid on degraded)', (rp.json?.orders || []).every((o) => o.patientId === anyPatient.patientId || o.patientId === null), JSON.stringify(rp.json?.orders?.map((o) => o.patientId)));
  } else console.log('SKIP 7a/b (no patientId on page1)');
  const r404 = await get(`${B}?patientId=999999999`);
  ok('7c unknown patient 404', r404.status === 404 && r404.json?.error?.code === 'PATIENT_NOT_FOUND', `${r404.status} ${JSON.stringify(r404.json?.error).slice(0,160)}`);
  if (anyPatient) {
    const foreign = await get(`${B}?patientId=${anyPatient.patientId}`, mint(OTHER_CUSTOMER));
    ok('7d other-tenant token 404 for same patient', foreign.status === 404, `${foreign.status} ${JSON.stringify(foreign.json).slice(0,160)} (NOTE: passes only if patient has no orders under ${OTHER_CUSTOMER})`);
  }

  // 8. lookup mode regression (unchanged)
  const lk = await get(`${B}?placerId=NO-SUCH-PLACER-VP18030`);
  ok('8a lookup 404 unchanged', lk.status === 404 && lk.json?.error?.code === 'ORDER_NOT_FOUND', `${lk.status} ${lk.json?.error?.code}`);

  // 9. latency summary
  const t1 = await get(B);
  console.log(`   latency: bare list ${t1.ms}ms (count=${t1.json?.count})`);

  console.log(`\nRESULT: ${pass} pass / ${fail} fail`);
  process.exit(fail ? 1 : 0);
})().catch((e) => { console.error('SUITE ERROR', e); process.exit(2); });
