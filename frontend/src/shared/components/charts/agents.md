# Chart Components — Agent Rules

> Parent rules: [`/workspace/frontend/src/shared/agents.md`](../../agents.md)

## Critical Rule

**This is the single source of truth for ALL chart rendering in FlowForge.** Canvas data preview, dashboard widget card, and embed iframe all import from this directory. Never create chart components in feature directories.

## Component Catalog

| Component      | File                   | Chart Library             | Use Case                                      |
| -------------- | ---------------------- | ------------------------- | --------------------------------------------- |
| Bar Chart      | `BarChart.tsx`         | Recharts `<BarChart>`     | Horizontal/vertical bars, stacked, grouped    |
| Line Chart     | `LineChart.tsx`        | Recharts `<LineChart>`    | Time-series, multi-series, area fill          |
| Candlestick    | `CandlestickChart.tsx` | Recharts (custom)         | OHLC with volume subplot (fintech-specific)   |
| Scatter Plot   | `ScatterPlot.tsx`      | Recharts `<ScatterChart>` | X/Y scatter with size/color dimensions        |
| KPI Card       | `KPICard.tsx`          | Custom (no Recharts)      | Single-value metric with threshold coloring   |
| Pivot Table    | `PivotTable.tsx`       | Custom (no Recharts)      | Row/column pivot crosstab                     |
| Chart Renderer | `ChartRenderer.tsx`    | Dispatch                  | Routes chart type string to correct component |

## Props Contract

All chart components follow the same props interface:

```typescript
interface ChartComponentProps {
  data: ChartData; // Array of row objects
  config: ChartConfig; // Axis mappings, colors, options
  interactive?: boolean; // Enable click handlers (default: true)
  onDrillDown?: (filters: FilterChip[]) => void; // Click → drill-down
}
```

Type definitions live in `types.ts` within this directory.

## Rules

1. **No per-mode variants.** Never create `CanvasBarChart`, `DashboardBarChart`, `EmbedBarChart`. One component, three contexts.
2. **Responsive sizing.** Charts fill their container — never set fixed pixel width/height. The parent (canvas preview panel, widget card, embed viewport) controls dimensions.
3. **Dark theme default.** All charts use dark background colors matching the app theme. Light theme support is optional.
4. **Recharts only.** Do not introduce ECharts, Chart.js, D3 directly, or any other chart library. Recharts is the standard.
5. **No data fetching.** Chart components are pure renderers — they receive `data` and `config` as props. Data fetching is the responsibility of the parent (via TanStack Query hooks).
6. **Tailwind for layout.** Use Tailwind classes for chart container styling. Recharts handles internal chart styling via props.

## ChartRenderer Dispatch

`ChartRenderer.tsx` maps a chart type string to the correct component:

```typescript
// Used by WidgetCard and EmbedWidget to render any chart type
<ChartRenderer type="bar" data={data} config={config} />
```

When adding a new chart type, register it in `ChartRenderer.tsx`.

## Adding a New Chart Type

1. Create `NewChart.tsx` in this directory
2. Follow the `ChartComponentProps` interface
3. Register in `ChartRenderer.tsx` dispatch
4. Add type definitions to `types.ts`
5. Export from this directory's barrel (if one exists)
