variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region"
  type        = string
  default     = "us-central1"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "prod"
}

# GKE
variable "default_machine_type" {
  description = "Machine type for GKE default node pool"
  type        = string
  default     = "e2-standard-8"
}

variable "default_node_count" {
  description = "Node count for GKE default pool"
  type        = number
  default     = 3
}

variable "default_max_node_count" {
  description = "Max node count for autoscaler"
  type        = number
  default     = 6
}

variable "stateful_machine_type" {
  description = "Machine type for GKE stateful node pool"
  type        = string
  default     = "e2-standard-8"
}

variable "stateful_node_count" {
  description = "Node count for GKE stateful pool"
  type        = number
  default     = 3
}

variable "enable_spot_nodes" {
  description = "Use spot/preemptible nodes for cost optimization"
  type        = bool
  default     = false
}

variable "enable_binary_authorization" {
  description = "Enable Binary Authorization"
  type        = bool
  default     = true
}

variable "master_authorized_cidr_blocks" {
  description = "CIDR blocks authorized to access GKE master"
  type = list(object({
    cidr_block   = string
    display_name = string
  }))
  default = []
}

# Cloud SQL
variable "cloudsql_tier" {
  description = "Cloud SQL instance tier"
  type        = string
  default     = "db-custom-4-8192"
}

variable "cloudsql_disk_size" {
  description = "Cloud SQL disk size in GB"
  type        = number
  default     = 50
}

variable "cloudsql_enable_ha" {
  description = "Enable Cloud SQL HA"
  type        = bool
  default     = true
}

variable "backup_retention_days" {
  description = "Cloud SQL backup retention days"
  type        = number
  default     = 30
}

# Memorystore
variable "memorystore_size_gb" {
  description = "Memorystore Redis memory size in GB"
  type        = number
  default     = 5
}

variable "memorystore_tier" {
  description = "Memorystore Redis tier"
  type        = string
  default     = "STANDARD_HA"
}

variable "memorystore_auth_enabled" {
  description = "Enable Memorystore AUTH"
  type        = bool
  default     = true
}

# Networking
variable "subnet_cidr" {
  description = "Primary subnet CIDR"
  type        = string
  default     = "10.20.0.0/20"
}

variable "pods_cidr" {
  description = "Secondary range CIDR for pods"
  type        = string
  default     = "10.24.0.0/14"
}

variable "services_cidr" {
  description = "Secondary range CIDR for services"
  type        = string
  default     = "10.28.0.0/20"
}

# DNS
variable "domain" {
  description = "Base domain for DNS"
  type        = string
  default     = "flowforge.io"
}

variable "dns_zone_name" {
  description = "Cloud DNS zone name"
  type        = string
  default     = "flowforge-prod"
}

variable "lb_ip_address" {
  description = "Load balancer IP address for DNS records"
  type        = string
  default     = ""
}
