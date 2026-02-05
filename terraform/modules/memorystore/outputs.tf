output "host" {
  description = "Redis instance host IP"
  value       = google_redis_instance.cache.host
}

output "port" {
  description = "Redis instance port"
  value       = google_redis_instance.cache.port
}

output "auth_string" {
  description = "Redis AUTH string (empty if auth not enabled)"
  value       = google_redis_instance.cache.auth_string
  sensitive   = true
}
