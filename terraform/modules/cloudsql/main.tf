locals {
  labels = {
    environment = var.environment
    project     = "flowforge"
    managed-by  = "terraform"
  }
}

# -----------------------------------------------------------------------------
# Cloud SQL PostgreSQL 16 Instance
# -----------------------------------------------------------------------------
resource "google_sql_database_instance" "primary" {
  name                = "flowforge-${var.environment}-pg"
  project             = var.project_id
  region              = var.region
  database_version    = "POSTGRES_16"
  deletion_protection = var.deletion_protection

  settings {
    tier              = var.tier
    disk_size         = var.disk_size_gb
    disk_type         = "PD_SSD"
    disk_autoresize   = true
    availability_type = var.enable_ha ? "REGIONAL" : "ZONAL"

    ip_configuration {
      ipv4_enabled                                  = false
      private_network                               = var.network_id
      enable_private_path_for_google_cloud_services = true
    }

    backup_configuration {
      enabled                        = true
      point_in_time_recovery_enabled = true
      start_time                     = "03:00"
      transaction_log_retention_days = var.backup_retention_days

      backup_retention_settings {
        retained_backups = var.backup_retention_days
      }
    }

    maintenance_window {
      day          = 7 # Sunday
      hour         = 3
      update_track = "stable"
    }

    dynamic "database_flags" {
      for_each = var.database_flags
      content {
        name  = database_flags.key
        value = database_flags.value
      }
    }

    user_labels = local.labels
  }
}

# -----------------------------------------------------------------------------
# Database
# -----------------------------------------------------------------------------
resource "google_sql_database" "flowforge" {
  name     = "flowforge"
  project  = var.project_id
  instance = google_sql_database_instance.primary.name
}

# -----------------------------------------------------------------------------
# Database Users
# -----------------------------------------------------------------------------
resource "google_sql_user" "app" {
  name     = "flowforge_app"
  project  = var.project_id
  instance = google_sql_database_instance.primary.name
  type     = "BUILT_IN"

  # Password managed via Secret Manager — set out-of-band
  password = "CHANGE_ME_VIA_SECRET_MANAGER"

  lifecycle {
    ignore_changes = [password]
  }
}

resource "google_sql_user" "migrate" {
  name     = "flowforge_migrate"
  project  = var.project_id
  instance = google_sql_database_instance.primary.name
  type     = "BUILT_IN"

  # Password managed via Secret Manager — set out-of-band
  password = "CHANGE_ME_VIA_SECRET_MANAGER"

  lifecycle {
    ignore_changes = [password]
  }
}
