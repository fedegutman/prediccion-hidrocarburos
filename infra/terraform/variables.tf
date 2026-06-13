# Variables de entrada de la infraestructura de Fase 1.
# Los valores por defecto reflejan lo que estaba desplegado antes del borrado de la cuenta.

variable "aws_region" {
  description = "Región de AWS donde se crea toda la infraestructura."
  type        = string
  default     = "us-east-2"
}

variable "project" {
  description = "Nombre del proyecto, usado como prefijo y tag en los recursos."
  type        = string
  default     = "tp-software"
}

variable "github_repo" {
  description = "Repositorio de GitHub (owner/repo) que asume los roles via OIDC."
  type        = string
  default     = "fedegutman/tp-software"
}

variable "ecr_repository_name" {
  description = "Nombre del repositorio de ECR. Debe coincidir con ECR_REPOSITORY en CI.yml."
  type        = string
  default     = "api"
}

variable "instance_type" {
  description = "Tipo de instancia EC2 (free tier). Ver ADR-002."
  type        = string
  default     = "t2.micro"
}

variable "environments" {
  description = <<-EOT
    Mapa de ambientes -> tag Name de la instancia EC2.
    Los tags DEBEN coincidir con los targets de CD.yml (Key=tag:Name).
    OJO: producción usa 'tp-prod' (no 'tp-production').
  EOT
  type        = map(string)
  default = {
    development = "tp-development"
    staging     = "tp-staging"
    production  = "tp-prod"
  }
}

variable "ingress_ports" {
  description = "Puertos TCP expuestos en el Security Group. NO incluye 22 (deploy via SSM, ver ADR-005)."
  type        = list(number)
  default     = [8000, 3000, 9090, 9093, 9100]
}

variable "allowed_cidr" {
  description = "CIDR autorizado a acceder a los puertos del stack. 0.0.0.0/0 = público (como estaba en Fase 1)."
  type        = string
  default     = "0.0.0.0/0"
}
