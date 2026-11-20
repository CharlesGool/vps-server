"""Mini Drive: download limits of public links, and where a "fetch from URL" may connect.

A link's download limit counts every GET that sends the file from its first byte, whatever
its Range header says; resuming further in does not count. Fetching a URL connects only
to the addresses that passed the internal-address check, so DNS rebinding gets nowhere.
"""
import http.server
import io
import re
import socket
import ssl
import sys
import tempfile
import threading
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "web"))
import file_share  # noqa: E402
from features.files import FilesMixin  # noqa: E402

CONTENT = b"0123456789abcdef"  # 16 bytes


class Blocked(Exception):
    pass


class Meter:
    def check(self, key):
        pass

    def piece(self, key, direction, size):
        return size

    def take(self, key, direction, size):
        pass


class Download(FilesMixin):
    """One public download request through FilesMixin without a socket."""

    def __init__(self, store, method, path, range_header=None):
        self.context = type("Context", (), {
            "FILE_STORE": store, "APP_METER": Meter(), "TrafficBlocked": Blocked, "BASE_DIR": None, "re": re,
            "module_feature_enabled": staticmethod(lambda base, name: True)})
        self.headers = {"Range": range_header} if range_header is not None else {}
        self.wfile, self.status, self.sent = io.BytesIO(), None, {}
        self.route_files_public(method, path)
        self.body = self.wfile.getvalue()

    def send_response(self, code):
        self.status = code

    def send_header(self, key, value):
        self.sent[key] = value

    def end_headers(self):
        pass


class DownloadLimitTest(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.store = file_share.FileStore(Path(directory.name) / "files")
        with mock.patch.object(file_share.FileStore, "disk_free", return_value=10 * file_share.GIB):
            self.entry = self.store.upload("a.bin", io.BytesIO(CONTENT), len(CONTENT))

    def link(self, max_downloads):
        link = self.store.add_link(self.entry["id"], 60, max_downloads)
        return link["token"], f"/f/{link['token']}/a.bin"

    def downloads(self, token):
        return next(link for link in self.store.state()["links"] if link["token"] == token)["downloads"]

    def test_a_suffix_range_longer_than_the_file_counts(self):
        token, path = self.link(1)
        first = Download(self.store, "GET", path, "bytes=-1000")
        self.assertEqual((first.status, first.body), (206, CONTENT))
        self.assertEqual(Download(self.store, "GET", path).status, 404)

    def test_an_unparsable_range_sends_everything_and_counts(self):
        for header in ("bytes=abc", "items=5-", "bytes=0-1,4-5", "bytes=00-"):
            with self.subTest(range=header):
                token, path = self.link(1)
                first = Download(self.store, "GET", path, header)
                self.assertIn(first.status, (200, 206))
                self.assertEqual(first.body[:1], CONTENT[:1])
                self.assertIsNone(self.store.resolve(token))
                self.assertEqual(Download(self.store, "GET", path).status, 404)

    def test_resuming_does_not_count_but_starting_over_does(self):
        token, path = self.link(2)
        resumed = Download(self.store, "GET", path, "bytes=5-")
        self.assertEqual((resumed.status, resumed.body), (206, CONTENT[5:]))
        tail = Download(self.store, "GET", path, "bytes=-4")
        self.assertEqual((tail.status, tail.body), (206, CONTENT[-4:]))
        self.assertEqual(self.downloads(token), 0)
        self.assertEqual(Download(self.store, "GET", path).body, CONTENT)
        self.assertEqual(Download(self.store, "GET", path, "bytes=0-3").body, CONTENT[:4])
        self.assertEqual(Download(self.store, "GET", path).status, 404)

    def test_head_and_unsatisfiable_ranges_do_not_count(self):
        token, path = self.link(1)
        head = Download(self.store, "HEAD", path)
        self.assertEqual((head.status, head.body, head.sent["Content-Length"]), (200, b"", str(len(CONTENT))))
        self.assertEqual(Download(self.store, "GET", path, "bytes=100-").status, 416)
        self.assertEqual(self.downloads(token), 0)
        self.assertEqual(Download(self.store, "GET", path).body, CONTENT)

    def test_looking_up_never_counts_and_only_one_request_takes_the_last_download(self):
        token, _path = self.link(1)
        # Two requests found the live link before either counted.
        self.assertIsNotNone(self.store.resolve(token))
        self.assertIsNotNone(self.store.resolve(token))
        self.assertEqual(self.downloads(token), 0)
        self.assertTrue(self.store.count_download(token))
        self.assertFalse(self.store.count_download(token))
        self.assertIsNone(self.store.resolve(token))

    def test_a_link_used_up_between_lookup_and_send_answers_not_found(self):
        token, path = self.link(1)
        resolve = self.store.resolve

        def resolve_then_lose_the_race(value):
            entry = resolve(value)
            self.store.count_download(value)  # another request takes the last download
            return entry

        with mock.patch.object(self.store, "resolve", resolve_then_lose_the_race):
            late = Download(self.store, "GET", path)
        self.assertEqual((late.status, late.body), (404, b"Not found\n"))


def resolver(*answers):
    """A getaddrinfo stand-in: each call answers with the next address (the last one repeats)."""
    calls = []

    def resolve(host, port, type=0):
        address = answers[min(len(calls), len(answers) - 1)]
        calls.append(host)
        family = socket.AF_INET6 if ":" in address else socket.AF_INET
        return [(family, socket.SOCK_STREAM, 6, "", (address, port or 0))]
    resolve.calls = calls
    return resolve


class MetadataAddressTest(unittest.TestCase):
    def test_metadata_addresses_outside_link_local_are_refused(self):
        for address in ("100.100.100.200", "fd00:ec2::254", "fd20:ce::254", "168.63.129.16", "192.0.0.192",
                        "100.100.100.100", "::ffff:100.100.100.200", "169.254.169.254", "fd00:ec2::254%eth0"):
            with self.subTest(address=address):
                with self.assertRaises(file_share.FileShareError) as caught:
                    file_share.refuse_internal("http://example.test/x", resolver(address))
                self.assertEqual(caught.exception.code, "url_blocked")

    def test_neighbouring_addresses_stay_allowed(self):
        # Tailscale peers live in 100.64.0.0/10, a NAS in a private range.
        for address in ("100.100.100.201", "100.101.2.3", "fd00:ec2::253", "192.168.1.10", "93.184.216.34"):
            with self.subTest(address=address):
                file_share.refuse_internal("http://example.test/x", resolver(address))


class PinnedConnectionTest(unittest.TestCase):
    def test_connects_to_the_checked_address_not_the_name(self):
        resolve = resolver("93.184.216.34")
        with mock.patch.object(socket, "create_connection", return_value="sock") as create:
            self.assertEqual(file_share.connect_checked(("files.test", 80), 5, None, resolve=resolve), "sock")
        create.assert_called_once_with(("93.184.216.34", 80), 5, None)
        self.assertEqual(resolve.calls, ["files.test"])

    def test_an_internal_answer_at_connect_time_is_refused_before_connecting(self):
        with mock.patch.object(socket, "create_connection") as create:
            with self.assertRaises(file_share.FileShareError) as caught:
                file_share.connect_checked(("files.test", 80), resolve=resolver("127.0.0.1"))
        self.assertEqual(caught.exception.code, "url_blocked")
        create.assert_not_called()

    def test_dns_rebinding_after_the_check_gets_nowhere(self):
        # The first answer (the page's early check) is public, every later one is loopback.
        resolve = resolver("93.184.216.34", "127.0.0.1")
        file_share.refuse_internal("http://rebind.test/x", resolve)
        with mock.patch.object(socket, "create_connection") as create:
            with self.assertRaises(file_share.FileShareError) as caught:
                file_share.fetch_opener(resolve).open("http://rebind.test/x", timeout=5)
        self.assertEqual(caught.exception.code, "url_blocked")
        create.assert_not_called()


class Origin(http.server.BaseHTTPRequestHandler):
    """A local server standing in for the public one the resolver names."""
    hosts = []

    def do_GET(self):
        Origin.hosts.append(self.headers.get("Host"))
        if self.path == "/moved":
            self.send_response(302)
            self.send_header("Location", "http://inner.test/secret")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Length", "5")
        self.end_headers()
        self.wfile.write(b"hello")

    def log_message(self, *args):
        pass


class PinnedFetchTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = http.server.HTTPServer(("127.0.0.1", 0), Origin)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        Origin.hosts.clear()
        self.connected = []
        real = socket.create_connection
        port = self.server.server_address[1]

        def create(address, *args, **kwargs):
            # Record where the fetch asked to connect; the bytes go to the local stand-in.
            self.connected.append(address)
            return real(("127.0.0.1", port), *args, **kwargs)
        patcher = mock.patch.object(socket, "create_connection", create)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_fetch_goes_to_the_checked_address_with_the_original_host_name(self):
        names = {"files.test": "93.184.216.34"}

        def resolve(host, port, type=0):
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (names[host], port or 0))]
        with file_share.fetch_opener(resolve).open("http://files.test/a.bin", timeout=5) as response:
            self.assertEqual(response.read(), b"hello")
        self.assertEqual(self.connected, [("93.184.216.34", 80)])
        self.assertEqual(Origin.hosts, ["files.test"])

    def test_every_redirect_hop_is_checked_when_connecting(self):
        # files.test answers with a redirect to inner.test, whose answer at connect time is internal.
        # (The redirect's early check uses the real resolver, which knows no .test names.)
        names = {"files.test": "93.184.216.34", "inner.test": "127.0.0.1"}

        def resolve(host, port, type=0):
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (names[host], port or 0))]
        with self.assertRaises(file_share.FileShareError) as caught:
            file_share.fetch_opener(resolve).open("http://files.test/moved", timeout=5)
        self.assertEqual(caught.exception.code, "url_blocked")
        self.assertEqual(self.connected, [("93.184.216.34", 80)])

    def test_tls_still_uses_the_host_name_for_sni_and_certificate(self):
        names = []

        class Recording(ssl.SSLContext):
            def wrap_socket(self, sock, *args, server_hostname=None, **kwargs):
                names.append(server_hostname)
                sock.close()
                raise ssl.SSLError("stop here")

        context = Recording(ssl.PROTOCOL_TLS_CLIENT)
        with self.assertRaises(urllib.error.URLError):
            file_share.fetch_opener(resolver("93.184.216.34"), context).open("https://files.test/a.bin", timeout=5)
        self.assertEqual(self.connected, [("93.184.216.34", 443)])
        self.assertEqual(names, ["files.test"])
        self.assertTrue(context.check_hostname)


if __name__ == "__main__":
    unittest.main()
