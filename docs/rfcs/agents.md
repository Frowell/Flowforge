# RFCs (Requests for Comments) — Agent Rules

> Parent rules: [`/workspace/docs/agents.md`](../agents.md)

## Purpose

RFCs are **proposals for significant changes** that need discussion before implementation. Use an RFC when a change affects multiple components, introduces new architecture, or has multiple valid approaches that need evaluation.

## When to Write an RFC

- New features that touch 3+ directories or introduce new patterns
- Changes to the serving layer contract or schema propagation engine
- New infrastructure components (databases, message queues, external services)
- Changes that would require updating `agents.md` rules

## When NOT to Write an RFC

- Bug fixes, small features, refactors within a single component
- Changes that follow established patterns (e.g., adding a new node type using the existing checklist)
- Anything already covered by an accepted ADR

## Format

```markdown
# RFC-NNNN: Title

**Status:** Draft | In Discussion | Accepted | Rejected | Withdrawn
**Author:** Name
**Date:** YYYY-MM-DD

## Summary
One paragraph: what and why.

## Motivation
Why is this change needed? What problem does it solve?

## Detailed Design
How would this work? Be specific enough that someone could implement it.

## Alternatives Considered
What other approaches were evaluated? Why were they rejected?

## Open Questions
What still needs to be resolved?
```

## Lifecycle

1. **Draft** — Author writes the RFC
2. **In Discussion** — Team reviews (via PR or direct discussion)
3. **Accepted** — Decision made; key choices recorded as ADRs in `docs/decisions/`
4. **Rejected/Withdrawn** — Not proceeding; document kept for historical record

## Naming Convention

`NNNN-kebab-case-title.md` — same numbering scheme as ADRs but in a separate sequence.

## Rules

- **RFCs produce ADRs.** When an RFC is accepted, extract the key decisions into one or more ADRs in `docs/decisions/`.
- **Keep RFCs after acceptance.** They provide richer context than the ADR alone.
- **Don't use RFCs as task lists.** RFCs describe *what* and *why*, not *how to implement step by step*. Implementation plans belong in GitHub issues or project boards.
