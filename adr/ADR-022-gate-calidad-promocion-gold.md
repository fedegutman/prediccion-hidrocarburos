# ADR-022: Gate de calidad en la promoción a Gold (Write-Audit-Publish)

**Fecha**: 2026-06-28
**Estado**: Aceptado

## Contexto

[ADR-019](ADR-019-calidad-de-datos.md) definió la estrategia de calidad (tests dbt + `store_failures` + bloqueo) pero su propia sección de consecuencias ([ADR-019:41](ADR-019-calidad-de-datos.md)) reconoce un gap abierto: **el bloqueo solo vive en el CI**, sobre el fixture chico de `ci/fixtures/bronze_seed.sql`. En la corrida real, el DAG `dbt_transform` hacía un **`dbt build` plano** que materializa `gold.fct_produccion` en el **schema `gold` vivo** (el que leen la API y Metabase) y *después* corre los tests: si un test ERROR falla, dbt frena lo de aguas abajo, pero **la tabla ya quedó escrita en `gold`** y se expone hasta la próxima corrida.

Esto se vuelve crítico de cara a la Fase 3: el feature store y el entrenamiento del modelo van a **consumir `gold`**. Sin un gate de promoción real, un dato roto entrenaría/serviría predicciones inválidas (*garbage in, garbage out*). Hace falta replicar el bloqueo **dentro del DAG**, antes de exponer el dato.

Además, el CI hoy solo tiene un fixture "verde" (datos 100% limpios): prueba que el pipeline **corre**, no que la calidad **detecta** un dato malo. Un test mal escrito que nunca dispara pasaría igual.

## Alternativas consideradas

**Cómo promover Gold:**
- **`dbt build` plano sobre el schema vivo (status quo):** materializa Gold antes de testear → el dato roto queda expuesto. No cumple "bloqueo antes de exponer". Rechazado.
- **Separar `dbt run` y `dbt test` en dos tareas, sobre el schema vivo:** ordena run→test, pero Gold igual se materializa en `gold` antes del test → persiste la ventana de exposición. Mínimo, insuficiente.
- **Write-Audit-Publish: construir y testear en un schema staging y hacer swap solo si pasa (elegida):** `gold` vivo nunca ve dato sin validar; si los tests fallan, queda intacto en su última versión buena.
- **Great Expectations / herramienta de DQ dedicada:** ya descartada en ADR-019 (sobredimensionada; dbt ya cubre las dimensiones sobre los mismos modelos).

**Mecanismo de swap:**
- **Rename de schemas en una transacción (elegido):** `gold` → `gold_old`, `gold_staging` → `gold`, drop `gold_old`. Atómico, una operación para todas las tablas de Gold a la vez, transparente para la API (mismos nombres).
- **Rename tabla por tabla:** más operaciones, ventana inconsistente entre tablas (la fact podría quedar de una versión y una dim de otra).
- **Vistas con puntero (blue/green por views):** indirección extra y los consumidores leerían vistas, no tablas; innecesario para este tamaño.

**Validación en CI:**
- **Solo fixture verde (status quo):** no prueba que el gate detecte. Insuficiente.
- **Agregar un fixture "rojo" que DEBE hacer fallar `dbt build` (elegido):** prueba el detector, no solo el camino feliz.

## Decisión

Promoción **Write-Audit-Publish** en el DAG `dbt_transform`, en cuatro pasos encadenados (`trigger_rule=all_success`):

1. **build_silver** — `dbt build --select silver`: construye las vistas Silver y corre sus tests.
2. **build_gold_staging** — `dbt run --select gold --vars '{gold_schema: gold_staging}'`: materializa Gold en un schema **staging**, no en el vivo.
3. **test_gold_staging** — `dbt test --select gold --vars '{gold_schema: gold_staging}'`: corre los tests de Gold contra el staging.
4. **swap_gold** — solo si todo pasó, **swap atómico** de schemas en una transacción (`gold_staging` → `gold`).

Para habilitarlo, el `+schema` de Gold pasa a ser parametrizable: `+schema: "{{ var('gold_schema', 'gold') }}"`. El **default `gold`** preserva el comportamiento de `dbt build` local y del CI (que no pasan la var).

En CI se agrega el fixture `ci/fixtures/bronze_seed_red.sql` y el job `dbt-tests-red`, que **assertea que `dbt build` falla** sobre datos rotos (año NULL → `not_null`; mes = 13 → `accepted_values`). Queda en `needs` de `build-and-scan`, de modo que un gate que dejó de detectar bloquea el deploy.

## Consecuencias

**Pros:**
- El schema `gold` vivo **nunca expone dato sin validar**: si un test ERROR falla, queda en su última versión buena y el DAG falla (alerta).
- El bloqueo deja de vivir solo en CI: ahora opera **dentro del DAG, con datos reales**, antes de exponer.
- Precondición sólida para Fase 3 (el modelo consume Gold validado).
- El fixture rojo prueba que la calidad **detecta**, no solo que el pipeline corre.
- Cambio no disruptivo: el SQL de los modelos no cambia y el default de la var mantiene local/CI igual.

**Contras / límites:**
- El swap toma un lock `ACCESS EXCLUSIVE` breve sobre los schemas; con consumidores activos puede esperar unos instantes (aceptable en el warehouse local).
- `gold_staging` duplica transitoriamente el storage de Gold durante la construcción.
- La primera corrida (sin `gold` previo) requiere el caso especial de omitir el rename del viejo (resuelto en el DAG).
- No agrega histórico de DQ: `store_failures` sigue sobreescribiendo (gap aún abierto de ADR-019, a resolver aparte).
