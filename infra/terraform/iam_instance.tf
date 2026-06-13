# IAM Instance Role de las EC2 (ADR-004: instanceECRDeployRole).
# Permite a cada instancia:
#   - hacer docker pull desde ECR sin credenciales explícitas
#   - ser administrada por SSM (recibir los send-command del CD)

data "aws_iam_policy_document" "ec2_assume_role" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "instance" {
  name               = "instanceECRDeployRole"
  assume_role_policy = data.aws_iam_policy_document.ec2_assume_role.json
}

# Permite que la instancia sea target de SSM (send-command, Session Manager).
resource "aws_iam_role_policy_attachment" "instance_ssm" {
  role       = aws_iam_role.instance.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

# Permite docker pull desde ECR (solo lectura).
resource "aws_iam_role_policy_attachment" "instance_ecr" {
  role       = aws_iam_role.instance.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
}

resource "aws_iam_instance_profile" "instance" {
  name = "instanceECRDeployProfile"
  role = aws_iam_role.instance.name
}
