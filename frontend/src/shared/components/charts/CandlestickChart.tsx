/**
 * Candlestick chart component — OHLC financial data visualization.
 *
 * Same component everywhere. No per-mode variants.
 */

import { cn } from "@/shared/lib/cn";
import type { BaseChartProps, CandlestickConfig } from "./types";

interface Props extends BaseChartProps {
  config: CandlestickConfig & Record<string, unknown>;
}

export default function CandlestickChart({ data, config, className }: Props) {
  // TODO: Implement with lightweight-charts or custom SVG rendering
  // Recharts doesn't natively support candlestick charts

  return (
    <div className={cn("w-full h-full min-h-[200px] flex items-center justify-center", className)}>
      <div className="text-white/30 text-sm">
        Candlestick chart — {data.length} data points
        <br />
        OHLC: {config.openColumn}/{config.highColumn}/{config.lowColumn}/{config.closeColumn}
      </div>
    </div>
  );
}
