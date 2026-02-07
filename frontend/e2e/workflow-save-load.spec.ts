/**
 * E2E: Save a workflow, navigate away, reload, verify state restores.
 *
 * Uses dev auth mode (VITE_DEV_AUTH=true) — no Keycloak needed.
 */

import { test, expect } from "@playwright/test";

const MOCK_WORKFLOW = {
  id: "wf-e2e-save-001",
  name: "My Test Workflow",
  description: "E2E test workflow",
  graph_json: {
    nodes: [
      {
        id: "data_source_abc123",
        type: "data_source",
        position: { x: 100, y: 200 },
        data: {
          label: "data source",
          nodeType: "data_source",
          config: { table: "trades" },
        },
      },
      {
        id: "filter_def456",
        type: "filter",
        position: { x: 400, y: 200 },
        data: {
          label: "filter",
          nodeType: "filter",
          config: { column: "symbol", operator: "=", value: "AAPL" },
        },
      },
    ],
    edges: [
      {
        id: "edge-ds-filter",
        source: "data_source_abc123",
        target: "filter_def456",
      },
    ],
  },
  created_by: "dev-user-001",
  created_at: "2025-01-01T00:00:00Z",
  updated_at: "2025-01-01T00:00:00Z",
};

const MOCK_WORKFLOW_LIST = {
  items: [MOCK_WORKFLOW],
  total: 1,
  page: 1,
  page_size: 20,
};

const MOCK_SCHEMA = {
  tables: [
    {
      name: "trades",
      columns: [
        { name: "trade_id", dtype: "String", nullable: false },
        { name: "symbol", dtype: "String", nullable: false },
        { name: "price", dtype: "Float64", nullable: false },
      ],
    },
  ],
};

test.describe("Workflow Save & Load Flow", () => {
  test.beforeEach(async ({ page }) => {
    let savedWorkflow = { ...MOCK_WORKFLOW };

    // Mock API: workflow list
    await page.route("**/api/v1/workflows", async (route) => {
      if (route.request().method() === "GET") {
        await route.fulfill({ json: MOCK_WORKFLOW_LIST });
      } else if (route.request().method() === "POST") {
        await route.fulfill({ json: savedWorkflow });
      } else {
        await route.fulfill({ json: savedWorkflow });
      }
    });

    // Mock API: get/save specific workflow
    await page.route(`**/api/v1/workflows/${MOCK_WORKFLOW.id}`, async (route) => {
      if (route.request().method() === "PUT" || route.request().method() === "PATCH") {
        const body = route.request().postDataJSON();
        savedWorkflow = { ...savedWorkflow, ...body, updated_at: new Date().toISOString() };
        await route.fulfill({ json: savedWorkflow });
      } else {
        await route.fulfill({ json: savedWorkflow });
      }
    });

    // Mock API: schema
    await page.route("**/api/v1/schema**", async (route) => {
      await route.fulfill({ json: MOCK_SCHEMA });
    });

    // Mock API: preview
    await page.route("**/api/v1/preview/**", async (route) => {
      await route.fulfill({
        json: {
          columns: [{ name: "symbol", dtype: "String" }],
          rows: [{ symbol: "AAPL" }],
          total_rows: 1,
          execution_ms: 10,
          cache_hit: false,
          offset: 0,
          limit: 100,
          chart_config: null,
        },
      });
    });
  });

  test("loads a workflow with existing nodes and edges", async ({ page }) => {
    await page.goto(`/canvas/${MOCK_WORKFLOW.id}`);

    // Wait for the workflow name to appear in the header
    await expect(page.getByText("My Test Workflow")).toBeVisible();

    // Nodes should be rendered on the canvas (2 nodes from mock)
    const nodes = page.locator(".react-flow__node");
    await expect(nodes).toHaveCount(2, { timeout: 5000 });

    // Edges should be rendered (1 edge)
    const edges = page.locator(".react-flow__edge");
    await expect(edges).toHaveCount(1, { timeout: 5000 });
  });

  test("save button triggers API call", async ({ page }) => {
    await page.goto(`/canvas/${MOCK_WORKFLOW.id}`);
    await expect(page.getByText("My Test Workflow")).toBeVisible();

    // Track API calls
    const saveRequests: string[] = [];
    page.on("request", (req) => {
      if (req.url().includes(`/workflows/${MOCK_WORKFLOW.id}`) && req.method() !== "GET") {
        saveRequests.push(req.method());
      }
    });

    // Click save
    const saveButton = page.getByRole("button", { name: "Save" });
    await saveButton.click();

    // Should show "Saving..." briefly
    // Then revert to "Save"
    await expect(saveButton).toHaveText("Save", { timeout: 5000 });

    // Verify a save request was made
    expect(saveRequests.length).toBeGreaterThan(0);
  });

  test("navigating away and back preserves the workflow", async ({ page }) => {
    // Load the canvas with workflow
    await page.goto(`/canvas/${MOCK_WORKFLOW.id}`);
    await expect(page.getByText("My Test Workflow")).toBeVisible();

    // Navigate to dashboards
    await page.getByRole("link", { name: "Dashboards" }).click();
    await page.waitForURL("**/dashboards**");

    // Navigate back to canvas
    await page.getByRole("link", { name: "Canvas" }).click();
    await page.waitForURL("**/canvas**");

    // Click the workflow card to re-open it
    await page.getByText("My Test Workflow").click();
    await page.waitForURL(`**/canvas/${MOCK_WORKFLOW.id}`);

    // Workflow should reload with same name and nodes
    await expect(page.getByText("My Test Workflow")).toBeVisible();
    const nodes = page.locator(".react-flow__node");
    await expect(nodes).toHaveCount(2, { timeout: 5000 });
  });

  test("workflow picker lists existing workflows", async ({ page }) => {
    await page.goto("/canvas");

    // Should show the workflow list
    await expect(page.getByText("My Test Workflow")).toBeVisible();
    await expect(page.getByText("E2E test workflow")).toBeVisible();
  });

  test("clicking a workflow card opens it", async ({ page }) => {
    await page.goto("/canvas");

    // Click the workflow card
    await page.getByText("My Test Workflow").click();

    // Should navigate to the workflow
    await page.waitForURL(`**/canvas/${MOCK_WORKFLOW.id}`);
    await expect(page.getByText("My Test Workflow")).toBeVisible();
  });
});
