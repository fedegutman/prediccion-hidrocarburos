# ADR-NNN: Deploy remoto a EC2 via AWS SSM

**Fecha**: 2026-04-23
**Estado**: Aceptado

## Contexto

El pipeline de CD necesita ejecutar comandos en las instancias EC2 (instalar Docker, clonar el repositorio, levantar el stack) de forma automatizada desde GitHub Actions. Para eso, requiere algún mecanismo de acceso remoto a las instancias.

## Alternativas consideradas

- **SSH directo**: el método más común para acceso remoto a EC2. Requiere abrir el puerto 22 en el Security Group de cada instancia y almacenar la clave privada SSH como secreto en GitHub Actions (`EC2_SSH_KEY`). Esta fue la primera aproximación evaluada: es directa y fácil de entender, pero exponer el puerto 22 a internet amplía la superficie de ataque. Además, si la clave SSH se filtra, otorga acceso directo a la instancia. Cada nueva instancia requiere generar y distribuir una nueva clave.

- **AWS SSM Session Manager**: servicio administrado de AWS que permite ejecutar comandos en instancias EC2 sin abrir ningún puerto de red. La instancia se comunica con SSM via HTTPS saliente, sin requerir IP pública ni security group permisivo. La autenticación se delega a IAM: GitHub Actions asume el `InstanceCDRole` con permisos SSM, y la instancia tiene el SSM Agent instalado. No se manejan claves SSH.

## Decisión

Se migró de SSH a AWS SSM `send-command` con el documento `AWS-RunShellScript` para ejecutar los pasos del deploy en cada instancia. El pipeline espera la finalización del comando, verifica el status y registra el output en caso de error. No se abre el puerto 22 en ninguna instancia. La clave `EC2_SSH_KEY` que se usó inicialmente fue eliminada de los secrets del repositorio.

La decisión de migrar surgió al configurar el acceso IAM para ECR y SSM: una vez que las instancias tenían el Instance Role y el pipeline tenía el `InstanceCDRole` via OIDC, SSH pasó a ser redundante e innecesario.

## Consecuencias

**Pros:**
- Sin puertos abiertos al exterior: menor superficie de ataque
- Sin claves SSH que gestionar o rotar
- La autenticación se centraliza en IAM, consistente con el resto del acceso a AWS desde el pipeline
- El output del comando queda registrado en CloudWatch Logs automáticamente
- Escala sin fricción a nuevas instancias: solo requieren tener el SSM Agent y el Instance Role

**Contras:**
- Requiere que el SSM Agent esté instalado y activo en las instancias (viene preinstalado en Amazon Linux 2)
- Los comandos remotos via SSM tienen un overhead de latencia mayor que SSH directo
- Si SSM no está disponible (falla del servicio de AWS), el deploy queda bloqueado sin alternativa de acceso directa