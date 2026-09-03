output "cluster_name" {
  value = module.eks.cluster_name
}

output "cluster_endpoint" {
  value = module.eks.cluster_endpoint
}

output "configure_kubectl" {
  description = "Run this to point kubectl at the new cluster."
  value       = "aws eks update-kubeconfig --name ${module.eks.cluster_name} --region ${var.aws_region}"
}

output "mlflow_db_endpoint" {
  value = aws_db_instance.mlflow.address
}

output "mlflow_artifacts_bucket" {
  value = aws_s3_bucket.mlflow_artifacts.bucket
}

output "dvc_store_bucket" {
  value = aws_s3_bucket.dvc_store.bucket
}

output "github_actions_role_arn" {
  description = "Put this in your GitHub Actions workflow's role-to-assume input."
  value       = module.iam_oidc.role_arn
}
