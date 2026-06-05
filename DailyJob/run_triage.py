#!/usr/bin/env python3
"""HL7 File Input Daily Triage Script"""
import subprocess
import json
import time
import datetime
import requests
import re
import sys
import os

# ─── Config ───────────────────────────────────────────────────────────────────
JWT_SECRET = r"v=I+paq@`n>0[ddC|0!go1-RtZ*:+c+_Wfj+bE|IO>lsAK2gJl8C7R>yZ@|`slg*"
BUNDLE_API_TOKEN = "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VySWQiOjU0Njc0LCJ1c2VyX3Blcm1pc3Npb24iOiIzZjkwM2ZlMDAwMiIsImN1c3RvbWVyX2lkIjo5OTk5OTcsImNsaW5pY19pZCI6MTAxMzYsIm9sZF9jbGluaWNfaWQiOjk5OTk5NywicGF0aWVudF9pZCI6bnVsbCwiaW50ZXJuYWxfdXNlcl9pZCI6Nzg2LCJpbnRlcm5hbF91c2VyX25hbWUiOiJuZXcub3JkZXJwYWdlIiwiaW50ZXJuYWxfdXNlcl9yb2xlIjoibmF2aWdhdG9yIiwicm9sZSI6ImN1c3RvbWVyIiwiY3VzdG9tZXJfbGlzdCI6W10sInNlc3Npb25faWQiOiIzOThBMjE0OTUzMzY0RkI5MjBFMEE2QkMxMjVDMTJDMCIsImVtYWlsX2xvZ19pbl9pZCI6InRlc3RAdmlicmFudC1hbWVyaWNhLmNvbSIsImJldGFfcHJvZ3JhbV9lbmFibGVkIjp0cnVlLCJiZXRhX3Byb2dyYW1zIjpbXSwiaWF0IjoxNzE0Njg2MjU3LCJleHAiOjIzNDU4MzgyNTd9.WZo5DKV_qTZ0PKFvVIUf1cpNk_wzlNEslsGrSosVe30"

MYSQL_CLI = "/opt/homebrew/opt/mysql-client/bin/mysql"
MYSQL_CONN = "lisportalprod2.mysql.database.azure.com"
MYSQL_PORT = "3306"
MYSQL_USER = "lis_core_emr"
MYSQL_PASS = "md?At3pUJnS2?Zx68"
MYSQL_DB = "lis_emr"

TODAY = datetime.date.today().isoformat()
OUTPUT_DIR = "/Users/hung.l/src/lis-code-agent/DailyJob/hl7_fail"
OUTPUT_FILE = f"{OUTPUT_DIR}/triage_{TODAY}.md"

# ─── DB Helper ────────────────────────────────────────────────────────────────
def run_sql(sql, db=MYSQL_DB):
    cmd = [
        MYSQL_CLI,
        f"-h{MYSQL_CONN}", f"-P{MYSQL_PORT}",
        f"-u{MYSQL_USER}", f"-p{MYSQL_PASS}",
        "--ssl-mode=REQUIRED",
        "--batch", "--raw",
        db,
        "-e", sql
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        raise RuntimeError(f"MySQL error: {result.stderr}")
    return result.stdout

def parse_table(output):
    lines = output.strip().split("\n")
    if not lines or len(lines) < 2:
        return []
    headers = lines[0].split("\t")
    rows = []
    for line in lines[1:]:
        vals = line.split("\t")
        row = {}
        for i, h in enumerate(headers):
            row[h] = vals[i] if i < len(vals) else None
        rows.append(row)
    return rows

# ─── JWT Helper ───────────────────────────────────────────────────────────────
def gen_jwt(customer_id, clinic_id, role="clinic", get_pm=False):
    import jwt as pyjwt
    now = int(time.time())
    payload = {
        "userId": 54674,
        "user_permission": "3f903fe0002",
        "customer_id": int(customer_id) if customer_id else None,
        "clinic_id": int(clinic_id) if clinic_id else None,
        "old_clinic_id": int(customer_id) if customer_id else None,
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
        "exp": now + 6000
    }
    if get_pm:
        payload["getTokenCustomerPM"] = True
    return pyjwt.encode(payload, JWT_SECRET, algorithm="HS256")

# ─── API Helpers ──────────────────────────────────────────────────────────────
def get_bundle_mapping():
    url = "https://api.vibrant-wellness.com/v1/pricing/item/promotion/getLegacyBundleMapping?currency=usd"
    headers = {"Authorization": BUNDLE_API_TOKEN}
    r = requests.get(url, headers=headers, timeout=30)
    r.raise_for_status()
    return r.json()

def get_payment_methods(customer_id, clinic_id):
    token = gen_jwt(customer_id, clinic_id, role="clinic", get_pm=True)
    url = "https://www.vibrant-america.com/lisapi/v1/charging/paymentMethod/allSharedPaymentMethods"
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.get(url, headers=headers, timeout=30)
    r.raise_for_status()
    return r.json()

def transaction_pay(customer_id, clinic_id, amount, payment_token, customer_token):
    token = gen_jwt(customer_id, clinic_id, role="clinic", get_pm=True)
    url = "https://www.vibrant-america.com/lisapi/v1/charging/transaction/pay"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    body = {
        "account_id": int(customer_id),
        "account_type": "customer",
        "amount": float(amount),
        "currency": "usd",
        "charge_type": "testorder",
        "type": "card",
        "token_platform": "stax",
        "payment_source": "emr",
        "payment_token": payment_token,
        "customer_token": customer_token,
        "new_sample": True
    }
    r = requests.post(url, json=body, headers=headers, timeout=30)
    r.raise_for_status()
    return r.json()

def place_order(customer_id, clinic_id, order_input):
    token = gen_jwt(customer_id, clinic_id, role="customer")
    url = "https://www.vibrant-america.com/lisapi/v1/portal/order/orderTest/order"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    if isinstance(order_input, str):
        body = json.loads(order_input)
    else:
        body = order_input
    r = requests.post(url, json=body, headers=headers, timeout=30)
    r.raise_for_status()
    return r.json()

# ─── Lookup Helpers ───────────────────────────────────────────────────────────
def get_clinic_info_by_sftp(sftp_dir):
    sql = f"""
        SELECT oc.clinic_name, oc.clinic_id, oc.customer_id
        FROM order_clients oc
        WHERE oc.sftp_dir = '{sftp_dir}'
        LIMIT 1;
    """
    out = run_sql(sql)
    rows = parse_table(out)
    if rows:
        return rows[0]
    # fallback via ehr_integrations
    sql2 = f"""
        SELECT ei.clinic_name, ei.clinic_id, ei.customer_id
        FROM ehr_integrations ei
        WHERE ei.sftp_dir = '{sftp_dir}' AND ei.status = 'LIVE'
        LIMIT 1;
    """
    out2 = run_sql(sql2)
    rows2 = parse_table(out2)
    return rows2[0] if rows2 else {}

def get_clinic_info_by_clinic_id(clinic_id):
    sql = f"""
        SELECT oc.clinic_name, oc.clinic_id, oc.customer_id
        FROM order_clients oc
        WHERE oc.clinic_id = {clinic_id}
        LIMIT 1;
    """
    out = run_sql(sql)
    rows = parse_table(out)
    if rows:
        return rows[0]
    sql2 = f"""
        SELECT ei.clinic_name, ei.clinic_id, ei.customer_id
        FROM ehr_integrations ei
        WHERE ei.clinic_id = {clinic_id} AND ei.status = 'LIVE'
        LIMIT 1;
    """
    out2 = run_sql(sql2)
    rows2 = parse_table(out2)
    return rows2[0] if rows2 else {}

# ─── Main ─────────────────────────────────────────────────────────────────────
def main():
    print(f"[{TODAY}] Starting HL7 triage...")

    # Step 1: Query failed records
    print("Step 1: Querying failed records...")
    sql = """
        SELECT id, file_name, emr_code_not_found, sftpDir, emr_service, retry_num,
               parse_finished, received_time, LEFT(order_input, 2000) as order_input
        FROM hl7_file_input
        WHERE parse_finished = 0 AND retry_num = 0 AND received_time >= NOW() - INTERVAL 72 HOUR
        ORDER BY received_time DESC;
    """
    raw = run_sql(sql)
    records = parse_table(raw)

    if not records:
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        with open(OUTPUT_FILE, "w") as f:
            f.write(f"# HL7 File Input Daily Triage — {TODAY}\n\nNo failed records found.\n")
        print("No failed records. Done.")
        return

    print(f"Found {len(records)} failed records.")

    # Step 2: Classify
    type_a, type_b, type_c = [], [], []
    for r in records:
        code = (r.get("emr_code_not_found") or "").strip()
        oi = (r.get("order_input") or "").strip()
        if code and code != "NULL":
            r["_type"] = "A"
            type_a.append(r)
        elif oi and oi != "NULL":
            r["_type"] = "B"
            type_b.append(r)
        else:
            r["_type"] = "C"
            type_c.append(r)

    print(f"Type A: {len(type_a)}, Type B: {len(type_b)}, Type C: {len(type_c)}")

    # Step 3: Type A — Bundle mapping analysis
    print("Step 3: Analyzing Type A (code not found)...")
    bundle_map = {}
    try:
        bm_resp = get_bundle_mapping()
        # Build lookup: panelId -> bundle info
        # API returns dict keyed by bundleId: {"1": {...}, "10": {...}, ...}
        if isinstance(bm_resp, dict):
            for bundle_id_str, item in bm_resp.items():
                if isinstance(item, dict):
                    bundle_map[bundle_id_str] = item
        elif isinstance(bm_resp, list):
            for item in bm_resp:
                pid = str(item.get("bundleId", item.get("panelId", "")))
                if pid:
                    bundle_map[pid] = item
        print(f"  Bundle map loaded: {len(bundle_map)} entries")
    except Exception as e:
        print(f"  Bundle map fetch failed: {e}")

    type_a_results = []
    for r in type_a:
        code = r.get("emr_code_not_found", "")
        sftp = r.get("sftpDir", "")
        clinic_info = get_clinic_info_by_sftp(sftp) if sftp and sftp != "NULL" else {}

        # Extract panelId from code (e.g. VACP12345 -> 12345)
        panel_id_match = re.search(r'\d+', code or "")
        panel_id = panel_id_match.group(0) if panel_id_match else ""
        in_bundle = bundle_map.get(panel_id, None)

        type_a_results.append({
            "id": r["id"],
            "file_name": r.get("file_name", ""),
            "code": code,
            "panel_id": panel_id,
            "clinic_name": clinic_info.get("clinic_name", "N/A"),
            "clinic_id": clinic_info.get("clinic_id", "N/A"),
            "customer_id": clinic_info.get("customer_id", "N/A"),
            "sftp_dir": sftp,
            "bundle_status": f"Found (panelId={panel_id})" if in_bundle else f"NOT in bundle map (panelId={panel_id})"
        })

    # Step 4: Type B — Payment + Order Recovery
    print("Step 4: Processing Type B (payment/order recovery)...")
    type_b_results = []
    b_recovered = 0
    b_failed = 0

    for r in type_b:
        rec_id = r["id"]
        file_name = r.get("file_name", "")
        sftp = r.get("sftpDir", "")
        oi_str = r.get("order_input", "{}")
        result_entry = {"id": rec_id, "file_name": file_name, "sftp_dir": sftp}

        try:
            oi = json.loads(oi_str) if oi_str and oi_str != "NULL" else {}
        except json.JSONDecodeError as e:
            result_entry["status"] = f"FAILED: order_input JSON parse error: {e}"
            result_entry["new_sample_id"] = ""
            type_b_results.append(result_entry)
            b_failed += 1
            continue

        try:
            # Extract clinic_id and amount
            clinic_id = oi.get("clinic_id") or oi.get("clinicId")
            amount = oi.get("total") or oi.get("amount") or oi.get("price")

            if not clinic_id:
                raise ValueError("clinic_id not found in order_input")

            # Get customer_id
            clinic_info = {}
            if sftp and sftp != "NULL":
                clinic_info = get_clinic_info_by_sftp(sftp)
            if not clinic_info.get("customer_id"):
                clinic_info = get_clinic_info_by_clinic_id(clinic_id)
            customer_id = clinic_info.get("customer_id")
            if not customer_id:
                raise ValueError(f"customer_id not found for clinic_id={clinic_id}")

            result_entry["clinic_name"] = clinic_info.get("clinic_name", "N/A")
            result_entry["clinic_id"] = clinic_id
            result_entry["customer_id"] = customer_id
            result_entry["amount"] = amount

            # Get payment methods
            pm_resp = get_payment_methods(customer_id, clinic_id)
            # Find first valid payment method
            pm_list = pm_resp if isinstance(pm_resp, list) else pm_resp.get("data", pm_resp.get("result", []))
            if not pm_list:
                raise ValueError("No payment methods found")
            pm = pm_list[0]
            payment_token = pm.get("payment_token") or pm.get("paymentToken") or pm.get("token")
            customer_token = pm.get("customer_token") or pm.get("customerToken")
            if not payment_token:
                raise ValueError(f"No payment_token in response: {pm}")

            if not amount:
                raise ValueError("amount not found in order_input")

            # Transaction pay
            pay_resp = transaction_pay(customer_id, clinic_id, amount, payment_token, customer_token)
            new_payment_id = pay_resp.get("paymentId") or pay_resp.get("payment_id") or pay_resp.get("id")
            new_sample_id = pay_resp.get("sampleId") or pay_resp.get("sample_id")
            julien_barcode = pay_resp.get("julienBarcode") or pay_resp.get("julien_barcode")
            sample_id_payment = pay_resp.get("sampleIdPayment") or pay_resp.get("sample_id_payment")

            if not new_payment_id:
                raise ValueError(f"No paymentId in pay response: {pay_resp}")

            # Update order_input with payment info
            updated_oi = dict(oi)
            if new_sample_id:
                updated_oi["sampleId"] = new_sample_id
            if new_payment_id:
                updated_oi["payment_id"] = new_payment_id
                updated_oi["paymentId"] = new_payment_id
            if julien_barcode:
                updated_oi["julienBarcode"] = julien_barcode
            if sample_id_payment:
                updated_oi["sampleIdPayment"] = sample_id_payment

            # Place order
            order_resp = place_order(customer_id, clinic_id, updated_oi)
            final_sample_id = order_resp.get("sampleId") or order_resp.get("sample_id") or new_sample_id

            # Update DB
            sp = str(final_sample_id).replace("'", "\\'") if final_sample_id else ""
            pi = str(new_payment_id).replace("'", "\\'") if new_payment_id else ""
            jb = str(julien_barcode).replace("'", "\\'") if julien_barcode else ""
            sip = str(sample_id_payment).replace("'", "\\'") if sample_id_payment else ""

            update_sql = f"""
                UPDATE hl7_file_input
                SET parse_finished=1,
                    sample_id='{sp}',
                    payment_id='{pi}',
                    julien_barcode='{jb}',
                    sample_id_payment='{sip}',
                    retry_num=0
                WHERE id={rec_id};
            """
            run_sql(update_sql)

            result_entry["status"] = "RECOVERED"
            result_entry["new_sample_id"] = final_sample_id
            result_entry["new_payment_id"] = new_payment_id
            b_recovered += 1
            print(f"  [{rec_id}] RECOVERED - sample_id={final_sample_id}")

        except Exception as e:
            result_entry["status"] = f"FAILED: {e}"
            result_entry["new_sample_id"] = ""
            b_failed += 1
            print(f"  [{rec_id}] FAILED: {e}")

        type_b_results.append(result_entry)

    # Step 5: Generate report
    print("Step 5: Writing report...")
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    lines = []
    lines.append(f"# HL7 File Input Daily Triage — {TODAY}\n")
    lines.append("## Summary")
    lines.append(f"- 總失敗數: {len(records)}")
    lines.append(f"- Type A (code not found): {len(type_a)}")
    lines.append(f"- Type B (order failure): {b_recovered} 成功恢復, {b_failed} 失敗")
    lines.append(f"- Type C (parse failure): {len(type_c)}")
    lines.append("")

    lines.append("## Type A — EMR Code Not Found")
    if not type_a_results:
        lines.append("無 Type A 記錄。")
    else:
        lines.append("| id | file_name | code | clinic | clinic_id | customer_id | bundle 狀態 |")
        lines.append("|---|---|---|---|---|---|---|")
        for a in type_a_results:
            lines.append(f"| {a['id']} | {a['file_name']} | {a['code']} | {a['clinic_name']} | {a['clinic_id']} | {a['customer_id']} | {a['bundle_status']} |")
    lines.append("")

    lines.append("## Type B — Payment/Order Recovery")
    if not type_b_results:
        lines.append("無 Type B 記錄。")
    else:
        lines.append("| id | file_name | clinic | customer_id | amount | status | new_sample_id |")
        lines.append("|---|---|---|---|---|---|---|")
        for b in type_b_results:
            lines.append(
                f"| {b['id']} | {b['file_name']} | {b.get('clinic_name','N/A')} | "
                f"{b.get('customer_id','N/A')} | {b.get('amount','N/A')} | "
                f"{b['status']} | {b.get('new_sample_id','')} |"
            )
    lines.append("")

    lines.append("## Type C — Parse Failures")
    if not type_c:
        lines.append("無 Type C 記錄。")
    else:
        lines.append("| id | file_name | emr_service | sftpDir | received_time |")
        lines.append("|---|---|---|---|---|")
        for c in type_c:
            lines.append(
                f"| {c['id']} | {c.get('file_name','')} | {c.get('emr_service','')} | "
                f"{c.get('sftpDir','')} | {c.get('received_time','')} |"
            )
    lines.append("")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"Report written to: {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
