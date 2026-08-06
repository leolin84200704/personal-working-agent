#!/usr/bin/env python3
"""Result-delivery failure watch (VP-17631 follow-up).

Nothing watches the result side. When result generation fails, the BullMQ job retries
5 times (exponential backoff, base 120s -> roughly a 30 minute window) and then
markPermanentFailure() writes GENERATION_ERROR / TRANSMISSION_ERROR with
next_retry_at = NULL. After that no cron re-drives it: TIMEOUT_RETRY (VP-17343) only
fires from a request-level timeout, and emr-v2's @Cron jobs cover order fetch, mapping
cache and scheduled reports only. So a report that fails past the retry window is never
delivered and never surfaces anywhere.

VP-17631 made the OBR-grouping path fail loudly instead of silently mislabelling panels,
which turns "wrong report delivered" into "no report delivered" — an improvement only if
somebody notices. This job is that somebody.

Report only by default. Set AUTO_REPUSH=1 to also re-drive the rows this job judges
eligible (see is_repush_eligible); every repush is verified against the live row.
"""

import json
import os
import subprocess
import sys
import time
from datetime import datetime

import pymysql

# ── Config ──────────────────────────────────────────────────────────────────
DB_HOST = os.environ.get("LIS_DB_HOST", "lisportalprod2.mysql.database.azure.com")
DB_PORT = int(os.environ.get("LIS_DB_PORT", "3306"))
DB_USER = os.environ.get("LIS_DB_USER", "lis_core_emr")
DB_PASS = os.environ.get("LIS_DB_PASS", "md?At3pUJnS2?Zx68")
DB_NAME = "lis_emr"

LOOKBACK_DAYS = int(os.environ.get("RESULT_FAIL_LOOKBACK_DAYS", "30"))
AUTO_REPUSH = os.environ.get("AUTO_REPUSH", "0") == "1"
MAX_REPUSH = int(os.environ.get("RESULT_FAIL_MAX_REPUSH", "10"))
# >=10s between GenerateResultHl7 calls: bursts degrade the lis-core v1 gRPC service
# (VP-17493 backfill, 2026-07-27 — 3 calls fine, then every call failed for minutes).
REPUSH_PACING_SECONDS = int(os.environ.get("RESULT_FAIL_REPUSH_PACING", "10"))
# How long a row must sit untouched before it counts as abandoned rather than in flight.
QUIET_HOURS = int(os.environ.get("RESULT_FAIL_QUIET_HOURS", "2"))

GRPC_TARGET = os.environ.get("RESULT_REPUSH_GRPC", "192.168.60.6:31317")
PROTO_DIR = os.environ.get(
    "RESULT_REPUSH_PROTO_DIR", "/Users/hung.l/src/lis-backend-emr-v2/src/proto"
)
PROTO_FILE = "result-generation.proto"

TODAY = datetime.now().strftime("%Y-%m-%d")
JOB_DIR = os.path.dirname(os.path.abspath(__file__))
REPORT_PATH = os.path.join(JOB_DIR, f"report_{TODAY}.md")

# Error classes. Order matters — first match wins.
ERROR_CLASSES = [
    ("obr_grouping", ("OBR grouping", "OBR_GROUPING")),
    ("upstream_grpc", ("getTestsResultsDetailData", "DEADLINE_EXCEEDED", "UNAVAILABLE", "13 INTERNAL")),
    ("sftp", ("SFTP", "sftp")),
    ("pod_restart", ("Abandoned mid-flight",)),
    ("pdf", ("PDF", "pdf")),
]
# Classes where a plain re-drive is the whole fix once the cause has passed. Anything
# else needs a human to look first, so it is reported but never auto-repushed.
REPUSHABLE_CLASSES = {"obr_grouping", "upstream_grpc", "sftp", "pod_restart"}


def get_db():
    return pymysql.connect(
        host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASS,
        database=DB_NAME, ssl={"ssl_ca": None}, ssl_disabled=False,
        connect_timeout=30, cursorclass=pymysql.cursors.DictCursor,
    )


def classify(error_message: str) -> str:
    msg = error_message or ""
    for name, needles in ERROR_CLASSES:
        if any(n in msg for n in needles):
            return name
    return "other"


def fetch_undelivered(conn):
    """Reports with no successful delivery and nothing left in flight.

    Deliberately asks about the OUTCOME, not a status combination:

    * `next_retry_at` is not a promise. Nothing reads that column — TIMEOUT_RETRY only
      fires from a request-level timeout and there is no sweeper cron — so a row with a
      future next_retry_at is just as abandoned as one with NULL. Filtering on
      "next_retry_at IS NULL" hides exactly the rows a failed retry just touched.
    * the status pair varies by where it broke: GENERATION_ERROR/TRANSMISSION_ERROR when
      grouping or an upstream call failed, GENERATED/TRANSMISSION_ERROR when only the
      upload failed, PENDING or GENERATING when the job died mid-flight. All three mean
      the clinic has no report.

    So: not TRANSMITTED, untouched for QUIET_HOURS (BullMQ's five attempts span roughly
    30 minutes, so anything older is not still trying), and no later successful sibling
    for the same sample and destination.
    """
    sql = """
        SELECT r.id, r.sample_id, r.emr_service, r.integration_request_id, r.result_client_id,
               r.result_client_type, r.generation_status, r.transmission_status, r.retry_count,
               r.next_retry_at, r.error_message, r.file_name, r.sftp_remote_path,
               r.push_scope_key, r.created_at, r.updated_at
        FROM result_transmission_records r
        WHERE r.transmission_status <> 'TRANSMITTED'
          AND r.created_at >= NOW() - INTERVAL %s DAY
          AND r.updated_at < NOW() - INTERVAL %s HOUR
          AND NOT EXISTS (
                SELECT 1 FROM result_transmission_records s
                WHERE s.sample_id = r.sample_id
                  AND s.transmission_status = 'TRANSMITTED'
                  AND s.created_at > r.created_at
                  AND (r.emr_service IS NULL OR s.emr_service = r.emr_service)
          )
        ORDER BY r.created_at DESC
    """
    with conn.cursor() as cur:
        cur.execute(sql, (LOOKBACK_DAYS, QUIET_HOURS))
        return cur.fetchall()


def fetch_broken_vendors(conn):
    """Vendors whose most recent attempt failed — deliberately NOT windowed.

    Cascades broke on 2026-06-18 and every attempt since failed; a 30-day lookback would
    have shown only the two most recent and hidden that the destination had been down for
    seven weeks. "Last attempt failed" is the question that cannot be aged out.
    """
    sql = """
        SELECT emr_service,
               MAX(CASE WHEN transmission_status = 'TRANSMITTED' THEN created_at END) AS last_ok,
               MAX(CASE WHEN transmission_status <> 'TRANSMITTED' THEN created_at END) AS last_fail,
               SUM(transmission_status <> 'TRANSMITTED') AS failures
        FROM result_transmission_records
        WHERE emr_service IS NOT NULL
        GROUP BY emr_service
        HAVING last_fail IS NOT NULL AND (last_ok IS NULL OR last_fail > last_ok)
        ORDER BY last_fail DESC
    """
    with conn.cursor() as cur:
        cur.execute(sql)
        return cur.fetchall()


def later_success_exists(conn, row) -> bool:
    """Did the same destination get this sample delivered after the failure?

    A failed row is not a missing report if a later attempt to the same vendor path
    succeeded — that one self-healed and only matters as context.
    """
    sql = """
        SELECT COUNT(*) AS n
        FROM result_transmission_records
        WHERE sample_id = %s
          AND transmission_status = 'TRANSMITTED'
          AND created_at > %s
          AND (%s IS NULL OR emr_service = %s)
    """
    with conn.cursor() as cur:
        cur.execute(sql, (row["sample_id"], row["created_at"], row["emr_service"], row["emr_service"]))
        return cur.fetchone()["n"] > 0


def integration_still_live(conn, row) -> bool:
    """Only re-drive to a destination that is still configured to receive results."""
    if row.get("integration_request_id"):
        sql = """
            SELECT COUNT(*) AS n FROM ehr_integrations
            WHERE id = %s AND status = 'LIVE' AND result_enabled = 1
        """
        params = (row["integration_request_id"],)
    elif row.get("result_client_type") == "clinic":
        sql = """
            SELECT COUNT(*) AS n FROM ehr_integrations
            WHERE customer_id = '-1' AND clinic_id = %s AND status = 'LIVE' AND result_enabled = 1
        """
        params = (row["result_client_id"],)
    else:
        sql = """
            SELECT COUNT(*) AS n FROM ehr_integrations
            WHERE customer_id = %s AND status = 'LIVE' AND result_enabled = 1
        """
        params = (str(row["result_client_id"]),)
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchone()["n"] > 0


def is_repush_eligible(conn, row) -> tuple[bool, str]:
    cls = classify(row.get("error_message"))
    if cls not in REPUSHABLE_CLASSES:
        return False, f"error class '{cls}' needs a human"
    if later_success_exists(conn, row):
        return False, "already delivered by a later attempt"
    if not integration_still_live(conn, row):
        return False, "integration no longer LIVE/result_enabled"
    return True, f"class '{cls}', no later delivery, integration live"


def repush(sample_id: int) -> dict:
    """Re-drive generation+delivery. Idempotent: the vendor gets the file again."""
    payload = json.dumps({"sample_id": sample_id, "send_result": True})
    cmd = [
        "grpcurl", "-plaintext",
        "-import-path", PROTO_DIR, "-proto", PROTO_FILE,
        "-max-time", "300", "-d", payload,
        GRPC_TARGET, "resultgeneration.ResultGenerationService/GenerateResultHl7",
    ]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=360)
    except subprocess.TimeoutExpired:
        return {"ok": False, "detail": "grpcurl timed out"}
    if out.returncode != 0:
        return {"ok": False, "detail": (out.stderr or out.stdout).strip()[:200]}
    try:
        res = json.loads(out.stdout)
    except json.JSONDecodeError:
        return {"ok": False, "detail": out.stdout.strip()[:200]}
    return {
        "ok": bool(res.get("success")),
        "record_id": res.get("resultTransmissionRecordId"),
        "detail": res.get("errorMessage") or "",
    }


def verify_repush(conn, sample_id: int, since) -> dict:
    """A repush is not done until the live row says it landed."""
    sql = """
        SELECT id, generation_status, transmission_status, file_size_bytes,
               sftp_remote_path, transmission_completed_at
        FROM result_transmission_records
        WHERE sample_id = %s AND updated_at >= %s
        ORDER BY updated_at DESC LIMIT 1
    """
    with conn.cursor() as cur:
        cur.execute(sql, (sample_id, since))
        return cur.fetchone() or {}


def notify(message: str) -> None:
    subprocess.run(
        ["osascript", "-e",
         f'display notification "{message}" with title "LIS Code Agent" sound name "Basso"'],
        capture_output=True,
    )


def render(undelivered, broken_vendors, repush_log) -> str:
    lines = [f"# Result Delivery Failure Watch — {TODAY}", ""]
    lines.append(
        f"Lookback: {LOOKBACK_DAYS} days, quiet period {QUIET_HOURS}h. "
        f"Auto-repush: {'ON' if AUTO_REPUSH else 'OFF (report only)'}."
    )
    lines.append("")

    lines.append(f"## Destinations whose last attempt failed — all time, not windowed ({len(broken_vendors)})")
    lines.append("")
    if not broken_vendors:
        lines.append("None — every vendor's most recent attempt succeeded.")
    else:
        lines.append("| vendor | last success | last failure | total failures |")
        lines.append("|---|---|---|---|")
        for v in broken_vendors:
            last_ok = f"{v['last_ok']:%Y-%m-%d}" if v["last_ok"] else "never"
            lines.append(
                f"| {v['emr_service']} | {last_ok} | {v['last_fail']:%Y-%m-%d %H:%M} | {v['failures']} |"
            )
    lines.append("")

    lines.append(f"## Undelivered reports — no successful delivery, nothing retrying ({len(undelivered)})")
    lines.append("")
    if not undelivered:
        lines.append("None.")
    else:
        lines.append("| created | sample | vendor | generation / transmission | class | error |")
        lines.append("|---|---|---|---|---|---|")
        for r in undelivered:
            err = (r.get("error_message") or "").replace("\n", " ").replace("|", "/")[:80]
            lines.append(
                f"| {r['created_at']:%Y-%m-%d %H:%M} | {r['sample_id']} | {r['emr_service'] or '-'} | "
                f"{r['generation_status']} / {r['transmission_status']} | "
                f"{classify(r.get('error_message'))} | {err} |"
            )
    lines.append("")

    if repush_log:
        lines.append(f"## Auto-repush ({len(repush_log)})")
        lines.append("")
        lines.append("| sample | attempted | new record | verified status | note |")
        lines.append("|---|---|---|---|---|")
        for e in repush_log:
            lines.append(
                f"| {e['sample_id']} | {e['attempted']} | {e.get('record_id') or '-'} | "
                f"{e.get('verified') or '-'} | {e.get('note','')[:80]} |"
            )
        lines.append("")

    lines.append("## What to do")
    lines.append("")
    lines.append("Every row in the undelivered table is a clinic that never received that report.")
    lines.append("Re-drive one once its cause has passed:")
    lines.append("")
    lines.append("```")
    lines.append(f"grpcurl -plaintext -import-path {PROTO_DIR} -proto {PROTO_FILE} \\")
    lines.append('  -d \'{"sample_id": <id>, "send_result": true}\' \\')
    lines.append(f"  {GRPC_TARGET} resultgeneration.ResultGenerationService/GenerateResultHl7")
    lines.append("```")
    lines.append("")
    lines.append("Then confirm the row reads TRANSMITTED and the file reached the vendor. An empty")
    lines.append("vendor folder is not proof of failure — most vendors collect and delete, so check")
    lines.append("their archive directory before concluding the upload did not land.")
    return "\n".join(lines) + "\n"


def main() -> int:
    print(f"[{datetime.now():%H:%M:%S}] Connecting to prod lis_emr...")
    conn = get_db()

    undelivered = fetch_undelivered(conn)
    broken_vendors = fetch_broken_vendors(conn)
    print(f"  undelivered reports: {len(undelivered)}")
    print(f"  destinations currently failing: {len(broken_vendors)}")

    repush_log = []
    if AUTO_REPUSH:
        done = 0
        for r in undelivered:
            if done >= MAX_REPUSH:
                print(f"  repush cap {MAX_REPUSH} reached — {len(undelivered) - done} row(s) left for the next run")
                break
            eligible, why = is_repush_eligible(conn, r)
            if not eligible:
                repush_log.append({"sample_id": r["sample_id"], "attempted": "no", "note": why})
                continue
            started = datetime.now()
            print(f"  repushing sample {r['sample_id']} ({why})")
            res = repush(r["sample_id"])
            entry = {"sample_id": r["sample_id"], "attempted": "yes",
                     "record_id": res.get("record_id"), "note": res.get("detail", "")}
            if res["ok"]:
                row = verify_repush(conn, r["sample_id"], started)
                entry["verified"] = row.get("transmission_status", "no row found")
            else:
                entry["verified"] = "repush failed"
            repush_log.append(entry)
            done += 1
            time.sleep(REPUSH_PACING_SECONDS)

    with open(REPORT_PATH, "w") as fh:
        fh.write(render(undelivered, broken_vendors, repush_log))
    print(f"  report: {REPORT_PATH}")

    if undelivered or broken_vendors:
        notify(
            f"{len(undelivered)} report(s) never delivered, "
            f"{len(broken_vendors)} destination(s) failing — see result_fail report"
        )
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
