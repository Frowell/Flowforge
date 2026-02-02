/**
 * Global dashboard filters — date range, dropdowns that apply to all widgets.
 *
 * Only offers columns present in ALL widget schemas (intersection).
 */

import { useState } from "react";
import { useGlobalFilters } from "../hooks/useGlobalFilters";

interface AddFilterForm {
  column: string;
  type: "date_range" | "text";
}

export default function GlobalFilters() {
  const { activeFilters, setFilter, clearFilters } = useGlobalFilters();
  const [showPopover, setShowPopover] = useState(false);
  const [newFilter, setNewFilter] = useState<AddFilterForm>({ column: "", type: "date_range" });

  const handleAddFilter = () => {
    if (!newFilter.column) return;

    if (newFilter.type === "date_range") {
      setFilter({ column: newFilter.column, type: "date_range", value: { from: "", to: "" } });
    } else {
      setFilter({ column: newFilter.column, type: "text", value: "" });
    }
    setNewFilter({ column: "", type: "date_range" });
    setShowPopover(false);
  };

  const removeFilter = (column: string) => {
    // Remove by replacing the entire filter list without the target column
    const remaining = activeFilters.filter((f) => f.column !== column);
    clearFilters();
    for (const f of remaining) {
      setFilter(f);
    }
  };

  const updateFilterValue = (column: string, value: unknown) => {
    const existing = activeFilters.find((f) => f.column === column);
    if (existing) {
      setFilter({ ...existing, value });
    }
  };

  return (
    <div className="flex items-center gap-2">
      {/* Active filter chips */}
      {activeFilters.map((filter) => (
        <div key={filter.column} className="flex items-center gap-1 bg-canvas-bg border border-white/10 rounded px-2 py-0.5">
          <span className="text-xs text-white/60">{filter.column}:</span>
          {filter.type === "date_range" && (
            <div className="flex items-center gap-1">
              <input
                type="date"
                value={(filter.value as { from: string; to: string })?.from ?? ""}
                onChange={(e) =>
                  updateFilterValue(filter.column, {
                    ...(filter.value as object),
                    from: e.target.value,
                  })
                }
                className="bg-transparent border-none text-xs text-white w-28 outline-none"
              />
              <span className="text-white/30 text-xs">to</span>
              <input
                type="date"
                value={(filter.value as { from: string; to: string })?.to ?? ""}
                onChange={(e) =>
                  updateFilterValue(filter.column, {
                    ...(filter.value as object),
                    to: e.target.value,
                  })
                }
                className="bg-transparent border-none text-xs text-white w-28 outline-none"
              />
            </div>
          )}
          {filter.type === "text" && (
            <input
              type="text"
              value={(filter.value as string) ?? ""}
              onChange={(e) => updateFilterValue(filter.column, e.target.value)}
              placeholder="value..."
              className="bg-transparent border-none text-xs text-white w-20 outline-none"
            />
          )}
          <button
            onClick={() => removeFilter(filter.column)}
            className="text-white/30 hover:text-white text-xs ml-1"
          >
            &times;
          </button>
        </div>
      ))}

      {/* Add filter button + popover */}
      <div className="relative">
        <button
          onClick={() => setShowPopover(!showPopover)}
          className="text-xs text-white/40 hover:text-white border border-white/10 rounded px-2 py-0.5"
        >
          + Filter
        </button>

        {showPopover && (
          <div className="absolute right-0 top-8 bg-canvas-node border border-canvas-border rounded-lg p-3 w-56 z-50 shadow-lg">
            <div className="space-y-2">
              <div>
                <label className="text-xs text-white/50 block mb-1">Column</label>
                <input
                  type="text"
                  value={newFilter.column}
                  onChange={(e) => setNewFilter({ ...newFilter, column: e.target.value })}
                  placeholder="Column name"
                  className="w-full bg-canvas-bg border border-white/10 rounded px-2 py-1 text-xs text-white"
                />
              </div>
              <div>
                <label className="text-xs text-white/50 block mb-1">Type</label>
                <select
                  value={newFilter.type}
                  onChange={(e) => setNewFilter({ ...newFilter, type: e.target.value as "date_range" | "text" })}
                  className="w-full bg-canvas-bg border border-white/10 rounded px-2 py-1 text-xs text-white"
                >
                  <option value="date_range">Date Range</option>
                  <option value="text">Text</option>
                </select>
              </div>
              <button
                onClick={handleAddFilter}
                disabled={!newFilter.column}
                className="w-full px-2 py-1 text-xs bg-canvas-accent text-white rounded hover:opacity-80 disabled:opacity-40"
              >
                Add Filter
              </button>
            </div>
          </div>
        )}
      </div>

      {activeFilters.length > 0 && (
        <button
          onClick={clearFilters}
          className="text-xs text-white/40 hover:text-white"
        >
          Clear all
        </button>
      )}
    </div>
  );
}
