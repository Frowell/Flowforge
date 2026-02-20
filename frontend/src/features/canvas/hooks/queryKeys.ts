/**
 * Shared query key constants for workflow-related queries.
 * Prevents drift between hooks that depend on the same cache keys.
 */

export const WORKFLOWS_KEY = ["workflows"] as const;
export const VERSIONS_KEY = ["workflow-versions"] as const;
