variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region"
  type        = string
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
}

variable "network_id" {
  description = "VPC network ID"
  type        = string
}

variable "subnet_id" {
  description = "GKE subnet ID"
  type        = string
}

variable "default_machine_type" {
  description = "Machine type for default node pool"
  type        = string
  default     = "e2-standard-4"
}

variable "default_node_count" {
  description = "Initial node count for default pool"
  type        = number
  default     = 2
}

variable "default_max_node_count" {
  description = "Max node count for default pool autoscaler (null disables autoscaling)"
  type        = number
  default     = null
}

variable "stateful_machine_type" {
  description = "Machine type for stateful node pool (ClickHouse, Materialize, Redpanda)"
  type        = string
  default     = "e2-standard-8"
}

variable "stateful_node_count" {
  description = "Node count for stateful pool"
  type        = number
  default     = 2
}

variable "master_authorized_cidr_blocks" {
  description = "CIDR blocks authorized to access the GKE master"
  type = list(object({
    cidr_block   = string
    display_name = string
  }))
  default = []
}

variable "enable_binary_authorization" {
  description = "Enable Binary Authorization (prod only)"
  type        = bool
  default     = false
}

variable "enable_spot_nodes" {
  description = "Use spot/preemptible nodes for default pool (dev cost optimization)"
  type        = bool
  default     = false
}
