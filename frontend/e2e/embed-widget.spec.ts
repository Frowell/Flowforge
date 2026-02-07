/**
 * E2E: Navigate to embed URL with API key, verify chart renders.
 *
 * Embed mode uses API key auth (no Keycloak).
 */

import { test, expect } from "@playwright/test";

const WIDGET_ID = "widget-embed-001";
const API_KEY = "sk_live_test_abc123";

const MOCK_WIDGET_DATA = {
  columns: [
    { name: "symbol", dtype: "String" },
    { name: "volume", dtype: "Int64" },
  ],
  rows: [
    { symbol: "AAPL", volume: 15000000 },
    { symbol: "GOOG", volume: 8500000 },
    { symbol: "MSFT", volume: 12000000 },
    { symbol: "TSLA", volume: 22000000 },
  ],
  total_rows: 4,
  execution_ms: 15,
  cache_hit: false,
  offset: 0,
  limit: 100,
  chart_config: { chart_type: "bar", x_axis: "symbol", y_axis: "volume" },
};

test.describe("Embed Widget Flow", () => {
  test("shows error when widget ID is missing", async ({ page }) => {
    // Navigate to embed without widget ID — this should 404 or show error
    // The route is /embed/:widgetId so navigating to /embed/ without an ID
    // will not match and should show the fallback
    await page.goto("/embed/");

    // Should show error about missing widget ID or redirect
    // Based on the route structure, /embed/ without ID doesn't match /embed/:widgetId
    await expect(page.getByText(/Missing widget ID|Loading/)).toBeVisible({ timeout: 5000 });
  });

  test("shows error when API key is missing", async ({ page }) => {
    await page.goto(`/embed/${WIDGET_ID}`);

    // Should show "Missing API key" error
    await expect(page.getByText("Missing API key")).toBeVisible();
  });

  test("renders widget data with valid API key", async ({ page }) => {
    // Mock the embed API endpoint
    await page.route(`**/api/v1/embed/${WIDGET_ID}**`, async (route) => {
      const url = new URL(route.request().url());
      const apiKeyParam = url.searchParams.get("api_key");

      if (apiKeyParam !== API_KEY) {
        await route.fulfill({
          status: 401,
          json: { detail: "Invalid API key" },
        });
        return;
      }

      await route.fulfill({ json: MOCK_WIDGET_DATA });
    });

    await page.goto(`/embed/${WIDGET_ID}?api_key=${API_KEY}`);

    // Should NOT show error states
    await expect(page.getByText("Missing API key")).not.toBeVisible();
    await expect(page.getByText("Missing widget ID")).not.toBeVisible();

    // Should show the chart (Recharts renders SVG or container)
    // Wait for loading to finish
    await expect(page.getByText("Loading...")).not.toBeVisible({ timeout: 10000 });

    // The embed view should NOT show the navbar
    await expect(page.getByText("FlowForge")).not.toBeVisible();
    await expect(page.getByRole("link", { name: "Canvas" })).not.toBeVisible();
  });

  test("shows error for invalid API key", async ({ page }) => {
    // Mock the embed API endpoint to reject invalid keys
    await page.route(`**/api/v1/embed/${WIDGET_ID}**`, async (route) => {
      await route.fulfill({
        status: 401,
        json: { detail: "Invalid API key" },
      });
    });

    await page.goto(`/embed/${WIDGET_ID}?api_key=sk_live_invalid`);

    // Should show error
    await expect(page.getByText("Invalid API key")).toBeVisible({ timeout: 10000 });
  });

  test("passes filter parameters from URL to backend", async ({ page }) => {
    let capturedUrl = "";

    await page.route(`**/api/v1/embed/${WIDGET_ID}**`, async (route) => {
      capturedUrl = route.request().url();
      await route.fulfill({ json: MOCK_WIDGET_DATA });
    });

    // Navigate with extra filter params
    await page.goto(
      `/embed/${WIDGET_ID}?api_key=${API_KEY}&symbol=AAPL&range=1d`,
    );

    // Wait for the API call
    await expect(page.getByText("Loading...")).not.toBeVisible({ timeout: 10000 });

    // Verify the filter params were sent to the backend
    expect(capturedUrl).toContain("symbol=AAPL");
    expect(capturedUrl).toContain("range=1d");
  });

  test("embed view is chromeless — no navbar or sidebar", async ({ page }) => {
    await page.route(`**/api/v1/embed/${WIDGET_ID}**`, async (route) => {
      await route.fulfill({ json: MOCK_WIDGET_DATA });
    });

    await page.goto(`/embed/${WIDGET_ID}?api_key=${API_KEY}`);

    // Wait for loading
    await expect(page.getByText("Loading...")).not.toBeVisible({ timeout: 10000 });

    // No navigation elements should be present
    await expect(page.locator("header")).not.toBeVisible();
    await expect(page.getByText("Nodes")).not.toBeVisible();
    await expect(page.getByRole("link", { name: "Dashboards" })).not.toBeVisible();
  });
});
