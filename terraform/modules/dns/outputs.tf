output "zone_name" {
  description = "Cloud DNS managed zone name"
  value       = google_dns_managed_zone.flowforge.name
}

output "name_servers" {
  description = "Cloud DNS name servers for the zone"
  value       = google_dns_managed_zone.flowforge.name_servers
}
