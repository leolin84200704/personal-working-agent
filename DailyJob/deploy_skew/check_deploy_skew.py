#!/usr/bin/env python3
"""Deploy-skew check for lis-backend-emr-v2.

Answers the one question a merge log cannot: is each deployment target actually RUNNING what
was last built for it?

Written after the 2026-08-17 incident. VP-17595 made a Kafka connect failure fatal on a pod
that could never authenticate to Key Vault, so every on-prem pod created after 2026-08-04
CrashLoopBackOffed. `maxUnavailable: 0` kept the last healthy pod serving, so the service
looked fine while ~45 main merges silently failed to roll out for 13 days. Jenkins posted
FAILURE to Slack every time; nobody read a red build as "the deploy did not happen".

Two independent signals per target, because each alone has a blind spot:
  1. image identity — a mutable `:latest` target is compared against the digest the registry
     currently serves; a sha-tagged target against the head of the branch it tracks. A stuck
     rollout shows up here even when every pod is Ready.
  2. rollout health — `Progressing=ProgressDeadlineExceeded` means the last rollout never
     finished, no matter how healthy the surviving pod looks. This is the signal that was
     sitting in the cluster, unread, for 13 days.

Exit code 1 when anything is stale or stuck, so a wrapper can surface it.

On-prem access: that cluster is not in the local kubeconfig — reach it through the bastion.
Set ONPREM_SSH_HOST / ONPREM_SSH_USER, and either use an ssh key (preferred) or point
ONPREM_SSH_PASSWORD_FILE at a 0600 file OUTSIDE this repo. No credential belongs in here.
"""

import base64
import os
import re
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone

REPO = "/Users/hung.l/src/lis-backend-emr-v2"
REPORT_DIR = os.path.dirname(os.path.abspath(__file__))
MAX_SKEW_HOURS = 6  # a deploy that has not landed within hours of the build is stuck, not slow

ONPREM_HOST = os.environ.get("ONPREM_SSH_HOST", "192.168.60.5")
ONPREM_USER = os.environ.get("ONPREM_SSH_USER", "leo")
ONPREM_PASSWORD_FILE = os.environ.get("ONPREM_SSH_PASSWORD_FILE", "")

# `branch` is declared per target rather than guessed from the deployment name: the on-prem
# staging deployment is called `lis-emr-v2-deployment`, with no "staging" in it, so a name
# heuristic silently compares it against main.
TARGETS = [
    {"name": "AKS prod", "where": "aks", "ns": "emr-v2",
     "deploy": "lis-emr-v2-deployment-prod", "branch": "origin/main"},
    {"name": "AKS staging", "where": "aks", "ns": "emr-v2",
     "deploy": "lis-emr-v2-deployment-staging", "branch": "origin/staging"},
    {"name": "on-prem prod", "where": "onprem", "ns": "default",
     "deploy": "lis-emr-v2-deployment-prod", "branch": "origin/main"},
    {"name": "on-prem staging", "where": "onprem", "ns": "default",
     "deploy": "lis-emr-v2-deployment", "branch": "origin/staging"},
]

SEP = "|@|"
DEPLOY_JSONPATH = (
    "{.metadata.annotations.deployment\\.kubernetes\\.io/revision}" + SEP +
    '{.status.conditions[?(@.type=="Progressing")].reason}' + SEP +
    '{.status.conditions[?(@.type=="Progressing")].message}' + SEP +
    "{.spec.template.spec.containers[0].image}" + SEP +
    "{.spec.selector.matchLabels.app}"
)
POD_JSONPATH = (
    "{range .items[*]}{.metadata.name}" + SEP + "{.status.phase}" + SEP + "{.status.startTime}" +
    SEP + '{range .status.containerStatuses[*]}{.name}~{.imageID}~{.ready},{end}' + '{"\\n"}{end}'
)


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=120, **kw)


def onprem(remote_cmd):
    """Run a command on the on-prem bastion, base64'd on the far side.

    Two reasons for the encoding: the password fallback runs under expect, whose transcript
    interleaves the spawn banner and password prompt with real output, and expect's buffer
    silently truncates large payloads. Everything this script asks for is a short jsonpath
    projection, never a full object, so the payload stays well inside safe limits.
    """
    # The command itself is base64'd too. jsonpath arguments are full of { } and Tcl treats
    # braces as quoting, so embedding the raw command in the expect script makes it unparseable
    # in a way that surfaces as "no output" rather than as a syntax error.
    payload = base64.b64encode(f"({remote_cmd}) | base64".encode()).decode()
    wrapped = f"echo {payload} | base64 -d | bash"
    args = ["-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=10",
            f"{ONPREM_USER}@{ONPREM_HOST}", wrapped]
    r = run(["ssh", "-o", "BatchMode=yes"] + args)
    if r.returncode == 0:
        return _decode(r.stdout)
    if not ONPREM_PASSWORD_FILE or not os.path.exists(ONPREM_PASSWORD_FILE):
        raise RuntimeError(
            "on-prem unreachable: no ssh key, and ONPREM_SSH_PASSWORD_FILE is unset or missing. "
            f"ssh said: {r.stderr.strip()[:200]}"
        )
    pw = open(ONPREM_PASSWORD_FILE).read().strip()
    script = (
        "set timeout 120\n"
        f'spawn ssh {" ".join(args)}\n'
        "expect {\n"
        f'  -re {{[Pp]assword:}} {{ send "{pw}\\r"; exp_continue }}\n'
        "  eof\n"
        "}\n"
    )
    return _decode(run(["expect", "-"], input=script).stdout)


def _decode(blob):
    chunks = re.findall(r"^[A-Za-z0-9+/=]{8,}$", blob.replace("\r", ""), re.MULTILINE)
    if not chunks:
        raise RuntimeError(f"no base64 payload in remote output: {blob.strip()[:200]}")
    return base64.b64decode("".join(chunks)).decode("utf-8", "replace")


def kube(target, args):
    if target["where"] == "aks":
        r = run(["kubectl"] + args)
        if r.returncode != 0:
            raise RuntimeError(r.stderr.strip()[:200])
        return r.stdout
    return onprem("kubectl " + " ".join(f"'{a}'" if " " in a or "{" in a else a for a in args))


def registry_digest(image):
    """Digest the registry currently serves for an image reference like host/repo:tag."""
    ref, _, tag = image.rpartition(":")
    host, _, path = ref.partition("/")
    req = urllib.request.Request(
        f"http://{host}/v2/{path}/manifests/{tag}",
        headers={"Accept": "application/vnd.docker.distribution.manifest.v2+json"},
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.headers.get("Docker-Content-Digest", "")


def registry_built_at(image):
    """When the registry's current image for this reference was built."""
    ref, _, tag = image.rpartition(":")
    host, _, path = ref.partition("/")
    _, manifest = _manifest_with_body(host, path, tag)
    with urllib.request.urlopen(
        f"http://{host}/v2/{path}/blobs/{manifest['config']['digest']}", timeout=20
    ) as r:
        import json as _json
        return _json.loads(r.read()).get("created", "")


def _manifest_with_body(host, path, tag):
    req = urllib.request.Request(
        f"http://{host}/v2/{path}/manifests/{tag}",
        headers={"Accept": "application/vnd.docker.distribution.manifest.v2+json"},
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        import json as _json
        return r.headers.get("Docker-Content-Digest", ""), _json.loads(r.read())


def branch_commit_time(branch):
    return run(["git", "-C", REPO, "log", "-1", "--format=%cI", branch]).stdout.strip()


def branch_head(branch):
    return run(["git", "-C", REPO, "log", "-1", "--format=%H", branch]).stdout.strip()


def check(target):
    """Return (state, revision, detail, findings) for one deployment target."""
    findings = []
    raw = kube(target, ["get", "deploy", target["deploy"], "-n", target["ns"],
                        "-o", "jsonpath=" + DEPLOY_JSONPATH])
    rev, reason, message, image, app = (raw.split(SEP) + [""] * 5)[:5]

    state = "OK"
    if reason == "ProgressDeadlineExceeded":
        state = "STUCK"
        findings.append(
            f"{target['name']}: the last rollout never finished — {message.strip()}. "
            "Ready pods do not prove the deploy landed."
        )

    pods = kube(target, ["get", "pods", "-n", target["ns"], "-l", f"app={app}",
                         "-o", "jsonpath=" + POD_JSONPATH])
    digests, starts, running, not_ready = set(), [], 0, []
    for line in [l for l in pods.splitlines() if l.strip()]:
        name, phase, start, containers = (line.split(SEP) + [""] * 4)[:4]
        if phase == "Running":
            running += 1
        if start:
            starts.append(start)
        for c in [c for c in containers.split(",") if c]:
            cname, _, rest = c.partition("~")
            image_id, _, ready = rest.partition("~")
            if not cname.startswith("lis-emr-v2"):
                continue
            if image_id:
                digests.add(image_id.split("@")[-1])
            if ready != "true":
                not_ready.append(name)
    if not_ready:
        state = "STUCK" if state == "OK" else state
        findings.append(f"{target['name']}: container not ready in {', '.join(sorted(set(not_ready)))}")

    tag = image.rpartition(":")[2]
    if tag == "latest":
        want = registry_digest(image)
        if want and digests and want not in digests:
            state = "STALE"
            findings.append(
                f"{target['name']}: running {sorted(digests)[0]} but {image} in the registry is "
                f"{want} — the pod is not running what was built."
            )
        # A mutable tag hides a second failure: matching the registry proves the pod took the
        # last build, not that the last build contains the last merge. Without this, a branch
        # that merged but never built reports OK on both sides — the pod and the registry are
        # consistently stale. (Observed the first time this ran after a merge.)
        built = registry_built_at(image)
        head_time = branch_commit_time(target["branch"])
        if built and head_time:
            lag = (datetime.fromisoformat(head_time) -
                   datetime.fromisoformat(built.replace("Z", "+00:00"))).total_seconds() / 3600
            if lag > MAX_SKEW_HOURS:
                state = "STALE"
                findings.append(
                    f"{target['name']}: {image} was built {built}, older than "
                    f"{target['branch']} head ({head_time}) by {lag:.1f}h — the BUILD never ran, "
                    "so the pod matching the registry means nothing."
                )
            elif lag > 0:
                findings.append(
                    f"{target['name']}: {target['branch']} moved {lag * 60:.0f}min ago and the "
                    f"image is older — build likely still in flight, re-check."
                )
    elif len(tag) >= 12 and all(c in "0123456789abcdef" for c in tag.lower()):
        head = branch_head(target["branch"])
        if head and not (head.startswith(tag) or tag.startswith(head[:12])):
            state = "STALE"
            findings.append(
                f"{target['name']}: deployed tag {tag[:12]} != {target['branch']} head {head[:12]}."
            )

    oldest = min(starts) if starts else ""
    return state, rev, f"{running} running, oldest {oldest or '?'}", findings


def self_test():
    """Replay the 2026-08-17 incident through the decision logic.

    A check that prints "all OK" the day after a fix proves nothing about whether it would
    have caught the failure. This feeds `check()` the exact strings the cluster was serving
    while on-prem was frozen and asserts both signals fire. Run it after any edit here.
    """
    global kube, registry_digest, branch_head
    frozen_deploy = SEP.join([
        "234", "ProgressDeadlineExceeded",
        'ReplicaSet "lis-emr-v2-deployment-prod-54c5dd9564" has timed out progressing.',
        "192.168.60.10:6004/vibrant/lis-backend-emr-v2:latest", "lis-emr-v2-prod",
    ])
    frozen_pods = SEP.join([
        "lis-emr-v2-deployment-prod-777c956c9b-xs52b", "Running", "2026-08-04T19:16:02Z",
        "lis-emr-v2-prod~docker-pullable://192.168.60.10:6004/vibrant/"
        "lis-backend-emr-v2@sha256:stale000000000000000000000000000000000000000000000000000000~true,",
    ])
    kube = lambda t, args: frozen_deploy if args[1] == "deploy" else frozen_pods  # noqa: E731
    registry_digest = lambda image: "sha256:4e59151f2a749a3eae5ce232cad8b01987fe3e0e060e92377c24a1ddda5f6f04"  # noqa: E731
    branch_head = lambda b: "dc43eef8d681"  # noqa: E731

    state, rev, detail, findings = check(TARGETS[2])
    blob = " ".join(findings)
    assert state in ("STUCK", "STALE"), f"expected a failure state, got {state}"
    assert "never finished" in blob, "the stuck rollout was not reported"
    assert "not running what was built" in blob, "the stale image was not reported"
    print("self-test PASS — the frozen 2026-08-04 state is reported as:", state)
    for f in findings:
        print("  -", f)
    return 0


def main():
    if "--self-test" in sys.argv:
        return self_test()
    run(["git", "-C", REPO, "fetch", "-q", "origin"])
    rows, findings = [], []
    for t in TARGETS:
        try:
            state, rev, detail, f = check(t)
            rows.append((t["name"], state, f"rev {rev}", detail))
            findings += f
        except Exception as e:  # noqa: BLE001 — one unreachable target must not hide the rest
            rows.append((t["name"], "UNKNOWN", "-", "-"))
            findings.append(f"{t['name']}: could not be checked ({e}) — treat as unverified, not as OK")

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out = [f"# emr-v2 deploy skew — {today}", "",
           f"origin/main `{branch_head('origin/main')[:12]}` · "
           f"origin/staging `{branch_head('origin/staging')[:12]}`", "",
           "| target | state | revision | pods |", "|---|---|---|---|"]
    out += [f"| {n} | {s} | {r} | {p} |" for n, s, r, p in rows]
    out += ["", "## Findings", ""]
    out += [f"- {f}" for f in findings] if findings else ["- none: every target runs the current build"]

    path = os.path.join(REPORT_DIR, f"skew_{today}.md")
    open(path, "w").write("\n".join(out) + "\n")
    print("\n".join(out))
    print(f"\nreport: {path}")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
