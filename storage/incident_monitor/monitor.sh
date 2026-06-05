#!/bin/bash
# INCIDENT-20260604 — every-5min tick. Idempotent.
set +e

STATE="/Users/hung.l/src/lis-code-agent/storage/incident_monitor/INCIDENT-20260604.state.json"
LOG="/Users/hung.l/src/lis-code-agent/storage/incident_monitor/INCIDENT-20260604.ticks.log"

NOW_TS=$(date +%s)
NOW_ISO=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

if [[ ! -f "$STATE" ]]; then
  echo "{\"start_ts\": $NOW_TS, \"tick_count\": 0}" > "$STATE"
fi
START_TS=$(grep -oE '"start_ts": *[0-9]+' "$STATE" | grep -oE '[0-9]+')
TICK=$(grep -oE '"tick_count": *[0-9]+' "$STATE" | grep -oE '[0-9]+')
TICK=$((TICK + 1))
ELAPSED=$((NOW_TS - START_TS))

# Run ssh+kubectl. Use {curly} braces for expect's spawn so $-vars don't bite.
run_ssh() {
  local cmd="$1"
  local exp_script=$(mktemp)
  cat > "$exp_script" <<EXPECT
#!/usr/bin/expect -f
set timeout 90
spawn ssh -o StrictHostKeyChecking=no leo@192.168.60.5 {$cmd}
expect "password:"
send "abc123\r"
expect eof
EXPECT
  chmod +x "$exp_script"
  "$exp_script" 2>/dev/null \
    | grep -v "^spawn " \
    | grep -v "password" \
    | grep -v "Defaulting container name" \
    | grep -v "Use 'kubectl describe pod"
  rm -f "$exp_script"
}

PROD_POD=$(run_ssh "kubectl get pods -n default -l app=lis-emr-v2-prod --no-headers -o custom-columns=NAME:.metadata.name" | tr -d ' \r\n')
if [[ -z "$PROD_POD" ]]; then
  echo "[$NOW_ISO] tick=$TICK elapsed=${ELAPSED}s FAIL pod_not_found" >> "$LOG"
  echo "FAIL pod_not_found"
  exit 1
fi

# Outcomes in last 6 min
RAW_OUTCOMES=$(run_ssh "kubectl logs -n default $PROD_POD -c lis-emr-v2-prod --since=6m" \
  | grep -oE 'outcome=[a-z_]+' | sort | uniq -c | awk '{printf "%s:%d ", $2, $1}')

# Active sockets to MDHQ 34.199.194.51
NETSTAT=$(run_ssh "kubectl exec -n default $PROD_POD -c lis-emr-v2-prod -- sh -c 'netstat -ntp 2>/dev/null | grep 34.199.194.51 | awk \"{print \\\$6}\" | sort | uniq -c | awk \"{printf \\\"%s:%d \\\", \\\$2, \\\$1}\"'")

TOTAL=$(run_ssh "kubectl logs -n default $PROD_POD -c lis-emr-v2-prod --since=6m" | grep -c '\[SFTP_CLOSE\]')
WARN=$(run_ssh "kubectl logs -n default $PROD_POD -c lis-emr-v2-prod --since=6m" | grep -E 'outcome=fin_then_rst|outcome=fin_then_destroy|outcome=destroy_only|outcome=no_socket|outcome=already_destroyed' | wc -l | tr -d ' ')

cat > "$STATE" <<JSON
{"start_ts": $START_TS, "tick_count": $TICK, "prod_pod": "$PROD_POD", "last_tick_ts": $NOW_TS, "last_elapsed_s": $ELAPSED}
JSON

LINE="[$NOW_ISO] tick=$TICK/24 elapsed=${ELAPSED}s pod=$PROD_POD total=$TOTAL warn=$WARN outcomes={ $RAW_OUTCOMES} mdhq_socks={ $NETSTAT}"
echo "$LINE" >> "$LOG"
echo "$LINE"
