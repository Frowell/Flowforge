/**
 * E2E: Browse template picker, select a template, verify workflow creation.
 *
 * Uses dev auth mode (VITE_DEV_AUTH=true) — no Keycloak needed.
 */

import { test, expect } from "@playwright/test";

const MOCK_TEMPLATES = {
  items: [
    {
      id: "tpl-vwap",
      name: "VWAP Analysis",
      description: "Volume-weighted average price with rolling windows",
      category: "Trading",
      tags: ["vwap", "analytics"],
      graph_json: {
        nodes: [{ id: "ds_1", type: "data_source", position: { x: 0, y: 0 }, data: {} }],
        edges: [],
      },
      thumbnail: null,
    },
    {
      id: "tpl-pnl",
      name: "Daily P&L Report",
      description: "Profit and loss dashboard with daily rollups",
      category: "Risk",
      tags: ["pnl", "risk"],
      graph_json: { nodes: [], edges: [] },
      thumbnail: null,
    },
  ],
};

const MOCK_CREATED_WORKFLOW = {
  id: "wf-from-template-001",
  name: "VWAP Analysis",
  description: "Volume-weighted average price with rolling windows",
  graph_json: MOCK_TEMPLATES.items[0].graph_json,
  tenant_id: "dev-tenant-001",
  created_by: "dev-user-001",
  created_at: "2025-01-01T00:00:00Z",
  updated_at: "2025-01-01T00:00:00Z",
};

test.describe("Template Instantiation Flow", () => {
  test.beforeEach(async ({ page }) => {
    // Mock templates list
    await page.route("**/api/v1/templates", async (route) => {
      await route.fulfill({ json: MOCK_TEMPLATES });
    });

    // Mock template instantiation
    await page.route("**/api/v1/templates/*/instantiate", async (route) => {
      await route.fulfill({ json: MOCK_CREATED_WORKFLOW, status: 201 });
    });

    // Mock workflow endpoints for post-creation
    await page.route("**/api/v1/workflows", async (route) => {
      if (route.request().method() === "GET") {
        await route.fulfill({
          json: { items: [], total: 0, page: 1, page_size: 20 },
        });
      } else {
        await route.fulfill({ json: MOCK_CREATED_WORKFLOW, status: 201 });
      }
    });

    await page.route(`**/api/v1/workflows/${MOCK_CREATED_WORKFLOW.id}`, async (route) => {
      await route.fulfill({ json: MOCK_CREATED_WORKFLOW });
    });

    await page.route("**/api/v1/schema**", async (route) => {
      await route.fulfill({ json: { tables: [] } });
    });
  });

  test("template picker shows available templates", async ({ page }) => {
    await page.goto("/canvas");
    await page.getByText("New Workflow").click();

    // Template picker should show templates
    await expect(page.getByText("VWAP Analysis")).toBeVisible();
    await expect(page.getByText("Daily P&L Report")).toBeVisible();
  });

  test("template picker shows Start from blank option", async ({ page }) => {
    await page.goto("/canvas");
    await page.getByText("New Workflow").click();

    await expect(page.getByText("Start from blank")).toBeVisible();
  });

  test("template shows category badge and tags", async ({ page }) => {
    await page.goto("/canvas");
    await page.getByText("New Workflow").click();

    // Category badges
    await expect(page.getByText("Trading")).toBeVisible();
    await expect(page.getByText("Risk")).toBeVisible();

    // Tags
    await expect(page.getByText("vwap")).toBeVisible();
  });

  test("selecting a template creates a workflow", async ({ page }) => {
    await page.goto("/canvas");
    await page.getByText("New Workflow").click();

    // Click the VWAP Analysis template
    await page.getByText("VWAP Analysis").first().click();

    // Should navigate to the new canvas
    await page.waitForURL(`**/canvas/${MOCK_CREATED_WORKFLOW.id}`);
  });
});
