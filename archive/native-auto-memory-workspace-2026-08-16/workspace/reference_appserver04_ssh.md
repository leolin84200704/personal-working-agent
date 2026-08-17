---
name: appserver04-ssh
description: "On-prem K8s access — appserver04 (192.168.60.5) hosts V1 Java EMR-Backend + V2 lis-backend-emr-v2 prod/staging pods. Mac kubectl lisportalprod context = Azure AKS only, can't see on-prem."
metadata: 
  node_type: memory
  type: reference
  originSessionId: 904372bb-59eb-4895-ba9d-b023a08378ae
---

`ssh leo@192.168.60.5` (password 從 Leo 取) → 直接跑 `kubectl get pods` / `kubectl logs <pod> -c <container>` / `kubectl rollout restart deployment <name>`。

**為什麼必要**：本機 `~/.kube/config` 的 `lisportalprod` context 連的是 Azure AKS，**看不到** on-prem 的 v2 prod/staging pod 跟 v1 Java pod。所有 EMR 相關 pod (`lis-emr-prod*`, `lis-emr-v2-deployment*`) 都在 appserver04。

**自動化跑 kubectl** — 本機沒 sshpass，用 `expect` 帶密碼：
```bash
expect << 'EOF'
set timeout 30
spawn ssh -o StrictHostKeyChecking=no leo@192.168.60.5
expect "password:"; send "<pw>\r"
expect -re {\$ ?$}
send "kubectl logs <pod> -c <container> --since=10m\r"
expect -re {\$ ?$}; send "exit\r"; expect eof
EOF
```
sudo 用 `echo <pw> | sudo -S <cmd>`。expect heredoc 內含 `[^...]` regex character class 會被誤判 → 把 shell script base64 編碼再 `base64 -d | bash` 跑。

**One-shot 最可靠形式**（2026-06-12 VP-16968 實測）：用 expect brace-quote 把整段遠端命令當單一參數傳給 ssh，`spawn ssh -o StrictHostKeyChecking=accept-new -o PubkeyAuthentication=no leo@192.168.60.5 {cmd1; cmd2; kubectl ... | grep ...}` + `expect -re "(?i)password:" {send "abc123\r"; exp_continue}` + `eof`。`echo <b64> | base64 -d | bash` 的 one-shot 形式在此 session **輸出常常空白**(password 後立即 eof)，brace-quote 純命令穩定。注意：brace `{...}` 內**不能**含 `{}`（如 jsonpath `{.spec...}` 會破壞 expect brace 配對）→ 改用 `kubectl describe pod X | grep -i Image:`。password = abc123（Leo 提供）。image registry: `192.168.60.10:6004/vibrant/lis-backend-emr-v2:latest`（:latest 是 mutable tag）。

**Pod naming 易混淆**：
- `lis-emr-prod-<hash>` = V1 Java EMR-Backend
- `lis-emr-v2-deployment-prod-<hash>` = V2 NestJS prod (連 `lisportalprod2.mysql.database.azure.com`)
- `lis-emr-v2-deployment-<hash>`（無 `-prod`） = V2 NestJS staging（連 `192.168.60.11`）

詳細見 [[lis-code-agent/long-term-memory/repos.md]] "On-prem K8s 存取" 區段 + STM [[INCIDENT-20260528]]。
