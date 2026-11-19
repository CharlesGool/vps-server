"""Small settings helpers shared by the JSON API."""


class SettingsMixin:


    def describe_agent(self, agent):
        browser = next((name for pattern, name in ((r"Edg/", "Edge"), (r"OPR/|Opera", "Opera"),
                                                   (r"Firefox/", "Firefox"), (r"Chrome/|CriOS/", "Chrome"),
                                                   (r"Safari/", "Safari"), (r"curl/", "curl"))
                        if self.context.re.search(pattern, agent)), "")
        system = next((name for pattern, name in ((r"Android", "Android"), (r"iPhone|iPad|iOS", "iOS"),
                                                  (r"Windows", "Windows"), (r"Mac OS X|Macintosh", "macOS"),
                                                  (r"Linux", "Linux"))
                       if self.context.re.search(pattern, agent)), "")
        return " · ".join(part for part in (browser, system) if part) or agent[:40]


    def cert_autoselect_patterns(self):
        """Addresses this console answers on, as browser URL patterns."""
        from caddy_sites import console_port, names, read_sites
        hosts = []
        current = (self.headers.get("Host") or "").strip()
        if self.context.re.fullmatch(r"[A-Za-z0-9.:\[\]-]{1,255}", current):
            hosts.append(current)
        port = console_port() or self.context.CONSOLE_PORT
        try:
            sites = [site for site in read_sites() if site.get("enabled", True)]
        except (OSError, ValueError):
            sites = []
        for site in sites:
            if site.get("ip"):
                hosts.append(f'{site["host"]}:{port}')
            elif site.get("console"):
                hosts += names(site)
        return list(dict.fromkeys("https://" + host.lower() for host in hosts))


    SECURITY_POSTS = {
        "/settings/ip/add": ("ip-add", ({"csrf", "ip"},)),
        "/settings/ip/remove": ("ip-remove", ({"csrf", "ip"},)),
        "/settings/ip/toggle": ("ip-toggle", ({"csrf", "enabled"},)),
        "/settings/password": ("password", ({"csrf", "new", "confirm"},)),
        "/settings/login-ban/toggle": ("login-ban-toggle", ({"csrf", "enabled"},)),
        "/settings/login-ban/clear": ("login-ban-clear", ({"csrf"},)),
        "/settings/console-access/toggle": ("console-access-toggle", ({"csrf", "enabled"},)),
        "/settings/console-access/add": ("console-access-add", ({"csrf", "network"},)),
        "/settings/console-access/remove": ("console-access-remove", ({"csrf", "network"},)),
        "/settings/sessions/revoke": ("session-revoke", ({"csrf", "id"},)),
        "/settings/sessions/revoke-others": ("session-revoke-others", ({"csrf"},)),
        "/settings/alerts": ("alerts-save", tuple({"csrf", "server", "key"} | set(extra)
                                                   for extra in ((), ("new_ip",), ("ban",), ("new_ip", "ban")))),
        "/settings/alerts/test": ("alerts-test", ({"csrf"},)),
        "/settings/alerts/clear-key": ("alerts-clear-key", ({"csrf"},)),
    }
