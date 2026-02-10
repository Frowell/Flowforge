# Documentation — Agent Rules

> Parent rules: [`/workspace/agents.md`](../agents.md)

## Purpose

Technical reference guides, architecture decision records, and proposal documents. Organized into four categories with distinct lifecycles.

## Directory Structure

```
docs/
├── decisions/       # ADRs — immutable records of key technical decisions
├── rfcs/            # Proposals for significant changes (pre-decision)
├── archive/         # Completed planning docs (legacy reference only)
├── node-type-guide.md
├── multi-tenancy.md
├── serving-layer.md
└── agents.md
```

## Document Types

| Type | Location | Lifecycle | Purpose |
|------|----------|-----------|---------|
| **Reference Guides** | `docs/*.md` | Living — edited in place | Cross-cutting technical patterns (node types, tenancy, serving layer) |
| **ADRs** | `docs/decisions/` | Immutable — superseded, never edited | Record *why* key technical decisions were made |
| **RFCs** | `docs/rfcs/` | Proposed -> Accepted/Rejected | Proposals for significant changes needing discussion |
| **Archive** | `docs/archive/` | Frozen | Legacy planning docs, historical reference only |

## Reference Guides

| Document | Audience | Covers |
|----------|----------|--------|
| `node-type-guide.md` | Backend + Frontend agents | Node type checklist (6 files per type), schema propagation rules, query merging requirements |
| `multi-tenancy.md` | Backend + Frontend agents | 10 tenant isolation rules, code patterns, test requirements, cache scoping |
| `serving-layer.md` | Backend agents | Table catalog (ClickHouse, Materialize, Redis), query router dispatch rules, SQL dialects |

## Conventions

- **Markdown only** — GitHub-flavored markdown, rendered in VS Code and GitHub.
- **Tables for reference** — use tables for catalogs, rules, and option lists.
- **Code examples** — show correct and incorrect patterns side by side where applicable.
- **Cross-link to agents.md** — reference the relevant directory's `agents.md` for implementation details.
- **Keep current** — update docs when the code changes. Stale docs are worse than no docs.

## Rules

- **Do not duplicate `agents.md` content** — docs complement agents.md, they don't replace it. If a rule belongs in a directory's agents.md, put it there.
- **Do not create new docs without clear need** — every doc should answer a specific question that multiple agents encounter. One-off notes belong in the relevant agents.md.
- **No auto-generated API docs** — the Swagger UI at `/docs` is the API reference. These docs cover architectural patterns, not endpoint signatures.
- **ADRs are immutable** — never edit an accepted ADR. Write a new one that supersedes it.
- **RFCs produce ADRs** — when an RFC is accepted, extract key decisions into `docs/decisions/`.
