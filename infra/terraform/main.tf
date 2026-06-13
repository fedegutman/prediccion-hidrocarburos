# Provider de AWS y datos comunes a todos los recursos.

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project   = var.project
      ManagedBy = "terraform"
      Phase     = "fase1"
    }
  }
}

# Identidad de la cuenta donde se está aplicando (account id, ARNs, etc.).
data "aws_caller_identity" "current" {}

# AMI de Amazon Linux 2 más reciente (ver ADR-002 / ADR-005: el SSM Agent
# viene preinstalado en Amazon Linux 2). Se resuelve dinámicamente para no
# hardcodear un AMI id que cambia por región y queda obsoleto.
data "aws_ami" "amazon_linux_2" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["amzn2-ami-hvm-*-x86_64-gp2"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

locals {
  account_id = data.aws_caller_identity.current.account_id
}
