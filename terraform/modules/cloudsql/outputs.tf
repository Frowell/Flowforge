output "instance_name" {
  description = "Cloud SQL instance name"
  value       = google_sql_database_instance.primary.name
}

output "instance_connection_name" {
  description = "Cloud SQL instance connection name"
  value       = google_sql_database_instance.primary.connection_name
}

output "private_ip" {
  description = "Cloud SQL private IP address"
  value       = google_sql_database_instance.primary.private_ip_address
}

output "database_name" {
  description = "Database name"
  value       = google_sql_database.flowforge.name
}
