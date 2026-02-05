locals {
  labels = {
    environment = var.environment
    project     = "flowforge"
    managed-by  = "terraform"
  }
}

# -----------------------------------------------------------------------------
# GKE Cluster
# -----------------------------------------------------------------------------
resource "google_container_cluster" "primary" {
  name     = "flowforge-${var.environment}"
  project  = var.project_id
  location = var.region

  network    = var.network_id
  subnetwork = var.subnet_id

  # We manage node pools separately
  remove_default_node_pool = true
  initial_node_count       = 1

  # Private cluster configuration
  private_cluster_config {
    enable_private_nodes    = true
    enable_private_endpoint = false
    master_ipv4_cidr_block  = "172.16.0.0/28"
  }

  # Master authorized networks
  dynamic "master_authorized_networks_config" {
    for_each = length(var.master_authorized_cidr_blocks) > 0 ? [1] : []
    content {
      dynamic "cidr_blocks" {
        for_each = var.master_authorized_cidr_blocks
        content {
          cidr_block   = cidr_blocks.value.cidr_block
          display_name = cidr_blocks.value.display_name
        }
      }
    }
  }

  # IP allocation policy for VPC-native cluster
  ip_allocation_policy {
    cluster_secondary_range_name  = "pods"
    services_secondary_range_name = "services"
  }

  # Workload Identity
  workload_identity_config {
    workload_pool = "${var.project_id}.svc.id.goog"
  }

  # Release channel — stable
  release_channel {
    channel = "STABLE"
  }

  # Binary Authorization
  dynamic "binary_authorization" {
    for_each = var.enable_binary_authorization ? [1] : []
    content {
      evaluation_mode = "PROJECT_SINGLETON_POLICY_ENFORCE"
    }
  }

  # Logging and monitoring
  logging_config {
    enable_components = ["SYSTEM_COMPONENTS", "WORKLOADS"]
  }

  monitoring_config {
    enable_components = ["SYSTEM_COMPONENTS"]
    managed_prometheus {
      enabled = true
    }
  }

  resource_labels = local.labels

  # Prevent accidental deletion
  deletion_protection = var.environment == "prod" ? true : false
}

# -----------------------------------------------------------------------------
# Default Node Pool — application workloads
# -----------------------------------------------------------------------------
resource "google_container_node_pool" "default" {
  name     = "default"
  project  = var.project_id
  location = var.region
  cluster  = google_container_cluster.primary.name

  initial_node_count = var.default_node_count

  # Autoscaling (only when max is set)
  dynamic "autoscaling" {
    for_each = var.default_max_node_count != null ? [1] : []
    content {
      min_node_count = var.default_node_count
      max_node_count = var.default_max_node_count
    }
  }

  node_config {
    machine_type = var.default_machine_type
    spot         = var.enable_spot_nodes

    disk_size_gb = 100
    disk_type    = "pd-ssd"

    oauth_scopes = [
      "https://www.googleapis.com/auth/cloud-platform",
    ]

    workload_metadata_config {
      mode = "GKE_METADATA"
    }

    labels = merge(local.labels, {
      "flowforge.io/pool" = "default"
    })

    metadata = {
      disable-legacy-endpoints = "true"
    }
  }

  management {
    auto_repair  = true
    auto_upgrade = true
  }
}

# -----------------------------------------------------------------------------
# Stateful Node Pool — ClickHouse, Materialize, Redpanda
# -----------------------------------------------------------------------------
resource "google_container_node_pool" "stateful" {
  name     = "stateful"
  project  = var.project_id
  location = var.region
  cluster  = google_container_cluster.primary.name

  node_count = var.stateful_node_count

  node_config {
    machine_type = var.stateful_machine_type

    disk_size_gb = 200
    disk_type    = "pd-ssd"

    oauth_scopes = [
      "https://www.googleapis.com/auth/cloud-platform",
    ]

    workload_metadata_config {
      mode = "GKE_METADATA"
    }

    labels = merge(local.labels, {
      "flowforge.io/pool" = "stateful"
    })

    taint {
      key    = "flowforge.io/pool"
      value  = "stateful"
      effect = "NO_SCHEDULE"
    }

    metadata = {
      disable-legacy-endpoints = "true"
    }
  }

  management {
    auto_repair  = true
    auto_upgrade = true
  }
}
