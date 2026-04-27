# ADR-013: Decisiones de diseño del dashboard de Grafana

**Fecha**: 2026-04-16
**Estado**: Aceptado

## Contexto

El dashboard de monitoreo requiere múltiples decisiones de diseño sobre qué métricas mostrar, cómo organizarlas y cómo calcularlas. Cada decisión tiene implicancias sobre la utilidad operativa del dashboard y la fidelidad de los KPIs del PRD.

## Decisiones

### 1. Error rate: solo errores 5xx

El panel "Error Rate %" mide únicamente errores HTTP 5xx (errores del servidor), excluyendo los 4xx (errores del cliente).

**Justificación**: un 403 por API key incorrecta es un error del cliente, no una falla del servicio. Incluir 4xx en el error rate distorsionaría el KPI, mezclando comportamiento esperado (uso incorrecto de la API) con fallos reales del sistema. Los errores 4xx tienen su propio indicador dedicado (`TasaAutenticacionFallida`) porque son un indicador de seguridad, no de estabilidad.

### 2. Provisioning del dashboard vía YAML y JSON

El dashboard y sus datasources se configuran mediante archivos de provisioning en `monitoring/grafana/provisioning/`, no a través de la UI de Grafana.

**Justificación**: la configuración manual en la UI no es reproducible — si se pierde el volumen de Grafana, el dashboard desaparece. El provisioning por código garantiza que el dashboard se recrea automáticamente al levantar el stack, es versionable en git y puede revisarse en un PR como cualquier otro cambio.

### 3. Organización en 4 filas temáticas

El dashboard se organiza en cuatro secciones: Disponibilidad, Latencia, Tráfico y Métricas de Negocio, y Sistema.

**Justificación**: agrupar paneles por tema permite leer el dashboard de forma progresiva — primero el estado general del servicio, luego el rendimiento, luego el tráfico, y finalmente el estado del host. Facilita la identificación rápida del área con problemas durante un incidente.

### 4. Ventana de 5 minutos para rate()

Todas las queries que usan `rate()` emplean una ventana de `[5m]`.

**Justificación**: una ventana corta (1m) genera demasiado ruido ante picos puntuales. Una ventana larga (15m) suaviza demasiado y oculta degradaciones recientes. 5 minutos es el balance estándar en la industria para servicios web de baja a media carga.

### 5. Threshold de latencia p95 alineado al KPI del PRD

El panel de latencia p95 usa un threshold en 5 segundos, que cambia el color del panel a rojo cuando se supera.

**Justificación**: el PRD define explícitamente que el tiempo de respuesta del pronóstico debe ser menor a 5 segundos. El threshold visual en el dashboard refleja ese mismo límite, haciendo que el incumplimiento del KPI sea inmediatamente visible sin necesidad de interpretar el valor numérico.

### 6. Métricas del host vía node-exporter

El dashboard incluye una sección de métricas del sistema (CPU, memoria, I/O de disco) obtenidas de node-exporter, además de las métricas propias de la API.

**Justificación**: las métricas de la API solas no permiten distinguir si un problema de latencia se debe al código o a la infraestructura. Tener CPU y memoria del host en el mismo dashboard permite correlacionar degradación del servicio con saturación de recursos sin cambiar de herramienta.
