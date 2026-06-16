# ADR-019: Plataforma de gobierno de datos

**Fecha**: 2026-06-15
**Estado**: Aceptado

## Contexto

La adenda exige una plataforma de gobierno de datos que permita ver:
- Los workflows de extracción de datos
- Los datos en el data warehouse
- La última vez que los datos fueron actualizados
- Lineage a nivel tabla

La herramienta recomendada es DataHub.

## Alternativas consideradas

**1. DataHub**
- Plataforma dedicada de gobierno de datos
- Lineage a nivel tabla y columna
- Catálogo centralizado con descripciones, owners y tags
- Integración nativa con Airflow y dbt via ingestion recipes
- Requiere 7+ contenedores (Kafka, Zookeeper, Elasticsearch, MySQL, GMS, frontend)
- Mínimo 8GB de RAM para correr el stack completo
- Alta complejidad de setup y mantenimiento

**2. dbt docs + Airflow**
- dbt docs → lineage a nivel tabla y columna, catálogo de modelos y columnas
- Airflow UI → workflows de extracción, historial de runs, última actualización
- Ya integrado en el stack existente, sin contenedores adicionales
- Se levanta automáticamente con `docker compose up -d`
- Liviano y portable

**3. OpenMetadata**
- Similar a DataHub pero con menor adopción en la industria
- Requiere igualmente varios contenedores adicionales
- No fue visto en clase ni en tutoría

## Decisión

Se utiliza **dbt docs + Airflow** como plataforma de gobierno de datos.

## Justificación

DataHub es la herramienta recomendada por la adenda y fue evaluada durante el desarrollo.
Sin embargo, su arquitectura requiere un mínimo de 8GB de RAM para correr los servicios
necesarios (Kafka, Zookeeper, Elasticsearch, MySQL, GMS y frontend). Las instancias EC2
t2.micro del stack actual tienen 1GB de RAM, insuficiente para levantar DataHub.
Crear una instancia dedicada con los recursos necesarios (t3.xlarge, 16GB RAM) implicaría
un costo adicional de ~$0.20/hora que no está justificado para el scope del TP.

La combinación de dbt docs + Airflow cubre todos los requerimientos de la adenda
sin infraestructura adicional, corriendo en el mismo stack de Docker Compose existente:

- **Workflows de extracción** → Airflow UI (`http://localhost:8080`) muestra DAGs, historial y logs
- **Datos en el warehouse** → dbt docs muestra tablas, columnas y descripciones
- **Última actualización** → Airflow UI muestra el último run exitoso de cada DAG
- **Lineage a nivel tabla** → dbt docs muestra el grafo completo Bronze → Silver → Gold

## Consecuencias

**Pros:**
- Sin infraestructura adicional ni costo extra
- Lineage siempre actualizado con cada `dbt build`
- No requiere mantenimiento adicional
- Portable — corre igual en local y en EC2

**Contras:**
- No hay una única UI centralizada de gobierno — requiere navegar entre Airflow y dbt docs
- En producción real con múltiples equipos se migraría a DataHub o similar