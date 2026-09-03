variable "project_name" {
  type = string
}

variable "github_org" {
  type = string
}

variable "github_repos" {
  description = "List of \"org/repo\" strings allowed to assume this role."
  type        = list(string)
}
