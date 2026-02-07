/**
 * E2E: Pin a chart output to a dashboard, verify widget renders.
 *
 * Uses dev auth mode (VITE_DEV_AUTH=true) — no Keycloak needed.
 */

import { test, expect } from "@playwright/test";

const MOCK_DASHBOARD = {
  id: "dash-e2e-001",
  name: "Trading Dashboard",
  description: "E2E test dashboard",
  created_by: "dev-user-001",
  created_at: "2025-01-01T00:00:00Z",
  updated_at: "2025-01-01T00:00:00Z",
};

const MOCK_DASHBOARD_LIST = {
  items: [MOCK_DASHBOARD],
  total: 1,
  page: 1,
  page_size: 20,
};

const MOCK_WIDGET = {
  id: "widget-e2e-001",
  dashboard_id: "dash-e2e-001",
  source_workflow_id: "wf-e2e-001",
  source_node_id: "chart_output_abc",
  title: "AAPL Price Chart",
  layout: { x: 0, y: 0, w: 6, h: 4 },
  config_overrides: {},
  auto_refresh_interval: null,
  created_at: "2025-01-01T00:00:00Z",
  updated_at: "2025-01-01T00:00:00Z",
};

const MOCK_WIDGET_DATA = {
  columns: [
    { name: "date", dtype: "DateTime" },
    { name: "price", dtype: "Float64" },
  ],
  rows: [
    { date: "2025-01-01", price: 180.5 },
    { date: "2025-01-02", price: 182.3 },
    { date: "2025-01-03", price: 185.1 },
  ],
  total_rows: 3,
  execution_ms: 25,
  cache_hit: false,
  offset: 0,
  limit: 100,
  chart_config: { chart_type: "bar" },
};

test.describe("Dashboard Pin Flow", () => {
  test.beforeEach(async ({ page }) => {
    // Mock API: dashboard list
    await page.route("**/api/v1/dashboards", async (route) => {
      if (route.request().method() === "GET") {
        await route.fulfill({ json: MOCK_DASHBOARD_LIST });
      } else {
        await route.fulfill({ json: MOCK_DASHBOARD });
      }
    });

    // Mock API: get specific dashboard
    await page.route(`**/api/v1/dashboards/${MOCK_DASHBOARD.id}`, async (route) => {
      await route.fulfill({ json: MOCK_DASHBOARD });
    });

    // Mock API: dashboard widgets
    await page.route(`**/api/v1/dashboards/${MOCK_DASHBOARD.id}/widgets`, async (route) => {
      if (route.request().method() === "GET") {
        await route.fulfill({ json: [MOCK_WIDGET] });
      } else if (route.request().method() === "POST") {
        await route.fulfill({ json: MOCK_WIDGET, status: 201 });
      } else {
        await route.fulfill({ json: [MOCK_WIDGET] });
      }
    });

    // Mock API: widget data
    await page.route(`**/api/v1/widgets/*/data**`, async (route) => {
      await route.fulfill({ json: MOCK_WIDGET_DATA });
    });
  });

  test("dashboard picker shows available dashboards", async ({ page }) => {
    await page.goto("/dashboards");

    // Should show dashboard list
    await expect(page.getByText("Trading Dashboard")).toBeVisible();
  });

  test("clicking a dashboard opens the grid view", async ({ page }) => {
    await page.goto("/dashboards");

    // Click the dashboard card
    await page.getByText("Trading Dashboard").click();

    // Should navigate to the dashboard
    await page.waitForURL(`**/dashboards/${MOCK_DASHBOARD.id}`);

    // Dashboard name should appear in the header
    await expect(page.getByText("Trading Dashboard")).toBeVisible();
  });

  test("dashboard shows widgets with chart content", async ({ page }) => {
    await page.goto(`/dashboards/${MOCK_DASHBOARD.id}`);

    // Dashboard header
    await expect(page.getByText("Trading Dashboard")).toBeVisible();

    // Widget title should be visible
    await expect(page.getByText("AAPL Price Chart")).toBeVisible({ timeout: 5000 });
  });

  test("Edit Layout toggle works", async ({ page }) => {
    await page.goto(`/dashboards/${MOCK_DASHBOARD.id}`);
    await expect(page.getByText("Trading Dashboard")).toBeVisible();

    // Click "Edit Layout"
    const editButton = page.getByRole("button", { name: "Edit Layout" });
    await expect(editButton).toBeVisible();
    await editButton.click();

    // Button should change to "Done Editing"
    await expect(page.getByRole("button", { name: "Done Editing" })).toBeVisible();

    // Click "Done Editing"
    await page.getByRole("button", { name: "Done Editing" }).click();

    // Button should revert to "Edit Layout"
    await expect(page.getByRole("button", { name: "Edit Layout" })).toBeVisible();
  });

  test("Copy link button is visible", async ({ page }) => {
    await page.goto(`/dashboards/${MOCK_DASHBOARD.id}`);
    await expect(page.getByText("Trading Dashboard")).toBeVisible();

    const copyButton = page.getByRole("button", { name: "Copy link" });
    await expect(copyButton).toBeVisible();
  });

  test("empty dashboard shows placeholder message", async ({ page }) => {
    // Override widgets endpoint to return empty list
    await page.route(`**/api/v1/dashboards/${MOCK_DASHBOARD.id}/widgets`, async (route) => {
      await route.fulfill({ json: [] });
    });

    await page.goto(`/dashboards/${MOCK_DASHBOARD.id}`);
    await expect(page.getByText("Trading Dashboard")).toBeVisible();

    // Should show empty state
    await expect(page.getByText("No widgets yet")).toBeVisible({ timeout: 5000 });
  });
});
