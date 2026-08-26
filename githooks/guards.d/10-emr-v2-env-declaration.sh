#!/usr/bin/env sh
# Instance guard: a new env var in lis-backend-emr-v2 must have a declared home.
#
# Moved here from the shared factory hook, where it did not belong: of the 48
# repos that hook is wired into, exactly one matches this convention, and a guard
# that speaks up in the other 47 is a guard that gets the whole hook switched off.
#
# It also no longer derives its scope the way the factory version did. That
# version keyed on the presence of `*-config.yaml` at the repo root — files which
# are GITIGNORED, so they exist only in whichever working copy happened to create
# them and are absent from every worktree and fresh clone. The guard was
# therefore active or silent depending on where you committed from; commits made
# from a worktree sailed past it. Scope is now the repo identity, which is the
# same everywhere.
#
# Why this warns instead of blocking: the comparison target is unsettled
# (VP-17916). The repo's local ConfigMap copies are a stale snapshot that no
# deploy step reads, and the live cluster ConfigMap is the real source of truth —
# so there is no file in the tree that a hard failure could honestly point at.
# Shipping an env var with a deliberate code-side default is also legitimate, and
# blocking it would be a false positive. Once VP-17916 picks a source of truth,
# this should become a hard gate against that.

[ -n "$repo_root" ] || exit 0
case "$(git config --get remote.origin.url 2>/dev/null)" in
    *lis-backend-emr-v2*) ;;
    *) exit 0 ;;   # out of scope, silently
esac

added_vars="$(git diff --cached --unified=0 -- '*.ts' '*.js' 2>/dev/null \
    | grep '^+' | grep -v '^+++' \
    | grep -oE 'process\.env\.[A-Za-z_][A-Za-z0-9_]*' \
    | sed 's/process\.env\.//' | sort -u || true)"
[ -n "$added_vars" ] || exit 0

KC="kubectl --context lisportalprod -n emr-v2 --request-timeout=5s"
cluster_keys="$($KC get cm lis-emr-v2-config -o go-template='{{range $k,$v := .data}}{{$k}}
{{end}}' 2>/dev/null)"

echo ""
if [ -z "$cluster_keys" ]; then
    echo "! [emr-v2 env] could not reach the cluster to check where these belong:"
    echo "$added_vars" | sed 's/^/      /'
    echo "  The live lis-emr-v2-config / -config-prod ConfigMaps are the source of"
    echo "  truth (the repo's *-config.yaml copies are a gitignored stale snapshot"
    echo "  that no deploy reads — see VP-17916). Verify on VPN before pushing, or"
    echo "  state the code-side default deliberately."
    exit 0
fi

missing=""
for v in $added_vars; do
    echo "$cluster_keys" | grep -qx "$v" || missing="$missing $v"
done

if [ -n "$missing" ]; then
    echo "! [emr-v2 env] not present in the live lis-emr-v2-config ConfigMap:"
    for v in $missing; do echo "      $v"; done
    echo "  Either add them to the ConfigMap (kubectl edit configmap lis-emr-v2-config)"
    echo "  or record in the PR that the code-side default is the intended value."
    echo "  Editing k8s/base/configmap.yaml does NOT reach a pod (VP-17916)."
else
    echo "✓ [emr-v2 env] all new env vars already exist in the live ConfigMap."
fi
exit 0
