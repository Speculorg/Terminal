from __future__ import annotations
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading
from typing import Optional, Any
from core.metrics import Metrics

class _Handler(BaseHTTPRequestHandler):
    registry: Metrics = None  # type: ignore
    path_export: str = "/metrics"

    def do_GET(self):
        if self.path != self.path_export:
            self.send_response(404)
            self.end_headers()
            return
        body = self.registry.export_prometheus().encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        return

class PrometheusMetrics(Metrics):
    """Реестр метрик + опциональный HTTP-экспорт в формате Prometheus."""
    def __init__(self, cfg: Any = None, logger: Any = None, *, host: str | None = None, port: int | None = None, path: str | None = None) -> None:
        super().__init__()
        self._server: Optional[HTTPServer] = None
        if cfg is not None:
            if host is None: host = "0.0.0.0"
            if port is None: port = int(getattr(getattr(cfg, "metrics", object()), "port", 8000))
            if path is None: path = str(getattr(getattr(cfg, "metrics", object()), "path", "/metrics"))
        self._host = host or "0.0.0.0"
        self._port = int(port or 8000)
        self._path = path or "/metrics"
        self._logger = logger

    def start_http_exporter(self, *, host: str | None = None, port: int | None = None, path: str | None = None) -> None:
        host = host or self._host
        port = int(port or self._port)
        path = path or self._path

        class Handler(_Handler):
            pass
        Handler.registry = self
        Handler.path_export = path

        srv = HTTPServer((host, port), Handler)
        self._server = srv
        t = threading.Thread(target=srv.serve_forever, name=f"prom-metrics:{port}", daemon=True)
        t.start()
        if self._logger:
            try:
                self._logger.info("metrics.http_exporter.started", host=host, port=port, path=path)
            except Exception:
                pass

    def stop_http_exporter(self) -> None:
        srv = self._server
        if srv:
            try:
                srv.shutdown()
            finally:
                self._server = None
