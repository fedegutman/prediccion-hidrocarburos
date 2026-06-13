# Amazon ECR: registro privado de imágenes Docker (ADR-003).
# El repo se llama "api" para coincidir con ECR_REPOSITORY en CI.yml.

resource "aws_ecr_repository" "api" {
  name                 = var.ecr_repository_name
  image_tag_mutability = "MUTABLE" # las imágenes se re-tagean por rama (develop/staging/main)

  image_scanning_configuration {
    scan_on_push = true # complementa el escaneo de Trivy en CI (ADR-007)
  }
}

# Política de ciclo de vida: conservar pocas imágenes para no acumular costo/almacenamiento.
resource "aws_ecr_lifecycle_policy" "api" {
  repository = aws_ecr_repository.api.name

  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Conservar solo las últimas 10 imágenes"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = 10
      }
      action = { type = "expire" }
    }]
  })
}
