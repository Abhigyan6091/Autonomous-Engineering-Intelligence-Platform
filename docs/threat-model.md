# Threat Model — Autonomous Engineering Intelligence Platform

## 1. System Overview & Trust Boundaries

The platform operates across four distinct trust boundaries:

```
┌─────────────────────────────────────────────────────────────┐
│ 1. Untrusted External Context (Repos, Logs, Metrics, Docs)   │
└──────────────────────────────┬──────────────────────────────┘
                               │ (Strict Sanitization & Redaction)
┌──────────────────────────────▼──────────────────────────────┐
│ 2. Control Plane & API Layer (FastAPI, JWT, RBAC)           │
└──────────────────────────────┬──────────────────────────────┘
                               │ (Structured Pydantic Payloads)
┌──────────────────────────────▼──────────────────────────────┐
│ 3. Execution Plane (LangGraph Agents, Tool Gateway)         │
└──────────────────────────────┬──────────────────────────────┘
                               │ (Docker Sandbox / Restricted Subprocess)
┌──────────────────────────────▼──────────────────────────────┐
│ 4. Execution Sandbox (Isolated Environment for Code/Tests)   │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Identified Threats & Mitigations (STRIDE Matrix)

| Threat Category | Specific Threat | Impact | Mitigation Strategy |
| :--- | :--- | :--- | :--- |
| **Spoofing** | Forged JWT or actor identity | Unauthorized investigation access | Cryptographically signed tokens (HS256/RS256), per-project RBAC enforcement. |
| **Tampering** | Indirect Prompt Injection via repository comments/docs/logs | Agent hijacks execution flow or exfiltrates context | Untrusted context framing (`=== UNTRUSTED REPOSITORY CONTENT ===`), structured output schemas, refusal to interpret repository text as instructions. |
| **Repudiation** | Operator or agent executes action without tracking | Inability to audit incidents or compliance violations | Immutable `audit_events` logged in PostgreSQL with trace IDs, tool hashes, and actor identifiers. |
| **Information Disclosure** | Credentials embedded in logs/code leaked to LLM providers | Secret leakage across third-party LLM APIs | Pre-LLM regex redaction layer (`SecretRedactor`) scrubbing AWS keys, passwords, bearer tokens, connection strings. |
| **Denial of Service** | Agent enters infinite loops or exhausts API tokens | Resource exhaustion, uncontrolled cloud costs | Per-investigation token limits (500k tokens), max tool call thresholds (200), graph recursion limits, exponential backoff. |
| **Elevation of Privilege** | Arbitrary shell execution or container escape via tests/linters | Host filesystem corruption or breakout | Isolated unprivileged Docker sandbox, `cap_drop: ALL`, `read_only` rootfs, `tmpfs`, command allowlist, banned shell pipes. |

---

## 3. Prompt Injection Defense in Depth

1. **System Prompt Hardening**: System instructions explicitly disclaim authority from repository context.
2. **Context Wrapping**: All user data, code, logs, and files are delimited and clearly labeled as data-only.
3. **Structured Tool Schemas**: The LLM cannot emit freeform terminal commands; it can only invoke registered Pydantic tool schemas.
4. **Mandatory Human Approval**: No branch creation, patch application, or PR generation can execute without explicit operator sign-off.
