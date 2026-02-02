# Embed Feature — Agent Rules

> Parent rules: [`/workspace/frontend/agents.md`](../../../agents.md) | Architecture: [`/workspace/planning.md`](../../../../../planning.md)

## Route

```
/embed/:widget_id?api_key=sk_live_...
```

## Chromeless Rendering

- **No shell, sidebar, or header** — the widget fills the entire viewport.
- Responsive: widget sizes to fill the iframe container.
- Minimal UI: just the chart/table and optionally a title.

## Authentication

- **API key only** — not session auth. The `api_key` parameter is validated server-side and scoped to specific widgets.
- No login flow, no redirect — if the key is invalid, show an error state.
- URL parameters for filter overrides: `?symbol=AAPL&range=1d`.

## Same Chart Component

The embed widget renders using the exact same chart components from `shared/components/charts/` as the canvas and dashboard. No embed-specific chart variants.

## Minimal Bundle

- **No React Flow imports** — the embed route does not need the canvas library.
- **No Zustand** — no client-side state management needed for a single read-only widget.
- Use `React.lazy()` and code splitting to keep the embed bundle small.
- Only import what the specific widget type needs (e.g., don't load CandlestickChart for a BarChart embed).

## Multi-Tenancy in Embed

- Embed mode authenticates via API key, not Keycloak. The API key is stored in the `api_keys` table with a `tenant_id` column.
- The backend validates that the API key's `tenant_id` matches the widget's dashboard's `tenant_id`. A key from tenant A cannot access widgets from tenant B.
- The frontend embed route does not handle tenant logic — it passes the `api_key` to the backend and renders whatever is returned or shows an error state.
