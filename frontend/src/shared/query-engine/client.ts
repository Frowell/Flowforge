/**
 * Single HTTP fetch wrapper with Keycloak Bearer token injection.
 *
 * All API calls flow through this client. Components never call
 * fetch() directly — they use TanStack Query hooks that use this client.
 */

import { getAccessToken } from "@/shared/auth/keycloak";

const BASE_URL = "";

class APIClient {
  private baseUrl: string;

  constructor(baseUrl: string = BASE_URL) {
    this.baseUrl = baseUrl;
  }

  async get<T>(path: string, params?: Record<string, string>): Promise<T> {
    const url = new URL(`${this.baseUrl}${path}`, window.location.origin);
    if (params) {
      for (const [key, value] of Object.entries(params)) {
        url.searchParams.set(key, value);
      }
    }
    return this.request<T>(url.toString(), { method: "GET" });
  }

  async post<T>(path: string, body?: unknown, signal?: AbortSignal): Promise<T> {
    return this.request<T>(`${this.baseUrl}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: body ? JSON.stringify(body) : undefined,
      signal,
    });
  }

  async patch<T>(path: string, body: unknown): Promise<T> {
    return this.request<T>(`${this.baseUrl}${path}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  }

  async delete(path: string): Promise<void> {
    await this.request<void>(`${this.baseUrl}${path}`, { method: "DELETE" });
  }

  private async request<T>(url: string, init: RequestInit): Promise<T> {
    const headers = new Headers(init.headers);

    // Inject Keycloak Bearer token for authenticated requests
    const token = await getAccessToken();
    if (token) {
      headers.set("Authorization", `Bearer ${token}`);
    }

    const response = await fetch(url, {
      ...init,
      headers,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: response.statusText }));
      throw new APIError(response.status, error.detail ?? "Request failed");
    }

    if (response.status === 204) return undefined as T;
    return response.json() as Promise<T>;
  }
}

export class APIError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "APIError";
  }
}

export const apiClient = new APIClient();
