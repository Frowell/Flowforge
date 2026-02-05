output "backend_service_account_email" {
  description = "Backend GCP service account email"
  value       = google_service_account.backend.email
}

output "frontend_service_account_email" {
  description = "Frontend GCP service account email"
  value       = google_service_account.frontend.email
}

output "clickhouse_service_account_email" {
  description = "ClickHouse GCP service account email"
  value       = google_service_account.clickhouse.email
}

output "materialize_service_account_email" {
  description = "Materialize GCP service account email"
  value       = google_service_account.materialize.email
}
