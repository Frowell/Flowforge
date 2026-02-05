output "cluster_name" {
  description = "GKE cluster name"
  value       = module.gke.cluster_name
}

output "cluster_endpoint" {
  description = "GKE cluster endpoint"
  value       = module.gke.cluster_endpoint
  sensitive   = true
}

output "cloudsql_private_ip" {
  description = "Cloud SQL private IP address"
  value       = module.cloudsql.private_ip
}

output "cloudsql_connection_name" {
  description = "Cloud SQL instance connection name"
  value       = module.cloudsql.instance_connection_name
}

output "redis_host" {
  description = "Memorystore Redis host"
  value       = module.memorystore.host
}

output "redis_port" {
  description = "Memorystore Redis port"
  value       = module.memorystore.port
}

output "registry_url" {
  description = "Artifact Registry URL"
  value       = module.registry.repository_url
}

output "backend_service_account" {
  description = "Backend GCP service account email"
  value       = module.iam.backend_service_account_email
}

output "secret_ids" {
  description = "Secret Manager secret IDs"
  value       = module.secrets.secret_ids
}

output "dns_name_servers" {
  description = "DNS zone name servers"
  value       = length(module.dns) > 0 ? module.dns[0].name_servers : []
}
