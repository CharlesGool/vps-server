"""JSON API for the recent visitors table."""


class VisitorsApiMixin:
    API_ROUTES_VISITORS = {
        ("GET", "visitors"): "api_visitors",
        ("POST", "visitors/clear"): "api_visitors_clear",
    }

    def _visitors_closed(self):
        if self.context.closed_page_module("/visitors"):
            self.api_error(403, "feature_closed", url="/closed?module=visitors")
            return True
        return False

    def api_visitors(self):
        if self._visitors_closed():
            return
        rows = [{"ip": row["ip"], "scope": row["scope"], "direction": row["direction"] or "in",
                 "firstSeen": row["first_seen"], "lastSeen": row["last_seen"], "hits": row["hits"],
                 "ports": row["ports"] or "",
                 "lastRequest": f'{row["last_method"]} {row["last_path"]} → {row["last_status"]}' if row["hits"] else ""}
                for row in self.context.recent_visitors()]
        return self.api_ok({"max": self.context.MAX_VISITOR_ROWS, "rows": rows})

    def api_visitors_clear(self):
        if self._visitors_closed():
            return
        if self.read_json() is None:
            return self.api_error(400, "invalid_request")
        self.context.clear_visitor_history()
        return self.api_ok()
