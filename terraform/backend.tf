# Remote state so Terraform state isn't sitting on a laptop.
# Create the S3 bucket + DynamoDB table ONCE by hand (or with a small
# bootstrap config) before running `terraform init` against this backend --
# a backend can't create the place it stores its own state.
#
#   aws s3api create-bucket --bucket <your-unique-tfstate-bucket> \
#     --region <region> --create-bucket-configuration LocationConstraint=<region>
#   aws s3api put-bucket-versioning --bucket <your-unique-tfstate-bucket> \
#     --versioning-configuration Status=Enabled
#   aws dynamodb create-table --table-name terraform-locks \
#     --attribute-definitions AttributeName=LockID,AttributeType=S \
#     --key-schema AttributeName=LockID,KeyType=HASH \
#     --billing-mode PAY_PER_REQUEST

terraform {
  required_version = ">= 1.6.0"

  backend "s3" {
    bucket         = "rmhzaal-creditcard-fraud-mlops-tfstate"
    key            = "creditcard-fraud-mlops/terraform.tfstate"
    region         = "eu-west-2"
    dynamodb_table = "terraform-locks"
    encrypt        = true
  }

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
    tls = {
      source  = "hashicorp/tls"
      version = "~> 4.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}
