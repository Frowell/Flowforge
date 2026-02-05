/**
 * Candlestick chart component — OHLC financial data visualization.
 *
 * Custom SVG rendering with responsive container.
 * Same component everywhere. No per-mode variants.
 */

import { useRef, useState, useEffect, useCallback, useMemo } from "react";
import { cn } from "@/shared/lib/cn";
import type { BaseChartProps, CandlestickConfig } from "./types";

interface Props extends BaseChartProps {
  config: CandlestickConfig & Record<string, unknown>;
}

interface CandleData {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
  bullish: boolean;
}

const PADDING = { top: 20, right: 60, bottom: 40, left: 10 };
const BULLISH_COLOR = "#22c55e";
const BEARISH_COLOR = "#ef4444";

export default function CandlestickChart({ data, config, interactive = true, className }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState({ width: 0, height: 0 });
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);

  const { timeColumn, openColumn, highColumn, lowColumn, closeColumn, volumeColumn } = config;

  useEffect(() => {
    if (!containerRef.current) return;
    const observer = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (entry) {
        setDimensions({
          width: entry.contentRect.width,
          height: entry.contentRect.height,
        });
      }
    });
    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, []);

  const candles: CandleData[] = useMemo(
    () =>
      data.reduce<CandleData[]>((acc, row) => {
        const open = Number(row[openColumn]);
        const high = Number(row[highColumn]);
        const low = Number(row[lowColumn]);
        const close = Number(row[closeColumn]);
        if (isNaN(open) || isNaN(high) || isNaN(low) || isNaN(close)) return acc;
        acc.push({
          time: String(row[timeColumn] ?? ""),
          open,
          high,
          low,
          close,
          volume: volumeColumn ? Number(row[volumeColumn]) || 0 : undefined,
          bullish: close >= open,
        });
        return acc;
      }, []),
    [data, timeColumn, openColumn, highColumn, lowColumn, closeColumn, volumeColumn],
  );

  const handleMouseMove = useCallback(
    (e: React.MouseEvent<SVGSVGElement>) => {
      if (!interactive || candles.length === 0) return;
      const rect = e.currentTarget.getBoundingClientRect();
      const x = e.clientX - rect.left - PADDING.left;
      const chartWidth = dimensions.width - PADDING.left - PADDING.right;
      const candleWidth = chartWidth / candles.length;
      const index = Math.floor(x / candleWidth);
      setHoveredIndex(index >= 0 && index < candles.length ? index : null);
    },
    [interactive, candles.length, dimensions.width],
  );

  if (candles.length === 0 || dimensions.width === 0 || dimensions.height === 0) {
    return (
      <div ref={containerRef} className={cn("w-full h-full min-h-[200px]", className)}>
        {candles.length === 0 && dimensions.width > 0 && (
          <div className="flex items-center justify-center h-full text-white/30 text-sm">
            No valid OHLC data
          </div>
        )}
      </div>
    );
  }

  const chartWidth = dimensions.width - PADDING.left - PADDING.right;
  const hasVolume = volumeColumn && candles.some((c) => c.volume !== undefined);
  const priceHeight = hasVolume
    ? (dimensions.height - PADDING.top - PADDING.bottom) * 0.75
    : dimensions.height - PADDING.top - PADDING.bottom;
  const volumeHeight = hasVolume ? (dimensions.height - PADDING.top - PADDING.bottom) * 0.2 : 0;
  const volumeTop =
    PADDING.top + priceHeight + (dimensions.height - PADDING.top - PADDING.bottom) * 0.05;

  const priceMin = Math.min(...candles.map((c) => c.low));
  const priceMax = Math.max(...candles.map((c) => c.high));
  const priceRange = priceMax - priceMin || 1;

  const volumeMax = hasVolume ? Math.max(...candles.map((c) => c.volume ?? 0)) || 1 : 1;

  const candleWidth = chartWidth / candles.length;
  const bodyWidth = Math.max(1, candleWidth * 0.7);

  const scaleY = (price: number) =>
    PADDING.top + priceHeight - ((price - priceMin) / priceRange) * priceHeight;

  const scaleVolumeY = (vol: number) => volumeTop + volumeHeight - (vol / volumeMax) * volumeHeight;

  // Y-axis ticks
  const tickCount = 5;
  const ticks = Array.from(
    { length: tickCount },
    (_, i) => priceMin + (priceRange * i) / (tickCount - 1),
  );

  // X-axis labels — show ~6 evenly spaced
  const labelCount = Math.min(6, candles.length);
  const labelStep = Math.max(1, Math.floor(candles.length / labelCount));

  const hovered = hoveredIndex !== null ? candles[hoveredIndex] : null;

  return (
    <div ref={containerRef} className={cn("w-full h-full min-h-[200px] relative", className)}>
      <svg
        width={dimensions.width}
        height={dimensions.height}
        onMouseMove={handleMouseMove}
        onMouseLeave={() => setHoveredIndex(null)}
      >
        {/* Y-axis labels + grid lines */}
        {ticks.map((tick) => (
          <g key={tick}>
            <line
              x1={PADDING.left}
              x2={dimensions.width - PADDING.right}
              y1={scaleY(tick)}
              y2={scaleY(tick)}
              stroke="rgba(255,255,255,0.06)"
            />
            <text
              x={dimensions.width - PADDING.right + 5}
              y={scaleY(tick) + 4}
              fill="rgba(255,255,255,0.4)"
              fontSize={10}
            >
              {tick.toFixed(2)}
            </text>
          </g>
        ))}

        {/* X-axis labels */}
        {candles.map((candle, i) =>
          i % labelStep === 0 ? (
            <text
              key={i}
              x={PADDING.left + i * candleWidth + candleWidth / 2}
              y={dimensions.height - 8}
              fill="rgba(255,255,255,0.4)"
              fontSize={10}
              textAnchor="middle"
            >
              {candle.time.length > 10 ? candle.time.slice(0, 10) : candle.time}
            </text>
          ) : null,
        )}

        {/* Volume bars */}
        {hasVolume &&
          candles.map((candle, i) => (
            <rect
              key={`vol-${i}`}
              x={PADDING.left + i * candleWidth + (candleWidth - bodyWidth) / 2}
              y={scaleVolumeY(candle.volume ?? 0)}
              width={bodyWidth}
              height={volumeTop + volumeHeight - scaleVolumeY(candle.volume ?? 0)}
              fill={candle.bullish ? BULLISH_COLOR : BEARISH_COLOR}
              opacity={0.25}
            />
          ))}

        {/* Candles */}
        {candles.map((candle, i) => {
          const cx = PADDING.left + i * candleWidth + candleWidth / 2;
          const bodyTop = scaleY(Math.max(candle.open, candle.close));
          const bodyBottom = scaleY(Math.min(candle.open, candle.close));
          const bodyH = Math.max(1, bodyBottom - bodyTop);
          const color = candle.bullish ? BULLISH_COLOR : BEARISH_COLOR;

          return (
            <g key={i}>
              {/* Wick */}
              <line
                x1={cx}
                x2={cx}
                y1={scaleY(candle.high)}
                y2={scaleY(candle.low)}
                stroke={color}
                strokeWidth={1}
              />
              {/* Body */}
              <rect
                x={cx - bodyWidth / 2}
                y={bodyTop}
                width={bodyWidth}
                height={bodyH}
                fill={color}
              />
            </g>
          );
        })}

        {/* Hover crosshair */}
        {hoveredIndex !== null && (
          <line
            x1={PADDING.left + hoveredIndex * candleWidth + candleWidth / 2}
            x2={PADDING.left + hoveredIndex * candleWidth + candleWidth / 2}
            y1={PADDING.top}
            y2={PADDING.top + priceHeight}
            stroke="rgba(255,255,255,0.3)"
            strokeDasharray="4 2"
          />
        )}
      </svg>

      {/* Tooltip */}
      {interactive && hovered && (
        <div className="absolute top-2 left-2 bg-[#0f3460] border border-white/20 rounded px-2 py-1 text-xs text-white pointer-events-none">
          <div className="text-white/60">{hovered.time}</div>
          <div>
            O: {hovered.open.toFixed(2)} H: {hovered.high.toFixed(2)}
          </div>
          <div>
            L: {hovered.low.toFixed(2)} C: {hovered.close.toFixed(2)}
          </div>
          {hovered.volume !== undefined && <div>Vol: {hovered.volume.toLocaleString()}</div>}
        </div>
      )}
    </div>
  );
}
