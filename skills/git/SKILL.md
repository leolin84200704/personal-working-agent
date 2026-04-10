# Git Operations Skill

> Git branch, commit, and push operations

---

## Metadata
```yaml
name: git
type: vcs
agent: code-agent
priority: high
```

---

## Purpose

Handle Git operations for ticket implementation:
- Create feature branches
- Commit changes
- Push to remote

---

## Branch Naming Convention

**STRICT RULES - No exceptions:**
- New features: `feature/leo/{ticket_id}`
- Bug fixes: `bugfix/leo/{ticket_id}`

Examples:
- `feature/leo/VP-15979`
- `bugfix/leo/LIS-12345`

---

## Safety Rules

**Allowed:**
- ✅ `git checkout -b feature/leo/*`
- ✅ `git commit`
- ✅ `git push` (to own branch only)

**Blocked:**
- ❌ `git push origin main:*`
- ❌ `git push --force`
- ❌ `git reset --hard`

**Merge:**
- User decides, Agent only generates Draft PR

---

## Commit Message Format

```
[{ticket_id}] {brief description}

Example:
[VP-15979] Add EMR integration for Holistic Health Code
```

---

*Last Updated: 2026-04-07*
