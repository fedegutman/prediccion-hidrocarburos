# ADR-021: Topología del warehouse en producción

**Fecha**: 2026-06-15
**Estado**: Aceptado

## Contexto

La API REST de solo lectura sobre Gold (ver [ADR-018](ADR-018-api-rest-sobre-gold.md)) necesita, para servir dato real en producción, un **data warehouse Postgres con la capa `gold` poblada** y alcanzable desde el contenedor de la API. Hasta ahora la API en prod respondía `503` en `/produccion` y `/pozos` por no tener warehouse.

La restricción dura es de **recursos**: las instancias EC2 del TP son **t2.micro (1 GB de RAM)** y se apagan por costo. El stack completo de la plataforma de datos (Airflow + Metabase + 2 Postgres) consume **~6 GB medidos**, así que **no entra** en la instancia (ver también la justificación de [ADR-020](ADR-020-gobierno-de-datos.md)). Hay que decidir **dónde y cómo corre el warehouse en producción**.

## Alternativas consideradas

- **Plataforma completa en la misma instancia (resize a t3.large/xlarge)**: levantar todo el `data_platform` (Airflow + Metabase + warehouse) agrandando la instancia a 8–16 GB. Da BI y gobierno vivos en prod, pero **contradice la decisión de costo** de ADR-020, suma ops (Terraform, security groups, puertos) y pisa el territorio del compañero (Airflow/Metabase).

- **Instancia dedicada para la plataforma de datos**: un segundo box right-sized solo para los datos, separado de la API. Es la buena práctica a escala (no co-locar una plataforma pesada con el servicio), pero **cuesta lo mismo que el resize** (igual necesita ~t3.large) y agrega más ops (dos máquinas, redes). Sobredimensionado para el alcance del TP.

- **Postgres manejado fuera de la EC2 (RDS / Railway / Neon)**: el warehouse como servicio gestionado; la t2.micro no se entera. Robusto y sin pelea de RAM. Contra: RDS suma setup de infra (Terraform + security group); Railway/Neon **introducen un proveedor fuera del stack AWS**, inconsistente con el resto del proyecto (todo es EC2/ECR/Terraform).

- **Warehouse colocado en la t2.micro como contenedor magro**: un único Postgres (`gold`) junto a la API y el monitoreo, en el mismo `docker-compose`. La API solo necesita el dato, no el pipeline. Mitigando el RAM (config magra + `mem_limit` + swapfile), entra en 1 GB.

## Decisión

Se corre el warehouse como **contenedor `postgres:16` colocado en la EC2**, dentro del `docker-compose` que ya despliega el CD, con tres mitigaciones por el RAM ajustado (medido: ~374 MB libres en estado estable):

- **Postgres magro**: `shared_buffers=64MB`, `work_mem=4MB`, `maintenance_work_mem=64MB`, `max_connections=20`.
- **`mem_limit: 320m`** en el contenedor → no puede ahogar a la API ni al monitoreo.
- **Swapfile de 1 GB** en la instancia (persistente vía `/etc/fstab`) como colchón ante picos (ej. el restore inicial).

El **puerto no se expone** públicamente; la API lo alcanza por la red interna del compose (host `warehouse`). El `gold` se carga **una sola vez** con `pg_dump` desde el pipeline (que corre local) → restore dentro del contenedor. **Airflow, dbt y Metabase NO se despliegan en prod**: corren en local y se demuestran en el video.

## Consecuencias

**Pros:**
- API sirviendo **gold real** en prod sin agrandar la instancia ni sumar costo.
- Coherente con el stack (todo AWS, mismo `docker-compose` + CD existente).
- No pisa el trabajo del compañero (BI/orquestación quedan local).
- Sin proveedor nuevo.

**Contras / límites:**
- **RAM ajustada**: la convivencia depende del swap; bajo carga alta el warehouse podría swapear (lento, aceptable para demo). No es una topología de producción "real".
- El `gold` de prod es una **copia cargada por dump/restore**, no refrescada por el pipeline en vivo → para actualizarlo hay un procedimiento manual (ver runbook [`data-engineer`](../docs/runbooks/data-engineer.md)).
- **A escala**, la plataforma de datos viviría en su **propia instancia right-sized** (alternativa de instancia dedicada); se difiere por el alcance y el costo del TP.
