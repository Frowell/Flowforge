# 0003: Dual Schema Propagation Engines (TypeScript + Python)

**Status:** Accepted
**Date:** 2025-10-01
**Deciders:** Architecture team

## Context

The canvas needs to show users real-time schema information as they build workflows — column names in dropdowns, type-appropriate operators, and instant error highlighting when incompatible nodes are connected. This requires computing the output schema of every node in the DAG after each change.

The backend (Python) needs the same logic to validate workflows before compilation and to verify schema correctness server-side.

## Decision

Maintain **two schema propagation engines** that must produce identical results:

1. **TypeScript** (`frontend/src/shared/schema/propagation.ts`) — synchronous, runs on every connection change, provides instant feedback. Target: < 10ms for 50 nodes.
2. **Python** (`backend/app/services/schema_engine.py`) — authoritative, runs server-side for validation and compilation.

Both engines are tested against 11 shared JSON fixtures in `tests/fixtures/schema/`. The `scripts/validate-schema-parity.sh` script verifies parity and runs in CI.

## Alternatives Considered

**Server-side only**: Every connection change triggers an API call. At 50-200ms round-trip, the canvas feels sluggish. Debouncing helps but introduces visible lag in dropdown population.

**Client-side only**: Fast but the backend can't trust client-reported schemas. A malicious or buggy client could claim any schema, bypassing validation.

**WASM compilation of a single engine**: Write once in Rust/Go, compile to WASM for the browser and native for the backend. Eliminates drift but adds build complexity and a third language to the stack.

**Code generation from a shared DSL**: Define transforms in a neutral format, generate TypeScript and Python. Eliminates drift but the generator becomes a complex tool to maintain.

## Consequences

- **Positive**: Instant schema feedback in the canvas — dropdowns populate in < 10ms.
- **Positive**: Server-side validation catches any client-side bugs or tampering.
- **Positive**: Shared fixtures make drift detectable in CI before it reaches production.
- **Negative**: Every new node type requires implementing the transform twice. The node type checklist has 6 files minimum.
- **Negative**: Subtle behavioral differences between TypeScript and Python (floating point, null handling) can cause hard-to-debug parity failures.
