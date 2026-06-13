# Versiones de Terraform y del provider de AWS.
# Se fija una versión mínima para garantizar reproducibilidad de la infra.
terraform {
  required_version = ">= 1.6"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Estado local por simplicidad (alcance académico). Para trabajo en equipo,
  # migrar a un backend remoto (S3 + DynamoDB lock) descomentando el bloque.
  # backend "s3" {
  #   bucket = "tp-software-tfstate"
  #   key    = "fase1/terraform.tfstate"
  #   region = "us-east-2"
  # }
}
