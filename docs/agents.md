# Documentation — Agent Rules

> Parent rules: [`/workspace/agents.md`](../agents.md)

## Purpose

Focused technical guides for specific cross-cutting concerns. These supplement the per-directory `agents.md` files with deeper dives.

## Document Catalog

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
