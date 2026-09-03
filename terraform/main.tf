# Root module. Wires together the network, cluster, database, storage,
# and the OIDC trust that lets GitHub Actions deploy without static keys.
#
# Uses the well-maintained community modules for VPC/EKS rather than
# hand-rolling them -- reading THEIR source is a good exercise once this
# is working, but writing your own from scratch teaches little extra for
# the time it costs.

data "aws_availability_zones" "available" {
  state = "available"
}

module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.8"

  name = "${var.project_name}-vpc"
  cidr = var.vpc_cidr

  azs             = slice(data.aws_availability_zones.available.names, 0, 2)
  private_subnets = [cidrsubnet(var.vpc_cidr, 4, 0), cidrsubnet(var.vpc_cidr, 4, 1)]
  public_subnets  = [cidrsubnet(var.vpc_cidr, 4, 8), cidrsubnet(var.vpc_cidr, 4, 9)]

  enable_nat_gateway   = true
  single_nat_gateway   = true # cost trade-off for a portfolio project; note this in your README
  enable_dns_hostnames = true

  public_subnet_tags = {
    "kubernetes.io/role/elb" = 1
  }
  private_subnet_tags = {
    "kubernetes.io/role/internal-elb" = 1
  }

  tags = {
    Project = var.project_name
  }
}

module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 20.0"

  cluster_name    = "${var.project_name}-cluster"
  cluster_version = var.cluster_version
  iam_role_name   = "${var.project_name}-eks"

  cluster_endpoint_public_access = true

  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnets

  enable_cluster_creator_admin_permissions = true

  eks_managed_node_groups = {
    default = {
      instance_types = var.node_instance_types
      min_size       = 1
      max_size       = 3
      desired_size   = var.node_desired_size
    }
  }

  tags = {
    Project = var.project_name
  }
}

# Phase 3: lets the MLflow pod (running on any node) read/write the
# artifacts bucket. Attached at the node level rather than scoped to the
# MLflow pod specifically via IRSA -- a deliberate simplification for a
# 2-day portfolio build (every pod on the node inherits this permission,
# not just MLflow's). Note this trade-off in your README; IRSA (per-pod
# identity) is the fix if you come back to harden this later.
resource "aws_iam_role_policy" "node_mlflow_s3" {
  name = "${var.project_name}-node-mlflow-s3"
  role = module.eks.eks_managed_node_groups["default"].iam_role_name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject", "s3:ListBucket"]
      Resource = [
        aws_s3_bucket.mlflow_artifacts.arn,
        "${aws_s3_bucket.mlflow_artifacts.arn}/*"
      ]
    }]
  })
}

resource "aws_security_group" "rds" {
  name_prefix = "${var.project_name}-rds-"
  vpc_id      = module.vpc.vpc_id

  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [module.eks.node_security_group_id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_db_subnet_group" "mlflow" {
  name       = "${var.project_name}-mlflow-db"
  subnet_ids = module.vpc.private_subnets
}

resource "random_password" "db" {
  length  = 24
  special = false
}

resource "aws_db_instance" "mlflow" {
  identifier             = "${var.project_name}-mlflow"
  engine                 = "postgres"
  engine_version         = "16"
  instance_class         = var.db_instance_class
  allocated_storage      = 20
  db_name                = var.db_name
  username               = var.db_username
  password               = random_password.db.result
  db_subnet_group_name   = aws_db_subnet_group.mlflow.name
  vpc_security_group_ids = [aws_security_group.rds.id]
  skip_final_snapshot    = true
  publicly_accessible    = false

  # In Phase 9 of the guide, move this password into AWS Secrets Manager
  # and reference it via External Secrets Operator instead of reading it
  # from Terraform output.
}

resource "aws_s3_bucket" "mlflow_artifacts" {
  bucket        = "${var.project_name}-mlflow-artifacts-${data.aws_caller_identity.current.account_id}"
  force_destroy = true
}

resource "aws_s3_bucket" "dvc_store" {
  bucket        = "${var.project_name}-dvc-store-${data.aws_caller_identity.current.account_id}"
  force_destroy = true
}

data "aws_caller_identity" "current" {}

module "iam_oidc" {
  source = "./modules/iam-oidc"

  project_name = var.project_name
  github_org   = var.github_org
  github_repos = var.github_repos
}

# We're using GitHub Actions to deploy directly (push model, see Section 2.3
# of the guide) instead of a GitOps controller like ArgoCD. That means the
# CI role needs its own permission to talk to the cluster -- this is the
# modern EKS Access Entries API, which replaces hand-editing the old
# aws-auth ConfigMap. Scoped to one namespace rather than cluster-wide.
resource "aws_eks_access_entry" "github_actions" {
  cluster_name  = module.eks.cluster_name
  principal_arn = module.iam_oidc.role_arn
  type          = "STANDARD"
}

resource "aws_eks_access_policy_association" "github_actions_edit" {
  cluster_name  = module.eks.cluster_name
  principal_arn = module.iam_oidc.role_arn
  policy_arn    = "arn:aws:eks::aws:cluster-access-policy/AmazonEKSEditPolicy"

  access_scope {
    type       = "namespace"
    namespaces = ["creditcard-fraud-mlops"]
  }
}
