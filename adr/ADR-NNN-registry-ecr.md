# ADR-NNN: Registry de imágenes Docker: Amazon ECR
 
**Fecha**: 2026-04-19
**Estado**: Aceptado
 
## Contexto
 
El pipeline de CI necesita un registro privado donde almacenar las imágenes Docker construidas para cada rama (`develop`, `staging`, `main`). Las instancias EC2 deben poder descargar esas imágenes durante el deploy. Se requiere un registro privado, seguro y accesible desde el pipeline de GitHub Actions y desde las instancias EC2.
 
## Alternativas consideradas
 
- **GitHub Container Registry (ghcr.io)**: registro privado integrado con GitHub. No requiere infraestructura adicional y la autenticación desde GitHub Actions es nativa. Sin embargo, las instancias EC2 necesitarían un token de GitHub con permisos de lectura para hacer `docker pull`, lo que agrega un secreto adicional a gestionar en las instancias.
- **Docker Hub**: registro público con tier gratuito limitado. El tier gratuito permite solo un repositorio privado y tiene rate limits en el pull de imágenes, lo que puede generar fallos intermitentes en el deploy.
- **Amazon ECR (Elastic Container Registry)**: registro privado de AWS. La autenticación desde EC2 se realiza mediante el IAM Role de la instancia, sin necesidad de credenciales adicionales. La autenticación desde GitHub Actions se realiza con el mismo IAM Role que ya se usa para SSM, mediante OIDC. Las imágenes quedan en la misma región que las instancias (`us-east-2`), eliminando latencia de red en el pull.

## Decisión
 
Se utiliza Amazon ECR como registro privado de imágenes. El pipeline de CI buildea la imagen, la escanea con Trivy y la pushea a ECR tageada con el nombre de la rama. El pipeline de CD referencia esa imagen en el deploy via la variable `API_IMAGE` inyectada en el `.env` de cada instancia.
 
## Consecuencias
 
**Pros:**
- Autenticación integrada con IAM: las instancias EC2 y GitHub Actions (via OIDC) no necesitan credenciales adicionales
- Sin rate limits en el pull desde instancias EC2 en la misma región
- Mismo ecosistema AWS que el resto de la infraestructura
- Soporte nativo para escaneo de vulnerabilidades (complementa el escaneo con Trivy en CI)
**Contras:**
- Requiere renovar el token de autenticación de ECR cada 12 horas (`ecr get-login-password`), lo que el pipeline de CD maneja automáticamente pero agrega un paso
- Si se abandona AWS como proveedor, el registry debe migrarse