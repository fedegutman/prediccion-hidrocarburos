# Runbook — Data Analyst / Usuario de BI: Consultar producción y validar antes de reportar

**Rol:** Data Analyst / Usuario de BI (perfil de negocio).
**Última actualización:** 2026-06-15.

## Propósito y disparador
Obtener y **validar** los números de producción de hidrocarburos **antes de usarlos
en un reporte o una decisión** (planificación, presupuesto, presentación a dirección).

**Disparador:** pedido de un reporte/análisis, o necesidad de un número de producción
para una decisión.

## Rol/dueño y prerrequisitos
- **Quién lo corre:** el Data Analyst / usuario de planificación.
- **Accesos/insumos:** la **API key** (header `X-API-Key`) para la API REST, o acceso al dashboard de **Metabase**.
- **Herramientas:** API REST (`/api/v1/produccion`, `/api/v1/pozos`) o Metabase (dashboard "Producción de Hidrocarburos").

## Pasos
1. **Elegir la fuente:** dashboard de Metabase (visual) o API REST (programático).
2. **Consultar el dato.** Por API:
   ```bash
   curl -H "X-API-Key: <tu-key>" "http://<host>:8000/api/v1/produccion?anio=2024&limit=50"
   ```
   O en Metabase, abrir el dashboard "Producción de Hidrocarburos".
3. **Verificar la frescura:** hasta qué período hay datos cargados (no asumir que el último mes calendario está disponible).
4. **Comparar contra un control** conocido (ej. un total ya validado de un período anterior) antes de publicar.

## Validación
- La respuesta trae los campos esperados, con números **no nulos y no negativos** para el período.
- El total coincide en orden de magnitud con el período de control.
- Si el dato parece raro (caídas bruscas, ceros inesperados), **no reportarlo** → escalar.

## Si algo falla
- **API devuelve `503`:** el warehouse no está disponible (ej. en prod hasta que la base esté deployada). Avisar al equipo de datos; **no** usar números viejos como si fueran actuales.
- **`403`:** API key inválida/faltante → pedir o renovar la key.
- **Número sospechoso:** escalar al **Data Engineer** (puede ser dato de fuente sin rectificar → backfill, ver `data-engineer.md`).

## Consideraciones no funcionales
- **Frescura:** no reportar sobre dato desactualizado sin aclararlo.
- **Consistencia:** usar la **misma fuente de verdad** (`gold`) para que API y BI den el mismo número.
- **Latencia:** las consultas deben responder en segundos (RNF del PRD: < 5 s).
- **Privacidad:** datos públicos, sin PII.

## Decisiones explícitas (justificadas)
**Funcional — las métricas se definen una sola vez en `gold` (no en cada herramienta):**
Se decide que los agregados de negocio salgan de `gold` (modelo estrella), no recalculados ad-hoc en cada reporte/herramienta. Desde los incentivos del analyst, esto garantiza que **el número que reporto coincide con el que ve cualquier otro** (API, BI, dirección) y evita el "cada uno tiene su número", que destruye la confianza en los datos.

**No funcional — frescura visible antes de reportar (no usar dato más viejo que el último período cargado sin aclararlo):**
Se decide chequear y comunicar la frescura del dato. Desde los incentivos del analyst, reportar un número **desactualizado sin aclararlo** es peor que demorar: una decisión de planificación sobre dato viejo puede salir cara, y la responsabilidad por la veracidad recae en quien reporta.
