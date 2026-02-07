/**
 * E2E: Create a workflow with DataSource + Filter nodes, connect them, preview data.
 *
 * Uses dev auth mode (VITE_DEV_AUTH=true) — no Keycloak needed.
 */

import { test, expect } from "@playwright/test";

const MOCK_WORKFLOW = {
  id: "wf-e2e-001",
  name: "Untitled Workflow",
  description: null,
  graph_json: { nodes: [], edges: [] },
  created_by: "dev-user-001",
  created_at: "2025-01-01T00:00:00Z",
  updated_at: "2025-01-01T00:00:00Z",
};

const MOCK_PREVIEW = {
  columns: [
    { name: "trade_id", dtype: "String" },
    { name: "symbol", dtype: "String" },
    { name: "price", dtype: "Float64" },
  ],
  rows: [
    { trade_id: "T001", symbol: "AAPL", price: 185.5 },
    { trade_id: "T002", symbol: "GOOG", price: 142.3 },
    { trade_id: "T003", symbol: "MSFT", price: 378.9 },
  ],
  total_rows: 3,
  execution_ms: 42,
  cache_hit: false,
  offset: 0,
  limit: 100,
  chart_config: null,
};

const MOCK_SCHEMA = {
  tables: [
    {
      name: "trades",
      columns: [
        { name: "trade_id", dtype: "String", nullable: false },
        { name: "symbol", dtype: "String", nullable: false },
        { name: "price", dtype: "Float64", nullable: false },
        { name: "quantity", dtype: "Int64", nullable: false },
      ],
    },
  ],
};

test.describe("Workflow Create Flow", () => {
  test.beforeEach(async ({ page }) => {
    // Mock API: create workflow
    await page.route("**/api/v1/workflows", async (route) => {
      if (route.request().method() === "POST") {
        await route.fulfill({ json: MOCK_WORKFLOW });
      } else {
        await route.fulfill({
          json: { items: [], total: 0, page: 1, page_size: 20 },
        });
      }
    });

    // Mock API: get workflow by ID
    await page.route(`**/api/v1/workflows/${MOCK_WORKFLOW.id}`, async (route) => {
      if (route.request().method() === "GET") {
        await route.fulfill({ json: MOCK_WORKFLOW });
      } else {
        await route.fulfill({ json: MOCK_WORKFLOW });
      }
    });

    // Mock API: schema catalog
    await page.route("**/api/v1/schema**", async (route) => {
      await route.fulfill({ json: MOCK_SCHEMA });
    });

    // Mock API: preview
    await page.route("**/api/v1/preview/**", async (route) => {
      await route.fulfill({ json: MOCK_PREVIEW });
    });
  });

  test("can navigate to canvas and see the workflow picker", async ({ page }) => {
    await page.goto("/canvas");
    await expect(page.getByText("New Workflow")).toBeVisible();
  });

  test("can create a new workflow and open the canvas", async ({ page }) => {
    await page.goto("/canvas");

    // Click "New Workflow" button
    await page.getByText("New Workflow").click();

    // Should navigate to the canvas with the workflow
    await page.waitForURL(`**/canvas/${MOCK_WORKFLOW.id}`);

    // Canvas should show the node palette
    await expect(page.getByText("Nodes")).toBeVisible();

    // Node categories should be visible
    await expect(page.getByText("input")).toBeVisible();
    await expect(page.getByText("transform")).toBeVisible();
    await expect(page.getByText("output")).toBeVisible();
  });

  test("can see node types in the palette", async ({ page }) => {
    await page.goto(`/canvas/${MOCK_WORKFLOW.id}`);

    // Wait for canvas to load
    await expect(page.getByText("Nodes")).toBeVisible();

    // Check key node types are listed
    await expect(page.getByText("Data Source")).toBeVisible();
    await expect(page.getByText("Filter")).toBeVisible();
    await expect(page.getByText("Select")).toBeVisible();
    await expect(page.getByText("Sort")).toBeVisible();
    await expect(page.getByText("Table View")).toBeVisible();
    await expect(page.getByText("Chart")).toBeVisible();
  });

  test("can drag a node from the palette onto the canvas", async ({ page }) => {
    await page.goto(`/canvas/${MOCK_WORKFLOW.id}`);
    await expect(page.getByText("Nodes")).toBeVisible();

    // Find the Data Source node in the palette
    const dataSourceNode = page.locator("div[draggable='true']").filter({ hasText: "Data Source" });
    await expect(dataSourceNode).toBeVisible();

    // Get the canvas area (the ReactFlow container)
    const canvas = page.locator(".react-flow");
    await expect(canvas).toBeVisible();

    // Drag the node onto the canvas
    const canvasBox = await canvas.boundingBox();
    expect(canvasBox).toBeTruthy();

    await dataSourceNode.dragTo(canvas, {
      targetPosition: { x: canvasBox!.width / 2, y: canvasBox!.height / 2 },
    });

    // A node should appear on the canvas (React Flow renders it as a node element)
    await expect(page.locator(".react-flow__node")).toBeVisible({ timeout: 5000 });
  });

  test("save button is visible and clickable", async ({ page }) => {
    await page.goto(`/canvas/${MOCK_WORKFLOW.id}`);

    const saveButton = page.getByRole("button", { name: "Save" });
    await expect(saveButton).toBeVisible();
    await expect(saveButton).toBeEnabled();
  });

  test("navbar shows Canvas and Dashboards links", async ({ page }) => {
    await page.goto(`/canvas/${MOCK_WORKFLOW.id}`);

    await expect(page.getByRole("link", { name: "Canvas" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Dashboards" })).toBeVisible();
    await expect(page.getByRole("link", { name: "FlowForge" })).toBeVisible();
  });
});
