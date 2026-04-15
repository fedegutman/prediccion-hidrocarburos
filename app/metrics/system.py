"""Métricas de sistema y middleware de Prometheus."""

import time

from fastapi import Request
from prometheus_client import Counter, Gauge, Histogram, make_asgi_app
from starlette.middleware.base import BaseHTTPMiddleware

REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total de requests HTTP recibidos",
    ["method", "endpoint", "status_code"],
)

REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "Latencia de los requests HTTP en segundos",
    ["method", "endpoint"],
)

REQUESTS_IN_PROGRESS = Gauge(
    "http_requests_in_progress",
    "Requests HTTP en curso",
    ["method", "endpoint"],
)

metrics_app = make_asgi_app()


class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware que registra métricas de sistema en cada request."""

    async def dispatch(self, request: Request, call_next):
        method = request.method
        endpoint = request.url.path

        REQUESTS_IN_PROGRESS.labels(method=method, endpoint=endpoint).inc()
        start_time = time.time()

        response = await call_next(request)

        duration = time.time() - start_time
        status_code = str(response.status_code)

        REQUEST_COUNT.labels(method=method, endpoint=endpoint, status_code=status_code).inc()
        REQUEST_LATENCY.labels(method=method, endpoint=endpoint).observe(duration)
        REQUESTS_IN_PROGRESS.labels(method=method, endpoint=endpoint).dec()

        return response
