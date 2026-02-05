output "network_id" {
  description = "VPC network ID"
  value       = google_compute_network.vpc.id
}

output "network_name" {
  description = "VPC network name"
  value       = google_compute_network.vpc.name
}

output "subnet_id" {
  description = "GKE subnet ID"
  value       = google_compute_subnetwork.gke.id
}

output "subnet_name" {
  description = "GKE subnet name"
  value       = google_compute_subnetwork.gke.name
}

output "private_service_access_address" {
  description = "Private Service Access address range name"
  value       = google_compute_global_address.private_service_access.name
}
