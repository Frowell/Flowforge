locals {
  labels = {
    environment = var.environment
    project     = "flowforge"
    managed-by  = "terraform"
  }

  service_accounts = {
    backend     = "flowforge-backend"
    frontend    = "flowforge-frontend"
    clickhouse  = "flowforge-clickhouse"
    materialize = "flowforge-materialize"
  }
}

# -----------------------------------------------------------------------------
# GCP Service Accounts
# -----------------------------------------------------------------------------
resource "google_service_account" "backend" {
  account_id   = "${local.service_accounts.backend}-${var.environment}"
  display_name = "FlowForge Backend (${var.environment})"
  project      = var.project_id
}

resource "google_service_account" "frontend" {
  account_id   = "${local.service_accounts.frontend}-${var.environment}"
  display_name = "FlowForge Frontend (${var.environment})"
  project      = var.project_id
}

resource "google_service_account" "clickhouse" {
  account_id   = "${local.service_accounts.clickhouse}-${var.environment}"
  display_name = "FlowForge ClickHouse (${var.environment})"
  project      = var.project_id
}

resource "google_service_account" "materialize" {
  account_id   = "${local.service_accounts.materialize}-${var.environment}"
  display_name = "FlowForge Materialize (${var.environment})"
  project      = var.project_id
}

# -----------------------------------------------------------------------------
# IAM Roles for Backend SA
# -----------------------------------------------------------------------------
resource "google_project_iam_member" "backend_cloudsql_client" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.backend.email}"
}

resource "google_project_iam_member" "backend_secret_accessor" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.backend.email}"
}

# -----------------------------------------------------------------------------
# Workload Identity Bindings (K8s SA → GCP SA)
# -----------------------------------------------------------------------------
resource "google_service_account_iam_member" "backend_workload_identity" {
  service_account_id = google_service_account.backend.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "serviceAccount:${var.gke_workload_identity_pool}[flowforge/flowforge-backend]"
}

resource "google_service_account_iam_member" "frontend_workload_identity" {
  service_account_id = google_service_account.frontend.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "serviceAccount:${var.gke_workload_identity_pool}[flowforge/flowforge-frontend]"
}

resource "google_service_account_iam_member" "clickhouse_workload_identity" {
  service_account_id = google_service_account.clickhouse.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "serviceAccount:${var.gke_workload_identity_pool}[flowforge-data/clickhouse]"
}

resource "google_service_account_iam_member" "materialize_workload_identity" {
  service_account_id = google_service_account.materialize.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "serviceAccount:${var.gke_workload_identity_pool}[flowforge-data/materialize]"
}
