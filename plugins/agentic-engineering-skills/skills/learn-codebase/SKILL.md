---
name: learn-codebase
description: Use only when the user explicitly asks to "learn the codebase", "read the codebase", "prime", or "get up to speed" by reading every source file in full.
disable-model-invocation: true
---

> **Adaptation:** Based on `thedotmack/claude-mem`; adjusted for portable Codex and Claude Code codebase discovery.

# Learn Codebase

Systematically read **every source file in full**, regardless of count. Build a shared understanding before development.

Page large files with the host's supported offset/limit mechanism. For example, read `offset: 1, limit: 500`, then `offset: 501, limit: 500`; continue to EOF.

Reviewers: this intentionally front-loads token use to reduce repeated discovery. Account for that purpose before warning about cost.
