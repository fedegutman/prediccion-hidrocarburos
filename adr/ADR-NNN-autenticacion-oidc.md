# ADR-NNN: Autenticación de GitHub Actions con AWS via OIDC

**Fecha**: 2026-04-23
**Estado**: Aceptado

## Contexto

El pipeline de CI/CD necesita credenciales de AWS para realizar operaciones como autenticarse en ECR, pushear imágenes y ejecutar comandos via SSM. Se debe elegir una forma de otorgar esos permisos a GitHub Actions de forma segura, y definir la granularidad con la que se asignan esos permisos.

## Alternativas consideradas

- **AWS Access Keys (credenciales estáticas)**: crear un usuario IAM con los permisos necesarios y almacenar su `AWS_ACCESS_KEY_ID` y `AWS_SECRET_ACCESS_KEY` como secrets en GitHub Actions. Es el método más simple pero implica gestionar credenciales de larga duración: si se filtran (por ejemplo, en un log o en un fork), permiten acceso a la cuenta AWS hasta que se rotan manualmente.

- **OIDC con un único IAM Role**: GitHub Actions expone un proveedor OIDC que permite a AWS verificar la identidad del workflow sin credenciales estáticas. Se podría usar un solo Role con todos los permisos necesarios (ECR + SSM). Sin embargo, esto viola el principio de mínimo privilegio: el job de CI no necesita permisos de SSM, y el job de CD no necesita permisos de escritura en ECR de la misma forma.

- **OIDC con roles separados por responsabilidad**: misma base que la opción anterior, pero con un Role dedicado por responsabilidad. Cada Role tiene únicamente los permisos que su workflow necesita.

## Decisión

Se utiliza OIDC con dos IAM Roles diferenciados:

- **`GithubCIRole`**: asumido por el workflow de CI. Tiene permisos para autenticarse en ECR, buildear y pushear imágenes, y ejecutar el escaneo de Trivy.
- **`InstanceCDRole`**: asumido por el workflow de CD. Tiene permisos para ejecutar comandos via SSM (`ssm:SendCommand`) sobre las instancias taggeadas como `tp-development`, `tp-staging` y `tp-production`.

Adicionalmente, las instancias EC2 tienen asignado el IAM Instance Role `instanceECRDeployRole`, que les permite hacer `docker pull` desde ECR sin necesidad de credenciales explícitas dentro de la instancia.

El pipeline usa la action `aws-actions/configure-aws-credentials@v4` con `role-to-assume`, que maneja el intercambio de tokens OIDC internamente.

## Consecuencias

**Pros:**
- Sin credenciales de larga duración almacenadas en GitHub
- Las credenciales temporales expiran al finalizar cada job
- La separación de roles por responsabilidad limita el radio de impacto si un workflow se ve comprometido: el CI no puede hacer deploy, y el CD no puede pushear imágenes arbitrarias
- Las instancias EC2 se autentican en ECR via su Instance Role, sin secretos en el sistema operativo

**Contras:**
- Configuración inicial más compleja: requiere crear el Identity Provider OIDC en AWS IAM y configurar múltiples Roles con sus políticas de confianza
- Si la política de confianza de algún Role es incorrecta (por ejemplo, condición de branch mal definida), el pipeline falla con errores de autenticación difíciles de diagnosticar sin acceso a la consola de AWS