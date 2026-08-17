---
name: core-v7-via-azure-no-vpn
description: lis_core_v7 is queryable WITHOUT VPN — it lives on lisportalprod2 Azure MySQL; creds from AKS coresamplesv2 secret
metadata: 
  node_type: memory
  type: project
  originSessionId: f5e56f76-a2c5-454d-b18b-4f9710c970df
  modified: 2026-08-14T23:05:40.047Z
---

`lis_core_v7`（core ground truth，sample / order_info / customer / clinic）不需要 VPN：它和 `lis_emr` 同在 `lisportalprod2.mysql.database.azure.com:3306`。

**How:** creds 從 AKS 拿 — `kubectl get secret -n coresamplesv2 lis-coresamples-secret -o jsonpath='{.data.MYSQL}' | base64 -d` → `coresamplesv2:{pass}@tcp(lisportalprod2...)/coresamplesv2`，該 user 同時可讀 `lis_core_v7`。欄位注意：`customer.customer_npi_number`（不是 customer_npi）、`sample` 無 clinic_id（join `order_info`）。

192.168.60.3:3307 / ClickHouse 192.168.62.85 仍需 VPN，但日常 core 驗證用這條就夠。相關：[[hl7-triage-db-port-blocked]]
