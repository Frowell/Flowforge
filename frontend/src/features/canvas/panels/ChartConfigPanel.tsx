/**
 * Chart output config panel — chart type selection and per-type axis mapping.
 */

import { useState } from "react";
import { useParams } from "react-router-dom";

import { useNodeInputSchema } from "../hooks/useSchemaEngine";
import { useWorkflowStore } from "../stores/workflowStore";
import PinToDialog from "@/features/dashboards/components/PinToDialog";

interface Props {
  nodeId: string;
}

const CHART_TYPES = ["bar", "line", "scatter", "candlestick", "kpi", "pivot"] as const;
const AGGREGATIONS = ["SUM", "AVG", "COUNT", "MIN", "MAX", "LAST"] as const;

const selectClass =
  "w-full bg-canvas-bg border border-white/10 rounded px-2 py-1.5 text-sm text-white";
const labelClass = "text-xs text-white/50 block mb-1";
const checkboxClass = "mr-2 accent-canvas-accent";

function ColumnSelect({
  label,
  value,
  columns,
  onChange,
  placeholder = "Select column...",
}: {
  label: string;
  value: string;
  columns: Array<{ name: string }>;
  onChange: (v: string) => void;
  placeholder?: string;
}) {
  return (
    <div>
      <label className={labelClass}>{label}</label>
      <select value={value} onChange={(e) => onChange(e.target.value)} className={selectClass}>
        <option value="">{placeholder}</option>
        {columns.map((col) => (
          <option key={col.name} value={col.name}>
            {col.name}
          </option>
        ))}
      </select>
    </div>
  );
}

function MultiColumnSelect({
  label,
  selected,
  columns,
  onChange,
}: {
  label: string;
  selected: string[];
  columns: Array<{ name: string }>;
  onChange: (v: string[]) => void;
}) {
  const toggle = (name: string) => {
    if (selected.includes(name)) {
      onChange(selected.filter((s) => s !== name));
    } else {
      onChange([...selected, name]);
    }
  };

  return (
    <div>
      <label className={labelClass}>{label}</label>
      <div className="max-h-32 overflow-y-auto border border-white/10 rounded p-1.5 space-y-0.5">
        {columns.length === 0 && (
          <span className="text-xs text-white/30">No columns available</span>
        )}
        {columns.map((col) => (
          <label
            key={col.name}
            className="flex items-center text-xs text-white cursor-pointer hover:bg-white/5 px-1 rounded"
          >
            <input
              type="checkbox"
              checked={selected.includes(col.name)}
              onChange={() => toggle(col.name)}
              className={checkboxClass}
            />
            {col.name}
          </label>
        ))}
      </div>
    </div>
  );
}

export default function ChartConfigPanel({ nodeId }: Props) {
  const { workflowId } = useParams<{ workflowId: string }>();
  const inputSchema = useNodeInputSchema(nodeId);
  const updateNodeConfig = useWorkflowStore((s) => s.updateNodeConfig);
  const node = useWorkflowStore((s) => s.nodes.find((n) => n.id === nodeId));
  const config = (node?.data.config ?? {}) as Record<string, unknown>;
  const [showPinDialog, setShowPinDialog] = useState(false);

  const chartType = (config.chart_type as string) ?? "bar";
  const set = (updates: Record<string, unknown>) => updateNodeConfig(nodeId, updates);

  const toStringArray = (val: unknown): string[] => {
    if (Array.isArray(val)) return val.map(String);
    if (typeof val === "string" && val)
      return val
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);
    return [];
  };

  return (
    <div className="space-y-3">
      {/* Chart type selector */}
      <div>
        <label className={labelClass}>Chart Type</label>
        <select
          value={chartType}
          onChange={(e) => set({ chart_type: e.target.value })}
          className={selectClass}
        >
          {CHART_TYPES.map((ct) => (
            <option key={ct} value={ct}>
              {ct.charAt(0).toUpperCase() + ct.slice(1)}
            </option>
          ))}
        </select>
      </div>

      {/* Bar chart config */}
      {chartType === "bar" && (
        <>
          <ColumnSelect
            label="X Axis"
            value={(config.x_axis as string) ?? ""}
            columns={inputSchema}
            onChange={(v) => set({ x_axis: v })}
          />
          <MultiColumnSelect
            label="Y Axis (values)"
            selected={toStringArray(config.y_axis)}
            columns={inputSchema}
            onChange={(v) => set({ y_axis: v })}
          />
          <ColumnSelect
            label="Color Group (optional)"
            value={(config.colorGroup as string) ?? ""}
            columns={inputSchema}
            onChange={(v) => set({ colorGroup: v })}
          />
          <div className="flex items-center gap-4">
            <label className="flex items-center text-xs text-white cursor-pointer">
              <input
                type="checkbox"
                checked={(config.stacked as boolean) ?? false}
                onChange={(e) => set({ stacked: e.target.checked })}
                className={checkboxClass}
              />
              Stacked
            </label>
            <label className="flex items-center text-xs text-white cursor-pointer">
              <input
                type="checkbox"
                checked={config.orientation === "horizontal"}
                onChange={(e) => set({ orientation: e.target.checked ? "horizontal" : "vertical" })}
                className={checkboxClass}
              />
              Horizontal
            </label>
          </div>
        </>
      )}

      {/* Line chart config */}
      {chartType === "line" && (
        <>
          <ColumnSelect
            label="X Axis"
            value={(config.x_axis as string) ?? ""}
            columns={inputSchema}
            onChange={(v) => set({ x_axis: v })}
          />
          <MultiColumnSelect
            label="Y Axis (series)"
            selected={toStringArray(config.y_axis)}
            columns={inputSchema}
            onChange={(v) => set({ y_axis: v })}
          />
          <label className="flex items-center text-xs text-white cursor-pointer">
            <input
              type="checkbox"
              checked={(config.areaFill as boolean) ?? false}
              onChange={(e) => set({ areaFill: e.target.checked })}
              className={checkboxClass}
            />
            Area Fill
          </label>
        </>
      )}

      {/* Scatter config */}
      {chartType === "scatter" && (
        <>
          <ColumnSelect
            label="X Axis"
            value={(config.x_axis as string) ?? ""}
            columns={inputSchema}
            onChange={(v) => set({ x_axis: v })}
          />
          <ColumnSelect
            label="Y Axis"
            value={(config.y_axis as string) ?? ""}
            columns={inputSchema}
            onChange={(v) => set({ y_axis: v })}
          />
          <ColumnSelect
            label="Size Column (optional)"
            value={(config.sizeColumn as string) ?? ""}
            columns={inputSchema}
            onChange={(v) => set({ sizeColumn: v })}
          />
          <ColumnSelect
            label="Color Column (optional)"
            value={(config.colorColumn as string) ?? ""}
            columns={inputSchema}
            onChange={(v) => set({ colorColumn: v })}
          />
          <label className="flex items-center text-xs text-white cursor-pointer">
            <input
              type="checkbox"
              checked={(config.trendLine as boolean) ?? false}
              onChange={(e) => set({ trendLine: e.target.checked })}
              className={checkboxClass}
            />
            Trend Line
          </label>
        </>
      )}

      {/* Candlestick config */}
      {chartType === "candlestick" && (
        <>
          <ColumnSelect
            label="Time Column"
            value={(config.timeColumn as string) ?? ""}
            columns={inputSchema}
            onChange={(v) => set({ timeColumn: v })}
          />
          <ColumnSelect
            label="Open"
            value={(config.openColumn as string) ?? ""}
            columns={inputSchema}
            onChange={(v) => set({ openColumn: v })}
          />
          <ColumnSelect
            label="High"
            value={(config.highColumn as string) ?? ""}
            columns={inputSchema}
            onChange={(v) => set({ highColumn: v })}
          />
          <ColumnSelect
            label="Low"
            value={(config.lowColumn as string) ?? ""}
            columns={inputSchema}
            onChange={(v) => set({ lowColumn: v })}
          />
          <ColumnSelect
            label="Close"
            value={(config.closeColumn as string) ?? ""}
            columns={inputSchema}
            onChange={(v) => set({ closeColumn: v })}
          />
          <ColumnSelect
            label="Volume (optional)"
            value={(config.volumeColumn as string) ?? ""}
            columns={inputSchema}
            onChange={(v) => set({ volumeColumn: v })}
          />
        </>
      )}

      {/* KPI config */}
      {chartType === "kpi" && (
        <>
          <ColumnSelect
            label="Metric Column"
            value={(config.metricColumn as string) ?? ""}
            columns={inputSchema}
            onChange={(v) => set({ metricColumn: v })}
          />
          <div>
            <label className={labelClass}>Aggregation</label>
            <select
              value={(config.aggregation as string) ?? "SUM"}
              onChange={(e) => set({ aggregation: e.target.value })}
              className={selectClass}
            >
              {AGGREGATIONS.map((agg) => (
                <option key={agg} value={agg}>
                  {agg}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className={labelClass}>Comparison Value</label>
            <input
              type="number"
              value={(config.comparisonValue as number) ?? ""}
              onChange={(e) =>
                set({ comparisonValue: e.target.value ? Number(e.target.value) : undefined })
              }
              placeholder="Optional"
              className={selectClass}
            />
          </div>
          <div className="space-y-1">
            <label className={labelClass}>Thresholds</label>
            <div className="grid grid-cols-3 gap-1">
              <input
                type="number"
                placeholder="Red below"
                value={(config.threshold_red as number) ?? ""}
                onChange={(e) =>
                  set({ threshold_red: e.target.value ? Number(e.target.value) : undefined })
                }
                className="bg-canvas-bg border border-red-500/30 rounded px-2 py-1 text-xs text-white"
              />
              <input
                type="number"
                placeholder="Yellow below"
                value={(config.threshold_yellow as number) ?? ""}
                onChange={(e) =>
                  set({ threshold_yellow: e.target.value ? Number(e.target.value) : undefined })
                }
                className="bg-canvas-bg border border-yellow-500/30 rounded px-2 py-1 text-xs text-white"
              />
              <input
                type="number"
                placeholder="Green above"
                value={(config.threshold_green as number) ?? ""}
                onChange={(e) =>
                  set({ threshold_green: e.target.value ? Number(e.target.value) : undefined })
                }
                className="bg-canvas-bg border border-green-500/30 rounded px-2 py-1 text-xs text-white"
              />
            </div>
          </div>
        </>
      )}

      {/* Pivot config */}
      {chartType === "pivot" && (
        <>
          <MultiColumnSelect
            label="Row Dimensions"
            selected={toStringArray(config.rowDimensions)}
            columns={inputSchema}
            onChange={(v) => set({ rowDimensions: v })}
          />
          <MultiColumnSelect
            label="Column Dimensions"
            selected={toStringArray(config.columnDimensions)}
            columns={inputSchema}
            onChange={(v) => set({ columnDimensions: v })}
          />
          <ColumnSelect
            label="Value Column"
            value={(config.valueColumn as string) ?? ""}
            columns={inputSchema}
            onChange={(v) => set({ valueColumn: v })}
          />
          <div>
            <label className={labelClass}>Aggregation</label>
            <select
              value={(config.aggregation as string) ?? "SUM"}
              onChange={(e) => set({ aggregation: e.target.value })}
              className={selectClass}
            >
              {AGGREGATIONS.filter((a) => a !== "LAST").map((agg) => (
                <option key={agg} value={agg}>
                  {agg}
                </option>
              ))}
            </select>
          </div>
        </>
      )}

      {/* Pin to Dashboard */}
      {workflowId && (
        <div className="pt-2 border-t border-canvas-border">
          <button
            onClick={() => setShowPinDialog(true)}
            className="w-full px-3 py-2 text-xs bg-canvas-accent text-white rounded hover:opacity-80"
          >
            Pin to Dashboard
          </button>
        </div>
      )}

      {showPinDialog && workflowId && (
        <PinToDialog
          workflowId={workflowId}
          nodeId={nodeId}
          onClose={() => setShowPinDialog(false)}
          onPin={() => setShowPinDialog(false)}
        />
      )}
    </div>
  );
}
