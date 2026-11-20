"""Domain forwarding: site records and requests in, Caddy's native JSON out.

caddy_config() is pure; the request checks in front of it (normalize_host, _target,
_access, _aliases, read_sites, apply) run with temporary files and mocks, so no
root, Caddy binary or Cloudflare account is needed. Only stable key structure is
asserted, not the whole document.
"""
import contextlib
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _isolation  # noqa: E402,F401

import caddy_sites as cs  # noqa: E402

KEY = "k" * 43
CA = Path("/test/client-ca.pem")
HASH = "$2a$14$abcdefghijklmnopqrstuuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0"
ABORT = {"handle": [{"handler": "static_response", "abort": True}]}
# Things that must never reach a Caddy config as a host name: JSON breakers,
# line breaks, Caddy placeholders, paths, ports, wildcards and spaces.
BAD_HOSTS = ('app.example.com"', 'a"b.example.com', "app.example.com\nevil.example.com", "app.example.com\rx.example.com",
             "{http.request.host}", "a{b}.example.com", "app.example.com}", "app.example.com/x",
             "app.example.com:443", "*.example.com", "a b.example.com", "app.example.com\\", "app.<b>.com",
             "app.example.com'", "app\x00.example.com", "", "com", "-a.example.com", "a..example.com",
             "例{子}.example.com")


def build(sites, **kwargs):
    config = cs.caddy_config(sites, **kwargs)
    return json.loads(json.dumps(config))  # what is written to caddy.json


def https(config):
    return config["apps"]["http"]["servers"]["https"]


def http(config):
    return config["apps"]["http"]["servers"]["http"]


def routes_for(config, host):
    return [route for route in https(config)["routes"]
            if any(host in match.get("host", []) for match in route.get("match", []))]


def proxy_route(config, host):
    """The route that serves host (not the 403 for addresses outside its allow list)."""
    found = [route for route in routes_for(config, host) if not any("not" in m for m in route["match"])]
    return found[0] if len(found) == 1 else None


def handler(route, name):
    return next((item for item in route["handle"] if item["handler"] == name), None)


class CaddyConfigTest(unittest.TestCase):
    def test_reverse_proxy_to_a_local_port(self):
        config = build([{"host": "app.example.com", "port": 8080}])
        route = proxy_route(config, "app.example.com")
        self.assertEqual(route["match"], [{"host": ["app.example.com"]}])
        self.assertTrue(route["terminal"])
        self.assertEqual(len(route["handle"]), 1)
        proxy = route["handle"][0]
        self.assertEqual(proxy["handler"], "reverse_proxy")
        self.assertEqual(proxy["upstreams"], [{"dial": "127.0.0.1:8080"}])
        self.assertNotIn("transport", proxy)       # plain HTTP to the backend
        self.assertNotIn("headers", proxy)         # Caddy keeps the visitor's Host for HTTP
        server = https(config)
        self.assertEqual(server["listen"], [":443"])
        self.assertEqual(server["routes"][-1], ABORT)  # any other name is dropped
        self.assertNotIn("tls_connection_policies", server)
        self.assertNotIn("automatic_https", server)
        self.assertNotIn("strict_sni_host", server)
        self.assertEqual(http(config), {"listen": [":80"], "routes": [ABORT]})
        self.assertNotIn("tls", config["apps"])

    def test_fixed_parts_of_the_document(self):
        config = build([])
        self.assertEqual(config["admin"], {"listen": "unix/" + cs.ADMIN_SOCKET})
        self.assertEqual(config["storage"], {"module": "file_system", "root": str(cs.DATA_DIR)})
        access = config["logging"]["logs"]["access"]
        self.assertEqual(access["include"], ["http.log.access"])
        self.assertEqual(access["writer"]["filename"], str(cs.ACCESS_LOG))
        self.assertEqual(config["logging"]["logs"]["default"], {"exclude": ["http.log.access"]})
        self.assertEqual(https(config)["routes"], [ABORT])
        self.assertEqual(https(config)["logs"], {})

    def test_reverse_proxy_to_the_console(self):
        site = {"host": "panel.example.com", "console": True}
        config = build([site], console=9443, key=KEY, client_ca=CA)
        proxy = handler(proxy_route(config, "panel.example.com"), "reverse_proxy")
        self.assertEqual(proxy["upstreams"], [{"dial": "127.0.0.1:9443"}])
        self.assertEqual(proxy["transport"], {"protocol": "http", "tls": {"insecure_skip_verify": True}})
        sent = proxy["headers"]["request"]["set"]
        self.assertEqual(sent["X-Vps-Server-Proxy"], [KEY])
        self.assertEqual(sent["Host"], ["{http.request.hostport}"])
        self.assertEqual(sent["X-Vps-Server-Client-Serial"], ["{http.request.tls.client.serial}"])
        self.assertEqual(sent["X-Vps-Server-Client-IP"], ["{http.request.remote.host}"])
        # A certificate is asked for on the console's names only; the console decides if it is required.
        policies = https(config)["tls_connection_policies"]
        self.assertEqual(policies[0], {"match": {"sni": ["panel.example.com"]}, "client_authentication": {
            "ca": {"provider": "file", "pem_files": [str(CA)]}, "mode": "verify_if_given"}})
        self.assertEqual(policies[-1], {})

    def test_console_site_without_a_console_or_key_is_left_unanswered(self):
        site = {"host": "panel.example.com", "console": True}
        for kwargs in ({}, {"console": 9443}, {"key": KEY}, {"console": 9443, "key": ""}):
            config = build([site], **kwargs, client_ca=CA)
            self.assertEqual(routes_for(config, "panel.example.com"), [], kwargs)
            self.assertNotIn("tls_connection_policies", https(config))
        # No client CA: the console is still reached, nothing asks for a certificate.
        config = build([site], console=9443, key=KEY)
        self.assertIsNotNone(proxy_route(config, "panel.example.com"))
        self.assertNotIn("tls_connection_policies", https(config))

    def test_https_backend(self):
        config = build([{"host": "nas.example.com", "port": 5001, "backend_tls": True}])
        proxy = handler(proxy_route(config, "nas.example.com"), "reverse_proxy")
        self.assertEqual(proxy["transport"], {"protocol": "http", "tls": {"insecure_skip_verify": True}})
        self.assertEqual(proxy["headers"]["request"]["set"]["Host"], ["{http.request.hostport}"])
        # Sending the backend's own address instead, for either kind of backend.
        for backend_tls in (True, False):
            config = build([{"host": "nas.example.com", "port": 5001, "backend_tls": backend_tls,
                             "upstream_host": True}])
            proxy = handler(proxy_route(config, "nas.example.com"), "reverse_proxy")
            self.assertEqual(proxy["headers"]["request"]["set"]["Host"], ["{http.reverse_proxy.upstream.hostport}"])
            self.assertEqual("transport" in proxy, backend_tls)

    def test_several_names_for_one_site(self):
        site = {"host": "example.com", "port": 8080,
                "aliases": ["www.example.com", "bad name!", "x.example.com\n", "example.org", 7]}
        config = build([site])
        route = proxy_route(config, "example.com")
        self.assertEqual(route["match"], [{"host": ["example.com", "www.example.com", "example.org"]}])
        console = {"host": "panel.example.com", "console": True, "aliases": ["admin.example.com"]}
        config = build([console], console=9443, key=KEY, client_ca=CA)
        self.assertEqual(https(config)["tls_connection_policies"][0]["match"],
                         {"sni": ["panel.example.com", "admin.example.com"]})

    def test_several_sites_keep_their_order_and_the_drop_comes_last(self):
        sites = [{"host": f"s{n}.example.com", "port": 8000 + n} for n in range(5)]
        routes = https(build(sites))["routes"]
        self.assertEqual([r["match"][0]["host"] for r in routes[:-1]], [[s["host"]] for s in sites])
        self.assertEqual([r["handle"][0]["upstreams"][0]["dial"] for r in routes[:-1]],
                         [f"127.0.0.1:{s['port']}" for s in sites])
        self.assertEqual(routes[-1], ABORT)
        self.assertTrue(all(r["terminal"] for r in routes[:-1]))

    def test_allowed_addresses(self):
        site = {"host": "app.example.com", "port": 8080, "aliases": ["www.example.com"],
                "allow_ips": ["203.0.113.0/24", "2001:db8::/32", 5, None]}
        routes = routes_for(build([site]), "app.example.com")
        self.assertEqual(len(routes), 2)
        refuse, serve = routes
        # The refusal comes first and matches everyone outside the list, on every name.
        self.assertEqual(refuse["match"], [{"host": ["app.example.com", "www.example.com"],
                                            "not": [{"remote_ip": {"ranges": ["203.0.113.0/24", "2001:db8::/32"]}}]}])
        self.assertEqual(refuse["handle"], [{"handler": "static_response", "status_code": 403, "body": "Forbidden"}])
        self.assertTrue(refuse["terminal"])
        self.assertEqual(serve["handle"][0]["handler"], "reverse_proxy")
        # An empty list means no restriction.
        self.assertEqual(len(routes_for(build([{**site, "allow_ips": []}]), "app.example.com")), 1)

    def test_password(self):
        site = {"host": "app.example.com", "port": 8080, "auth": {"user": "alice", "hash": HASH}}
        route = proxy_route(build([site]), "app.example.com")
        auth, proxy = route["handle"]
        self.assertEqual(auth["handler"], "authentication")
        basic = auth["providers"]["http_basic"]
        self.assertEqual(basic["accounts"], [{"username": "alice", "password": HASH}])
        self.assertEqual(basic["hash"], {"algorithm": "bcrypt"})
        self.assertEqual(basic["realm"], "app.example.com")
        self.assertEqual(proxy["handler"], "reverse_proxy")
        # Allowed addresses are checked before the password.
        both = build([{**site, "allow_ips": ["198.51.100.7/32"]}])
        first, second = routes_for(both, "app.example.com")
        self.assertEqual(first["handle"][0]["status_code"], 403)
        self.assertEqual(second["handle"][0]["handler"], "authentication")
        # Half a password record, or a console site, gets no password prompt.
        for broken in ({"user": "alice"}, {"hash": HASH}, {"user": "", "hash": HASH}, "alice:" + HASH):
            route = proxy_route(build([{**site, "auth": broken}]), "app.example.com")
            self.assertIsNone(handler(route, "authentication"), broken)
        console = {"host": "panel.example.com", "console": True, "auth": {"user": "alice", "hash": HASH}}
        route = proxy_route(build([console], console=9443, key=KEY), "panel.example.com")
        self.assertIsNone(handler(route, "authentication"))

    def test_disabled_sites_are_not_served(self):
        sites = [{"host": "off.example.com", "port": 8080, "enabled": False},
                 {"host": "on.example.com", "port": 8081, "enabled": True},
                 {"host": "203.0.113.7", "console": True, "ip": True, "enabled": False}]
        config = build(sites, probe=(True, True))
        self.assertEqual(routes_for(config, "off.example.com"), [])
        self.assertIsNotNone(proxy_route(config, "on.example.com"))
        redirect = http(config)["routes"][0]
        self.assertEqual(redirect["match"], [{"host": ["on.example.com"]}])
        self.assertNotIn("tls", config["apps"])
        self.assertEqual(routes_for(config, "203.0.113.7"), [])

    def test_ip_certificate(self):
        ip_site = {"host": "203.0.113.7", "console": True, "ip": True}
        config = build([ip_site], console=9443, key=KEY, client_ca=CA)
        # Only the certificate: the console serves the address on its own port.
        self.assertEqual(routes_for(config, "203.0.113.7"), [])
        self.assertEqual(https(config)["routes"], [ABORT])
        self.assertNotIn("tls_connection_policies", https(config))
        tls = config["apps"]["tls"]
        self.assertEqual(tls["certificates"], {"automate": ["203.0.113.7"]})
        self.assertEqual(tls["automation"]["policies"],
                         [{"subjects": ["203.0.113.7"], "issuers": [{"module": "acme", "profile": "shortlived"}]}])
        self.assertNotIn("tls", build([{"host": "app.example.com", "port": 8080}])["apps"])

    def test_public_page_off(self):
        config = build([{"host": "app.example.com", "port": 8080}, {"host": "203.0.113.7", "console": True, "ip": True}],
                       probe=(False, False))
        self.assertEqual(http(config)["routes"], [ABORT])
        self.assertNotIn("automatic_https", https(config))
        self.assertNotIn("strict_sni_host", https(config))
        self.assertEqual(https(config)["routes"][-1], ABORT)
        self.assertEqual(routes_for(config, "203.0.113.7"), [])

    def test_public_page_on_port_80(self):
        sites = [{"host": "app.example.com", "port": 8080, "aliases": ["www.example.com"]},
                 {"host": "203.0.113.7", "console": True, "ip": True}]
        config = build(sites, probe=(True, False))
        # Plain HTTP answers the page itself, so Caddy's own redirects are off ...
        self.assertEqual(https(config)["automatic_https"], {"disable_redirects": True})
        redirect, page = http(config)["routes"]
        # ... and the domain names get theirs from this route instead.
        self.assertEqual(redirect["match"], [{"host": ["app.example.com", "www.example.com"]}])
        self.assertEqual(redirect["handle"][0]["status_code"], 308)
        self.assertEqual(redirect["handle"][0]["headers"]["Location"], ["https://{http.request.host}{http.request.uri}"])
        self.assertEqual(page, json.loads(json.dumps(cs.probe_handler())))
        self.assertNotIn("match", page)            # any other name, or the bare address
        # Without domain sites there is nothing to redirect.
        self.assertEqual(http(build([], probe=(True, False)))["routes"], [page])

    def test_public_page_on_port_443(self):
        ip_site = {"host": "203.0.113.7", "console": True, "ip": True}
        config = build([{"host": "app.example.com", "port": 8080}, ip_site], probe=(False, True))
        routes = https(config)["routes"]
        self.assertEqual(routes[-1], ABORT)
        page = routes[-2]
        self.assertEqual(page["match"], [{"host": ["203.0.113.7"]}])
        self.assertTrue(page["terminal"])
        self.assertIs(https(config)["strict_sni_host"], False)   # browsers send no SNI for an address
        self.assertEqual(http(config)["routes"], [ABORT])
        # Without an address certificate there is nothing to show on 443.
        config = build([{"host": "app.example.com", "port": 8080}], probe=(False, True))
        self.assertEqual(len(https(config)["routes"]), 2)
        self.assertNotIn("strict_sni_host", https(config))

    def test_public_page_content(self):
        page = cs.probe_handler()
        root, missing = page["handle"][0]["routes"]
        self.assertEqual(root["match"], [{"path": ["/"]}])
        headers = root["handle"][0]
        self.assertEqual(headers["response"]["set"]["Content-Type"], ["text/plain; charset=utf-8"])
        self.assertEqual(headers["response"]["delete"], ["Server"])
        languages = root["handle"][1]["routes"]
        self.assertEqual([r.get("match", [{}])[0].get("header_regexp", {}).get("Accept-Language", {}).get("pattern")
                          for r in languages], ["(?i)^\\s*zh", "(?i)^\\s*es", None])  # English is the fallback
        for route in languages:
            body = route["handle"][0]["body"]
            self.assertTrue(body.endswith("{http.request.remote.host}\n"), body)
            self.assertEqual(body.count("{"), 1, body)       # no stray placeholder from a translation
        self.assertEqual(missing["handle"][1]["status_code"], 404)

    def test_input_is_not_changed(self):
        sites = [{"host": "app.example.com", "port": 8080, "allow_ips": ["203.0.113.0/24"],
                  "auth": {"user": "alice", "hash": HASH}, "aliases": ["www.example.com"]},
                 {"host": "panel.example.com", "console": True},
                 {"host": "203.0.113.7", "console": True, "ip": True}]
        before = copy.deepcopy(sites)
        first = build(sites, console=9443, key=KEY, client_ca=CA, probe=(True, True))
        self.assertEqual(sites, before)
        self.assertEqual(build(sites, console=9443, key=KEY, client_ca=CA, probe=(True, True)), first)


class SiteInputTest(unittest.TestCase):
    """What an add or edit request may put into a site, and what it may not."""

    def test_host_names_are_normalized(self):
        self.assertEqual(cs.normalize_host("  App.Example.COM. "), "app.example.com")
        self.assertEqual(cs.normalize_host("例子.example.com"), "xn--fsqu00a.example.com")
        self.assertEqual(cs.normalize_host("app.example.com\n"), "app.example.com")  # surrounding space only

    def test_bad_host_names_are_refused(self):
        for raw in BAD_HOSTS + (None, 5, ["app.example.com"]):
            with self.assertRaises(cs.SiteError, msg=repr(raw)) as caught:
                cs.normalize_host(raw)
            self.assertEqual(caught.exception.code, "host_invalid")
        for raw in BAD_HOSTS + ("app.example.com\n",):
            self.assertFalse(cs.valid_host(raw), repr(raw))

    def test_idna_deviation_characters_keep_their_meaning(self):
        # Python's "idna" codec is IDNA 2003: "faß" would become "fass" and a zero-width
        # non-joiner would be dropped, so the site, its certificate and its DNS record
        # would be made for a different domain from the one browsers mean (UTS 46 /
        # IDNA 2008: "xn--fa-hia"). normalize_host() refuses such names.
        for raw, remapped in (("faß.example.com", "fass.example.com"), ("a\u200cb.example.com", "ab.example.com")):
            try:
                host = cs.normalize_host(raw)
            except cs.SiteError:
                continue                    # refusing is fine too
            self.assertNotEqual(host, remapped, repr(raw))

    def test_target_port(self):
        with mock.patch.object(cs, "console_port", return_value=9443):
            self.assertEqual(cs._target({"port": 8080}),
                             {"port": 8080, "backend_tls": False, "upstream_host": False})
            self.assertEqual(cs._target({"port": 8080, "backend_tls": True, "upstream_host": "yes"}),
                             {"port": 8080, "backend_tls": True, "upstream_host": False})
            self.assertEqual(cs._target({"target": "console"}), {"console": True})
            self.assertEqual(cs._target({"port": 9443}), {"console": True})
            for port in (0, 80, 443, 65536, -1, "8080", "8080}", 8080.0, True, None):
                with self.assertRaises(cs.SiteError, msg=repr(port)):
                    cs._target({"port": port})
        with mock.patch.object(cs, "console_port", return_value=None):
            with self.assertRaises(cs.SiteError):
                cs._target({"target": "console"})

    def test_allowed_addresses_are_parsed(self):
        result = cs._access({"allow_ips": [" 10.0.0.1/8 ", "10.0.0.0/8", "203.0.113.9\n", "", "2001:DB8::1"]})
        self.assertEqual(result, {"allow_ips": ["10.0.0.0/8", "203.0.113.9/32", "2001:db8::1/128"]})
        for bad in ('1.2.3.4"', "1.2.3.4}", "{http.request.remote.host}", "1.2.3.4, 5.6.7.8", "1.2.3.4\n5.6.7.8",
                    "example.com", "300.1.1.1", "1.2.3.4/33"):
            with self.assertRaises(cs.SiteError, msg=repr(bad)) as caught:
                cs._access({"allow_ips": [bad]})
            self.assertEqual(caught.exception.code, "allow_invalid")
        with self.assertRaises(cs.SiteError):
            cs._access({"allow_ips": [f"10.0.{n}.0/24" for n in range(cs.MAX_ALLOW + 1)]})

    def test_password_requests(self):
        with mock.patch.object(cs, "hash_password", return_value=HASH) as hashed:
            result = cs._access({"auth_user": "alice", "auth_password": 'p"a{s}s\\w0rd'})
            self.assertEqual(result, {"auth": {"user": "alice", "hash": HASH}})
            hashed.assert_called_once_with('p"a{s}s\\w0rd')       # only the hash is kept
            # An edit without a new password keeps the stored one for the same user.
            current = {"auth": {"user": "alice", "hash": HASH}}
            self.assertEqual(cs._access({"auth_user": "alice"}, current), current)
            self.assertEqual(cs._access({"auth_user": "alice", "auth_clear": True}, current), {})
            for request in ({"auth_user": "bob"}, {"auth_user": "alice", "auth_password": "short"},
                            {"auth_user": "alice", "auth_password": "x" * 129}):
                with self.assertRaises(cs.SiteError, msg=request):
                    cs._access(request, current)
            for user in ('al"ice', "al ice", "alice:x", "a{b}", "alice\nbob", "x" * 65, "ålice", "<b>"):
                with self.assertRaises(cs.SiteError, msg=repr(user)) as caught:
                    cs._access({"auth_user": user, "auth_password": "long-enough"})
                self.assertEqual(caught.exception.code, "auth_invalid")

    def test_a_password_with_a_line_break_is_refused(self):
        # hash_password() feeds the password to `caddy hash-password` on stdin, and Caddy
        # reads only up to the first line break: "ab\ncdefghij" would pass the 8-character
        # check but be stored as the hash of "ab".
        with mock.patch.object(cs, "hash_password", return_value=HASH):
            for password in ("ab\ncdefghij", "abcdefgh\r\nij"):
                with self.assertRaises(cs.SiteError, msg=repr(password)):
                    cs._access({"auth_user": "alice", "auth_password": password})

    def test_extra_names(self):
        sites = [{"host": "a.example.com", "port": 1000, "aliases": ["www.a.example.com"]},
                 {"host": "b.example.com", "port": 1001}]
        self.assertEqual(cs._aliases({"aliases": ["B2.example.com.", "b2.example.com", "b.example.com", " "]},
                                     sites, "b.example.com"), ["b2.example.com"])
        with self.assertRaises(cs.SiteError) as caught:
            cs._aliases({"aliases": ["www.a.example.com"]}, sites, "b.example.com")
        self.assertEqual(caught.exception.code, "host_exists")
        for bad in BAD_HOSTS:
            if not bad.strip():
                continue
            with self.assertRaises(cs.SiteError, msg=repr(bad)):
                cs._aliases({"aliases": [bad]}, sites, "b.example.com")
        with self.assertRaises(cs.SiteError) as caught:
            cs._aliases({"aliases": [f"n{n}.example.com" for n in range(cs.MAX_ALIASES + 1)]}, sites, "b.example.com")
        self.assertEqual(caught.exception.code, "too_many")

    def test_stored_sites_are_filtered_on_read(self):
        stored = [{"host": "ok.example.com", "port": 8080},
                  {"host": "panel.example.com", "console": True},
                  {"host": "93.184.216.34", "console": True, "ip": True},
                  {"host": 'bad".example.com', "port": 8080},
                  {"host": "bad.example.com\n", "port": 8080},
                  {"host": "{http.request.host}", "port": 8080},
                  {"host": "str.example.com", "port": "8080"},
                  {"host": "big.example.com", "port": 70000},
                  {"host": "10.0.0.5", "console": True, "ip": True},       # not a public address
                  {"host": "203.0.113.9", "console": True, "ip": True},    # documentation range, not public
                  {"host": "203.0.113.8", "ip": True},                      # an address site is the console's
                  "not a site"]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sites.json"
            path.write_text(json.dumps({"sites": stored}))
            self.assertEqual([site["host"] for site in cs.read_sites(path)],
                             ["ok.example.com", "panel.example.com", "93.184.216.34"])
            path.write_text(json.dumps({"sites": {"host": "x"}}))
            with self.assertRaises(ValueError):
                cs.read_sites(path)
            self.assertEqual(cs.read_sites(Path(tmp) / "missing.json"), [])


class ApplyTest(unittest.TestCase):
    """apply(): a request through to the stored sites and the Caddy config made from them."""

    def setUp(self):
        self.stored = []
        self.written = []
        patches = {
            "_locked": lambda: contextlib.nullcontext(), "read_sites": lambda: list(self.stored),
            "read_tokens": lambda: [], "read_zones": lambda: [], "write_sites": self.written.append,
            "render": mock.Mock(), "reload_caddy": mock.Mock(), "sync_dns": lambda *a, **k: {"sites": {}},
            "record_history": mock.Mock(), "_merge_dns": mock.Mock(), "console_port": lambda: 9443,
            "hash_password": lambda password: HASH,
        }
        for name, value in patches.items():
            patcher = mock.patch.object(cs, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_add_a_site_and_build_its_config(self):
        reply = cs.apply({"action": "add", "host": "App.Example.com", "port": 8080, "backend_tls": True,
                          "aliases": ["www.example.com"], "allow_ips": ["203.0.113.0/24"],
                          "auth_user": "alice", "auth_password": "long-enough"})
        self.assertEqual(reply, {"ok": True})
        site = self.written[-1][-1]
        self.assertEqual({k: site[k] for k in ("host", "port", "backend_tls", "aliases", "allow_ips", "auth")},
                         {"host": "app.example.com", "port": 8080, "backend_tls": True,
                          "aliases": ["www.example.com"], "allow_ips": ["203.0.113.0/24"],
                          "auth": {"user": "alice", "hash": HASH}})
        self.assertNotIn("long-enough", json.dumps(self.written))
        routes = routes_for(build(self.written[-1]), "www.example.com")
        self.assertEqual([r["handle"][0]["handler"] for r in routes], ["static_response", "authentication"])

    def test_a_console_site_takes_no_password(self):
        cs.apply({"action": "add", "host": "panel.example.com", "target": "console",
                  "auth_user": "alice", "auth_password": "long-enough"})
        site = self.written[-1][-1]
        self.assertEqual((site.get("console"), "auth" in site, "port" in site), (True, False, False))

    def test_bad_requests_change_nothing(self):
        self.stored = [{"host": "taken.example.com", "port": 8080}]
        requests = [{"action": "add", "host": host, "port": 8080} for host in BAD_HOSTS]
        requests += [
            {"action": "add", "host": "taken.example.com", "port": 8081},
            {"action": "add", "host": "new.example.com", "port": "8080"},
            {"action": "add", "host": "new.example.com", "port": 443},
            {"action": "add", "host": "new.example.com", "port": 8080, "aliases": ['x".example.com']},
            {"action": "add", "host": "new.example.com", "port": 8080, "aliases": ["taken.example.com"]},
            {"action": "add", "host": "new.example.com", "port": 8080, "allow_ips": ["1.2.3.4}"]},
            {"action": "add", "host": "new.example.com", "port": 8080, "auth_user": "a\"b", "auth_password": "long-enough"},
            {"action": "edit", "host": "taken.example.com\n{", "port": 8080},
            {"action": "remove", "host": "{http.request.host}"},
            {"action": "frobnicate"},
        ]
        for request in requests:
            with self.assertRaises(cs.SiteError, msg=repr(request)):
                cs.apply(request)
        self.assertEqual(self.written, [])


if __name__ == "__main__":
    unittest.main()
