from fastapi import FastAPI
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.forecast.routes import router as forecast_router
from app.limiter import limiter
from app.metrics.system import MetricsMiddleware, metrics_app
from app.pozos.routes import router as pozos_router
from app.produccion.routes import router as produccion_router
from app.wells.routes import router as wells_router

app = FastAPI(
    title="Oil & Gas Forecast API",
    version="1.1.0",
    description=(
        "API REST para consultar producción y pozos reales del data warehouse "
        "(capa gold), además del pronóstico de producción."
    ),
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(MetricsMiddleware)
app.mount("/metrics", metrics_app)

app.include_router(forecast_router, prefix="/api/v1", tags=["Pronóstico"])
app.include_router(wells_router, prefix="/api/v1", tags=["Pozos"])
app.include_router(pozos_router, prefix="/api/v1", tags=["Pozos"])
app.include_router(produccion_router, prefix="/api/v1", tags=["Producción"])


@app.get("/health")
def health():
    return {"status": "ok"}
