# Salidas: valores que necesitás para configurar los secrets de GitHub
# y actualizar el README con las nuevas IPs.

output "ecr_repository_url" {
  description = "URL del repo ECR. El registry es la parte antes de '/'."
  value       = aws_ecr_repository.api.repository_url
}

output "github_ci_role_arn" {
  description = "ARN del rol de CI. Cargar como secret AWS_CI_ROLE_ARN en GitHub."
  value       = aws_iam_role.github_ci.arn
}

output "github_cd_role_arn" {
  description = "ARN del rol de CD. Cargar como secret AWS_CD_ROLE_ARN en GitHub."
  value       = aws_iam_role.github_cd.arn
}

output "instance_public_ips" {
  description = "IPs públicas por ambiente. Actualizar el README con estos valores."
  value       = { for k, inst in aws_instance.env : k => inst.public_ip }
}

output "instance_ids" {
  description = "IDs de instancia por ambiente."
  value       = { for k, inst in aws_instance.env : k => inst.id }
}
