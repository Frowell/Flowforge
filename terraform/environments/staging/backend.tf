terraform {
  backend "gcs" {
    bucket = "flowforge-terraform-state"
    prefix = "environments/staging"
  }
}
