# Copy this to terraform.tfvars (same directory) before running terraform init/plan/apply.
# Nothing here is sensitive, so it's fine to commit terraform.tfvars itself for this project.

project_name = "creditcard-fraud-mlops"
github_org   = "rmhzaal"
github_repos = ["rmhzaal/creditcard-fraud-mlops"]
cluster_version = "1.34"
