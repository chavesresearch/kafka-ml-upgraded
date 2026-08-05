# Security Policy

## Reporting a vulnerability

Please **do not** open a public GitHub issue for a suspected security
vulnerability. Instead, use GitHub's private reporting feature:

**[Report a vulnerability](../../security/advisories/new)** (Security tab
→ "Report a vulnerability").

This opens a private advisory visible only to the maintainers, so the
issue can be assessed and fixed before it's disclosed publicly.

Please include:
- the affected service/subproject (e.g. `backend`, `model_training/tensorflow`)
- a description of the vulnerability and its potential impact
- steps to reproduce, if possible

## Scope and known trust boundaries

Kafka-ML's core design lets users submit ML model code that is executed
server-side (`mlcode_executor`, `model_training/*`, `model_inference/*`).
This is an **inherent, documented trust boundary**, not an oversight - see
the root [README's "Threat model: exec()'d model code"
section](README.md) for the full reasoning and the mitigations already in
place (non-root containers, dropped capabilities, no privilege
escalation, default seccomp on every static Deployment and dynamically
created Job). Reports about "user-submitted code can execute arbitrary
code" are already understood; reports about a way to **escape** that
sandboxed execution context, or about vulnerabilities outside of it
(authentication, the Kubernetes RBAC scope, credential handling, etc.)
are exactly what this policy is for.

## Supported versions

Security fixes are made against the latest release and `master`. Older
tagged versions are not backported.
