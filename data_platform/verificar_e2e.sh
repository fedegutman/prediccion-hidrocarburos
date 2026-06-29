#!/usr/bin/env bash
# Verificación end-to-end del pipeline de la plataforma.
# Confirma que cada eslabón funciona: ingesta -> transformación -> feature store ->
# calidad/point-in-time -> tracking (MLflow) -> inferencia (forecast).
# Requiere el stack levantado:  cd data_platform && docker compose up -d --build
set -uo pipefail

WH=$(docker ps --format '{{.Names}}' | grep warehouse | head -1)
MLFLOW_URL="http://localhost:5500"
fails=0
ok()  { echo "  ✓ $1"; }
bad() { echo "  ✗ $1"; fails=$((fails + 1)); }
q()   { docker exec "$WH" psql -U dwh -d oilgas -tAc "$1" 2>/dev/null; }

echo "=== Verificación end-to-end ==="

# 1) Stack arriba
[ -n "$WH" ] && ok "warehouse arriba ($WH)" || bad "warehouse no encontrado (¿stack levantado?)"
code=$(curl -s -o /dev/null -w '%{http_code}' "$MLFLOW_URL/health")
[ "$code" = "200" ] && ok "MLflow responde" || bad "MLflow no responde (HTTP $code)"

# 2) Ingesta -> Bronze
n=$(q "select count(*) from bronze.produccion")
[ "${n:-0}" -gt 0 ] && ok "Bronze con datos ($n filas)" || bad "Bronze vacío (correr DAG bronze_ingesta)"

# 3) Transformación -> Gold
n=$(q "select count(*) from gold.fct_produccion")
[ "${n:-0}" -gt 0 ] && ok "Gold fct_produccion ($n filas)" || bad "Gold vacío (correr dbt_transform)"

# 4) Feature store (RNF-1)
off=$(q "select count(*) from gold.feat_produccion_offline")
[ "${off:-0}" -gt 0 ] && ok "Feature store offline ($off filas)" || bad "feat_produccion_offline ausente"
onl=$(q "select count(*) from gold.feat_produccion_online")
[ "${onl:-0}" -gt 0 ] && ok "Feature store online ($onl pozos)" || bad "feat_produccion_online ausente"

# 5) Calidad / point-in-time (invariantes clave)
dup=$(q "select count(*) from (select idpozo from gold.feat_produccion_online group by idpozo having count(*)>1) t")
[ "${dup:-1}" = "0" ] && ok "online: una fila por pozo (lookup OK)" || bad "online con pozos duplicados"
leak=$(q "select count(*) from gold.feat_produccion_offline m
          join gold.feat_produccion_offline n
            on n.idpozo = m.idpozo and n.fecha_mes = (m.fecha_mes + interval '1 month')::date
          where m.target_prod_pet_m1 is distinct from n.prod_pet_lag0")
[ "${leak:-1}" = "0" ] && ok "target point-in-time correcto (sin data leakage)" || bad "target desalineado ($leak filas)"

# 6) Tracking + registry: modelo en Production
prod=$(curl -s "$MLFLOW_URL/api/2.0/mlflow/registered-models/get?name=forecast_prod_pet" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print('Production' in [a['alias'] for a in d['registered_model'].get('aliases', [])])
except Exception:
    print('False')" 2>/dev/null)
[ "$prod" = "True" ] && ok "MLflow: modelo forecast_prod_pet en Production" || bad "modelo/alias Production ausente (correr el tracer)"

# 7) Inferencia -> fct_forecast
n=$(q "select count(*) from gold.fct_forecast")
[ "${n:-0}" -gt 0 ] && ok "Predicciones en gold.fct_forecast ($n)" || bad "fct_forecast vacío (correr el tracer)"

echo ""
[ "$fails" = "0" ] && echo "RESULTADO: TODO OK end-to-end ✅" || echo "RESULTADO: $fails eslabón(es) fallando ⚠️"
exit "$fails"
