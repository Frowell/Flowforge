/**
 * Widget settings dropdown — configure auto-refresh interval.
 *
 * Values: null=Manual, 5000=5s, 30000=30s, 60000=1m, 300000=5m, -1=Live
 */

import { useState } from "react";
import { apiClient } from "@/shared/query-engine/client";
import { useQueryClient } from "@tanstack/react-query";

interface WidgetSettingsMenuProps {
  widgetId: string;
  currentInterval: number | null;
}

const REFRESH_OPTIONS = [
  { label: "Manual", value: null },
  { label: "5s", value: 5000 },
  { label: "30s", value: 30000 },
  { label: "1m", value: 60000 },
  { label: "5m", value: 300000 },
  { label: "Live", value: -1 },
] as const;

export default function WidgetSettingsMenu({
  widgetId,
  currentInterval,
}: WidgetSettingsMenuProps) {
  const [isOpen, setIsOpen] = useState(false);
  const queryClient = useQueryClient();

  const handleSelect = async (value: number | null) => {
    setIsOpen(false);
    await apiClient.patch(`/api/v1/widgets/${widgetId}`, {
      auto_refresh_interval: value,
    });
    queryClient.invalidateQueries({ queryKey: ["dashboardWidgets"] });
  };

  const currentLabel =
    REFRESH_OPTIONS.find((o) => o.value === currentInterval)?.label ?? "Manual";

  return (
    <div className="relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="text-white/30 hover:text-white text-[10px] px-1"
      >
        {currentLabel}
      </button>
      {isOpen && (
        <>
          <div className="fixed inset-0 z-10" onClick={() => setIsOpen(false)} />
          <div className="absolute right-0 top-full mt-1 z-20 bg-canvas-node border border-canvas-border rounded shadow-lg py-1 min-w-[100px]">
            {REFRESH_OPTIONS.map((option) => (
              <button
                key={String(option.value)}
                onClick={() => handleSelect(option.value)}
                className={`block w-full text-left px-3 py-1.5 text-xs hover:bg-white/10 transition-colors ${
                  option.value === currentInterval
                    ? "text-canvas-accent"
                    : "text-white/60"
                }`}
              >
                {option.label}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
