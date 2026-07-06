variable "cluster_name" {
  description = "Name of the local kind cluster"
  type        = string
  default     = "ragship"
}

variable "db_password" {
  description = "PostgreSQL password (override via TF_VAR_db_password; never commit)"
  type        = string
  sensitive   = true
  default     = "localdev"
}
