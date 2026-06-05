#!/usr/bin/env python3
"""
HL7 File Input Daily Triage — 2026-05-27
"""

import sys
import json
import time
import subprocess
import re
import requests
import jwt as pyjwt

# ── Constants ──────────────────────────────────────────────
TODAY = "2026-05-27"
OUTPUT_FILE = f"/Users/hung.l/src/lis-code-agent/DailyJob/hl7_fail/triage_{TODAY}.md"

DB_HOST = "lisportalprod2.mysql.database.azure.com"
DB_PORT = 3306
DB_USER = "lis_core_emr"
DB_PASS = "md?At3pUJnS2?Zx68"
DB_NAME = "lis_emr"

JWT_SECRET = r"v=I+paq@`n>0[ddC|0!go1-RtZ*:+c+_Wfj+bE|IO>lsAK2gJl8C7R>yZ@|`slg*"

BUNDLE_MAPPING_TOKEN = "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VySWQiOjU0Njc0LCJ1c2VyX3Blcm1pc3Npb24iOiIzZjkwM2ZlMDAwMiIsImN1c3RvbWVyX2lkIjo5OTk5OTcsImNsaW5pY19pZCI6MTAxMzYsIm9sZF9jbGluaWNfaWQiOjk5OTk5NywicGF0aWVudF9pZCI6bnVsbCwiaW50ZXJuYWxfdXNlcl9pZCI6Nzg2LCJpbnRlcm5hbF91c2VyX25hbWUiOiJuZXcub3JkZXJwYWdlIiwiaW50ZXJuYWxfdXNlcl9yb2xlIjoibmF2aWdhdG9yIiwicm9sZSI6ImN1c3RvbWVyIiwiY3VzdG9tZXJfbGlzdCI6W10sInNlc3Npb25faWQiOiIzOThBMjE0OTUzMzY0RkI5MjBFMEE2QkMxMjVDMTJDMCIsImVtYWlsX2xvZ19pbl9pZCI6InRlc3RAdmlicmFudC1hbWVyaWNhLmNvbSIsImJldGFfcHJvZ3JhbV9lbmFibGVkIjp0cnVlLCJiZXRhX3Byb2dyYW1zIjpbXSwiaWF0IjoxNzE0Njg2MjU3LCJleHAiOjIzNDU4MzgyNTd9.WZo5DKV_qTZ0PKFvVIUf1cpNk_wzlNEslsGrSosVe30"

BUNDLE_MAPPING_URL = "https://api.vibrant-wellness.com/v1/pricing/item/promotion/getLegacyBundleMapping?currency=usd"
PAYMENT_METHODS_URL = "https://www.vibrant-america.com/lisapi/v1/charging/paymentMethod/allSharedPaymentMethods"
TRANSACTION_PAY_URL = "https://www.vibrant-america.com/lisapi/v1/charging/transaction/pay"
ORDER_API_URL = "https://www.vibrant-america.com/lisapi/v1/portal/order/orderTest/order"

MYSQL = "/opt/homebrew/opt/mysql-client/bin/mysql"

# ── Helpers ────────────────────────────────────────────────

def run_query(sql, db=DB_NAME):
    """Execute SQL via mysql CLI (--batch, no --silent so headers are included), return list of dicts."""
    cmd = [
        MYSQL,
        f"-h{DB_HOST}", f"-P{DB_PORT}",
        f"-u{DB_USER}", f"-p{DB_PASS}",
        "--ssl-mode=REQUIRED",
        "--batch",            # tab-separated, with header row
        "-e", sql, db
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        # stderr may contain Warning about password on CLI — ignore it
        if result.returncode != 0:
            stderr_clean = result.stderr.replace("mysql: [Warning] Using a password on the command line interface can be insecure.\n", "")
            if stderr_clean.strip():
                print(f"[DB ERROR] {stderr_clean[:300]}", file=sys.stderr)
            return []
        lines = [l for l in result.stdout.strip().split("\n") if l]
        if not lines:
            return []
        headers = lines[0].split("\t")
        rows = []
        for line in lines[1:]:
            vals = line.split("\t")
            rows.append(dict(zip(headers, vals)))
        return rows
    except Exception as e:
        print(f"[DB EXCEPTION] {e}", file=sys.stderr)
        return []


def run_update(sql, db=DB_NAME):
    """Execute UPDATE/INSERT via mysql CLI."""
    cmd = [
        MYSQL,
        f"-h{DB_HOST}", f"-P{DB_PORT}",
        f"-u{DB_USER}", f"-p{DB_PASS}",
        "--ssl-mode=REQUIRED",
        "--batch",
        "-e", sql, db
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            stderr_clean = result.stderr.replace("mysql: [Warning] Using a password on the command line interface can be insecure.\n", "")
            return False, stderr_clean[:300]
        return True, ""
    except Exception as e:
        return False, str(e)


def make_jwt(customer_id, clinic_id, role="clinic", get_pm=False):
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
    return pyjwt.encode(payload, JWT_SECRET, algorithm="HS256")


def api_get(url, token):
    try:
        r = requests.get(url, headers={"Authorization": token}, timeout=30)
        try:
            return r.status_code, r.json()
        except Exception:
            return r.status_code, {"raw": r.text[:300]}
    except Exception as e:
        return 0, {"error": str(e)}


def api_post(url, token, body):
    try:
        r = requests.post(url, headers={"Authorization": token, "Content-Type": "application/json"},
                          json=body, timeout=30)
        try:
            return r.status_code, r.json()
        except Exception:
            return r.status_code, {"raw": r.text[:300]}
    except Exception as e:
        return 0, {"error": str(e)}


def null_to_none(val):
    if val in (None, "NULL", "null", "None", ""):
        return None
    return val


# ── Step 1: Query ──────────────────────────────────────────

print("[1] 查詢失敗記錄...")
sql_main = (
    "SELECT id, file_name, emr_code_not_found, sftpDir, emr_service, "
    "retry_num, parse_finished, received_time, "
    "LEFT(order_input, 2000) as order_input "
    "FROM hl7_file_input "
    "WHERE parse_finished = 0 AND retry_num = 0 "
    "AND received_time >= NOW() - INTERVAL 72 HOUR "
    "ORDER BY received_time DESC"
)
records = run_query(sql_main)
print(f"  查到 {len(records)} 筆失敗記錄")

if not records:
    with open(OUTPUT_FILE, "w") as f:
        f.write(f"# HL7 File Input Daily Triage — {TODAY}\n\n## Summary\n無失敗記錄 (72小時內 parse_finished=0, retry_num=0)。\n")
    print("No failed records found. 報告已寫入。")
    sys.exit(0)

# ── Step 2: 分類 ───────────────────────────────────────────

type_a, type_b, type_c = [], [], []

for r in records:
    code = null_to_none(r.get("emr_code_not_found"))
    oi = null_to_none(r.get("order_input"))
    if code:
        type_a.append(r)
    elif oi:
        type_b.append(r)
    else:
        type_c.append(r)

print(f"  Type A: {len(type_a)}, Type B: {len(type_b)}, Type C: {len(type_c)}")

# ── Bundle Mapping ─────────────────────────────────────────

print("[2] 取得 Bundle Mapping...")
bm_status_code, bm_data = api_get(BUNDLE_MAPPING_URL, BUNDLE_MAPPING_TOKEN)
bundle_map = {}
if bm_status_code == 200 and isinstance(bm_data, list):
    for item in bm_data:
        pid = str(item.get("panelId", ""))
        if pid:
            bundle_map[pid] = item
    print(f"  Bundle mapping 取得 {len(bundle_map)} 項")
else:
    print(f"  Bundle mapping 失敗: {bm_status_code} {str(bm_data)[:100]}")

# ── Helper: 反查 clinic info ───────────────────────────────

def get_clinic_info(sftp_dir):
    info = {"clinic_name": "unknown", "clinic_id": None, "customer_id": None}
    sftp_dir = null_to_none(sftp_dir)
    if not sftp_dir:
        return info
    safe = sftp_dir.replace("'", "''")
    sql = (
        f"SELECT oc.clinic_id, oc.customer_id, ei.name as clinic_name "
        f"FROM order_clients oc "
        f"LEFT JOIN ehr_integrations ei ON ei.clinic_id = oc.clinic_id AND ei.status = 'LIVE' "
        f"WHERE oc.sftp_directory = '{safe}' LIMIT 1"
    )
    rows = run_query(sql)
    if rows:
        info["clinic_id"] = null_to_none(rows[0].get("clinic_id"))
        info["customer_id"] = null_to_none(rows[0].get("customer_id"))
        info["clinic_name"] = null_to_none(rows[0].get("clinic_name")) or "unknown"
    else:
        sql2 = (
            f"SELECT clinic_id, name as clinic_name "
            f"FROM ehr_integrations "
            f"WHERE sftp_directory = '{safe}' AND status = 'LIVE' LIMIT 1"
        )
        rows2 = run_query(sql2)
        if rows2:
            info["clinic_id"] = null_to_none(rows2[0].get("clinic_id"))
            info["clinic_name"] = null_to_none(rows2[0].get("clinic_name")) or "unknown"
    return info


# ── Step 3: Type A ─────────────────────────────────────────

print("[3] 處理 Type A (emr_code_not_found)...")
type_a_results = []

for r in type_a:
    code = r.get("emr_code_not_found", "").strip()
    sftp = null_to_none(r.get("sftpDir", ""))
    clinic_info = get_clinic_info(sftp)

    panel_id = None
    bm_label = "not found in bundle mapping"
    if code:
        m = re.search(r'(\d+)', code)
        if m:
            panel_id = m.group(1)
            if panel_id in bundle_map:
                bm_label = f"found: {bundle_map[panel_id].get('name', 'unknown')}"
            else:
                bm_label = "not in bundle mapping"

    type_a_results.append({
        "id": r.get("id"),
        "file_name": r.get("file_name"),
        "code": code,
        "panel_id": panel_id,
        "emr_service": r.get("emr_service"),
        "sftp_dir": sftp,
        "clinic_name": clinic_info["clinic_name"],
        "clinic_id": clinic_info["clinic_id"],
        "customer_id": clinic_info["customer_id"],
        "bundle_status": bm_label,
    })
    print(f"  [{r.get('id')}] {code} → {bm_label}")


# ── Step 4: Type B ─────────────────────────────────────────

print("[4] 處理 Type B (Payment/Order Recovery)...")
type_b_results = []

for r in type_b:
    rec_id = r.get("id")
    file_name = r.get("file_name")
    sftp = null_to_none(r.get("sftpDir", ""))
    oi_raw = r.get("order_input", "")

    result = {
        "id": rec_id,
        "file_name": file_name,
        "clinic": "unknown",
        "clinic_id": None,
        "customer_id": None,
        "status": "pending",
        "new_sample_id": None,
        "new_payment_id": None,
        "new_julien_barcode": None,
        "error": None,
    }

    # Parse order_input JSON
    try:
        order_input = json.loads(oi_raw)
    except Exception as e:
        result["status"] = "failed"
        result["error"] = f"order_input JSON parse error: {e}"
        type_b_results.append(result)
        print(f"  [{rec_id}] JSON parse 失敗: {e}")
        continue

    # 從 order_input 提取 clinic_id 和 amount
    clinic_id_oi = order_input.get("clinic_id") or order_input.get("clinicId")
    amount = (order_input.get("total") or order_input.get("amount")
              or order_input.get("price") or order_input.get("totalAmount"))

    # 反查 customer_id
    clinic_info = get_clinic_info(sftp)
    customer_id = clinic_info.get("customer_id")
    result["clinic"] = clinic_info.get("clinic_name", "unknown")
    result["clinic_id"] = clinic_id_oi or clinic_info.get("clinic_id")
    result["customer_id"] = customer_id

    # 若 order_clients 無資料，從 ehr_integrations 補
    if not customer_id and clinic_id_oi:
        sql_ei = (
            f"SELECT customer_id FROM ehr_integrations "
            f"WHERE clinic_id = '{clinic_id_oi}' AND status = 'LIVE' LIMIT 1"
        )
        rows_ei = run_query(sql_ei)
        if rows_ei:
            customer_id = null_to_none(rows_ei[0].get("customer_id"))
            result["customer_id"] = customer_id

    if not customer_id:
        result["status"] = "failed"
        result["error"] = "無法取得 customer_id"
        type_b_results.append(result)
        print(f"  [{rec_id}] 無法取得 customer_id")
        continue

    if not amount:
        result["status"] = "failed"
        result["error"] = f"無法從 order_input 取得 amount，keys: {list(order_input.keys())[:10]}"
        type_b_results.append(result)
        print(f"  [{rec_id}] 無法取得 amount")
        continue

    # Step 4.3: 產生 payment JWT & 取 payment methods
    clinic_id_for_jwt = int(result["clinic_id"]) if result["clinic_id"] else 10136
    customer_id_int = int(customer_id)

    pm_token = make_jwt(customer_id_int, clinic_id_for_jwt, role="clinic", get_pm=True)
    pm_url = f"{PAYMENT_METHODS_URL}?customerId={customer_id}"
    pm_status, pm_data = api_get(pm_url, f"Bearer {pm_token}")

    if pm_status != 200:
        result["status"] = "failed"
        result["error"] = f"Payment methods API 失敗: {pm_status} {str(pm_data)[:200]}"
        type_b_results.append(result)
        print(f"  [{rec_id}] Payment methods 失敗: {pm_status}")
        continue

    pm_list = pm_data if isinstance(pm_data, list) else pm_data.get("data", [])
    payment_token = None
    customer_token = None
    for pm in pm_list:
        if pm.get("is_default") or pm.get("status") in ("active", "ACTIVE", 1, "1"):
            payment_token = pm.get("payment_token") or pm.get("paymentToken")
            customer_token = pm.get("customer_token") or pm.get("customerToken")
            break
    if not payment_token and pm_list:
        payment_token = pm_list[0].get("payment_token") or pm_list[0].get("paymentToken")
        customer_token = pm_list[0].get("customer_token") or pm_list[0].get("customerToken")

    if not payment_token:
        result["status"] = "failed"
        result["error"] = f"無 payment token，PM list count={len(pm_list)}"
        type_b_results.append(result)
        print(f"  [{rec_id}] 無 payment token (pm_list={len(pm_list)})")
        continue

    # Step 4.4: TransactionPay
    pay_body = {
        "account_id": customer_id_int,
        "account_type": "customer",
        "amount": float(amount),
        "currency": "usd",
        "charge_type": "testorder",
        "type": "card",
        "token_platform": "stax",
        "payment_source": "emr",
        "payment_token": payment_token,
        "customer_token": customer_token,
        "new_sample": True,
    }
    pay_token = make_jwt(customer_id_int, clinic_id_for_jwt, role="clinic", get_pm=True)
    pay_status, pay_data = api_post(TRANSACTION_PAY_URL, f"Bearer {pay_token}", pay_body)

    if pay_status not in (200, 201):
        result["status"] = "failed"
        result["error"] = f"TransactionPay 失敗: {pay_status} {str(pay_data)[:300]}"
        type_b_results.append(result)
        print(f"  [{rec_id}] TransactionPay 失敗: {pay_status}")
        continue

    # Check success flag
    success = pay_data.get("success") or pay_data.get("status") in ("success", "SUCCESS", "ok")
    if not success and pay_status in (200, 201):
        # Some APIs return 200 even on failure with a message
        err_msg = pay_data.get("message") or pay_data.get("error") or str(pay_data)[:200]
        # Still proceed if we have a sample_id
        new_sample_id = pay_data.get("sample_id") or pay_data.get("sampleId")
        if not new_sample_id:
            result["status"] = "failed"
            result["error"] = f"TransactionPay 回應無 success flag: {err_msg}"
            type_b_results.append(result)
            print(f"  [{rec_id}] TransactionPay 無 success: {err_msg[:100]}")
            continue

    new_sample_id = pay_data.get("sample_id") or pay_data.get("sampleId")
    new_payment_id = (pay_data.get("payment_id") or pay_data.get("paymentId")
                      or pay_data.get("id") or pay_data.get("transaction_id"))
    new_julien_barcode = (pay_data.get("julien_barcode") or pay_data.get("julienBarcode")
                          or pay_data.get("barcode") or pay_data.get("julienId"))

    # Step 4.5: 更新 order_input 並呼叫 Order API
    updated_oi = dict(order_input)
    if new_sample_id:
        updated_oi["sample_id"] = new_sample_id
        updated_oi["sampleId"] = new_sample_id
    if new_payment_id:
        updated_oi["payment_id"] = new_payment_id
        updated_oi["paymentId"] = new_payment_id
    if new_julien_barcode:
        updated_oi["julien_barcode"] = new_julien_barcode
        updated_oi["julienBarcode"] = new_julien_barcode

    order_token = make_jwt(customer_id_int, clinic_id_for_jwt, role="customer", get_pm=False)
    order_status, order_data = api_post(ORDER_API_URL, f"Bearer {order_token}", updated_oi)

    if order_status not in (200, 201):
        result["status"] = "failed"
        result["error"] = f"Order API 失敗: {order_status} {str(order_data)[:300]}"
        type_b_results.append(result)
        print(f"  [{rec_id}] Order API 失敗: {order_status}")
        continue

    final_sample_id = (order_data.get("sample_id") or order_data.get("sampleId") or new_sample_id or "")
    final_payment_id = (order_data.get("payment_id") or order_data.get("paymentId") or new_payment_id or "")
    final_barcode = (order_data.get("julien_barcode") or order_data.get("julienBarcode")
                     or new_julien_barcode or "")

    # Step 4.6: UPDATE DB
    update_sql = (
        f"UPDATE hl7_file_input SET "
        f"parse_finished=1, "
        f"sample_id='{str(final_sample_id).replace(chr(39), '')}', "
        f"payment_id='{str(final_payment_id).replace(chr(39), '')}', "
        f"julien_barcode='{str(final_barcode).replace(chr(39), '')}', "
        f"sample_id_payment='{str(final_sample_id).replace(chr(39), '')}', "
        f"retry_num=0 "
        f"WHERE id={rec_id}"
    )
    ok, err = run_update(update_sql)
    if ok:
        result["status"] = "recovered"
        result["new_sample_id"] = final_sample_id
        result["new_payment_id"] = final_payment_id
        result["new_julien_barcode"] = final_barcode
        print(f"  [{rec_id}] 成功 recover: sample_id={final_sample_id}")
    else:
        result["status"] = "partial_fail"
        result["error"] = f"Order 成功但 DB update 失敗: {err}"
        result["new_sample_id"] = final_sample_id
        print(f"  [{rec_id}] DB update 失敗: {err}")

    type_b_results.append(result)


# ── Step 5: 產出報告 ───────────────────────────────────────

print("[5] 產出報告...")

b_recovered = sum(1 for r in type_b_results if r["status"] == "recovered")
b_failed = sum(1 for r in type_b_results if r["status"] in ("failed", "partial_fail"))

lines = []
lines.append(f"# HL7 File Input Daily Triage — {TODAY}")
lines.append("")
lines.append("## Summary")
lines.append(f"- 總失敗筆數: {len(records)}")
lines.append(f"- Type A (code not found): {len(type_a)}")
lines.append(f"- Type B (order failure): {b_recovered} 成功, {b_failed} 失敗")
lines.append(f"- Type C (parse failure): {len(type_c)}")
lines.append("")

# Type A
lines.append("## Type A — EMR Code Not Found")
lines.append("")
if not type_a_results:
    lines.append("無 Type A 記錄。")
else:
    lines.append("| id | file_name | code | panel_id | clinic | clinic_id | customer_id | bundle_status |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for r in type_a_results:
        lines.append(
            f"| {r['id']} | {r['file_name']} | `{r['code']}` | {r['panel_id']} "
            f"| {r['clinic_name']} | {r['clinic_id']} | {r['customer_id']} | {r['bundle_status']} |"
        )
lines.append("")

# Type B
lines.append("## Type B — Payment/Order Recovery")
lines.append("")
if not type_b_results:
    lines.append("無 Type B 記錄。")
else:
    for r in type_b_results:
        status_zh = {
            "recovered": "成功 recover",
            "failed": "失敗",
            "partial_fail": "部分失敗 (Order 成功但 DB 未更新)",
            "pending": "未處理",
        }.get(r["status"], r["status"])
        lines.append(f"### [{r['id']}] {r['file_name']} — {status_zh}")
        lines.append(f"- Clinic: {r['clinic']} (clinic_id={r['clinic_id']}, customer_id={r['customer_id']})")
        if r["status"] == "recovered":
            lines.append(f"- new sample_id: {r['new_sample_id']}")
            lines.append(f"- new payment_id: {r['new_payment_id']}")
            lines.append(f"- new julien_barcode: {r['new_julien_barcode']}")
        else:
            lines.append(f"- 錯誤: {r['error']}")
        lines.append("")

# Type C
lines.append("## Type C — Parse Failures")
lines.append("")
if not type_c:
    lines.append("無 Type C 記錄。")
else:
    lines.append("| id | file_name | emr_service | sftpDir | received_time |")
    lines.append("|---|---|---|---|---|")
    for r in type_c:
        lines.append(
            f"| {r.get('id')} | {r.get('file_name')} | {r.get('emr_service')} "
            f"| {r.get('sftpDir')} | {r.get('received_time')} |"
        )

report = "\n".join(lines)
with open(OUTPUT_FILE, "w") as f:
    f.write(report)

print(f"\n完成！報告寫入: {OUTPUT_FILE}")
