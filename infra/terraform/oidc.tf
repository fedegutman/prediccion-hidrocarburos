# Identity Provider OIDC de GitHub Actions (ADR-004).
# Permite que los workflows asuman roles IAM sin credenciales estáticas.

resource "aws_iam_openid_connect_provider" "github" {
  url            = "https://token.actions.githubusercontent.com"
  client_id_list = ["sts.amazonaws.com"]
  # Thumbprint del CA de GitHub Actions. Desde 2023 AWS valida la cadena TLS
  # de forma nativa y este valor dejó de ser crítico, pero el campo es obligatorio.
  thumbprint_list = ["6938fd4d98bab03faadb97b34396831e3780aea1"]
}
