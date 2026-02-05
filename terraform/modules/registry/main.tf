locals {
  labels = {
    environment = var.environment
    project     = "flowforge"
    managed-by  = "terraform"
  }
}

# -----------------------------------------------------------------------------
# Artifact Registry — Docker Repository
# -----------------------------------------------------------------------------
resource "google_artifact_registry_repository" "flowforge" {
  repository_id = "flowforge"
  project       = var.project_id
  location      = var.region
  format        = "DOCKER"
  description   = "FlowForge Docker images (${var.environment})"

  labels = local.labels

  cleanup_policies {
    id     = "delete-untagged"
    action = "DELETE"

    condition {
      tag_state  = "UNTAGGED"
      older_than = "2592000s" # 30 days
    }
  }
}
