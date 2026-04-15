"""Métricas de negocio de la Plataforma Predictiva."""

from prometheus_client import Counter, Histogram

FORECAST_REQUESTS_BY_WELL = Counter(
    "forecast_requests_by_well_total",
    "Total de requests de pronóstico por pozo",
    ["id_well"],
)

FORECAST_DATE_RANGE_DAYS = Histogram(
    "forecast_date_range_days",
    "Rango de días consultado en cada request de pronóstico",
    buckets=[1, 7, 14, 30, 60, 90, 180, 365],
)
