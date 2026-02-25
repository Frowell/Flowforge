/**
 * E2E: Navigate to audit page, verify log entries render with correct action types.
 *
 * Uses dev auth mode (VITE_DEV_AUTH=true) — no Keycloak needed.
 */

import { test, expect } from "@playwright/test";

const MOCK_AUDIT_LOGS = {
  items: [
    {
      id: "audit-001",
      tenant_id: "dev-tenant-001",
      user_id: "dev-user-001",
      action: "created",
      resource_type: "workflow",
      resource_id: "00000000-0000-0000-0000-000000000001",
      metadata: { name: "VWAP Analysis" },
      created_at: "2025-01-03T14:30:00Z",
    },
    {
      id: "audit-002",
      tenant_id: "dev-tenant-001",
      user_id: "dev-user-001",
      action: "updated",
      resource_type: "dashboard",
      resource_id: "00000000-0000-0000-0000-000000000002",
      metadata: { fields: ["name"] },
      created_at: "2025-01-03T15:00:00Z",
    },
    {
      id: "audit-003",
      tenant_id: "dev-tenant-001",
      user_id: "dev-user-001",
      action: "executed",
      resource_type: "workflow",
      resource_id: "00000000-0000-0000-0000-000000000003",
      metadata: null,
      created_at: "2025-01-03T15:30:00Z",
    },
    {
      id: "audit-004",
      tenant_id: "dev-tenant-001",
      user_id: "dev-user-001",
      action: "deleted",
      resource_type: "widget",
      resource_id: "00000000-0000-0000-0000-000000000004",
      metadata: null,
      created_at: "2025-01-03T16:00:00Z",
    },
  ],
  total: 4,
  offset: 0,
  limit: 25,
};

test.describe("Audit Trail", () => {
  test.beforeEach(async ({ page }) => {
    await page.route("**/api/v1/audit-logs**", async (route) => {
      await route.fulfill({ json: MOCK_AUDIT_LOGS });
    });
  });

  test("audit page shows log entries", async ({ page }) => {
    await page.goto("/admin/audit");

    await expect(page.getByText("Audit Log")).toBeVisible();
    await expect(page.getByText("4 total events")).toBeVisible();
  });

  test("audit entries show action badges", async ({ page }) => {
    await page.goto("/admin/audit");

    // Action badges should be visible
    await expect(page.getByText("created")).toBeVisible();
    await expect(page.getByText("updated")).toBeVisible();
    await expect(page.getByText("executed")).toBeVisible();
    await expect(page.getByText("deleted")).toBeVisible();
  });

  test("audit entries show resource types", async ({ page }) => {
    await page.goto("/admin/audit");

    await expect(page.getByText("workflow").first()).toBeVisible();
    await expect(page.getByText("dashboard")).toBeVisible();
    await expect(page.getByText("widget")).toBeVisible();
  });

  test("audit page has resource type filter", async ({ page }) => {
    await page.goto("/admin/audit");

    // Resource type dropdown
    const resourceSelect = page.locator("select").first();
    await expect(resourceSelect).toBeVisible();
    await expect(resourceSelect).toContainText("All resources");
  });

  test("audit page has action filter", async ({ page }) => {
    await page.goto("/admin/audit");

    // Action dropdown — second select
    const selects = page.locator("select");
    const actionSelect = selects.nth(1);
    await expect(actionSelect).toBeVisible();
    await expect(actionSelect).toContainText("All actions");
  });

  test("audit page has pagination controls", async ({ page }) => {
    await page.goto("/admin/audit");

    await expect(page.getByRole("button", { name: "Prev" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Next" })).toBeVisible();
  });

  test("empty audit page shows no events message", async ({ page }) => {
    await page.route("**/api/v1/audit-logs**", async (route) => {
      await route.fulfill({
        json: { items: [], total: 0, offset: 0, limit: 25 },
      });
    });

    await page.goto("/admin/audit");
    await expect(page.getByText("No audit events found")).toBeVisible();
  });
});
