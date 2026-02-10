# Archive — Agent Rules

> Parent rules: [`/workspace/docs/agents.md`](../agents.md)

## Purpose

This directory contains **legacy planning documents** that guided FlowForge's initial development. All phases described in these documents have been implemented. They are preserved here for historical reference and onboarding context — **not as active requirements**.

## Archived Documents

| Document | Original Location | What It Was |
|----------|--------------------|-------------|
| `planning.md` | `/planning.md` | Original product planning spec — scope, architecture, 6 implementation phases, schema contracts |
| `Application plan.md` | `/Application plan.md` | Living reference with implementation status tracking, remaining work, success criteria |
| `open-issues.md` | `/open-issues.md` | Architectural issues identified during planning review — all resolved or decided |

## Rules

- **Do NOT treat these as active requirements.** The canonical source of truth for coding rules is `CLAUDE.md` / `agents.md` in each directory. These archived docs may contain outdated information.
- **Do NOT modify these files.** They are frozen snapshots of the planning process.
- **Reference for context only.** If you need to understand *why* something was built a certain way, these documents explain the original rationale. But the implemented code is the authority, not the plan.
- **No new files in this directory** unless explicitly archiving another completed planning document.
