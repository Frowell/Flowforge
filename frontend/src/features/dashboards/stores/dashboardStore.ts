/**
 * Dashboard Zustand store — UI state only.
 *
 * Layout positions, selected widget, filter values, drill-down state.
 * Widget data and dashboard metadata come from TanStack Query.
 */

import { create } from "zustand";

interface FilterValue {
  column: string;
  type: string;
  value: unknown;
}

export interface DrillDownFilter {
  widgetId: string;
  column: string;
  value: unknown;
}

interface DashboardState {
  selectedWidgetId: string | null;
  isEditing: boolean;
  activeFilters: FilterValue[];
  drillDownFilters: DrillDownFilter[];

  selectWidget: (widgetId: string | null) => void;
  setEditing: (editing: boolean) => void;
  setFilter: (filter: FilterValue) => void;
  clearFilters: () => void;
  addDrillDownFilter: (filter: DrillDownFilter) => void;
  removeDrillDownFilter: (widgetId: string, column: string) => void;
  clearDrillDownFilters: () => void;
}

export const useDashboardStore = create<DashboardState>((set, get) => ({
  selectedWidgetId: null,
  isEditing: false,
  activeFilters: [],
  drillDownFilters: [],

  selectWidget: (widgetId) => set({ selectedWidgetId: widgetId }),
  setEditing: (editing) => set({ isEditing: editing }),

  setFilter: (filter) => {
    const existing = get().activeFilters.filter((f) => f.column !== filter.column);
    set({ activeFilters: [...existing, filter] });
  },

  clearFilters: () => set({ activeFilters: [] }),

  addDrillDownFilter: (filter) => {
    const existing = get().drillDownFilters.filter(
      (f) => !(f.widgetId === filter.widgetId && f.column === filter.column),
    );
    set({ drillDownFilters: [...existing, filter] });
  },

  removeDrillDownFilter: (widgetId, column) => {
    set({
      drillDownFilters: get().drillDownFilters.filter(
        (f) => !(f.widgetId === widgetId && f.column === column),
      ),
    });
  },

  clearDrillDownFilters: () => set({ drillDownFilters: [] }),
}));
