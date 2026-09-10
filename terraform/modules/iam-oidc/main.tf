# Lets GitHub Actions assume an AWS role via short-lived tokens instead
# of a stored access key/secret. This is the module Phase 5 of the guide
# (CI/CD) depends on.

data "tls_certificate" "github" {
  url = "https://token.actions.githubusercontent.com/.well-known/openid-configuration"
}

resource "aws_iam_openid_connect_provider" "github" {
  url             = "https://token.actions.githubusercontent.com"
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = [data.tls_certificate.github.certificates[0].sha1_fingerprint]
}

data "aws_iam_policy_document" "trust" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity", "sts:TagSession"]

    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    # GitHub repos created after their July 2026 rollout use an immutable
    # owner-ID/repo-ID subject format (repo:owner@ownerID/repo@repoID:*)
    # instead of the plain name-based one. Matching both here so this
    # keeps working regardless of which format a given repo uses.
    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      values = concat(
        [for repo in var.github_repos : "repo:${repo}:*"],
        ["repo:rmhzaal@239316969/creditcard-fraud-mlops@1344074834:*"]
      )
    }
  }
}

resource "aws_iam_role" "github_actions" {
  name               = "${var.project_name}-github-actions"
  assume_role_policy = data.aws_iam_policy_document.trust.json
}

resource "aws_iam_role_policy_attachment" "ecr_push" {
  role       = aws_iam_role.github_actions.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryPowerUser"
}

data "aws_iam_policy_document" "eks_describe" {
  statement {
    effect    = "Allow"
    actions   = ["eks:DescribeCluster"]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "eks_describe" {
  name   = "${var.project_name}-eks-describe"
  role   = aws_iam_role.github_actions.id
  policy = data.aws_iam_policy_document.eks_describe.json
}

output "role_arn" {
  value = aws_iam_role.github_actions.arn
}
