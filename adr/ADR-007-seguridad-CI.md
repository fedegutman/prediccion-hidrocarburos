# ADR-007: Escaneo de vulnerabilidades en imágenes Docker

**Fecha**: 2026-04-21
**Estado**: Aceptado

## Contexto

Las imágenes Docker pueden contener vulnerabilidades conocidas en las dependencias del sistema operativo o de las librerías instaladas. Es necesario detectarlas antes de que lleguen a producción.

## Alternativas consideradas

- **Snyk**: herramienta popular de escaneo de vulnerabilidades, tiene integración con GitHub Actions. Requiere cuenta externa y token de autenticación adicional.

- **Docker Scout**: herramienta oficial de Docker para escaneo de imágenes. Integrada en Docker Desktop pero con funcionalidad limitada en el tier gratuito.

- **Trivy**: herramienta open source de Aqua Security, sin dependencias externas ni tokens adicionales. Soporta escaneo de imágenes Docker, filesystems y repositorios. Tiene acción oficial para GitHub Actions.

## Decisión

Se utiliza Trivy en el pipeline de CI/CD. El escaneo se realiza sobre la imagen buildeada antes de pushearla al registry. El reporte de vulnerabilidades se guarda como archivo Markdown en el repositorio. Si se detectan vulnerabilidades CRITICAL, el pipeline falla y la imagen no se pushea.

El escaneo usa `ignore-unfixed: true`: el pipeline solo falla ante vulnerabilidades CRITICAL que **tienen un fix disponible** (accionables). Las vulnerabilidades sin parche publicado (estado `fix_deferred`/`affected`, sin versión corregida) se siguen listando en el reporte pero no bloquean el build, porque no existe remediación posible vía actualización de dependencias y bloquearlas dejaría el deploy indefinidamente trabado sin acción correctiva. Un ejemplo concreto: CVEs de `perl-base` heredados de la imagen base `python:3.12-slim` (Debian) que Debian aún no parchea.

## Consecuencias

**Pros:**
- Open source, sin tokens ni cuentas externas
- Integración nativa con GitHub Actions
- El reporte queda versionado en el repositorio
- Bloquea imágenes vulnerables antes de llegar a producción

**Contras:**
- Agrega tiempo al pipeline por el doble escaneo (reporte + verificación)
- Puede generar falsos positivos que requieran revisión manual