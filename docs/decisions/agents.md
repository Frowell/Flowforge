# Architecture Decision Records — Agent Rules

> Parent rules: [`/workspace/docs/agents.md`](../agents.md)

## Purpose

Architecture Decision Records (ADRs) capture **why** key technical decisions were made. Each ADR is a short, immutable document recording the context, options considered, and rationale for a decision. They are numbered sequentially and never deleted — only superseded.

## Format

Every ADR follows this template (see `0000-template.md`):

```markdown
# NNNN: Title

**Status:** Accepted | Superseded by [NNNN](./NNNN-title.md) | Deprecated
**Date:** YYYY-MM-DD
**Deciders:** Who was involved

## Context
What is the problem or situation that requires a decision?

## Decision
What is the change that we're making?

## Consequences
What becomes easier or harder as a result of this decision?
```

## Naming Convention

`NNNN-kebab-case-title.md` — zero-padded to 4 digits, sequential, never reused.

Examples: `0001-sqlglot-over-dataframes.md`, `0002-multi-tenant-from-day-one.md`

## Lifecycle

| Status | Meaning |
|--------|---------|
| **Proposed** | Under discussion — not yet decided |
| **Accepted** | Decision made and in effect |
| **Superseded** | Replaced by a newer ADR (link to it) |
| **Deprecated** | No longer relevant (e.g., feature removed) |

Accepted ADRs are **immutable** — do not edit them. If a decision changes, write a new ADR that supersedes the old one and update the old ADR's status line to `Superseded by [NNNN](./NNNN-title.md)`.

## Rules

- **One decision per ADR.** Don't combine multiple decisions into one document.
- **Short and focused.** ADRs should be 1-2 pages max. Link to external docs for deep dives.
- **Record the alternatives.** The value of an ADR is understanding *why* option B was chosen over A and C.
- **Write ADRs when decisions are made**, not retroactively months later (though retroactive ADRs are better than none).
- **Never delete an ADR.** The historical record is the point. Supersede instead.
- **Number is permanent.** Even rejected proposals keep their number.
