provider "google" {
  project = var.project_id
  region  = var.region
}

provider "google-beta" {
  project = var.project_id
  region  = var.region
}

# -----------------------------------------------------------------------------
# Networking
# -----------------------------------------------------------------------------
module "networking" {
  source = "../../modules/networking"

  project_id    = var.project_id
  region        = var.region
  environment   = var.environment
  subnet_cidr   = var.subnet_cidr
  pods_cidr     = var.pods_cidr
  services_cidr = var.services_cidr
}

# -----------------------------------------------------------------------------
# GKE Cluster
# -----------------------------------------------------------------------------
module "gke" {
  source = "../../modules/gke"

  project_id                    = var.project_id
  region                        = var.region
  environment                   = var.environment
  network_id                    = module.networking.network_id
  subnet_id                     = module.networking.subnet_id
  default_machine_type          = var.default_machine_type
  default_node_count            = var.default_node_count
  default_max_node_count        = var.default_max_node_count
  stateful_machine_type         = var.stateful_machine_type
  stateful_node_count           = var.stateful_node_count
  master_authorized_cidr_blocks = var.master_authorized_cidr_blocks
  enable_binary_authorization   = var.enable_binary_authorization
  enable_spot_nodes             = var.enable_spot_nodes
}

# -----------------------------------------------------------------------------
# IAM + Workload Identity
# -----------------------------------------------------------------------------
module "iam" {
  source = "../../modules/iam"

  project_id                 = var.project_id
  environment                = var.environment
  gke_workload_identity_pool = module.gke.workload_identity_pool
}

# -----------------------------------------------------------------------------
# Cloud SQL (PostgreSQL)
# -----------------------------------------------------------------------------
module "cloudsql" {
  source = "../../modules/cloudsql"

  project_id            = var.project_id
  region                = var.region
  environment           = var.environment
  network_id            = module.networking.network_id
  tier                  = var.cloudsql_tier
  disk_size_gb          = var.cloudsql_disk_size
  enable_ha             = var.cloudsql_enable_ha
  backup_retention_days = var.backup_retention_days
  deletion_protection   = true

  depends_on = [module.networking]
}

# -----------------------------------------------------------------------------
# Memorystore (Redis)
# -----------------------------------------------------------------------------
module "memorystore" {
  source = "../../modules/memorystore"

  project_id     = var.project_id
  region         = var.region
  environment    = var.environment
  network_id     = module.networking.network_id
  memory_size_gb = var.memorystore_size_gb
  tier           = var.memorystore_tier
  auth_enabled   = var.memorystore_auth_enabled

  depends_on = [module.networking]
}

# -----------------------------------------------------------------------------
# Artifact Registry
# -----------------------------------------------------------------------------
module "registry" {
  source = "../../modules/registry"

  project_id  = var.project_id
  region      = var.region
  environment = var.environment
}

# -----------------------------------------------------------------------------
# Secret Manager
# -----------------------------------------------------------------------------
module "secrets" {
  source = "../../modules/secrets"

  project_id  = var.project_id
  environment = var.environment
}

# -----------------------------------------------------------------------------
# DNS (only when LB IP is available)
# -----------------------------------------------------------------------------
module "dns" {
  source = "../../modules/dns"
  count  = var.lb_ip_address != "" ? 1 : 0

  project_id    = var.project_id
  environment   = var.environment
  domain        = var.domain
  dns_zone_name = var.dns_zone_name
  lb_ip_address = var.lb_ip_address
}
