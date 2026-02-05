locals {
  labels = {
    environment = var.environment
    project     = "flowforge"
    managed-by  = "terraform"
  }
}

# -----------------------------------------------------------------------------
# Memorystore Redis Instance
# -----------------------------------------------------------------------------
resource "google_redis_instance" "cache" {
  name           = "flowforge-${var.environment}-redis"
  project        = var.project_id
  region         = var.region
  tier           = var.tier
  memory_size_gb = var.memory_size_gb
  redis_version  = var.redis_version

  authorized_network = var.network_id
  connect_mode       = "PRIVATE_SERVICE_ACCESS"

  auth_enabled = var.auth_enabled

  redis_configs = {
    maxmemory-policy = "allkeys-lru"
  }

  labels = local.labels
}
