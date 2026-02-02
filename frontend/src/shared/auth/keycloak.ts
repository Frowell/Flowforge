/**
 * Keycloak OIDC authentication.
 *
 * Canvas and dashboard routes authenticate via Keycloak SSO.
 * Supports multiple identity providers configured in the Keycloak realm.
 * Embed routes use API key auth (handled separately via URL params).
 */

import Keycloak from "keycloak-js";

export interface CurrentUser {
  id: string;
  tenantId: string;
  email: string;
  name: string;
  roles: string[];
}

const keycloak = new Keycloak({
  url: import.meta.env.VITE_KEYCLOAK_URL ?? "http://localhost:8080",
  realm: import.meta.env.VITE_KEYCLOAK_REALM ?? "flowforge",
  clientId: import.meta.env.VITE_KEYCLOAK_CLIENT_ID ?? "flowforge-app",
});

let _initialized = false;

/**
 * Initialize Keycloak — call once at app startup.
 *
 * Uses check-sso to silently check if the user has an active SSO session
 * without forcing a redirect on first load.
 */
export async function initKeycloak(): Promise<boolean> {
  if (_initialized) return keycloak.authenticated ?? false;

  const authenticated = await keycloak.init({
    onLoad: "check-sso",
    silentCheckSsoRedirectUri: `${window.location.origin}/silent-check-sso.html`,
    pkceMethod: "S256",
  });

  _initialized = true;

  // Auto-refresh token before expiry
  keycloak.onTokenExpired = () => {
    keycloak.updateToken(30).catch(() => {
      keycloak.login();
    });
  };

  return authenticated;
}

/**
 * Redirect to Keycloak login page.
 *
 * Keycloak handles the identity provider selection (Google, GitHub, SAML, etc.)
 * based on the realm configuration.
 */
export function login(): void {
  keycloak.login();
}

/**
 * Redirect to Keycloak logout and clear local session.
 */
export function logout(): void {
  keycloak.logout({ redirectUri: window.location.origin });
}

/**
 * Get the current access token for API calls.
 *
 * Automatically refreshes if the token is about to expire (within 30s).
 * Returns null if not authenticated.
 */
export async function getAccessToken(): Promise<string | null> {
  if (!keycloak.authenticated) return null;

  try {
    await keycloak.updateToken(30);
    return keycloak.token ?? null;
  } catch {
    // Token refresh failed — redirect to login
    keycloak.login();
    return null;
  }
}

/**
 * Get the current authenticated user's info from the token claims.
 */
export function getCurrentUser(): CurrentUser | null {
  if (!keycloak.authenticated || !keycloak.tokenParsed) return null;

  const token = keycloak.tokenParsed;
  const clientRoles =
    token.resource_access?.[keycloak.clientId ?? ""]?.roles ?? [];
  const realmRoles = token.realm_access?.roles ?? [];

  return {
    id: token.sub ?? "",
    tenantId: (token as Record<string, unknown>).tenant_id as string ?? "",
    email: token.email ?? "",
    name: token.name ?? token.preferred_username ?? "",
    roles: [...new Set([...realmRoles, ...clientRoles])],
  };
}

/**
 * Check if the current user has a specific role.
 */
export function hasRole(role: string): boolean {
  const user = getCurrentUser();
  return user?.roles.includes(role) ?? false;
}

/** Raw Keycloak instance — use sparingly, prefer the functions above. */
export { keycloak };
