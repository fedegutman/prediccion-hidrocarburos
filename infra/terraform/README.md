# Infraestructura de Fase 1 como código (Terraform)

Recrea la infraestructura AWS de la Fase 1 que vivía en la cuenta borrada. Todo el
código de la aplicación, monitoreo y CI/CD ya está en el repo: esto reconstruye
**solo el estado de la nube**.

## ¿Para qué sirve cada componente?

Explicación en lenguaje llano de las piezas, para entender qué hace cada una:

- **Terraform** — herramienta de *Infrastructure as Code*. En vez de crear los
  recursos a mano por la consola de AWS, los describís en archivos `.tf` y
  Terraform los crea, modifica o destruye por vos. La ventaja clave acá: la infra
  queda **versionada y reproducible**. Si vuelven a borrar la cuenta, un
  `terraform apply` la recrea entera en minutos (que es justo el problema que
  estamos resolviendo).

- **EC2 (Elastic Compute Cloud)** — máquinas virtuales en la nube de AWS. Sobre
  cada una corre, con Docker Compose, el stack completo: la API FastAPI +
  Prometheus + Grafana + Alertmanager + node-exporter. Hay una instancia por
  ambiente (desarrollo, staging, producción).

- **ECR (Elastic Container Registry)** — un repositorio privado de imágenes
  Docker, como un "Docker Hub" propio dentro de AWS. El pipeline de CI buildea la
  imagen de la API y la sube acá; las instancias EC2 la descargan en cada deploy.

- **OIDC Provider + roles IAM** — la forma segura de que GitHub Actions se
  autentique con AWS **sin guardar claves permanentes** en GitHub. AWS confía en
  los tokens efímeros que emite GitHub. Un *rol IAM* es un conjunto de permisos:
  `GithubCIRole` solo puede subir imágenes a ECR, `InstanceCDRole` solo puede
  deployar via SSM (separación de responsabilidades, ADR-004).

- **SSM (Systems Manager)** — servicio de AWS que permite ejecutar comandos dentro
  de las EC2 **sin abrir SSH** (puerto 22 cerrado). El pipeline de CD lo usa para
  correr los pasos del deploy de forma remota.

- **Instance Role / Instance Profile** — la identidad que lleva puesta cada EC2.
  Le permite descargar imágenes de ECR y ser administrada por SSM sin necesidad de
  guardar credenciales dentro del servidor.

- **Security Group** — el firewall de la instancia. Define qué puertos están
  abiertos al exterior (8000 API, 3000 Grafana, 9090 Prometheus, 9093
  Alertmanager, 9100 node-exporter). El 22 (SSH) queda **cerrado** a propósito.

## Qué crea

| Recurso | Detalle | ADR |
|---------|---------|-----|
| OIDC Provider | `token.actions.githubusercontent.com` | ADR-004 |
| `GithubCIRole` | rol OIDC para push a ECR (workflow CI) | ADR-004 |
| `InstanceCDRole` | rol OIDC para deploy via SSM (workflow CD) | ADR-004 |
| `instanceECRDeployRole` + instance profile | rol de las EC2 (pull ECR + SSM) | ADR-004 |
| ECR repo `api` | registry privado de imágenes, con scan-on-push | ADR-003 |
| Security Group | puertos 8000/3000/9090/9093/9100, **sin 22** | ADR-005 |
| 3× EC2 `t2.micro` | tags `tp-development`, `tp-staging`, `tp-prod` | ADR-002 |

## Requisitos previos

1. **AWS CLI con credenciales** de la cuenta nueva:
   ```bash
   aws configure            # access key + secret + region us-east-2
   # o, si usás IAM Identity Center / SSO:
   aws configure sso
   aws sts get-caller-identity   # debe devolver tu cuenta
   ```
2. **Terraform >= 1.6** (instalado).

## Uso

```bash
cd infra/terraform
terraform init
terraform plan      # revisá lo que va a crear
terraform apply     # escribí 'yes' para confirmar
```

Al terminar, mostrá los datos que necesitás:
```bash
terraform output
```

## Después del apply

1. **Cargar secrets en GitHub** (Settings → Secrets and variables → Actions):
   - `AWS_CI_ROLE_ARN`  → `terraform output github_ci_role_arn`
   - `AWS_CD_ROLE_ARN`  → `terraform output github_cd_role_arn`
   - `SLACK_WEBHOOK_URL` → tu Incoming Webhook de Slack
   - `GH_TOKEN`          → PAT con permiso de `repo` (lo usa el CD para clonar)
2. **Actualizar el README raíz** con las IPs nuevas (`terraform output instance_public_ips`).
3. **Disparar el pipeline**: push a `develop` → CI buildea/escanea/pushea a ECR y CD deploya solo.

> Nota: los workflows ya referencian dos secrets separados (`AWS_CI_ROLE_ARN` en
> `CI.yml` y `AWS_CD_ROLE_ARN` en `CD.yml`), respetando la separación de roles del
> ADR-004. Por eso hay que cargar los dos en GitHub.

## Costos / free tier

`t2.micro` es free-tier-eligible, pero el free tier cubre ~750 h/mes (≈ **1 sola
instancia 24/7**). Las 3 corriendo todo el tiempo superan ese límite (~US$17/mes
por las 2 extra). Para ahorrar: `terraform apply` solo cuando las necesites y
`aws ec2 stop-instances` cuando no, o reducí `var.environments` a un ambiente.
