/**
 * Global dashboard filters — date range, dropdowns that apply to all widgets.
 *
 * Only offers columns present in ALL widget schemas (intersection).
 */

import { useGlobalFilters } from "../hooks/useGlobalFilters";

export default function GlobalFilters() {
  const { activeFilters, clearFilters } = useGlobalFilters();

  return (
    <div className="flex items-center gap-2">
      {activeFilters.length > 0 && (
        <button
          onClick={clearFilters}
          className="text-xs text-white/40 hover:text-white"
        >
          Clear filters
        </button>
      )}
      {/* TODO: Render filter controls based on available columns */}
      <span className="text-xs text-white/30">
        {activeFilters.length > 0 ? `${activeFilters.length} active` : "No filters"}
      </span>
    </div>
  );
}
