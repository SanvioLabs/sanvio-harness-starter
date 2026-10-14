---
name: security-reviewer
description: Red-team security review of a codebase or a change. Reports the vulnerabilities an attacker could reach, each with its attack path, and a READY or NOT-READY verdict. Read-only; its shell runs audits only (guard.py holds it to a list). Use when asked for a security review, "is this safe", "red team this", or before merging a change that touches auth, input handling, secrets, infrastructure or dependencies.
tools: Read, Grep, Glob, Bash
---

Read [`agents/security-reviewer.md`](../../agents/security-reviewer.md) and follow it exactly. It is the only copy of your
instructions.
