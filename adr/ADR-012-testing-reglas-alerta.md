# ADR-012: Testing de reglas de alerta con promtool

**Fecha**: 2026-04-16
**Estado**: Aceptado

## Contexto

Las reglas de alerta de Prometheus son código declarativo en YAML que define condiciones críticas del sistema (servicio caído, latencia alta, error rate alto). Una regla mal escrita podría no disparar ante un incidente real, o disparar en falso generando ruido operativo. Se necesita una estrategia para validar que las reglas funcionan correctamente de forma automatizada.

## Alternativas consideradas

- **Tests manuales**: detener la API y verificar que la alerta llega a Slack. Funciona para validación inicial pero no es reproducible, es lento (requiere esperar minutos por el `for` de cada alerta y el `resolve_timeout`) y no puede correr en CI.

- **Tests de integración con stack completo**: levantar Prometheus, Alertmanager y la API en CI y disparar condiciones reales. Es el test más completo pero rompe el principio de CI rápido — cada test esperaría minutos en tiempo real para que las alertas disparen.

- **`promtool test rules`**: herramienta oficial de Prometheus para unit testear reglas de alerta. Permite definir series de métricas sintéticas y verificar que las alertas disparen o no disparen en condiciones simuladas. No requiere levantar ningún servicio y corre en menos de 1 segundo.

## Decisión

Se utiliza `promtool test rules` para testear las reglas de alerta de forma automatizada. Los tests se definen en `monitoring/prometheus/tests/alerts_test.yml` y corren en CI con cada PR.

Cada alerta tiene al menos dos tests:
- Un test que verifica que **dispara** cuando la condición se cumple
- Un test que verifica que **no dispara** en condiciones normales (evita falsos positivos)

## Consecuencias

**Pros:**
- Tests corren en < 1 segundo, sin levantar ningún servicio
- Detecta errores en expresiones PromQL antes de que lleguen a producción
- Se integra naturalmente en CI junto a los tests de la API
- Es la herramienta oficial de Prometheus — no agrega dependencias externas

**Contras:**
- No testea el pipeline completo
- Las anotaciones con valores dinámicos (ej. porcentajes calculados) requieren hardcodear el valor esperado, lo que hace el test frágil si cambia la expresión PromQL
