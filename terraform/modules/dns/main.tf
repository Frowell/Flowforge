# -----------------------------------------------------------------------------
# Cloud DNS Managed Zone
# -----------------------------------------------------------------------------
resource "google_dns_managed_zone" "flowforge" {
  name        = var.dns_zone_name
  project     = var.project_id
  dns_name    = "${var.domain}."
  description = "FlowForge DNS zone (${var.environment})"

  labels = {
    environment = var.environment
    project     = "flowforge"
    managed-by  = "terraform"
  }
}

# -----------------------------------------------------------------------------
# DNS A Records
# -----------------------------------------------------------------------------

# App subdomain (frontend + embed)
resource "google_dns_record_set" "app" {
  name         = "app.${google_dns_managed_zone.flowforge.dns_name}"
  project      = var.project_id
  managed_zone = google_dns_managed_zone.flowforge.name
  type         = "A"
  ttl          = 300
  rrdatas      = [var.lb_ip_address]
}

# API subdomain (backend)
resource "google_dns_record_set" "api" {
  name         = "api.${google_dns_managed_zone.flowforge.dns_name}"
  project      = var.project_id
  managed_zone = google_dns_managed_zone.flowforge.name
  type         = "A"
  ttl          = 300
  rrdatas      = [var.lb_ip_address]
}
