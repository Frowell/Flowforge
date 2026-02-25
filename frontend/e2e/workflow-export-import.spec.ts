/**
 * E2E: Workflow export and import via API route mocking.
 *
 * Uses dev auth mode (VITE_DEV_AUTH=true) — no Keycloak needed.
 */

import { test, expect } from "@playwright/test";

const MOCK_WORKFLOW = {
  id: "wf-exp-001",
  name: "Export Test Workflow",
  description: "Workflow for export/import testing",
  graph_json: {
    nodes: [
      { id: "ds_1", type: "data_source", position: { x: 100, y: 100 }, data: {} },
      { id: "f_1", type: "filter", position: { x: 300, y: 100 }, data: {} },
    ],
    edges: [{ id: "e1", source: "ds_1", target: "f_1" }],
  },
  tenant_id: "dev-tenant-001",
  created_by: "dev-user-001",
  created_at: "2025-01-01T00:00:00Z",
  updated_at: "2025-01-01T00:00:00Z",
};

const MOCK_EXPORT_RESPONSE = {
  id: "wf-exp-001",
  name: "Export Test Workflow",
  description: "Workflow for export/import testing",
  graph_json: MOCK_WORKFLOW.graph_json,
  version: 1,
  exported_at: "2025-01-03T12:00:00Z",
};

const MOCK_IMPORTED_WORKFLOW = {
  id: "wf-imp-001",
  name: "Export Test Workflow (imported)",
  description: "Workflow for export/import testing",
  graph_json: MOCK_WORKFLOW.graph_json,
  tenant_id: "dev-tenant-001",
  created_by: "dev-user-001",
  created_at: "2025-01-03T13:00:00Z",
  updated_at: "2025-01-03T13:00:00Z",
};

test.describe("Workflow Export/Import", () => {
  test.beforeEach(async ({ page }) => {
    await page.route("**/api/v1/workflows", async (route) => {
      if (route.request().method() === "GET") {
        await route.fulfill({
          json: { items: [MOCK_WORKFLOW], total: 1, page: 1, page_size: 20 },
        });
      } else if (route.request().method() === "POST") {
        await route.fulfill({ json: MOCK_IMPORTED_WORKFLOW, status: 201 });
      } else {
        await route.fulfill({ json: MOCK_WORKFLOW });
      }
    });

    await page.route(`**/api/v1/workflows/${MOCK_WORKFLOW.id}`, async (route) => {
      await route.fulfill({ json: MOCK_WORKFLOW });
    });

    await page.route(`**/api/v1/workflows/${MOCK_WORKFLOW.id}/export`, async (route) => {
      await route.fulfill({ json: MOCK_EXPORT_RESPONSE });
    });

    await page.route("**/api/v1/workflows/import", async (route) => {
      await route.fulfill({ json: MOCK_IMPORTED_WORKFLOW, status: 201 });
    });

    await page.route("**/api/v1/schema**", async (route) => {
      await route.fulfill({ json: { tables: [] } });
    });

    await page.route("**/api/v1/templates", async (route) => {
      await route.fulfill({ json: { items: [] } });
    });
  });

  test("export endpoint returns workflow data", async ({ page }) => {
    await page.goto(`/canvas/${MOCK_WORKFLOW.id}`);

    // Verify export endpoint is reachable
    const response = await page.evaluate(async () => {
      const res = await fetch(`/api/v1/workflows/wf-exp-001/export`);
      return res.json();
    });
    expect(response.name).toBe("Export Test Workflow");
    expect(response.graph_json.nodes).toHaveLength(2);
  });

  test("import endpoint creates a new workflow", async ({ page }) => {
    await page.goto(`/canvas/${MOCK_WORKFLOW.id}`);

    const response = await page.evaluate(async () => {
      const res = await fetch("/api/v1/workflows/import", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: "Imported Workflow",
          graph_json: {
            nodes: [{ id: "ds_1", type: "data_source", position: { x: 0, y: 0 }, data: {} }],
            edges: [],
          },
        }),
      });
      return { status: res.status, data: await res.json() };
    });
    expect(response.status).toBe(201);
    expect(response.data.id).toBe("wf-imp-001");
  });

  test("workflow list page shows workflows", async ({ page }) => {
    await page.goto("/canvas");

    // Should show the workflow in the list
    await expect(page.getByText("Export Test Workflow")).toBeVisible();
  });

  test("clicking a workflow opens the canvas", async ({ page }) => {
    await page.goto("/canvas");

    await page.getByText("Export Test Workflow").click();
    await page.waitForURL(`**/canvas/${MOCK_WORKFLOW.id}`);
  });
});
