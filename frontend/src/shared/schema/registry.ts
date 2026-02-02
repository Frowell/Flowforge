/**
 * Schema registry — wraps TanStack Query for catalog caching.
 *
 * Fetches from /api/v1/schema and caches via React Query.
 * Never stores schemas in Zustand.
 */

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/shared/query-engine/client";
import type { CatalogResponse, TableSchema } from "./types";

const CATALOG_KEY = ["schema", "catalog"] as const;

export function useCatalog() {
  return useQuery({
    queryKey: CATALOG_KEY,
    queryFn: async (): Promise<CatalogResponse> => {
      return apiClient.get<CatalogResponse>("/api/v1/schema");
    },
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

export function useTableSchema(tableName: string) {
  const { data: catalog } = useCatalog();
  return catalog?.tables.find((t: TableSchema) => t.name === tableName);
}

export function useRefreshCatalog() {
  const queryClient = useQueryClient();
  return async () => {
    await apiClient.post("/api/v1/schema/refresh");
    await queryClient.invalidateQueries({ queryKey: CATALOG_KEY });
  };
}
