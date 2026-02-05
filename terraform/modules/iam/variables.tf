variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
}

variable "gke_workload_identity_pool" {
  description = "GKE Workload Identity pool (format: <project_id>.svc.id.goog)"
  type        = string
}
