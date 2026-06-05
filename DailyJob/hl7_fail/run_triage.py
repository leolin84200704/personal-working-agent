#!/usr/bin/env python3
"""HL7 File Input Daily Triage Script"""

import json
import subprocess
import sys
import time
from datetime import datetime, timezone

import jwt
import requests
from typing import Optional

# ── Config ───────────────────────────────────────────────────────────────────
MYSQL_BIN = "/opt/homebrew/opt/mysql-client/bin/mysql"
MYSQL_ARGS = [
    MYSQL_BIN,
    "-h", "lisportalprod2.mysql.database.azure.com",
    "-P", "3306",
    "-u", "lis_core_emr",
    "-pmd?At3pUJnS2?Zx68",
    "--ssl-mode=REQUIRED",
    "-D", "lis_emr",
    "--batch",
]

JWT_SECRET = "v=I+paq@`n>0[ddC|0!go1-RtZ*:+c+_Wfj+bE|IO>lsAK2gJl8C7R>yZ@|`slg*"
BUNDLE_API_TOKEN = "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VySWQiOjU0Njc0LCJ1c2VyX3Blcm1pc3Npb24iOiIzZjkwM2ZlMDAwMiIsImN1c3RvbWVyX2lkIjo5OTk5OTcsImNsaW5pY19pZCI6MTAxMzYsIm9sZF9jbGluaWNfaWQiOjk5OTk5NywicGF0aWVudF9pZCI6bnVsbCwiaW50ZXJuYWxfdXNlcl9pZCI6Nzg2LCJpbnRlcm5hbF91c2VyX25hbWUiOiJuZXcub3JkZXJwYWdlIiwiaW50ZXJuYWxfdXNlcl9yb2xlIjoibmF2aWdhdG9yIiwicm9sZSI6ImN1c3RvbWVyIiwiY3VzdG9tZXJfbGlzdCI6W10sInNlc3Npb25faWQiOiIzOThBMjE0OTUzMzY0RkI5MjBFMEE2QkMxMjVDMTJDMCIsImVtYWlsX2xvZ19pbl9pZCI6InRlc3RAdmlicmFudC1hbWVyaWNhLmNvbSIsImJldGFfcHJvZ3JhbV9lbmFibGVkIjp0cnVlLCJiZXRhX3Byb2dyYW1zIjpbXSwiaWF0IjoxNzE0Njg2MjU3LCJleHAiOjIzNDU4MzgyNTd9.WZo5DKV_qTZ0PKFvVIUf1cpNk_wzlNEslsGrSosVe30"

BUNDLE_MAPPING_URL = "https://api.vibrant-wellness.com/v1/pricing/item/promotion/getLegacyBundleMapping?currency=usd"
PAYMENT_METHODS_URL = "https://www.vibrant-america.com/lisapi/v1/charging/paymentMethod/allSharedPaymentMethods"
TRANSACTION_PAY_URL = "https://www.vibrant-america.com/lisapi/v1/charging/transaction/pay"
ORDER_URL = "https://www.vibrant-america.com/lisapi/v1/portal/order/orderTest/order"

TODAY = datetime.now().strftime("%Y-%m-%d")
REPORT_PATH = f"/Users/hung.l/src/lis-code-agent/DailyJob/hl7_fail/triage_{TODAY}.md"


# ── DB helpers ───────────────────────────────────────────────────────────────
def run_query(sql: str) -> list[dict]:
    result = subprocess.run(
        MYSQL_ARGS + ["-e", sql],
        capture_output=True, text=True, timeout=120
    )
    if result.returncode != 0:
        raise RuntimeError(f"MySQL error: {result.stderr}")
    lines = result.stdout.strip().split("\n")
    if not lines or lines == [""]:
        return []
    headers = lines[0].split("\t")
    rows = []
    for line in lines[1:]:
        if line:
            values = line.split("\t")
            rows.append(dict(zip(headers, values)))
    return rows


def run_update(sql: str) -> int:
    result = subprocess.run(
        MYSQL_ARGS + ["-e", sql],
        capture_output=True, text=True, timeout=120
    )
    if result.returncode != 0:
        raise RuntimeError(f"MySQL update error: {result.stderr}")
    return 0


# ── JWT helpers ───────────────────────────────────────────────────────────────
def make_jwt(customer_id: int, clinic_id: int, role: str, get_pm: bool = False) -> str:
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


# ── Bundle mapping ────────────────────────────────────────────────────────────
def fetch_bundle_mapping() -> dict:
    resp = requests.get(
        BUNDLE_MAPPING_URL,
        headers={"Authorization": BUNDLE_API_TOKEN},
        timeout=30
    )
    resp.raise_for_status()
    data = resp.json()
    # API returns {bundleId_str: {bundleId, bundleName, ...}} — use as-is
    if isinstance(data, dict):
        return data
    # Fallback: list of items indexed by panelId
    mapping = {}
    for item in data:
        pid = str(item.get("panelId", "") or item.get("bundleId", ""))
        if pid:
            mapping[pid] = item
    return mapping


# ── Payment helpers ───────────────────────────────────────────────────────────
def get_payment_methods(customer_id: int, clinic_id: int) -> Optional[dict]:
    token = make_jwt(customer_id, clinic_id, role="clinic", get_pm=True)
    resp = requests.get(
        PAYMENT_METHODS_URL,
        headers={"Authorization": f"Bearer {token}"},
        timeout=30
    )
    if resp.status_code != 200:
        return None
    data = resp.json()
    methods = data.get("data", {})
    return methods


def charge_payment(customer_id: int, clinic_id: int, amount: float,
                   payment_token: str, customer_token: str) -> Optional[dict]:
    token = make_jwt(customer_id, clinic_id, role="clinic", get_pm=True)
    payload = {
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
    resp = requests.post(
        TRANSACTION_PAY_URL,
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
        timeout=30
    )
    if resp.status_code not in (200, 201):
        return None
    return resp.json()


def place_order(customer_id: int, clinic_id: int, order_input: dict) -> Optional[dict]:
    token = make_jwt(customer_id, clinic_id, role="customer")
    resp = requests.post(
        ORDER_URL,
        json=order_input,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        timeout=30
    )
    if resp.status_code not in (200, 201):
        return None
    return resp.json()


# ── Lookup clinic info from DB ────────────────────────────────────────────────
def get_clinic_info(sftp_dir: Optional[str], clinic_id_hint: Optional[str]) -> dict:
    info = {"clinic_name": "unknown", "clinic_id": None, "customer_id": None}

    if sftp_dir and sftp_dir != "NULL":
        rows = run_query(f"""
            SELECT DISTINCT oc.clinic_id, oc.customer_id, ehr.clinic_name, oc.emr_name
            FROM order_clients oc
            LEFT JOIN ehr_integrations ehr ON oc.clinic_id = ehr.clinic_id
            WHERE oc.remote_folder_path = '{sftp_dir}' AND oc.clinic_id IS NOT NULL
            LIMIT 5
        """)
        if rows:
            info["clinic_id"] = rows[0].get("clinic_id")
            info["customer_id"] = rows[0].get("customer_id")
            info["clinic_name"] = rows[0].get("clinic_name", "unknown")
            return info

    if clinic_id_hint and clinic_id_hint != "NULL":
        rows = run_query(f"""
            SELECT clinic_id, customer_id, clinic_name
            FROM ehr_integrations
            WHERE clinic_id = '{clinic_id_hint}' AND status = 'LIVE'
            LIMIT 1
        """)
        if rows:
            info["clinic_id"] = rows[0].get("clinic_id")
            info["customer_id"] = rows[0].get("customer_id")
            info["clinic_name"] = rows[0].get("clinic_name", "unknown")

    return info


# ── Main triage ───────────────────────────────────────────────────────────────
def main():
    print(f"[{datetime.now()}] 開始 HL7 Daily Triage...")

    # Step 1: 查詢失敗記錄
    print("Step 1: 查詢失敗記錄...")
    rows = run_query("""
        SELECT id, file_name, emr_code_not_found, sftpDir, emr_service,
               retry_num, parse_finished, received_time,
               LEFT(order_input, 2000) as order_input
        FROM hl7_file_input
        WHERE parse_finished = 0 AND retry_num = 0
          AND received_time >= NOW() - INTERVAL 72 HOUR
        ORDER BY received_time DESC
    """)

    if not rows:
        report = f"""# HL7 File Input Daily Triage — {TODAY}

## Summary
No failed records found in the past 72 hours.
"""
        with open(REPORT_PATH, "w") as f:
            f.write(report)
        print(f"無失敗記錄。報告寫入: {REPORT_PATH}")
        return

    print(f"找到 {len(rows)} 筆失敗記錄")

    # Step 2: 分類
    type_a, type_b, type_c = [], [], []
    for r in rows:
        code = r.get("emr_code_not_found", "NULL")
        oi = r.get("order_input", "NULL")
        if code and code != "NULL":
            type_a.append(r)
        elif oi and oi != "NULL":
            type_b.append(r)
        else:
            type_c.append(r)

    print(f"  Type A: {len(type_a)}, Type B: {len(type_b)}, Type C: {len(type_c)}")

    # Step 3: Type A 處理
    print("Step 3: 處理 Type A (emr_code_not_found)...")
    bundle_mapping = {}
    type_a_report_lines = []

    if type_a:
        try:
            bundle_mapping = fetch_bundle_mapping()
            print(f"  Bundle mapping 取得 {len(bundle_mapping)} 筆")
        except Exception as e:
            print(f"  Bundle mapping 取得失敗: {e}")

    for r in type_a:
        code = r["emr_code_not_found"]
        sftp_dir = r.get("sftpDir", "NULL")
        clinic_info = get_clinic_info(sftp_dir, None)

        # VACP 後面的數字是 panelId
        panel_id = None
        if code and code.upper().startswith("VACP"):
            panel_id = code[4:].strip()
        elif code:
            panel_id = code.strip()

        bundle_status = "not found in mapping"
        if panel_id and panel_id in bundle_mapping:
            bundle_status = f"found: {bundle_mapping[panel_id].get('bundleName', 'N/A')}"

        line = (
            f"| {code} | {clinic_info['clinic_name']} | {clinic_info['clinic_id']} "
            f"| {clinic_info['customer_id']} | {r['file_name']} | {bundle_status} |"
        )
        type_a_report_lines.append(line)
        print(f"  Type A: code={code}, clinic={clinic_info['clinic_name']}, bundle={bundle_status}")

    # Step 4: Type B 處理
    print("Step 4: 處理 Type B (payment/order recovery)...")
    type_b_results = []

    for r in type_b:
        rec_id = r["id"]
        file_name = r["file_name"]
        sftp_dir = r.get("sftpDir", "NULL")
        order_input_raw = r.get("order_input", "")

        result = {
            "id": rec_id,
            "file_name": file_name,
            "status": "failed",
            "error": None,
            "new_sample_id": None,
        }

        print(f"  處理 id={rec_id}, file={file_name}")

        try:
            order_input = json.loads(order_input_raw)
        except Exception as e:
            result["error"] = f"order_input JSON parse error: {e}"
            type_b_results.append(result)
            print(f"    JSON parse 失敗: {e}")
            continue

        # 取 clinic_id 和 amount
        clinic_id_from_order = order_input.get("clinic_id") or order_input.get("clinicId")
        amount = (order_input.get("total") or order_input.get("amount") or
                  order_input.get("totalAmount") or 0)
        try:
            amount = float(amount)
        except (TypeError, ValueError):
            amount = 0.0

        # 反查 customer_id
        clinic_info = get_clinic_info(sftp_dir if sftp_dir != "NULL" else None,
                                      str(clinic_id_from_order) if clinic_id_from_order else None)
        customer_id = clinic_info.get("customer_id")
        clinic_id = clinic_info.get("clinic_id") or clinic_id_from_order

        if not customer_id:
            result["error"] = f"無法取得 customer_id (sftp_dir={sftp_dir}, clinic_id={clinic_id_from_order})"
            type_b_results.append(result)
            print(f"    找不到 customer_id")
            continue

        try:
            customer_id = int(customer_id)
            clinic_id = int(clinic_id) if clinic_id else 0
        except (TypeError, ValueError):
            result["error"] = f"customer_id/clinic_id 型別轉換失敗: {customer_id}, {clinic_id}"
            type_b_results.append(result)
            continue

        # 取 payment methods
        print(f"    取得 payment methods (customer_id={customer_id})...")
        try:
            pm_data = get_payment_methods(customer_id, clinic_id)
        except Exception as e:
            result["error"] = f"get payment methods error: {e}"
            type_b_results.append(result)
            print(f"    取得 payment methods 失敗: {e}")
            continue

        if not pm_data:
            result["error"] = "取得 payment methods 失敗或回傳空值"
            type_b_results.append(result)
            print(f"    payment methods 為空")
            continue

        # 找 payment_token 和 customer_token
        payment_token = None
        customer_token = None

        # pm_data structure varies; try common keys
        cards = pm_data.get("cards") or pm_data.get("creditCards") or []
        if isinstance(cards, list) and cards:
            payment_token = cards[0].get("paymentToken") or cards[0].get("payment_token")
            customer_token = cards[0].get("customerToken") or cards[0].get("customer_token")

        if not payment_token:
            # Try flat structure
            payment_token = pm_data.get("paymentToken") or pm_data.get("payment_token")
            customer_token = pm_data.get("customerToken") or pm_data.get("customer_token")

        if not payment_token:
            result["error"] = f"找不到 payment_token，PM data keys: {list(pm_data.keys())[:10]}"
            type_b_results.append(result)
            print(f"    找不到 payment_token")
            continue

        # 扣款
        print(f"    扣款 amount={amount}, payment_token={payment_token[:20]}...")
        try:
            pay_resp = charge_payment(customer_id, clinic_id, amount, payment_token, customer_token)
        except Exception as e:
            result["error"] = f"transaction pay error: {e}"
            type_b_results.append(result)
            print(f"    扣款失敗: {e}")
            continue

        if not pay_resp:
            result["error"] = "transaction pay 回傳失敗"
            type_b_results.append(result)
            print(f"    扣款回傳失敗")
            continue

        pay_data = pay_resp.get("data", pay_resp)
        new_sample_id = pay_data.get("sampleId") or pay_data.get("sample_id")
        new_payment_id = pay_data.get("paymentId") or pay_data.get("payment_id") or pay_data.get("id")
        new_julien_barcode = pay_data.get("julienBarcode") or pay_data.get("julien_barcode")
        new_sample_id_payment = pay_data.get("sampleIdPayment") or pay_data.get("sample_id_payment")

        print(f"    扣款成功, sample_id={new_sample_id}, payment_id={new_payment_id}")

        # 更新 order_input
        updated_order = dict(order_input)
        if new_sample_id:
            updated_order["sampleId"] = new_sample_id
        if new_payment_id:
            updated_order["paymentId"] = new_payment_id
        if new_julien_barcode:
            updated_order["julienBarcode"] = new_julien_barcode
        if new_sample_id_payment:
            updated_order["sampleIdPayment"] = new_sample_id_payment

        # 下單
        print(f"    下單...")
        try:
            order_resp = place_order(customer_id, clinic_id, updated_order)
        except Exception as e:
            result["error"] = f"order API error: {e}"
            type_b_results.append(result)
            print(f"    下單失敗: {e}")
            continue

        if not order_resp:
            result["error"] = "order API 回傳失敗"
            type_b_results.append(result)
            print(f"    下單回傳失敗")
            continue

        order_data = order_resp.get("data", order_resp)
        final_sample_id = order_data.get("sampleId") or order_data.get("sample_id") or new_sample_id
        final_payment_id = order_data.get("paymentId") or order_data.get("payment_id") or new_payment_id
        final_julien = order_data.get("julienBarcode") or order_data.get("julien_barcode") or new_julien_barcode
        final_sip = order_data.get("sampleIdPayment") or order_data.get("sample_id_payment") or new_sample_id_payment

        print(f"    下單成功, final_sample_id={final_sample_id}")

        # 更新 DB
        update_parts = ["parse_finished=1", "retry_num=0"]
        if final_sample_id:
            update_parts.append(f"sample_id='{final_sample_id}'")
        if final_payment_id:
            update_parts.append(f"payment_id='{final_payment_id}'")
        if final_julien:
            update_parts.append(f"julien_barcode='{final_julien}'")
        if final_sip:
            update_parts.append(f"sample_id_payment='{final_sip}'")

        try:
            run_update(f"UPDATE hl7_file_input SET {', '.join(update_parts)} WHERE id={rec_id}")
            result["status"] = "recovered"
            result["new_sample_id"] = final_sample_id
            print(f"    DB 更新成功")
        except Exception as e:
            result["error"] = f"DB update error: {e}"
            print(f"    DB 更新失敗: {e}")

        type_b_results.append(result)

    # Step 5: 產出報告
    recovered = sum(1 for r in type_b_results if r["status"] == "recovered")
    failed_b = len(type_b_results) - recovered

    report_lines = [
        f"# HL7 File Input Daily Triage — {TODAY}",
        "",
        "## Summary",
        f"- 總失敗筆數: {len(rows)}",
        f"- Type A (emr_code_not_found): {len(type_a)}",
        f"- Type B (payment/order failure): {len(type_b)} 筆，{recovered} 筆恢復成功，{failed_b} 筆失敗",
        f"- Type C (parse failure): {len(type_c)}",
        "",
    ]

    # Type A section
    report_lines.append("## Type A — EMR Code Not Found")
    if type_a_report_lines:
        report_lines.append("")
        report_lines.append("| Code | Clinic | Clinic ID | Customer ID | File Name | Bundle Mapping 狀態 |")
        report_lines.append("|------|--------|-----------|-------------|-----------|---------------------|")
        report_lines.extend(type_a_report_lines)
    else:
        report_lines.append("無 Type A 記錄。")
    report_lines.append("")

    # Type B section
    report_lines.append("## Type B — Payment/Order Recovery")
    if type_b_results:
        report_lines.append("")
        for r in type_b_results:
            status_str = "成功" if r["status"] == "recovered" else f"失敗: {r['error']}"
            report_lines.append(f"- **id={r['id']}** `{r['file_name']}`")
            report_lines.append(f"  - 狀態: {status_str}")
            if r["new_sample_id"]:
                report_lines.append(f"  - 新 sample_id: {r['new_sample_id']}")
    else:
        report_lines.append("無 Type B 記錄。")
    report_lines.append("")

    # Type C section
    report_lines.append("## Type C — Parse Failures")
    if type_c:
        report_lines.append("")
        report_lines.append("| ID | File Name | EMR Service | SFTP Dir |")
        report_lines.append("|----|-----------|-------------|----------|")
        for r in type_c:
            report_lines.append(
                f"| {r['id']} | {r['file_name']} | {r.get('emr_service','N/A')} | {r.get('sftpDir','N/A')} |"
            )
    else:
        report_lines.append("無 Type C 記錄。")
    report_lines.append("")

    report = "\n".join(report_lines)
    with open(REPORT_PATH, "w") as f:
        f.write(report)

    print(f"\n完成。報告寫入: {REPORT_PATH}")
    print(report)


if __name__ == "__main__":
    main()
