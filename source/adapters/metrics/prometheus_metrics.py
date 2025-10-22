
from __future__ import annotations
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading
import json
from typing import Optional, Callable, Dict, Any
from core.metrics import Metrics

class _Handler(BaseHTTPRequestHandler):
    registry: Metrics = None  # type: ignore
    path_export: str = "/metrics"
    path_health: str = "/health"
    health_provider: Optional[Callable[[], Dict[str, Any]]] = None  # type: ignore

    def log_message(self, format, *args):
        # Глушим стандартный лог HTTPServer
        return

    def do_GET(self):
        # /metrics
        if self.path == self.path_export:
            body = self.registry.export_prometheus().encode("utf-8")  # type: ignore
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        # /health
        if self.path == self.path_health and self.health_provider is not None:
            try:
                payload = self.health_provider()  # type: ignore
                data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            except Exception:
                self.send_response(500)
                self.end_headers()
            return

        self.send_response(404)
        self.end_headers()

class PrometheusMetrics(Metrics):
    """Реестр метрик + опциональный HTTP-экспорт в формате Prometheus."""

    def __init__(self) -> None:
        super().__init__()
        self._server: Optional[HTTPServer] = None

    def set_health_provider(self, provider: Callable[[], Dict[str, Any]]) -> None:
        _Handler.health_provider = provider  # type: ignore

    def set_health_path(self, path: str = "/health") -> None:
        _Handler.path_health = path  # type: ignore

    def start_http_exporter(self, *, host: str = "0.0.0.0", port: int = 8000, path: str = "/metrics") -> None:
        if self._server is not None:
            return
        _Handler.registry = self
        _Handler.path_export = path
        self._server = HTTPServer((host, port), _Handler)
        t = threading.Thread(target=self._server.serve_forever, name="metrics-http", daemon=True)
        t.start()
