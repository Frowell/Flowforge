variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
}

variable "domain" {
  description = "Base domain for DNS records"
  type        = string
}

variable "dns_zone_name" {
  description = "Cloud DNS managed zone name"
  type        = string
}

variable "lb_ip_address" {
  description = "Load balancer IP address for DNS A records"
  type        = string
}
