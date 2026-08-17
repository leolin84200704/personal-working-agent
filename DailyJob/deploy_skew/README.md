# Deploy-skew check

Answers the question the merge log cannot: **is each target actually running what was last
built for it?**

## Why this exists

On 2026-08-04 a change made a Kafka connect failure fatal on the on-prem pod, which has no
Azure identity and therefore could never resolve its Key Vault secret. Every new on-prem pod
CrashLoopBackOffed. `maxUnavailable: 0` kept the last healthy pod serving, so the service
looked fine while ~45 main merges never rolled out. It surfaced 13 days later as unrelated
order failures, when a new enum value reached a Prisma client older than itself.

Every signal needed to catch this was already present and unread:

- the deployment's own `Progressing` condition said `ProgressDeadlineExceeded`;
- the running pod's image digest did not match the `:latest` the registry served;
- Jenkins posted `FAILURE` to Slack on every main build.

The gap was that nobody read a red build as "the deploy did not happen", and on-prem is the
half of a parallel rollout that no one verifies — it is not in the local kubeconfig, so it
gets inferred instead of checked. This job checks it.

## Running it

```bash
python3 DailyJob/deploy_skew/check_deploy_skew.py            # exits 1 on any finding
python3 DailyJob/deploy_skew/check_deploy_skew.py --self-test # replays the 2026-08-17 state
```

Run `--self-test` after touching the decision logic. It feeds `check()` the exact strings the
cluster served while on-prem was frozen and asserts both signals fire — a check that only
ever prints "all OK" has never demonstrated that it can say anything else.

## On-prem access

That cluster is not in the local kubeconfig; it is reached through the bastion
(`ONPREM_SSH_HOST`, default `192.168.60.5`). Prefer an ssh key. Otherwise point
`ONPREM_SSH_PASSWORD_FILE` at a 0600 file **outside this repo** — no credential belongs here.

## Install

```bash
cp DailyJob/deploy_skew/com.lis.deploy-skew.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.lis.deploy-skew.plist
```
