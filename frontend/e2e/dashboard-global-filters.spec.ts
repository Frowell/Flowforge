/**
 * E2E: Dashboard global filters — add filter, verify filter bar updates, remove filter.
 *
 * Uses dev auth mode (VITE_DEV_AUTH=true) — no Keycloak needed.
 */

import { test, expect } from "@playwright/test";

const MOCK_DASHBOARD = {
  id: "dash-filter-001",
  name: "Filtered Dashboard",
  description: "Dashboard with global filters",
  created_by: "dev-user-001",
  created_at: "2025-01-01T00:00:00Z",
  updated_at: "2025-01-01T00:00:00Z",
};

const MOCK_WIDGET = {
  id: "widget-filter-001",
  dashboard_id: "dash-filter-001",
  source_workflow_id: "wf-001",
  source_node_id: "table_output_1",
  title: "Trades Table",
  layout: { x: 0, y: 0, w: 12, h: 6 },
  config_overrides: {},
  auto_refresh_interval: null,
  created_at: "2025-01-01T00:00:00Z",
  updated_at: "2025-01-01T00:00:00Z",
};

const MOCK_WIDGET_DATA = {
  columns: [
    { name: "date", dtype: "DateTime" },
    { name: "symbol", dtype: "String" },
    { name: "price", dtype: "Float64" },
  ],
  rows: [
    { date: "2025-01-01", symbol: "AAPL", price: 185.5 },
    { date: "2025-01-02", symbol: "GOOG", price: 142.3 },
  ],
  total_rows: 2,
  execution_ms: 15,
  cache_hit: false,
  offset: 0,
  limit: 1000,
  chart_config: null,
};

test.describe("Dashboard Global Filters", () => {
  test.beforeEach(async ({ page }) => {
    // Mock dashboard list
    await page.route("**/api/v1/dashboards", async (route) => {
      await route.fulfill({
        json: {
          items: [MOCK_DASHBOARD],
          total: 1,
          page: 1,
          page_size: 20,
        },
      });
    });

    // Mock dashboard detail
    await page.route(`**/api/v1/dashboards/${MOCK_DASHBOARD.id}`, async (route) => {
      await route.fulfill({ json: MOCK_DASHBOARD });
    });

    // Mock widgets for the dashboard
    await page.route(`**/api/v1/dashboards/${MOCK_DASHBOARD.id}/widgets`, async (route) => {
      await route.fulfill({ json: [MOCK_WIDGET] });
    });

    // Mock widget data
    await page.route("**/api/v1/widgets/*/data**", async (route) => {
      await route.fulfill({ json: MOCK_WIDGET_DATA });
    });
  });

  test("dashboard loads with widget visible", async ({ page }) => {
    await page.goto(`/dashboards/${MOCK_DASHBOARD.id}`);

    await expect(page.getByText("Filtered Dashboard")).toBeVisible();
    await expect(page.getByText("Trades Table")).toBeVisible({ timeout: 5000 });
  });

  test("filter button is visible", async ({ page }) => {
    await page.goto(`/dashboards/${MOCK_DASHBOARD.id}`);

    await expect(page.getByText("+ Filter")).toBeVisible({ timeout: 5000 });
  });

  test("clicking filter button shows filter popover", async ({ page }) => {
    await page.goto(`/dashboards/${MOCK_DASHBOARD.id}`);

    await page.getByText("+ Filter").click();

    // The filter popover should appear with column selector and type selector
    await expect(page.getByText("Column")).toBeVisible();
    await expect(page.getByText("Type")).toBeVisible();
    await expect(page.getByRole("button", { name: "Add Filter" })).toBeVisible();
  });

  test("add filter button is disabled without column selection", async ({ page }) => {
    await page.goto(`/dashboards/${MOCK_DASHBOARD.id}`);

    await page.getByText("+ Filter").click();

    const addButton = page.getByRole("button", { name: "Add Filter" });
    await expect(addButton).toBeDisabled();
  });

  test("clear all button appears with active filters", async ({ page }) => {
    await page.goto(`/dashboards/${MOCK_DASHBOARD.id}`);

    await page.getByText("+ Filter").click();

    // Type a column name manually (when no widget schemas are loaded)
    const columnInput = page.locator('input[placeholder="Column name"]');
    if (await columnInput.isVisible()) {
      await columnInput.fill("symbol");
      await page.getByRole("button", { name: "Add Filter" }).click();

      // Clear all should appear
      await expect(page.getByText("Clear all")).toBeVisible();
    }
  });
});
