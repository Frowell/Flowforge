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
  description = "VPC network ID for private IP connectivity"
  type        = string
}

variable "tier" {
  description = "Cloud SQL machine tier"
  type        = string
  default     = "db-f1-micro"
}

variable "disk_size_gb" {
  description = "Disk size in GB"
  type        = number
  default     = 10
}

variable "enable_ha" {
  description = "Enable high availability (regional) deployment"
  type        = bool
  default     = false
}

variable "backup_retention_days" {
  description = "Number of days to retain backups"
  type        = number
  default     = 7
}

variable "database_flags" {
  description = "Map of database flags to set"
  type        = map(string)
  default = {
    max_connections = "200"
  }
}

variable "deletion_protection" {
  description = "Enable deletion protection"
  type        = bool
  default     = false
}
