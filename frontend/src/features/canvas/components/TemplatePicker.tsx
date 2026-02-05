/**
 * Template picker modal — shown when creating a new workflow.
 *
 * Offers "Start from blank" plus a grid of pre-defined templates.
 */

import { cn } from "@/shared/lib/cn";
import { useTemplates, useInstantiateTemplate } from "../hooks/useTemplates";
import type { TemplateResponse } from "../hooks/useTemplates";

interface TemplatePickerProps {
  open: boolean;
  onClose: () => void;
  onBlank: () => void;
}

const CATEGORY_COLORS: Record<string, string> = {
  Trading: "bg-blue-500/20 text-blue-300",
  Analytics: "bg-purple-500/20 text-purple-300",
  Risk: "bg-amber-500/20 text-amber-300",
};

export default function TemplatePicker({ open, onClose, onBlank }: TemplatePickerProps) {
  const { data, isLoading } = useTemplates();
  const instantiate = useInstantiateTemplate();

  if (!open) return null;

  const templates = data?.items ?? [];

  const handleSelect = (template: TemplateResponse) => {
    instantiate.mutate({ templateId: template.id });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <div className="bg-canvas-node border border-canvas-border rounded-xl shadow-2xl w-full max-w-3xl max-h-[80vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-canvas-border">
          <div>
            <h2 className="text-lg font-semibold text-white">New Workflow</h2>
            <p className="text-xs text-white/50 mt-0.5">
              Start from a template or create a blank canvas
            </p>
          </div>
          <button onClick={onClose} className="text-white/40 hover:text-white text-xl leading-none">
            &times;
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {/* Blank option */}
          <button
            onClick={onBlank}
            className="w-full mb-4 p-4 rounded-lg border-2 border-dashed border-white/10 hover:border-white/30 text-left transition-colors"
          >
            <span className="text-sm font-medium text-white">Start from blank</span>
            <span className="block text-xs text-white/40 mt-1">
              Empty canvas — add nodes manually
            </span>
          </button>

          {/* Template grid */}
          {isLoading && (
            <div className="text-white/30 text-sm text-center py-8">Loading templates...</div>
          )}

          <div className="grid grid-cols-2 gap-3">
            {templates.map((t) => (
              <button
                key={t.id}
                onClick={() => handleSelect(t)}
                disabled={instantiate.isPending}
                className={cn(
                  "p-4 rounded-lg border border-canvas-border text-left transition-colors",
                  "hover:border-white/30 hover:bg-white/5",
                  "disabled:opacity-50 disabled:cursor-not-allowed",
                )}
              >
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-sm font-medium text-white">{t.name}</span>
                  <span
                    className={cn(
                      "text-[10px] px-1.5 py-0.5 rounded-full uppercase tracking-wider",
                      CATEGORY_COLORS[t.category] ?? "bg-gray-500/20 text-gray-300",
                    )}
                  >
                    {t.category}
                  </span>
                </div>
                <p className="text-xs text-white/50 line-clamp-2">{t.description}</p>
                <div className="flex gap-1 mt-2 flex-wrap">
                  {t.tags.slice(0, 3).map((tag) => (
                    <span
                      key={tag}
                      className="text-[10px] px-1.5 py-0.5 rounded bg-white/5 text-white/30"
                    >
                      {tag}
                    </span>
                  ))}
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* Footer */}
        {instantiate.isPending && (
          <div className="px-6 py-3 border-t border-canvas-border text-xs text-white/40">
            Creating workflow from template...
          </div>
        )}
      </div>
    </div>
  );
}
