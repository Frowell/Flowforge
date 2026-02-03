/**
 * Template hooks — list and instantiate workflow templates via TanStack Query.
 */

import { useQuery, useMutation } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { apiClient } from "@/shared/query-engine/client";

export interface TemplateResponse {
  id: string;
  name: string;
  description: string;
  category: string;
  tags: string[];
  graph_json: Record<string, unknown>;
  thumbnail: string | null;
}

interface TemplateListResponse {
  items: TemplateResponse[];
}

interface WorkflowResponse {
  id: string;
  name: string;
}

const TEMPLATES_KEY = ["templates"] as const;

export function useTemplates() {
  return useQuery({
    queryKey: [...TEMPLATES_KEY],
    queryFn: () => apiClient.get<TemplateListResponse>("/templates"),
  });
}

export function useInstantiateTemplate() {
  const navigate = useNavigate();

  return useMutation({
    mutationFn: ({ templateId, name }: { templateId: string; name?: string }) =>
      apiClient.post<WorkflowResponse>(`/templates/${templateId}/instantiate`, {
        name: name ?? null,
      }),
    onSuccess: (data) => {
      navigate(`/canvas/${data.id}`);
    },
  });
}
