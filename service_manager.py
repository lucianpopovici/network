#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 PyPKI Contributors
"""
PyPKI Service Manager
=====================
Owns the lifecycle (start / stop / restart) of every optional sub-service
and exposes per-service configuration that can be updated live from the Web UI.

Design
------
Each service has a ServiceDef that carries its current startup kwargs and a
factory callable.  Starting a service calls the factory and stores the returned
server object; stopping calls server.shutdown().  Restarting is stop + start.

Config changes made via the Web UI patch only the affected service and restart
it.  Config changes made directly to config.json on disk are detected by a
background watcher thread and trigger a full restart of ALL services.

Services managed
----------------
  cmp   — CMPv2/v3 main server  (UI-visible, cannot restart from UI)
  acme  — ACME (RFC 8555)
  scep  — SCEP (RFC 8894)
  est   — EST  (RFC 7030)
  ocsp  — OCSP responder

The Web UI server is intentionally NOT managed here — restarting it mid-request
would drop the user's browser session.
"""

from __future__ import annotations

import copy
import logging
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger("service-manager")

# ---------------------------------------------------------------------------
# State constants
# ---------------------------------------------------------------------------
STATE_STOPPED  = "stopped"
STATE_RUNNING  = "running"
STATE_STARTING = "starting"
STATE_ERROR    = "error"


# ---------------------------------------------------------------------------
# ServiceDef
# ---------------------------------------------------------------------------

class ServiceDef:
    """
    Holds everything needed to manage one service.

    name     : short key used in the API  ("acme", "scep", ...)
    label    : human-readable name shown in the UI
    factory  : callable(**config) -> server-object with .shutdown().
               None means the service cannot be controlled (e.g. CMP main loop).
    config   : mutable dict of current startup kwargs
    enabled  : whether the service should currently be running
    """

    def __init__(
        self,
        name: str,
        label: str,
        factory: Optional[Callable],
        config: Dict[str, Any],
        enabled: bool = False,
    ):
        self.name    = name
        self.label   = label
        self.factory = factory
        self.config  = config
        self.enabled = enabled

        self._server: Any            = None
        self._state: str             = STATE_RUNNING if (factory is None and enabled) else STATE_STOPPED
        self._error: Optional[str]   = None
        self._lock                   = threading.Lock()

    # ---- public properties ----

    @property
    def state(self) -> str:
        return self._state

    @property
    def error(self) -> Optional[str]:
        return self._error

    @property
    def is_running(self) -> bool:
        return self._state == STATE_RUNNING

    def status_dict(self) -> Dict[str, Any]:
        return {
            "name":      self.name,
            "label":     self.label,
            "state":     self._state,
            "enabled":   self.enabled,
            "error":     self._error,
            "config":    copy.deepcopy(self.config),
            "unmanaged": self.factory is None,
        }

    # ---- lifecycle ----

    def start(self) -> bool:
        """Start the service. Returns True on success."""
        with self._lock:
            if self._state == STATE_RUNNING:
                logger.info("[%s] already running", self.name)
                return True
            if self.factory is None:
                self._state = STATE_ERROR
                self._error = "This service cannot be started from the Web UI."
                return False
            self._state = STATE_STARTING
            self._error = None

        try:
            logger.info("[%s] starting with config %s", self.name, self.config)
            srv = self.factory(**self.config)
            with self._lock:
                self._server = srv
                self._state  = STATE_RUNNING
                self.enabled = True
            logger.info("[%s] started", self.name)
            return True
        except Exception as exc:
            with self._lock:
                self._state  = STATE_ERROR
                self._error  = str(exc)
                self._server = None
            logger.error("[%s] start failed: %s", self.name, exc)
            return False

    def stop(self) -> bool:
        """Stop the service. Returns True on success."""
        with self._lock:
            if self.factory is None:
                self._error = "This service cannot be stopped from the Web UI."
                return False
            if self._state not in (STATE_RUNNING, STATE_ERROR, STATE_STARTING):
                return True
            srv = self._server
            self._server = None
            self._state  = STATE_STOPPED
            self.enabled = False

        if srv is not None:
            try:
                srv.shutdown()
                logger.info("[%s] stopped", self.name)
            except Exception as exc:
                logger.warning("[%s] shutdown raised: %s", self.name, exc)
        return True

    def restart(self) -> bool:
        """Stop then start. Returns True if service came back up."""
        if self.factory is None:
            return False
        self.stop()
        return self.start()

    def patch_config(self, updates: Dict[str, Any]) -> bool:
        """Merge *updates* into this service's config dict then restart."""
        with self._lock:
            _deep_merge(self.config, updates)
        logger.info("[%s] config patched: %s", self.name, updates)
        return self.restart()


# ---------------------------------------------------------------------------
# ServiceManager
# ---------------------------------------------------------------------------

class ServiceManager:
    """
    Registry and lifecycle controller for all PKI sub-services.

    Typical usage from pki_server.main()
    -------------------------------------
        sm = ServiceManager(config_path=ca_dir / "config.json")
        sm.register("acme", "ACME Server", start_acme_server,
                    config=dict(host=host, port=acme_port, ca=ca, ...),
                    enabled=True)
        sm.start_all_enabled()
        sm.start_config_watcher()

    Typical usage from web_ui.py
    ----------------------------
        sm.status_all()
        sm.start("acme")
        sm.stop("acme")
        sm.restart("acme")
        sm.patch_service_config("acme", {"cert_validity_days": 30})
    """

    # Which config top-level keys map to which services to restart.
    # Keys absent from this map trigger a full restart of everything.
    _KEY_TO_SERVICES: Dict[str, List[str]] = {
        "acme":     ["acme"],
        "scep":     ["scep"],
        "est":      ["est"],
        "ocsp":     ["ocsp"],
        "cmp":      [],      # CMP cannot restart from UI
        "validity": [],      # validity changes don't need a restart
        "services": [],
    }

    # Config-form schema — maps service name to list of field descriptors.
    # Each descriptor: {key, label, type, [min], [max], [options]}
    # type is one of: "number", "text", "password", "checkbox", "select"
    SERVICE_CONFIG_SCHEMA: Dict[str, List[Dict[str, Any]]] = {
        "cmp": [
            {"key": "prefix", "label": "Path prefix", "type": "text"},
        ],
        "acme": [
            {"key": "prefix",                     "label": "Path prefix",                  "type": "text"},
            {"key": "cert_validity_days",         "label": "Cert validity (days)",         "type": "number",   "min": 1},
            {"key": "short_lived_threshold_days", "label": "Short-lived threshold (days)", "type": "number",   "min": 1},
            {"key": "auto_approve_dns",           "label": "Auto-approve DNS challenges",  "type": "checkbox"},
            {"key": "base_url",                   "label": "Public base URL",              "type": "text"},
        ],
        "scep": [
            {"key": "prefix",    "label": "Path prefix",      "type": "text"},
            {"key": "challenge", "label": "Challenge secret", "type": "password"},
        ],
        "est": [
            {"key": "prefix",       "label": "Path prefix",             "type": "text"},
            {"key": "require_auth", "label": "Require authentication",  "type": "checkbox"},
        ],
        "ocsp": [
            {"key": "prefix",        "label": "Path prefix",         "type": "text"},
            {"key": "cache_seconds", "label": "Cache TTL (seconds)", "type": "number", "min": 1},
        ],
    }

    def __init__(self, config_path: Optional[Path] = None):
        self._services: Dict[str, ServiceDef] = {}
        self._lock         = threading.Lock()
        self._config_path  = config_path
        self._config_mtime = 0.0
        self._stop_watcher = threading.Event()
        self._watcher_thread: Optional[threading.Thread] = None

    # ---- registration ----

    def register(
        self,
        name: str,
        label: str,
        factory: Optional[Callable],
        config: Dict[str, Any],
        enabled: bool = False,
    ) -> ServiceDef:
        svc = ServiceDef(name, label, factory, config, enabled)
        with self._lock:
            self._services[name] = svc
        return svc

    def get(self, name: str) -> Optional[ServiceDef]:
        return self._services.get(name)

    # ---- bulk operations ----

    def start_all_enabled(self):
        for svc in self._services.values():
            if svc.enabled and svc.factory is not None:
                svc.start()

    def stop_all(self):
        for svc in self._services.values():
            if svc.is_running and svc.factory is not None:
                svc.stop()

    def restart_all(self):
        for svc in self._services.values():
            if (svc.is_running or svc.enabled) and svc.factory is not None:
                svc.restart()

    # ---- individual control ----

    def start(self, name: str) -> Tuple[bool, str]:
        svc = self._services.get(name)
        if svc is None:
            return False, f"Unknown service: {name}"
        ok = svc.start()
        return ok, svc.error or ""

    def stop(self, name: str) -> Tuple[bool, str]:
        svc = self._services.get(name)
        if svc is None:
            return False, f"Unknown service: {name}"
        ok = svc.stop()
        return ok, svc.error or ""

    def restart(self, name: str) -> Tuple[bool, str]:
        svc = self._services.get(name)
        if svc is None:
            return False, f"Unknown service: {name}"
        ok = svc.restart()
        return ok, svc.error or ""

    # ---- config management ----

    def patch_service_config(
        self,
        name: str,
        updates: Dict[str, Any],
    ) -> Tuple[bool, str]:
        """Update a single service's config and restart only that service."""
        svc = self._services.get(name)
        if svc is None:
            return False, f"Unknown service: {name}"
        ok = svc.patch_config(updates)
        return ok, svc.error or ""

    def update_global_config(
        self,
        updates: Dict[str, Any],
        source: str = "webui",
    ) -> List[str]:
        """
        Apply global config changes and restart only affected services.

        source="file"  -> restart ALL services (config.json edited on disk)
        source="webui" -> restart only services whose key appears in updates
        Returns list of service names that were restarted.
        """
        if source == "file":
            logger.info("config.json changed externally — restarting all services")
            self.restart_all()
            return [n for n, s in self._services.items()
                    if (s.enabled or s.is_running) and s.factory is not None]

        restarted: List[str] = []
        for key in updates:
            affected = self._KEY_TO_SERVICES.get(key)
            if affected is None:
                # Unknown key — safest to restart everything
                logger.warning("Config key '%s' not in restart map — restarting all", key)
                self.restart_all()
                return [n for n in self._services if self._services[n].factory is not None]
            for svc_name in affected:
                if svc_name not in restarted:
                    svc = self._services.get(svc_name)
                    if svc and (svc.is_running or svc.enabled) and svc.factory is not None:
                        svc.restart()
                        restarted.append(svc_name)
        return restarted

    # ---- status ----

    def status_all(self) -> Dict[str, Dict]:
        return {name: svc.status_dict() for name, svc in self._services.items()}

    def status_one(self, name: str) -> Optional[Dict]:
        svc = self._services.get(name)
        return svc.status_dict() if svc else None

    # ---- config-file watcher ----

    def start_config_watcher(self, poll_interval: float = 2.0):
        """
        Poll config.json every poll_interval seconds.  When the mtime changes
        after startup, restart_all() is called so the new settings take effect.
        """
        if self._config_path is None:
            return
        if self._watcher_thread and self._watcher_thread.is_alive():
            return

        try:
            self._config_mtime = self._config_path.stat().st_mtime
        except FileNotFoundError:
            self._config_mtime = 0.0

        self._stop_watcher.clear()

        def _watch():
            logger.info(
                "Config watcher started — polling %s every %.1fs",
                self._config_path, poll_interval,
            )
            while not self._stop_watcher.wait(poll_interval):
                try:
                    mtime = self._config_path.stat().st_mtime
                    if mtime != self._config_mtime:
                        logger.info(
                            "config.json changed (%.3f -> %.3f) — restarting all services",
                            self._config_mtime, mtime,
                        )
                        self._config_mtime = mtime
                        self.update_global_config({}, source="file")
                except FileNotFoundError:
                    pass
                except Exception as exc:
                    logger.warning("Config watcher error: %s", exc)

        self._watcher_thread = threading.Thread(
            target=_watch, daemon=True, name="pypki-config-watcher",
        )
        self._watcher_thread.start()

    def stop_config_watcher(self):
        self._stop_watcher.set()


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _deep_merge(base: dict, override: dict):
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v
