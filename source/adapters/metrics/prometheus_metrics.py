from __future__ import annotations
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading
from typing import Optional, Any
from core.metrics.facade import Metrics

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
        # подавляем болтливость http.server
        return

class PrometheusMetrics(Metrics):
    """Реестр метрик + опциональный HTTP-экспорт в формате Prometheus."""
    def __init__(self, cfg: Any = None, logger: Any = None, *, host: str | None = None, port: int | None = None, path: str | None = None) -> None:
        super().__init__()
        # resolve host/port/path из cfg, если есть
        resolved_host = host or "0.0.0.0"
        resolved_port = port or 0
        resolved_path = path or "/metrics"
        if cfg is not None:
            try:
                resolved_host = getattr(cfg.model.metrics, "host", resolved_host)
                resolved_port = int(getattr(cfg.model.metrics, "port", resolved_port))
                resolved_path = getattr(cfg.model.metrics, "path", resolved_path)
                svc_name = str(getattr(cfg.model.context, "name"))
                self.set_common_labels({"svc": svc_name})
            except Exception:
                # мягкое поведение: если нет полей в cfg — используем значения по умолчанию
                pass
        self._host = str(resolved_host)
        self._port = int(resolved_port)
        self._path = str(resolved_path)

        self._server: Optional[HTTPServer] = None
        self._thread: Optional[threading.Thread] = None
        self._http_enabled: bool = False

    # ---- управление HTTP-экспортом ----
    def start_http_exporter(self, *, host: str | None = None, port: int | None = None, path: str | None = None, deadline_ms: int = 2000) -> None:
        if self._http_enabled:
            return
        bind_host = host or self._host
        bind_port = int(port or self._port or 0)
        _Handler.registry = self
        if path:
            _Handler.path_export = path
        else:
            _Handler.path_export = self._path
        self._server = HTTPServer((bind_host, bind_port), _Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, name="prom-exporter", daemon=True)
        self._thread.start()
        self._http_enabled = True

    def stop_http_exporter(self) -> None:
        self.shutdown()

    def shutdown(self) -> None:
        if self._server:
            try:
                self._server.shutdown()
                self._server.server_close()
            finally:
                self._server = None
        if self._thread:
            self._thread.join(timeout=1.0)
            self._thread = None
        self._http_enabled = False
