#!/usr/bin/env python3
"""HL7 File Input Daily Triage — 2026-05-30"""
import json
import subprocess
import sys
import time
import requests
import jwt as pyjwt
from datetime import datetime

TODAY = "2026-05-30"
REPORT_PATH = f"/Users/hung.l/src/lis-code-agent/DailyJob/hl7_fail/triage_{TODAY}.md"

# ── Config ───────────────────────────────────────────────────────────────────
DB_HOST     = "lisportalprod2.mysql.database.azure.com"
DB_PORT     = "3306"
DB_USER     = "lis_core_emr"
DB_PASS     = "md?At3pUJnS2?Zx68"
DB_NAME     = "lis_emr"
MYSQL_CLI   = "/opt/homebrew/opt/mysql-client/bin/mysql"

JWT_SECRET  = "v=I+paq@`n>0[ddC|0!go1-RtZ*:+c+_Wfj+bE|IO>lsAK2gJl8C7R>yZ@|`slg*"
BUNDLE_TOKEN = "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VySWQiOjU0Njc0LCJ1c2VyX3Blcm1pc3Npb24iOiIzZjkwM2ZlMDAwMiIsImN1c3RvbWVyX2lkIjo5OTk5OTcsImNsaW5pY19pZCI6MTAxMzYsIm9sZF9jbGluaWNfaWQiOjk5OTk5NywicGF0aWVudF9pZCI6bnVsbCwiaW50ZXJuYWxfdXNlcl9pZCI6Nzg2LCJpbnRlcm5hbF91c2VyX25hbWUiOiJuZXcub3JkZXJwYWdlIiwiaW50ZXJuYWxfdXNlcl9yb2xlIjoibmF2aWdhdG9yIiwicm9sZSI6ImN1c3RvbWVyIiwiY3VzdG9tZXJfbGlzdCI6W10sInNlc3Npb25faWQiOiIzOThBMjE0OTUzMzY0RkI5MjBFMEE2QkMxMjVDMTJDMCIsImVtYWlsX2xvZ19pbl9pZCI6InRlc3RAdmlicmFudC1hbWVyaWNhLmNvbSIsImJldGFfcHJvZ3JhbV9lbmFibGVkIjp0cnVlLCJiZXRhX3Byb2dyYW1zIjpbXSwiaWF0IjoxNzE0Njg2MjU3LCJleHAiOjIzNDU4MzgyNTd9.WZo5DKV_qTZ0PKFvVIUf1cpNk_wzlNEslsGrSosVe30"

URL_BUNDLE       = "https://api.vibrant-wellness.com/v1/pricing/item/promotion/getLegacyBundleMapping?currency=usd"
URL_PAY_METHODS  = "https://api.vibrant-wellness.com/v1/charging/paymentMethod/allSharedPaymentMethods"
URL_TRANS_PAY    = "https://api.vibrant-wellness.com/v1/charging/transaction/pay"
URL_ORDER        = "https://api.vibrant-wellness.com/v1/portal/order/orderTest/order"


# ── DB helper ────────────────────────────────────────────────────────────────
def mysql_query(sql: str) -> list[dict]:
    cmd = [
        MYSQL_CLI,
        f"-h{DB_HOST}", f"-P{DB_PORT}", f"-u{DB_USER}", f"-p{DB_PASS}",
        "--ssl-mode=REQUIRED",
        "--batch", "--raw",
        DB_NAME,
        "-e", sql,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        raise RuntimeError(f"MySQL error: {result.stderr}")
    lines = result.stdout.strip().split("\n")
    if not lines or lines == [""]:
        return []
    headers = lines[0].split("\t")
    rows = []
    for line in lines[1:]:
        if not line:
            continue
        values = line.split("\t")
        rows.append(dict(zip(headers, values)))
    return rows


def mysql_execute(sql: str) -> None:
    cmd = [
        MYSQL_CLI,
        f"-h{DB_HOST}", f"-P{DB_PORT}", f"-u{DB_USER}", f"-p{DB_PASS}",
        "--ssl-mode=REQUIRED",
        DB_NAME,
        "-e", sql,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        raise RuntimeError(f"MySQL execute error: {result.stderr}")


# ── JWT helper ───────────────────────────────────────────────────────────────
def make_jwt(customer_id: int, clinic_id: int, role: str, get_token_customer_pm: bool = False) -> str:
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
    if get_token_customer_pm:
        payload["getTokenCustomerPM"] = True
    return pyjwt.encode(payload, JWT_SECRET, algorithm="HS256")


# ── Bundle mapping ────────────────────────────────────────────────────────────
def load_bundle_mapping() -> dict:
    """Returns panel_id → [panel info]. Also builds code → panel_id map."""
    r = requests.get(URL_BUNDLE, headers={"Authorization": BUNDLE_TOKEN}, timeout=30)
    r.raise_for_status()
    data = r.json()
    # structure varies; flatten to code → list of panel entries
    mapping = {}
    items = data if isinstance(data, list) else data.get("data", data.get("items", []))
    for item in items:
        panel_id = str(item.get("panelId", item.get("panel_id", "")))
        code = str(item.get("code", item.get("vacp_code", item.get("emr_code", ""))))
        if code:
            mapping.setdefault(code, []).append(item)
        if panel_id:
            mapping.setdefault(panel_id, []).append(item)
    return mapping


# ── Clinic lookup ─────────────────────────────────────────────────────────────
def lookup_clinic(sftp_dir: str) -> dict:
    """Look up clinic info via order_clients → ehr_integrations."""
    rows = mysql_query(
        f"SELECT oc.clinic_id, oc.customer_id, ei.clinic_name "
        f"FROM order_clients oc "
        f"LEFT JOIN ehr_integrations ei ON oc.clinic_id = ei.clinic_id "
        f"WHERE oc.sftp_dir = '{sftp_dir}' LIMIT 1"
    )
    if rows:
        return rows[0]
    # Fallback: use ehr_integrations directly with sftp_dir pattern
    rows = mysql_query(
        f"SELECT clinic_id, customer_id, clinic_name "
        f"FROM ehr_integrations "
        f"WHERE sftp_directory = '{sftp_dir}' AND status = 'LIVE' LIMIT 1"
    )
    return rows[0] if rows else {}


def lookup_clinic_by_id(clinic_id: str) -> dict:
    rows = mysql_query(
        f"SELECT oc.clinic_id, oc.customer_id, ei.clinic_name "
        f"FROM order_clients oc "
        f"LEFT JOIN ehr_integrations ei ON oc.clinic_id = ei.clinic_id "
        f"WHERE oc.clinic_id = '{clinic_id}' LIMIT 1"
    )
    if rows:
        return rows[0]
    rows = mysql_query(
        f"SELECT clinic_id, customer_id, clinic_name "
        f"FROM ehr_integrations "
        f"WHERE clinic_id = '{clinic_id}' AND status = 'LIVE' LIMIT 1"
    )
    return rows[0] if rows else {}


# ── Payment methods ───────────────────────────────────────────────────────────
def get_payment_methods(customer_id: int, clinic_id: int):
    token = make_jwt(customer_id, clinic_id, role="clinic", get_token_customer_pm=True)
    r = requests.get(
        URL_PAY_METHODS,
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    r.raise_for_status()
    data = r.json()
    methods = data if isinstance(data, list) else data.get("data", [])
    return methods


# ── Transaction pay ───────────────────────────────────────────────────────────
def transaction_pay(customer_id: int, clinic_id: int, amount: float,
                    payment_token: str, customer_token: str) -> dict:
    token = make_jwt(customer_id, clinic_id, role="clinic", get_token_customer_pm=True)
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
    r = requests.post(
        URL_TRANS_PAY,
        json=payload,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


# ── Order API ─────────────────────────────────────────────────────────────────
def place_order(customer_id: int, clinic_id: int, order_input: dict) -> dict:
    token = make_jwt(customer_id, clinic_id, role="customer")
    r = requests.post(
        URL_ORDER,
        json=order_input,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


# ── Main triage ───────────────────────────────────────────────────────────────
def main():
    print("=== Step 1: Query failed records ===")
    records = mysql_query(
        "SELECT id, file_name, emr_code_not_found, sftpDir, emr_service, retry_num, "
        "parse_finished, received_time, LEFT(order_input, 2000) as order_input "
        "FROM hl7_file_input "
        "WHERE parse_finished = 0 AND retry_num = 0 AND received_time >= NOW() - INTERVAL 72 HOUR "
        "ORDER BY received_time DESC"
    )
    print(f"  Found {len(records)} failed records")

    if not records:
        with open(REPORT_PATH, "w") as f:
            f.write(f"# HL7 File Input Daily Triage — {TODAY}\n\nNo failed records found.\n")
        print(f"Report written: {REPORT_PATH}")
        return

    # ── Step 2: Classify ──────────────────────────────────────────────────────
    type_a, type_b, type_c = [], [], []
    for rec in records:
        code = rec.get("emr_code_not_found", "")
        oi   = rec.get("order_input", "")
        null_vals = {"NULL", "None", "", None}
        if code not in null_vals:
            type_a.append(rec)
        elif oi not in null_vals:
            type_b.append(rec)
        else:
            type_c.append(rec)

    print(f"  Type A: {len(type_a)}, Type B: {len(type_b)}, Type C: {len(type_c)}")

    # ── Step 3: Type A ────────────────────────────────────────────────────────
    print("=== Step 3: Type A analysis ===")
    print("  Loading bundle mapping...")
    try:
        bundle_map = load_bundle_mapping()
        bundle_ok = True
    except Exception as e:
        print(f"  WARNING: Bundle mapping load failed: {e}")
        bundle_map = {}
        bundle_ok = False

    type_a_results = []
    for rec in type_a:
        code = rec["emr_code_not_found"]
        sftp = rec.get("sftpDir", "")
        clinic = lookup_clinic(sftp)
        # Check bundle mapping — VACP codes have format VACPxxxxx
        panel_id = code.replace("VACP", "").strip() if "VACP" in code.upper() else code
        in_bundle = panel_id in bundle_map or code in bundle_map
        type_a_results.append({
            "id": rec["id"],
            "file_name": rec["file_name"],
            "code": code,
            "panel_id": panel_id,
            "clinic_name": clinic.get("clinic_name", "unknown"),
            "clinic_id": clinic.get("clinic_id", sftp),
            "customer_id": clinic.get("customer_id", "unknown"),
            "sftp_dir": sftp,
            "emr_service": rec.get("emr_service", ""),
            "received_time": rec.get("received_time", ""),
            "in_bundle_mapping": in_bundle,
            "bundle_entry": bundle_map.get(panel_id, bundle_map.get(code, [])),
        })

    # ── Step 4: Type B ────────────────────────────────────────────────────────
    print("=== Step 4: Type B recovery ===")
    type_b_results = []
    recovered = 0
    failed_recovery = 0

    for rec in type_b:
        row_id    = rec["id"]
        file_name = rec["file_name"]
        sftp      = rec.get("sftpDir", "")
        oi_str    = rec.get("order_input", "")
        print(f"  Processing id={row_id} file={file_name}")

        result_entry = {
            "id": row_id,
            "file_name": file_name,
            "sftp_dir": sftp,
            "status": "unknown",
            "error": None,
            "new_sample_id": None,
            "new_payment_id": None,
        }

        try:
            # Parse order_input
            try:
                oi = json.loads(oi_str)
            except Exception:
                raise ValueError(f"Cannot parse order_input JSON: {oi_str[:200]}")

            clinic_id_raw = str(oi.get("clinic_id", oi.get("clinicId", "")))
            amount = float(oi.get("total", oi.get("amount", oi.get("totalAmount", 0))))

            # Lookup customer_id
            clinic_info = lookup_clinic(sftp)
            if not clinic_info:
                clinic_info = lookup_clinic_by_id(clinic_id_raw)
            if not clinic_info:
                raise ValueError(f"Cannot find clinic for sftpDir={sftp} clinic_id={clinic_id_raw}")

            customer_id = int(clinic_info["customer_id"])
            clinic_id   = int(clinic_info.get("clinic_id") or clinic_id_raw)

            print(f"    customer_id={customer_id} clinic_id={clinic_id} amount={amount}")

            # Get payment methods
            methods = get_payment_methods(customer_id, clinic_id)
            if not methods:
                raise ValueError("No payment methods found")
            method = methods[0]
            payment_token  = method.get("payment_method_id", method.get("paymentMethodId", method.get("id", "")))
            customer_token = method.get("customer_id", method.get("customerId", method.get("stax_customer_id", "")))
            print(f"    payment_token={payment_token} customer_token={customer_token}")

            # TransactionPay
            pay_resp = transaction_pay(customer_id, clinic_id, amount, payment_token, customer_token)
            print(f"    pay_resp keys: {list(pay_resp.keys()) if isinstance(pay_resp, dict) else type(pay_resp)}")

            new_payment_id = str(
                pay_resp.get("id", pay_resp.get("payment_id", pay_resp.get("transactionId", "")))
            )
            new_sample_id  = str(
                pay_resp.get("sampleId", pay_resp.get("sample_id", pay_resp.get("orderId", "")))
            )
            julien_barcode  = str(pay_resp.get("julienBarcode", pay_resp.get("barcode", "")))

            # Update order_input with payment results
            oi_updated = dict(oi)
            if new_sample_id:
                oi_updated["sampleId"] = new_sample_id
                oi_updated["sample_id"] = new_sample_id
            if new_payment_id:
                oi_updated["payment_id"] = new_payment_id
                oi_updated["paymentId"] = new_payment_id
            if julien_barcode:
                oi_updated["julienBarcode"] = julien_barcode

            # Place order
            order_resp = place_order(customer_id, clinic_id, oi_updated)
            print(f"    order_resp keys: {list(order_resp.keys()) if isinstance(order_resp, dict) else type(order_resp)}")

            final_sample_id = str(
                order_resp.get("sampleId", order_resp.get("sample_id", new_sample_id))
            )
            sample_id_payment = str(
                order_resp.get("sampleIdPayment", order_resp.get("sample_id_payment", ""))
            )

            # Update DB
            esc_sample = final_sample_id.replace("'", "\\'")
            esc_payment = new_payment_id.replace("'", "\\'")
            esc_barcode  = julien_barcode.replace("'", "\\'")
            esc_sp       = sample_id_payment.replace("'", "\\'")
            mysql_execute(
                f"UPDATE hl7_file_input SET "
                f"parse_finished=1, sample_id='{esc_sample}', payment_id='{esc_payment}', "
                f"julien_barcode='{esc_barcode}', sample_id_payment='{esc_sp}', retry_num=0 "
                f"WHERE id={row_id}"
            )

            result_entry.update({
                "status": "recovered",
                "new_sample_id": final_sample_id,
                "new_payment_id": new_payment_id,
                "julien_barcode": julien_barcode,
            })
            recovered += 1
            print(f"    SUCCESS: sample_id={final_sample_id}")

        except Exception as e:
            err_msg = str(e)
            print(f"    FAILED: {err_msg}")
            result_entry.update({"status": "failed", "error": err_msg})
            failed_recovery += 1

        type_b_results.append(result_entry)

    # ── Step 5: Report ────────────────────────────────────────────────────────
    print("=== Step 5: Writing report ===")

    lines = [
        f"# HL7 File Input Daily Triage — {TODAY}",
        "",
        "## 摘要",
        f"- 總失敗筆數: {len(records)}",
        f"- Type A (code not found): {len(type_a)}",
        f"- Type B (order failure): {recovered} 筆恢復, {failed_recovery} 筆失敗",
        f"- Type C (parse failure): {len(type_c)}",
        f"- Bundle mapping 載入: {'成功' if bundle_ok else '失敗 (API error)'}",
        "",
        "---",
        "",
        "## Type A — EMR Code Not Found",
        "",
    ]

    if type_a_results:
        for r in type_a_results:
            bundle_status = "存在於 bundle mapping" if r["in_bundle_mapping"] else "不在 bundle mapping 中"
            lines += [
                f"### id={r['id']} | {r['file_name']}",
                f"- Code: `{r['code']}` (panelId: {r['panel_id']})",
                f"- Clinic: {r['clinic_name']} (clinic_id={r['clinic_id']}, customer_id={r['customer_id']})",
                f"- EMR Service: {r['emr_service']}",
                f"- SFTP Dir: {r['sftp_dir']}",
                f"- Received: {r['received_time']}",
                f"- Bundle mapping: {bundle_status}",
                "",
            ]
    else:
        lines.append("無 Type A 記錄\n")

    lines += ["---", "", "## Type B — Payment/Order Recovery", ""]

    if type_b_results:
        for r in type_b_results:
            status_zh = "恢復成功" if r["status"] == "recovered" else "失敗"
            lines += [
                f"### id={r['id']} | {r['file_name']}",
                f"- SFTP Dir: {r['sftp_dir']}",
                f"- 狀態: {status_zh}",
            ]
            if r["status"] == "recovered":
                lines += [
                    f"- 新 sample_id: {r['new_sample_id']}",
                    f"- 新 payment_id: {r['new_payment_id']}",
                    f"- Julien barcode: {r.get('julien_barcode', '')}",
                ]
            else:
                lines.append(f"- 錯誤: {r['error']}")
            lines.append("")
    else:
        lines.append("無 Type B 記錄\n")

    lines += ["---", "", "## Type C — Parse Failures", ""]

    if type_c:
        for rec in type_c:
            lines += [
                f"### id={rec['id']} | {rec['file_name']}",
                f"- EMR Service: {rec.get('emr_service', 'unknown')}",
                f"- SFTP Dir: {rec.get('sftpDir', '')}",
                f"- Received: {rec.get('received_time', '')}",
                "",
            ]
    else:
        lines.append("無 Type C 記錄\n")

    report = "\n".join(lines)
    with open(REPORT_PATH, "w") as f:
        f.write(report)

    print(f"Report written: {REPORT_PATH}")
    print(f"Summary: Total={len(records)} A={len(type_a)} B(ok={recovered},fail={failed_recovery}) C={len(type_c)}")


if __name__ == "__main__":
    main()
