---
name: cors-debug-204-not-pass
description: Debug CORS 永遠驗 access-control-allow-origin header 本身，204 OPTIONS 不代表通過
metadata: 
  node_type: memory
  type: feedback
  originSessionId: d732b08a-9c71-4b63-b2df-d3274b205138
---

Debug CORS 時，**`204 OPTIONS` response 不等於 CORS pass**。必須 grep response 裡是否有 `access-control-allow-origin` 且值匹配 request 的 `Origin`。NestJS / Express `cors` middleware 在 origin 不在 allowlist 時是「靜默成功」：仍回 204 + `access-control-allow-methods` / `-headers` / `-credentials` / `vary: Origin` 全套，**唯獨省略 `access-control-allow-origin`**，瀏覽器就判 CORS fail。

**Why:** emr-v2 CORS debug 時，第一次 curl 回 204 + 一堆 CORS header，差點誤判已通；仔細看才發現 `access-control-allow-origin` 缺失才是 root cause。光看 status code 跟「有 CORS-related header」會被騙。

**How to apply:**

1. **永遠 grep 特定 header**：
   ```bash
   curl -i -X OPTIONS <url> \
     -H 'Origin: <test-origin>' \
     -H 'Access-Control-Request-Method: GET' \
     -H 'Access-Control-Request-Headers: authorization,content-type' \
     | grep -i 'access-control\|HTTP/'
   ```
   檢查清單：`access-control-allow-origin` 必須有，且值 = request `Origin`（或 `*`）

2. **二分定位用 control test**：當 origin A fail，重跑同 curl 換成已知在 allowlist 的 origin B：
   - B 有 Allow-Origin → A 不在 allowlist（→ 查 ConfigMap 內容 / pod env）
   - B 也沒 Allow-Origin → 整個 allowlist 沒讀進來（→ pod env / deployment 沒重啟）

3. **driver header — `x-powered-by: Express`** 確認 preflight 真的打到 NestJS（不是 gateway / Cloudflare 接走）；`vary: Origin` 確認後端在動態篩 origin

4. **驗 pod env 是 ground truth**（[[appserver04-ssh]]）：
   ```bash
   ssh leo@192.168.60.5
   kubectl exec -n <ns> <pod> -- printenv ALLOWED_ORIGINS
   ```
   ConfigMap 上對了 ≠ pod 真的拿到了。Azure ConfigMap 更新需要 rollout restart deployment 才會 propagate。

5. **emr-v2 CORS 把關處是 NestJS app 的 `ALLOWED_ORIGINS` env**（main.ts:60-72，讀兩份 ConfigMap [[config-yaml-coupling-with-code]]），**不是** `k8s/base/ingress.yaml` 那組 nginx annotation — 那份 ingress host 是 `api.vibrantamerica.com`，跟 prod 對外的 `www.vibrant-america.com/lisapi/*` 是完全不同 gateway。
