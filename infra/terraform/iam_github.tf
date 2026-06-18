# Roles IAM asumidos por GitHub Actions via OIDC (ADR-004).
# Se mantienen DOS roles separados por responsabilidad (mínimo privilegio):
#   - GithubCIRole:  login + push de imágenes a ECR (workflow CI).
#   - InstanceCDRole: ejecutar comandos via SSM sobre las EC2 (workflow CD).
# El CI no puede deployar y el CD no puede pushear imágenes arbitrarias.

# --- Política de confianza compartida (OIDC) ---
# Se restringe al repositorio. Se usa wildcard de ref porque el evento
# workflow_run del CD complica fijar la rama; la separación de privilegios
# se garantiza por las políticas de permisos, no por la rama (ver ADR-004).
data "aws_iam_policy_document" "github_assume_role" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["repo:${var.github_repo}:*"]
    }
  }
}

# ============================================================
# GithubCIRole — build + push a ECR
# ============================================================
resource "aws_iam_role" "github_ci" {
  name               = "GithubCIRole"
  assume_role_policy = data.aws_iam_policy_document.github_assume_role.json
}

data "aws_iam_policy_document" "ci_ecr" {
  # Token de autenticación de ECR (debe ser sobre "*").
  statement {
    sid       = "EcrAuthToken"
    effect    = "Allow"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }

  # Push/pull de imágenes, acotado al repositorio "api".
  statement {
    sid    = "EcrPushPull"
    effect = "Allow"
    actions = [
      "ecr:BatchCheckLayerAvailability",
      "ecr:GetDownloadUrlForLayer",
      "ecr:BatchGetImage",
      "ecr:PutImage",
      "ecr:InitiateLayerUpload",
      "ecr:UploadLayerPart",
      "ecr:CompleteLayerUpload",
    ]
    resources = [aws_ecr_repository.api.arn]
  }
}

resource "aws_iam_role_policy" "ci_ecr" {
  name   = "ci-ecr-push"
  role   = aws_iam_role.github_ci.id
  policy = data.aws_iam_policy_document.ci_ecr.json
}

# ============================================================
# InstanceCDRole — deploy via SSM
# ============================================================
resource "aws_iam_role" "github_cd" {
  name               = "InstanceCDRole"
  assume_role_policy = data.aws_iam_policy_document.github_assume_role.json
}

data "aws_iam_policy_document" "cd_ssm" {
  # ECR: el CD se loguea para resolver el registry, pero no pushea.
  statement {
    sid       = "EcrLogin"
    effect    = "Allow"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }

  # SendCommand acotado a las instancias del proyecto (por tag Name) y al documento.
  statement {
    sid       = "SsmSendCommandInstances"
    effect    = "Allow"
    actions   = ["ssm:SendCommand"]
    resources = ["arn:aws:ec2:${var.aws_region}:${local.account_id}:instance/*"]
    condition {
      test     = "StringEquals"
      variable = "ssm:resourceTag/Name"
      values   = values(var.environments)
    }
  }

  statement {
    sid       = "SsmSendCommandDocument"
    effect    = "Allow"
    actions   = ["ssm:SendCommand"]
    resources = ["arn:aws:ssm:${var.aws_region}::document/AWS-RunShellScript"]
  }

  # Lectura del estado del comando (necesario para el polling del CD).
  statement {
    sid    = "SsmReadInvocations"
    effect = "Allow"
    actions = [
      "ssm:ListCommandInvocations",
      "ssm:GetCommandInvocation",
      "ssm:DescribeInstanceInformation",
    ]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "cd_ssm" {
  name   = "cd-ssm-deploy"
  role   = aws_iam_role.github_cd.id
  policy = data.aws_iam_policy_document.cd_ssm.json
}
