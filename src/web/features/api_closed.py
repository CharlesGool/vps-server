"""JSON API for the page shown in place of a feature the operator has closed."""


class ClosedApiMixin:
    API_ROUTES_CLOSED = {("GET", "closed"): "api_closed"}

    def api_closed(self):
        context = self.context
        module = context.parse_qs(context.urlsplit(self.path).query).get("module", [""])[0]
        lang, _ = self.resolve_lang(context.urlsplit(self.path))
        info = self.closed_module(module, lang)
        if info is None:
            return self.api_error(404, "not_found")
        destination, name, closed = info
        return self.api_ok({"module": module, "name": name, "closed": closed, "destination": destination})
