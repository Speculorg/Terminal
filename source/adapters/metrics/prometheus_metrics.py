from __future__ import annotations
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading
from typing import Optional
from core.metrics import Metrics

class _Handler(BaseHTTPRequestHandler):
    registry: Metrics = None  # type: ignore
    path_export: str = "/metrics"

    def do_GET(self):
        if self.path != self.path_export:
            self.send_response(404)
            self.end_headers()
            return
        body = self.registry.export_prometheus().encode("utf-8")  # type: ignore
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        return

class PrometheusMetrics(Metrics):
    """Реестр метрик + опциональный HTTP-экспорт в формате Prometheus."""
    def __init__(self) -> None:
        super().__init__()
        self._server: Optional[HTTPServer] = None

    def start_http_exporter(self, *, host: str = "0.0.0.0", port: int = 8000, path: str = "/metrics") -> None:
        if self._server is not None:
            return
        _Handler.registry = self
        _Handler.path_export = path
        self._server = HTTPServer((host, port), _Handler)
        t = threading.Thread(target=self._server.serve_forever, name="metrics-http", daemon=True)
        t.start()
