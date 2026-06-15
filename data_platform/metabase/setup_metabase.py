"""
Configuracion inicial automatica de Metabase para la Plataforma de Hidrocarburos.
Crea el usuario admin, conecta al warehouse y genera los dashboards de produccion.
Se ejecuta una sola vez; si Metabase ya tiene setup, sale sin hacer nada.
"""
import os
import sys
import time

import requests

MB_HOST = os.environ.get("MB_HOST", "http://metabase:3000")
MB_ADMIN_EMAIL = os.environ.get("MB_ADMIN_EMAIL", "admin@oilgas.com")
MB_ADMIN_PASSWORD = os.environ.get("MB_ADMIN_PASSWORD", "Admin1234!")
MB_ADMIN_FIRST_NAME = os.environ.get("MB_ADMIN_FIRST_NAME", "Admin")
MB_ADMIN_LAST_NAME = os.environ.get("MB_ADMIN_LAST_NAME", "Oilgas")
MB_SITE_NAME = os.environ.get("MB_SITE_NAME", "Plataforma Hidrocarburos")
PG_HOST = os.environ.get("PG_HOST", "warehouse")
PG_PORT = int(os.environ.get("PG_PORT", "5432"))
PG_DB = os.environ.get("PG_DB", "oilgas")
PG_USER = os.environ.get("PG_USER", "dwh")
PG_PASSWORD = os.environ.get("PG_PASSWORD", "dwh")

QUERY_PRODUCCION_POR_MES = (
    "SELECT dt.fecha_mes, "
    "SUM(fp.prod_pet) as total_petroleo, "
    "SUM(fp.prod_gas) as total_gas, "
    "SUM(fp.prod_agua) as total_agua "
    "FROM gold.fct_produccion fp "
    "JOIN gold.dim_tiempo dt ON fp.tiempo_sk = dt.tiempo_sk "
    "GROUP BY 1 ORDER BY 1"
)

QUERY_TOP_EMPRESAS = (
    "SELECT de.id_empresa, "
    "SUM(fp.prod_pet) as total_petroleo, "
    "SUM(fp.prod_gas) as total_gas "
    "FROM gold.fct_produccion fp "
    "JOIN gold.dim_empresa de ON fp.empresa_sk = de.empresa_sk "
    "GROUP BY 1 ORDER BY 2 DESC LIMIT 10"
)

QUERY_PRODUCCION_POR_CUENCA = (
    "SELECT da.cuenca, "
    "SUM(fp.prod_pet) as total_petroleo, "
    "SUM(fp.prod_gas) as total_gas "
    "FROM gold.fct_produccion fp "
    "JOIN gold.dim_area da ON fp.area_sk = da.area_sk "
    "GROUP BY 1 ORDER BY 2 DESC"
)

def wait_for_metabase():
    print("Esperando que Metabase este disponible...")
    for intento in range(60):
        try:
            r = requests.get(f"{MB_HOST}/api/health", timeout=5)
            if r.status_code == 200 and r.json().get("status") == "ok":
                print("Metabase disponible.")
                return
        except requests.exceptions.RequestException:
            pass
        time.sleep(5)
        print(f"  intento {intento + 1}/60...")
    print("ERROR: Metabase no respondio en tiempo.")
    sys.exit(1)


def get_setup_token():
    r = requests.get(f"{MB_HOST}/api/session/properties", timeout=10)
    r.raise_for_status()
    return r.json().get("setup-token")


def setup_metabase(setup_token):
    # Las versiones nuevas de Metabase ignoran/rechazan la base embebida en el
    # payload de /api/setup; aca solo se crea el usuario admin y la conexion al
    # warehouse se da de alta aparte en create_database().
    payload = {
        "token": setup_token,
        "user": {
            "email": MB_ADMIN_EMAIL,
            "password": MB_ADMIN_PASSWORD,
            "first_name": MB_ADMIN_FIRST_NAME,
            "last_name": MB_ADMIN_LAST_NAME,
            "site_name": MB_SITE_NAME,
        },
        "prefs": {
            "allow_tracking": False,
            "site_name": MB_SITE_NAME,
        },
    }
    r = requests.post(f"{MB_HOST}/api/setup", json=payload, timeout=30)
    if r.status_code not in (200, 201):
        print(f"ERROR en setup: {r.status_code} {r.text}")
        sys.exit(1)
    print("Setup de Metabase completado.")
    return r.json().get("id")


def create_database(session_token):
    """Da de alta la conexion al warehouse Postgres (schema gold) y devuelve su id."""
    headers = {"X-Metabase-Session": session_token}
    payload = {
        "name": "DWH Warehouse",
        "engine": "postgres",
        "details": {
            "host": PG_HOST,
            "port": PG_PORT,
            "dbname": PG_DB,
            "user": PG_USER,
            "password": PG_PASSWORD,
            "schema-filters-type": "inclusion",
            "schema-filters-patterns": "gold",
        },
        "auto_run_queries": True,
        "is_full_sync": True,
    }
    r = requests.post(f"{MB_HOST}/api/database", json=payload, headers=headers, timeout=30)
    if r.status_code not in (200, 201, 202):
        print(f"ERROR creando la base: {r.status_code} {r.text}")
        sys.exit(1)
    db_id = r.json()["id"]
    print(f"Base 'DWH Warehouse' creada con id={db_id}.")
    requests.post(f"{MB_HOST}/api/database/{db_id}/sync_schema", headers=headers, timeout=30)
    time.sleep(8)
    return db_id


def create_card(session_token, db_id, name, query, display="bar"):
    headers = {"X-Metabase-Session": session_token}
    payload = {
        "name": name,
        "display": display,
        "dataset_query": {
            "type": "native",
            "native": {"query": query},
            "database": db_id,
        },
        "result_metadata": [],
        "visualization_settings": {},
    }
    r = requests.post(f"{MB_HOST}/api/card", json=payload, headers=headers, timeout=30)
    if r.status_code not in (200, 202):
        print(f"AVISO: no se pudo crear la card '{name}': {r.status_code}")
        return None
    card_id = r.json().get("id")
    print(f"Card '{name}' creada con id={card_id}.")
    return card_id


def create_dashboard(session_token, name, card_ids):
    headers = {"X-Metabase-Session": session_token}
    r = requests.post(
        f"{MB_HOST}/api/dashboard",
        json={"name": name},
        headers=headers,
        timeout=10,
    )
    if r.status_code not in (200, 202):
        print(f"AVISO: no se pudo crear el dashboard '{name}': {r.status_code}")
        return
    dashboard_id = r.json()["id"]
    # Metabase nuevo no acepta POST /dashboard/{id}/cards: las cards se mandan
    # juntas en un PUT /dashboard/{id} bajo la clave "dashcards".
    dashcards = []
    for idx, card_id in enumerate(c for c in card_ids if c is not None):
        dashcards.append({
            "id": -(idx + 1),
            "card_id": card_id,
            "row": idx * 7,
            "col": 0,
            "size_x": 24,
            "size_y": 7,
        })
    requests.put(
        f"{MB_HOST}/api/dashboard/{dashboard_id}",
        json={"dashcards": dashcards},
        headers=headers,
        timeout=30,
    )
    print(f"Dashboard '{name}' creado con id={dashboard_id}.")


def main():
    wait_for_metabase()
    setup_token = get_setup_token()
    if not setup_token:
        print("Metabase ya esta configurado, saltando setup.")
        sys.exit(0)
    session_token = setup_metabase(setup_token)
    db_id = create_database(session_token)
    card1 = create_card(session_token, db_id, "Produccion por mes", QUERY_PRODUCCION_POR_MES, "line")
    card2 = create_card(session_token, db_id, "Top 10 empresas por produccion", QUERY_TOP_EMPRESAS, "bar")
    card3 = create_card(session_token, db_id, "Produccion por cuenca", QUERY_PRODUCCION_POR_CUENCA, "bar")
    create_dashboard(session_token, "Produccion de Hidrocarburos", [card1, card2, card3])
    print("Configuracion de Metabase finalizada.")


if __name__ == "__main__":
    main()