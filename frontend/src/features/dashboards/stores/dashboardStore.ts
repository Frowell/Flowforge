/**
 * Dashboard Zustand store — UI state only.
 *
 * Layout positions, selected widget, filter values.
 * Widget data and dashboard metadata come from TanStack Query.
 */

import { create } from "zustand";

interface FilterValue {
  column: string;
  type: string;
  value: unknown;
}

interface DashboardState {
  selectedWidgetId: string | null;
  isEditing: boolean;
  activeFilters: FilterValue[];

  selectWidget: (widgetId: string | null) => void;
  setEditing: (editing: boolean) => void;
  setFilter: (filter: FilterValue) => void;
  clearFilters: () => void;
}

export const useDashboardStore = create<DashboardState>((set, get) => ({
  selectedWidgetId: null,
  isEditing: false,
  activeFilters: [],

  selectWidget: (widgetId) => set({ selectedWidgetId: widgetId }),
  setEditing: (editing) => set({ isEditing: editing }),

  setFilter: (filter) => {
    const existing = get().activeFilters.filter((f) => f.column !== filter.column);
    set({ activeFilters: [...existing, filter] });
  },

  clearFilters: () => set({ activeFilters: [] }),
}));
