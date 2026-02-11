"""Dev authentication helpers for benchmark runs.

Uses the dev-mode auth bypass (X-Dev-Tenant header) so benchmarks
don't require a running Keycloak instance.
"""

# Default dev tenant — matches VITE_DEV_AUTH=true mock user
DEV_TENANT_ID = "dev-tenant-001"
DEV_TOKEN = "dev-token"

# Headers that every benchmark request must include
AUTH_HEADERS = {
    "Authorization": f"Bearer {DEV_TOKEN}",
    "X-Dev-Tenant": DEV_TENANT_ID,
    "Content-Type": "application/json",
}


def get_auth_headers(tenant_id: str | None = None) -> dict[str, str]:
    """Return auth headers, optionally overriding the tenant."""
    headers = dict(AUTH_HEADERS)
    if tenant_id:
        headers["X-Dev-Tenant"] = tenant_id
    return headers
