# ADR-002: Plataforma de cómputo: Amazon EC2

**Fecha**: 2026-04-19
**Estado**: Aceptado

## Contexto

El sistema necesita una plataforma donde correr el stack contenerizado (API + Prometheus + Grafana + Alertmanager) en tres ambientes: desarrollo, staging y producción. Se debe elegir un servicio de cómputo en AWS que sea compatible con Docker Compose y con el nivel de complejidad del proyecto.

Para esto se usó **Amazon EC2** que permite levantar máquinas virtuales con control total del sistema operativo, sobre las cuales se puede instalar Docker y Docker Compose sin modificaciones. Esto facilita el deploy del stack completo y es compatible con el pipeline de CD via AWS SSM, que ejecuta comandos remotos sin necesidad de acceso SSH.

## Decisión

Se utilizan instancias EC2 `t2.micro` (una por ambiente: `tp-development`, `tp-staging`, `tp-production`) en la región `us-east-2`. El tipo `t2.micro` es suficiente para el volumen de tráfico de esta fase y está incluido en el free tier de AWS.

## Consecuencias

**Pros:**
- Control total sobre el entorno de ejecución
- `t2.micro` cubre los requerimientos de carga de la Fase 1 sin costo adicional (free tier)
- Integración simple con SSM para el deploy automatizado desde GitHub Actions

**Contras:**
- Requiere gestionar el sistema operativo, actualizaciones y seguridad del host manualmente
- Sin auto-scaling automático: ante picos de carga, la instancia no se escala sola
- Si la instancia cae, el servicio cae con ella (sin redundancia a nivel de instancia)