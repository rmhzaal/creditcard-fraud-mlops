variable "aws_region" {
  description = "AWS region to deploy into."
  type        = string
  default     = "eu-west-2"
}

variable "project_name" {
  description = "Short name used as a prefix for all resources."
  type        = string
  default     = "creditcard-fraud-mlops"
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC."
  type        = string
  default     = "10.20.0.0/16"
}

variable "cluster_version" {
  description = "Kubernetes version for EKS."
  type        = string
  default     = "1.30"
}

variable "node_instance_types" {
  description = "EC2 instance types for the EKS managed node group. No GPU needed for this project."
  type        = list(string)
  default     = ["t3.medium"]
}

variable "node_desired_size" {
  type    = number
  default = 2
}

variable "db_instance_class" {
  description = "RDS instance class for the MLflow backend store."
  type        = string
  default     = "db.t3.micro"
}

variable "db_name" {
  type    = string
  default = "mlflow"
}

variable "db_username" {
  type      = string
  default   = "mlflow"
  sensitive = true
}

variable "github_org" {
  description = "GitHub org/user that owns the repos allowed to assume the CI role via OIDC."
  type        = string
}

variable "github_repos" {
  description = "List of \"org/repo\" allowed to assume the CI OIDC role."
  type        = list(string)
  default     = []
}
