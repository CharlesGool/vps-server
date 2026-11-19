"""JSON API for module management (install and uninstall) and the detailed logs."""

from features.modules import (LOG_LEVELS, LOG_SOURCES, clear_log_source, host_findings, log_cutoffs,
                              log_service_units, module_history_text, module_job_recent, module_job_text,
                              service_log_text)

# Optional modules that can be installed and uninstalled, in display order.
MODULE_CATALOGUE = ("iperf3", "proxy_nodes", "frps", "frpc", "tailscale", "caddy")
# Modules whose install log is shown while the job runs.
PROGRESS_MODULES = ("iperf3", "proxy_nodes", "frps", "frpc")


class ModulesApiMixin:
    API_ROUTES_MODULES = {
        ("GET", "modules"): "api_modules",
        ("POST", "modules/manage"): "api_modules_manage",
        ("GET", "logs"): "api_logs",
        ("POST", "logs/clear"): "api_logs_clear",
    }

    def _module_present_enabled(self, module, installed):
        context = self.context
        if module == "proxy_nodes":
            present = "proxy" in installed
            return present, present and context._run_quiet(
                ["systemctl", "is-enabled", "--quiet", context.MANAGED_UNITS["proxy"]])
        present = module in installed
        if module == "frpc":
            return present, present and context.frpc_group_enabled(context.BASE_DIR)
        if module == "iperf3":
            return present, present and context.IPERF_ENABLED
        return present, present and context._run_quiet(
            ["systemctl", "is-enabled", "--quiet", context.MANAGED_UNITS[module]])

    def _module_progress(self, job, busy, now):
        if job.get("module") not in PROGRESS_MODULES or job.get("action") not in ("install", "uninstall"):
            return None
        try:
            log_path = self.context.module_log_path(self.context.BASE_DIR)
            modified = log_path.stat().st_mtime
            if modified < job.get("at", 0) - 2 or not (busy or now - modified < 30):
                return None
            lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
        except (OSError, TypeError, ValueError):
            return None
        return "\n".join(lines[-20:])

    def api_modules(self):
        context = self.context
        lang, _ = self.resolve_lang(context.urlsplit(self.path))
        t = context.STRINGS[lang]
        installed = context.installed_modules(context.BASE_DIR)
        modules = []
        for module in MODULE_CATALOGUE:
            present, enabled = self._module_present_enabled(module, installed)
            modules.append({"key": module, "installed": bool(present), "enabled": bool(enabled),
                            "needs": "" if present else host_findings(context, t, module)})
        job = self._module_job()
        now = context.time.time()
        busy = job.get("state") in ("queued", "running") and module_job_recent(job, now, 900)
        visible = busy or job.get("state") in ("done", "failed") and module_job_recent(job, now, 30)
        return self.api_ok({
            "modules": modules, "busy": busy,
            "job": ({"module": job.get("module"), "action": job.get("action"), "state": job.get("state"),
                     "text": module_job_text(t, job, self._module_names(t))} if job and visible else None),
            "progress": self._module_progress(job, busy, now) if job and visible else None,
        })

    def api_modules_manage(self):
        body = self.read_json() or {}
        if body.get("action") not in ("install", "uninstall") or body.get("module") not in MODULE_CATALOGUE:
            return self.api_error(400, "invalid_request")
        failure = self.start_module_job(body["module"], body["action"])
        if failure:
            return self.api_error(*failure)
        return self.api_modules()

    def api_logs(self):
        context = self.context
        query = context.parse_qs(context.urlsplit(self.path).query)
        source = query.get("source", ["all"])[0]
        level = query.get("level", ["all"])[0]
        if source not in ("all",) + LOG_SOURCES:
            return self.api_error(404, "not_found")
        if level not in dict(LOG_LEVELS):
            return self.api_error(400, "invalid_request")
        cutoffs = log_cutoffs(context)
        units = dict(log_service_units(context))
        sections = []
        if source in ("all", "modules"):
            sections.append({"source": "modules", "text": module_history_text(context)})
        for key in (LOG_SOURCES[1:] if source == "all" else () if source == "modules" else (source,)):
            # null: the service log could not be read.
            text = service_log_text(context, units[key], level, 250 if source == "all" else 1000,
                                    cutoffs.get(key)) if units[key] else ""
            if text and text.strip() == "-- No entries --":
                text = ""
            sections.append({"source": key, "text": text})
        return self.api_ok({"source": source, "level": level, "sections": sections})

    def api_logs_clear(self):
        body = self.read_json() or {}
        source = body.get("source")
        if source not in ("all",) + LOG_SOURCES:
            return self.api_error(400, "invalid_request")
        try:
            clear_log_source(self.context, source)
        except OSError:
            return self.api_error(500, "failed")
        return self.api_ok()
