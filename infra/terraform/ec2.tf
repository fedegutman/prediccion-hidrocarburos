# Instancias EC2 del stack (ADR-002) + Security Group.
# Una instancia por ambiente. NO se abre el puerto 22: el deploy es via SSM (ADR-005).

resource "aws_security_group" "stack" {
  name        = "${var.project}-stack-sg"
  description = "Puertos del stack (API, Grafana, Prometheus, Alertmanager, node-exporter). Sin SSH."

  dynamic "ingress" {
    for_each = var.ingress_ports
    content {
      description = "Puerto ${ingress.value} del stack"
      from_port   = ingress.value
      to_port     = ingress.value
      protocol    = "tcp"
      cidr_blocks = [var.allowed_cidr]
    }
  }

  # Salida abierta: necesaria para SSM (HTTPS saliente) y docker pull desde ECR.
  egress {
    description = "Todo el trafico saliente"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${var.project}-stack-sg" }
}

# Bootstrap mínimo: deja la instancia lista para que el CD (via SSM) levante el stack.
# El propio script de CD reinstala/asegura estos paquetes, así que esto solo acelera
# el primer deploy. El SSM Agent ya viene preinstalado en Amazon Linux 2.
locals {
  user_data = <<-EOF
    #!/bin/bash
    set -e
    yum update -y
    yum install -y docker git
    systemctl enable --now docker
    systemctl enable --now amazon-ssm-agent
    curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-Linux-x86_64" -o /usr/bin/docker-compose
    chmod +x /usr/bin/docker-compose
  EOF
}

resource "aws_instance" "env" {
  for_each = var.environments

  ami                    = data.aws_ami.amazon_linux_2.id
  instance_type          = var.instance_type
  iam_instance_profile   = aws_iam_instance_profile.instance.name
  vpc_security_group_ids = [aws_security_group.stack.id]
  user_data              = local.user_data

  tags = {
    # El tag Name es el target de los send-command del CD: NO cambiar sin
    # actualizar CD.yml. Producción = 'tp-prod'.
    Name        = each.value
    Environment = each.key
  }
}
