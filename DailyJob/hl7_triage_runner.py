#!/usr/bin/env python3
"""HL7 File Input Daily Triage Runner"""

import pymysql
import jwt
import time
import json
import requests
import sys
from datetime import datetime

# ── Config ──────────────────────────────────────────────────────────────────
DB_HOST = "lisportalprod2.mysql.database.azure.com"
DB_PORT = 3306
DB_USER = "lis_core_emr"
DB_PASS = "md?At3pUJnS2?Zx68"
DB_NAME = "lis_emr"

JWT_SECRET = "v=I+paq@`n>0[ddC|0!go1-RtZ*:+c+_Wfj+bE|IO>lsAK2gJl8C7R>yZ@|`slg*"
BUNDLE_API_TOKEN = (
    "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
    ".eyJ1c2VySWQiOjU0Njc0LCJ1c2VyX3Blcm1pc3Npb24iOiIzZjkwM2ZlMDAwMiIsImN1c3RvbWVyX2lkIjo5OTk5OTcsImNsaW5pY19pZCI6MTAxMzYsIm9sZF9jbGluaWNfaWQiOjk5OTk5NywicGF0aWVudF9pZCI6bnVsbCwiaW50ZXJuYWxfdXNlcl9pZCI6Nzg2LCJpbnRlcm5hbF91c2VyX25hbWUiOiJuZXcub3JkZXJwYWdlIiwiaW50ZXJuYWxfdXNlcl9yb2xlIjoibmF2aWdhdG9yIiwicm9sZSI6ImN1c3RvbWVyIiwiY3VzdG9tZXJfbGlzdCI6W10sInNlc3Npb25faWQiOiIzOThBMjE0OTUzMzY0RkI5MjBFMEE2QkMxMjVDMTJDMCIsImVtYWlsX2xvZ19pbl9pZCI6InRlc3RAdmlicmFudC1hbWVyaWNhLmNvbSIsImJldGFfcHJvZ3JhbV9lbmFibGVkIjp0cnVlLCJiZXRhX3Byb2dyYW1zIjpbXSwiaWF0IjoxNzE0Njg2MjU3LCJleHAiOjIzNDU4MzgyNTd9"
    ".WZo5DKV_qTZ0PKFvVIUf1cpNk_wzlNEslsGrSosVe30"
)

BUNDLE_API_URL = "https://api.vibrant-wellness.com/v1/pricing/item/promotion/getLegacyBundleMapping?currency=usd"
PAYMENT_METHODS_URL = "https://www.vibrant-america.com/lisapi/v1/charging/paymentMethod/allSharedPaymentMethods"
TRANSACTION_PAY_URL = "https://www.vibrant-america.com/lisapi/v1/charging/transaction/pay"
ORDER_API_URL = "https://www.vibrant-america.com/lisapi/v1/portal/order/orderTest/order"

TODAY = datetime.now().strftime("%Y-%m-%d")
REPORT_PATH = f"/Users/hung.l/src/lis-code-agent/DailyJob/hl7_fail/triage_{TODAY}.md"


# ── DB helper ────────────────────────────────────────────────────────────────
def get_db():
    return pymysql.connect(
        host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASS,
        database=DB_NAME, ssl={"ssl_ca": None}, ssl_disabled=False,
        connect_timeout=30, cursorclass=pymysql.cursors.DictCursor
    )


def query(conn, sql, args=None):
    with conn.cursor() as cur:
        cur.execute(sql, args or ())
        return cur.fetchall()


def execute(conn, sql, args=None):
    with conn.cursor() as cur:
        cur.execute(sql, args or ())
    conn.commit()


# ── JWT helper ───────────────────────────────────────────────────────────────
def make_jwt(customer_id, clinic_id, role, get_pm=False):
    now = int(time.time())
    payload = {
        "userId": 54674,
        "user_permission": "3f903fe0002",
        "customer_id": customer_id,
        "clinic_id": clinic_id,
        "old_clinic_id": customer_id,
        "patient_id": None,
        "internal_user_id": 786,
        "internal_user_name": "bolin.l",
        "internal_user_role": "admin",
        "role": role,
        "customer_list": [],
        "session_id": None,
        "email_log_in_id": "bolin.l@vibrant-america.com",
        "beta_program_enabled": False,
        "beta_programs": [],
        "iat": now,
        "exp": now + 6000,
    }
    if get_pm:
        payload["getTokenCustomerPM"] = True
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


# ── Step 1: Query ────────────────────────────────────────────────────────────
def step1_query(conn):
    sql = """
        SELECT id, file_name, emr_code_not_found, sftpDir, emr_service,
               retry_num, parse_finished, received_time,
               LEFT(order_input, 2000) AS order_input
        FROM hl7_file_input
        WHERE parse_finished = 0
          AND retry_num = 0
          AND received_time >= NOW() - INTERVAL 72 HOUR
        ORDER BY received_time DESC
    """
    return query(conn, sql)


# ── Step 2: Classify ─────────────────────────────────────────────────────────
def step2_classify(rows):
    type_a, type_b, type_c = [], [], []
    for r in rows:
        if r["emr_code_not_found"]:
            type_a.append(r)
        elif r["order_input"]:
            type_b.append(r)
        else:
            type_c.append(r)
    return type_a, type_b, type_c


# ── Step 3: Type A ───────────────────────────────────────────────────────────
def step3_type_a(conn, type_a_rows):
    results = []

    # Fetch bundle mapping once
    try:
        resp = requests.get(
            BUNDLE_API_URL,
            headers={"Authorization": BUNDLE_API_TOKEN},
            timeout=30
        )
        bundle_data = resp.json() if resp.ok else {}
    except Exception as e:
        bundle_data = {}
        print(f"[WARN] Bundle mapping API failed: {e}")

    # Build panelId lookup: panelId -> bundle info
    panel_lookup = {}
    if isinstance(bundle_data, list):
        for item in bundle_data:
            pid = item.get("panelId") or item.get("panel_id")
            if pid:
                panel_lookup[str(pid)] = item
    elif isinstance(bundle_data, dict):
        items = bundle_data.get("data") or bundle_data.get("result") or []
        for item in (items if isinstance(items, list) else [bundle_data]):
            pid = item.get("panelId") or item.get("panel_id")
            if pid:
                panel_lookup[str(pid)] = item

    # Group by emr_code_not_found
    code_groups = {}
    for r in type_a_rows:
        code = r["emr_code_not_found"]
        code_groups.setdefault(code, []).append(r)

    for code, rows in code_groups.items():
        # Extract panel id from VACP code (e.g. "VACP12345" -> "12345")
        panel_id = ""
        if code and code.upper().startswith("VACP"):
            panel_id = code[4:]
        bundle_status = "found" if panel_id and panel_id in panel_lookup else "not_found_in_bundle"

        # Look up clinic info per row
        clinic_infos = []
        for r in rows:
            sftp_dir = r.get("sftpDir") or ""
            clinic_info = {"sftp_dir": sftp_dir, "clinic_name": None, "clinic_id": None, "customer_id": None}
            if sftp_dir:
                try:
                    oc_rows = query(conn,
                        "SELECT oc.clinic_id, oc.customer_id, ei.clinic_name "
                        "FROM order_clients oc "
                        "LEFT JOIN ehr_integrations ei ON ei.clinic_id = oc.clinic_id "
                        "WHERE oc.sftp_dir = %s LIMIT 1",
                        (sftp_dir,)
                    )
                    if oc_rows:
                        clinic_info.update({
                            "clinic_id": oc_rows[0]["clinic_id"],
                            "customer_id": oc_rows[0]["customer_id"],
                            "clinic_name": oc_rows[0]["clinic_name"],
                        })
                except Exception as e:
                    clinic_info["error"] = str(e)
            clinic_infos.append(clinic_info)

        results.append({
            "code": code,
            "panel_id": panel_id,
            "bundle_status": bundle_status,
            "count": len(rows),
            "rows": rows,
            "clinic_infos": clinic_infos,
        })

    return results


# ── Step 4: Type B ───────────────────────────────────────────────────────────
def step4_type_b(conn, type_b_rows):
    results = []

    for r in type_b_rows:
        rec_id = r["id"]
        file_name = r["file_name"]
        sftp_dir = r.get("sftpDir") or ""
        result = {"id": rec_id, "file_name": file_name, "status": "failed", "error": None,
                  "new_sample_id": None, "new_payment_id": None, "new_julien_barcode": None}

        try:
            # Parse order_input
            order_input_str = r["order_input"] or ""
            try:
                order_input = json.loads(order_input_str)
            except Exception:
                result["error"] = f"Cannot parse order_input JSON: {order_input_str[:200]}"
                results.append(result)
                continue

            clinic_id = order_input.get("clinic_id") or order_input.get("clinicId")
            amount = (
                order_input.get("total") or
                order_input.get("amount") or
                order_input.get("price") or
                order_input.get("totalPrice") or
                0
            )

            # Look up customer_id
            customer_id = None
            if sftp_dir:
                oc_rows = query(conn,
                    "SELECT customer_id FROM order_clients WHERE sftp_dir = %s LIMIT 1",
                    (sftp_dir,)
                )
                if oc_rows:
                    customer_id = oc_rows[0]["customer_id"]

            if not customer_id and clinic_id:
                ei_rows = query(conn,
                    "SELECT customer_id FROM ehr_integrations "
                    "WHERE clinic_id = %s AND status = 'LIVE' LIMIT 1",
                    (clinic_id,)
                )
                if ei_rows:
                    customer_id = ei_rows[0]["customer_id"]

            if not customer_id:
                result["error"] = f"Cannot find customer_id for sftp_dir={sftp_dir}, clinic_id={clinic_id}"
                results.append(result)
                continue

            if not clinic_id:
                result["error"] = "clinic_id missing from order_input"
                results.append(result)
                continue

            # Get clinic info for display
            clinic_name = None
            ci_rows = query(conn,
                "SELECT clinic_name FROM ehr_integrations WHERE clinic_id = %s LIMIT 1",
                (clinic_id,)
            )
            if ci_rows:
                clinic_name = ci_rows[0]["clinic_name"]
            result["clinic_name"] = clinic_name
            result["clinic_id"] = clinic_id
            result["customer_id"] = customer_id

            # Generate payment JWT (role=clinic, getTokenCustomerPM=True)
            payment_jwt = make_jwt(customer_id, clinic_id, "clinic", get_pm=True)

            # Get payment methods
            pm_resp = requests.get(
                PAYMENT_METHODS_URL,
                headers={"Authorization": f"Bearer {payment_jwt}"},
                timeout=30
            )
            if not pm_resp.ok:
                result["error"] = f"Payment methods API {pm_resp.status_code}: {pm_resp.text[:300]}"
                results.append(result)
                continue

            pm_data = pm_resp.json()
            # Extract payment_token and customer_token
            payment_token = None
            customer_token = None
            pm_list = pm_data if isinstance(pm_data, list) else (pm_data.get("data") or [])
            if pm_list:
                first_pm = pm_list[0]
                payment_token = (
                    first_pm.get("payment_token") or
                    first_pm.get("paymentToken") or
                    first_pm.get("token") or
                    first_pm.get("id")
                )
                customer_token = (
                    first_pm.get("customer_token") or
                    first_pm.get("customerToken") or
                    first_pm.get("customer_id") or
                    first_pm.get("customerId")
                )

            if not payment_token:
                result["error"] = f"No payment_token found in PM response: {str(pm_data)[:300]}"
                results.append(result)
                continue

            # Call transactionPay
            pay_payload = {
                "account_id": customer_id,
                "account_type": "customer",
                "amount": amount,
                "currency": "usd",
                "charge_type": "testorder",
                "type": "card",
                "token_platform": "stax",
                "payment_source": "emr",
                "payment_token": payment_token,
                "customer_token": customer_token,
                "new_sample": True,
            }
            pay_resp = requests.post(
                TRANSACTION_PAY_URL,
                json=pay_payload,
                headers={"Authorization": f"Bearer {payment_jwt}", "Content-Type": "application/json"},
                timeout=30
            )
            if not pay_resp.ok:
                result["error"] = f"TransactionPay {pay_resp.status_code}: {pay_resp.text[:300]}"
                results.append(result)
                continue

            pay_data = pay_resp.json()
            new_sample_id = (
                pay_data.get("sampleId") or pay_data.get("sample_id") or
                pay_data.get("data", {}).get("sampleId") if isinstance(pay_data.get("data"), dict) else None
            )
            new_payment_id = (
                pay_data.get("paymentId") or pay_data.get("payment_id") or pay_data.get("id") or
                pay_data.get("data", {}).get("id") if isinstance(pay_data.get("data"), dict) else None
            )
            new_julien_barcode = (
                pay_data.get("julienBarcode") or pay_data.get("julien_barcode") or
                pay_data.get("data", {}).get("julienBarcode") if isinstance(pay_data.get("data"), dict) else None
            )

            # Update order_input with new values
            updated_order = dict(order_input)
            if new_sample_id:
                updated_order["sampleId"] = new_sample_id
                updated_order["sample_id"] = new_sample_id
            if new_payment_id:
                updated_order["payment_id"] = new_payment_id
                updated_order["paymentId"] = new_payment_id
            if new_julien_barcode:
                updated_order["julienBarcode"] = new_julien_barcode

            # Generate order JWT (role=customer)
            order_jwt = make_jwt(customer_id, clinic_id, "customer")

            # Call Order API
            order_resp = requests.post(
                ORDER_API_URL,
                json=updated_order,
                headers={"Authorization": f"Bearer {order_jwt}", "Content-Type": "application/json"},
                timeout=30
            )
            if not order_resp.ok:
                result["error"] = f"Order API {order_resp.status_code}: {order_resp.text[:300]}"
                results.append(result)
                continue

            order_data = order_resp.json()

            # UPDATE hl7_file_input
            execute(conn,
                """UPDATE hl7_file_input
                   SET parse_finished=1,
                       sample_id=%s,
                       payment_id=%s,
                       julien_barcode=%s,
                       sample_id_payment=%s,
                       retry_num=0
                   WHERE id=%s""",
                (new_sample_id, new_payment_id, new_julien_barcode, new_sample_id, rec_id)
            )

            result["status"] = "recovered"
            result["new_sample_id"] = new_sample_id
            result["new_payment_id"] = new_payment_id
            result["new_julien_barcode"] = new_julien_barcode

        except Exception as e:
            result["error"] = str(e)

        results.append(result)

    return results


# ── Step 5: Report ───────────────────────────────────────────────────────────
def step5_report(all_rows, type_a_results, type_b_results, type_c_rows):
    total = len(all_rows)
    ta_count = len(type_a_results)
    tb_recovered = sum(1 for r in type_b_results if r["status"] == "recovered")
    tb_failed = sum(1 for r in type_b_results if r["status"] == "failed")
    tc_count = len(type_c_rows)

    lines = [
        f"# HL7 File Input Daily Triage — {TODAY}",
        "",
        "## Summary",
        f"- 查詢時間範圍：過去 72 小時",
        f"- 失敗總筆數：{total}",
        f"- Type A（code not found）：{ta_count} 筆",
        f"- Type B（order failure）：{tb_recovered} 筆已恢復，{tb_failed} 筆失敗",
        f"- Type C（parse failure）：{tc_count} 筆",
        "",
        "---",
        "",
        "## Type A — EMR Code Not Found",
        "",
    ]

    if not type_a_results:
        lines.append("無 Type A 記錄。")
    else:
        for item in type_a_results:
            lines.append(f"### Code: `{item['code']}` (panel_id: {item['panel_id'] or 'N/A'})")
            lines.append(f"- 出現次數：{item['count']}")
            lines.append(f"- Bundle Mapping 狀態：{item['bundle_status']}")
            for i, (row, ci) in enumerate(zip(item["rows"], item["clinic_infos"])):
                lines.append(f"- 記錄 #{i+1}: id={row['id']}, file={row['file_name']}")
                lines.append(f"  - sftpDir: {row.get('sftpDir')}")
                lines.append(f"  - clinic_name: {ci.get('clinic_name')}, clinic_id: {ci.get('clinic_id')}, customer_id: {ci.get('customer_id')}")
            lines.append("")

    lines += [
        "---",
        "",
        "## Type B — Payment/Order Recovery",
        "",
    ]

    if not type_b_results:
        lines.append("無 Type B 記錄。")
    else:
        for r in type_b_results:
            status_label = "✓ 已恢復" if r["status"] == "recovered" else "✗ 失敗"
            lines.append(f"### id={r['id']} — {r['file_name']}")
            lines.append(f"- 狀態：{status_label}")
            lines.append(f"- clinic：{r.get('clinic_name')} (id={r.get('clinic_id')}), customer_id={r.get('customer_id')}")
            if r["status"] == "recovered":
                lines.append(f"- new sample_id：{r['new_sample_id']}")
                lines.append(f"- new payment_id：{r['new_payment_id']}")
                lines.append(f"- new julien_barcode：{r['new_julien_barcode']}")
            else:
                lines.append(f"- 錯誤：{r['error']}")
            lines.append("")

    lines += [
        "---",
        "",
        "## Type C — Parse Failures",
        "",
    ]

    if not type_c_rows:
        lines.append("無 Type C 記錄。")
    else:
        for r in type_c_rows:
            lines.append(f"- id={r['id']}, file={r['file_name']}, emr_service={r.get('emr_service')}, sftpDir={r.get('sftpDir')}, received={r.get('received_time')}")

    lines.append("")
    lines.append(f"---")
    lines.append(f"*Generated at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")

    return "\n".join(lines)


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Connecting to DB...")
    conn = get_db()

    print(f"[{datetime.now().strftime('%H:%M:%S')}] Step 1: Querying failed records...")
    rows = step1_query(conn)
    print(f"  Found {len(rows)} failed records")

    if not rows:
        report = f"# HL7 File Input Daily Triage — {TODAY}\n\nNo failed records found.\n"
        with open(REPORT_PATH, "w") as f:
            f.write(report)
        print(f"  No records. Report written to {REPORT_PATH}")
        conn.close()
        return

    print(f"[{datetime.now().strftime('%H:%M:%S')}] Step 2: Classifying...")
    type_a, type_b, type_c = step2_classify(rows)
    print(f"  Type A={len(type_a)}, Type B={len(type_b)}, Type C={len(type_c)}")

    print(f"[{datetime.now().strftime('%H:%M:%S')}] Step 3: Processing Type A...")
    type_a_results = step3_type_a(conn, type_a)

    print(f"[{datetime.now().strftime('%H:%M:%S')}] Step 4: Processing Type B (recovery)...")
    type_b_results = step4_type_b(conn, type_b)
    recovered = sum(1 for r in type_b_results if r["status"] == "recovered")
    print(f"  Recovered {recovered}/{len(type_b)} records")

    print(f"[{datetime.now().strftime('%H:%M:%S')}] Step 5: Generating report...")
    report = step5_report(rows, type_a_results, type_b_results, type_c)

    with open(REPORT_PATH, "w") as f:
        f.write(report)

    print(f"  Report written to {REPORT_PATH}")
    conn.close()
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Done.")


if __name__ == "__main__":
    main()
