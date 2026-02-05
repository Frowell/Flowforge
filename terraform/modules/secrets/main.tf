locals {
  labels = {
    environment = var.environment
    project     = "flowforge"
    managed-by  = "terraform"
  }
}

# -----------------------------------------------------------------------------
# Secret Manager Secrets
# Creates secret resources only — values are populated out-of-band (manually or via CI)
# -----------------------------------------------------------------------------
resource "google_secret_manager_secret" "secrets" {
  for_each  = toset(var.secret_names)
  secret_id = "${var.environment}-${each.value}"
  project   = var.project_id

  replication {
    auto {}
  }

  labels = local.labels
}
