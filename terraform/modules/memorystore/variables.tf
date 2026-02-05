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
  description = "VPC network ID for private connectivity"
  type        = string
}

variable "memory_size_gb" {
  description = "Redis memory size in GB"
  type        = number
  default     = 1
}

variable "tier" {
  description = "Memorystore tier (BASIC or STANDARD_HA)"
  type        = string
  default     = "BASIC"
}

variable "redis_version" {
  description = "Redis version"
  type        = string
  default     = "REDIS_7_0"
}

variable "auth_enabled" {
  description = "Enable AUTH for Redis connections"
  type        = bool
  default     = false
}
