variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
}

variable "secret_names" {
  description = "List of secret names to create in Secret Manager"
  type        = list(string)
  default = [
    "cloudsql-app-password",
    "cloudsql-migrate-password",
    "keycloak-admin-password",
    "keycloak-db-password",
    "redis-auth-string",
    "clickhouse-password",
    "jwt-signing-key",
    "api-key-encryption-key",
  ]
}
