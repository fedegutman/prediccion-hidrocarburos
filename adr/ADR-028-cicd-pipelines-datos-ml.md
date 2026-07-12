# ADR-028: CI/CD de los pipelines de datos/ML (validación en CI + ejecución local)

**Fecha**: 2026-07-12
**Estado**: Aceptado

## Contexto

La Adenda 3 pide que **los pipelines de procesamiento se desplieguen mediante un pipeline de CI/CD**. Al mismo tiempo, la propia adenda aclara que **el trabajo se entrega sin servicio live en producción** y que la Fase 3 se demuestra en un video corriendo en local.

El contexto de infraestructura del proyecto condiciona la decisión:
- El cómputo de producción es una **EC2 t2.micro (1 GB RAM)**; no alcanza para el stack de la plataforma (Airflow CeleryExecutor: scheduler + worker + triggerer + apiserver + redis + 2 Postgres + MLflow + Metabase).
- Ya existe una decisión tomada en el [ADR-021](ADR-021-topologia-warehouse-produccion.md) de correr el **pipeline (Airflow + dbt) y el BI en local** por costo/recursos, dejando en la EC2 solo la API + un warehouse `gold` colocado.
- El pipeline ya es **infraestructura como código** (los DAGs y `docker-compose.yaml` versionados) y ya está **validado por CI**.

La decisión, entonces, no es *si* hay CI/CD para los pipelines, sino **qué alcance** tiene ese CI/CD dado que no hay servicio live.

## Alternativas consideradas

**1. CI valida y gatea + despliegue como IaC ejecutado en local (elegida).**
- CI (`.github/workflows/CI.yml`) corre en todo push/PR sobre los pipelines: `dbt-tests` (build de Silver/Gold + tests de calidad), `dbt-tests-red` (verifica que datos rotos **fallan** el gate, ADR-022), `ml-lint` (ruff + `py_compile` del training DAG y del job de ML) y `pages` (genera y publica el catálogo dbt a GitHub Pages). El build de imagen se **gatea** con estos jobs (`build-and-scan.needs`).
- El "despliegue" del pipeline es **IaC versionada**: `docker compose up` levanta el stack reproduciblemente desde el código en git; los DAGs se recargan al actualizarse. No hay deploy a un runtime cloud porque no hay servicio live.
- Pros: cumple el espíritu del requisito (los pipelines pasan por un pipeline de CI/CD que los valida y gatea antes de integrarse), es **reproducible y portable**, y es coherente con la entrega "sin servicio live" y con ADR-021. Costo cero.
- Contra: no hay un job de CD que "empuje" el pipeline a un entorno corriendo 24/7 (no existe tal entorno por decisión de scope).

**2. Deploy del stack completo de la plataforma a la nube por CD (como la API).**
- Un job de CD que despliega Airflow + warehouse + MLflow a EC2 vía SSM, análogo al de la API.
- Contra: **inviable en la t2.micro** (RAM); requeriría infra dedicada (p. ej. t3.large/xlarge) con **costo recurrente** no justificado para el scope; contradice ADR-021; y la infra AWS está en reconstrucción. Alto esfuerzo y costo para un servicio que la adenda **no** exige live.

**3. Orquestación gestionada (Amazon MWAA / Cloud Composer / Astronomer).**
- Airflow administrado, desplegable por CI/CD "de fábrica".
- Contra: costo mensual fijo alto (MWAA ~USD 350+/mes), otra plataforma que aprender/operar, y rompe la portabilidad "un solo docker compose" que usan compañeros y profesores. Desproporcionado para el TP.

## Decisión

El CI/CD de los pipelines de datos/ML se define como **validación y gating en CI + despliegue como IaC ejecutado en local**:

- **CI** valida y gatea los pipelines en cada push/PR (`dbt-tests`, `dbt-tests-red`, `ml-lint`, `pages`); un fallo bloquea la integración.
- **Despliegue** = `docker compose` sobre el código versionado (los DAGs se recargan solos); **sin deploy a un runtime cloud**, por decisión de scope (sin servicio live) y de costo/recursos (ADR-021).
- En el video se demuestra el pipeline corriendo en local de punta a punta.

Si en el futuro hubiera presupuesto para un entorno live, agregar un job de CD que despliegue el stack (alternativa 2) es un cambio incremental sobre esta base ya validada por CI.

## Consecuencias

**Pros:**
- Cubre el requisito en su parte verificable y de mayor valor: **ningún cambio en los pipelines se integra sin pasar por CI** (tests de datos, gate rojo, lint, catálogo).
- Reproducible, portable y sin costo; coherente con ADR-021 y con la entrega sin servicio live.
- Deja el camino allanado para un CD real si cambia el scope.

**Contras / límites:**
- No hay un entorno del pipeline corriendo de forma permanente ni un job de CD que lo despliegue; la ejecución es on-demand en local.
