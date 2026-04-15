from fastapi import FastAPI

from app.forecast.routes import router as forecast_router
from app.metrics.system import MetricsMiddleware, metrics_app
from app.wells.routes import router as wells_router

app = FastAPI(
    title="Oil & Gas Forecast API",
    version="1.0.0",
    description="API simple para consultar el listado de pozos y sus pronosticos de producción.",
)

app.add_middleware(MetricsMiddleware)
app.mount("/metrics", metrics_app)

app.include_router(forecast_router, prefix="/api/v1")
app.include_router(wells_router, prefix="/api/v1")

