# Agent Types

## emr-integration-agent
Handles EMR Integration tickets (VP-xxxxx)。分析 ticket → gRPC 查 provider → 比對/更新 DB。
業務規則見 `knowledge/emr-integration.md`。

## code-agent
Handles code modification tickets。掃 repo → 找檔案 → 改 code → branch/commit/push。

## scan-agent
Scans Jira for assigned tickets，產生摘要。
