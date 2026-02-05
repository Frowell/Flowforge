locals {
  labels = {
    environment = var.environment
    project     = "flowforge"
    managed-by  = "terraform"
  }
}

# -----------------------------------------------------------------------------
# VPC
# -----------------------------------------------------------------------------
resource "google_compute_network" "vpc" {
  name                    = "flowforge-${var.environment}-vpc"
  project                 = var.project_id
  auto_create_subnetworks = false
  routing_mode            = "REGIONAL"
}

# -----------------------------------------------------------------------------
# Subnet with secondary ranges for GKE pods and services
# -----------------------------------------------------------------------------
resource "google_compute_subnetwork" "gke" {
  name                     = "flowforge-${var.environment}-gke-subnet"
  project                  = var.project_id
  region                   = var.region
  network                  = google_compute_network.vpc.id
  ip_cidr_range            = var.subnet_cidr
  private_ip_google_access = true

  secondary_ip_range {
    range_name    = "pods"
    ip_cidr_range = var.pods_cidr
  }

  secondary_ip_range {
    range_name    = "services"
    ip_cidr_range = var.services_cidr
  }

  log_config {
    aggregation_interval = "INTERVAL_10_MIN"
    flow_sampling        = 0.5
    metadata             = "INCLUDE_ALL_METADATA"
  }
}

# -----------------------------------------------------------------------------
# Cloud Router + NAT (outbound internet for private GKE nodes)
# -----------------------------------------------------------------------------
resource "google_compute_router" "router" {
  name    = "flowforge-${var.environment}-router"
  project = var.project_id
  region  = var.region
  network = google_compute_network.vpc.id
}

resource "google_compute_router_nat" "nat" {
  name                               = "flowforge-${var.environment}-nat"
  project                            = var.project_id
  region                             = var.region
  router                             = google_compute_router.router.name
  nat_ip_allocate_option             = "AUTO_ONLY"
  source_subnetwork_ip_ranges_to_nat = "ALL_SUBNETWORKS_ALL_IP_RANGES"

  log_config {
    enable = true
    filter = "ERRORS_ONLY"
  }
}

# -----------------------------------------------------------------------------
# Private Service Access (Cloud SQL + Memorystore private connectivity)
# -----------------------------------------------------------------------------
resource "google_compute_global_address" "private_service_access" {
  name          = "flowforge-${var.environment}-psa"
  project       = var.project_id
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 16
  network       = google_compute_network.vpc.id
}

resource "google_service_networking_connection" "private_service_access" {
  network                 = google_compute_network.vpc.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.private_service_access.name]
}

# -----------------------------------------------------------------------------
# Firewall rules
# -----------------------------------------------------------------------------

# Allow internal traffic within VPC
resource "google_compute_firewall" "allow_internal" {
  name    = "flowforge-${var.environment}-allow-internal"
  project = var.project_id
  network = google_compute_network.vpc.id

  allow {
    protocol = "tcp"
  }

  allow {
    protocol = "udp"
  }

  allow {
    protocol = "icmp"
  }

  source_ranges = [var.subnet_cidr, var.pods_cidr, var.services_cidr]
  priority      = 1000
}

# Allow GCP health check probes
resource "google_compute_firewall" "allow_health_checks" {
  name    = "flowforge-${var.environment}-allow-health-checks"
  project = var.project_id
  network = google_compute_network.vpc.id

  allow {
    protocol = "tcp"
  }

  # GCP health check source ranges
  source_ranges = ["130.211.0.0/22", "35.191.0.0/16"]
  priority      = 1000
}

# Deny all ingress from internet
resource "google_compute_firewall" "deny_ingress" {
  name    = "flowforge-${var.environment}-deny-ingress"
  project = var.project_id
  network = google_compute_network.vpc.id

  deny {
    protocol = "all"
  }

  source_ranges = ["0.0.0.0/0"]
  priority      = 65534
}
