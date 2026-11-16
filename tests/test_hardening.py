"""Fetch-URL address check and connection time limits."""
import socket
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "web"))
import file_share  # noqa: E402


def resolver(address):
    family = socket.AF_INET6 if ":" in address else socket.AF_INET
    return lambda host, port, type=0: [(family, type, 0, "", (address, 0))]


class RefuseInternalTest(unittest.TestCase):
    def blocked(self, address, url="http://example.test/x"):
        with self.assertRaises(file_share.FileShareError) as caught:
            file_share.refuse_internal(url, resolver(address))
        self.assertEqual(caught.exception.code, "url_blocked")

    def test_loopback_and_link_local_are_refused(self):
        for address in ("127.0.0.1", "127.8.8.8", "169.254.169.254", "0.0.0.0", "::1", "fe80::1",
                        "::ffff:127.0.0.1", "::ffff:169.254.169.254", "224.0.0.1"):
            with self.subTest(address=address):
                self.blocked(address)

    def test_public_and_lan_addresses_are_allowed(self):
        for address in ("93.184.216.34", "192.168.1.10", "10.0.0.5", "2606:2800:220:1::1"):
            with self.subTest(address=address):
                file_share.refuse_internal("http://example.test/x", resolver(address))

    def test_a_name_with_any_internal_answer_is_refused(self):
        both = lambda host, port, type=0: [(socket.AF_INET, type, 0, "", ("93.184.216.34", 0)),
                                           (socket.AF_INET, type, 0, "", ("127.0.0.1", 0))]
        with self.assertRaises(file_share.FileShareError):
            file_share.refuse_internal("http://rebind.test/", both)

    def test_redirect_to_an_internal_address_is_refused(self):
        handler = file_share._CheckedRedirects()
        with self.assertRaises(file_share.FileShareError):
            handler.redirect_request(None, None, 302, "Found", {}, "http://127.0.0.1:8080/secret")
        with self.assertRaises(file_share.FileShareError):
            handler.redirect_request(None, None, 302, "Found", {}, "ftp://example.test/x")

    def test_unresolvable_name_is_left_to_the_fetch(self):
        def fail(host, port, type=0):
            raise socket.gaierror("no such host")
        file_share.refuse_internal("http://nope.invalid/", fail)


class TimeoutTest(unittest.TestCase):
    def test_handlers_do_not_wait_forever_for_a_silent_client(self):
        # app.py needs a configured host to import, so read the source instead.
        source = (Path(__file__).resolve().parents[1] / "src" / "web" / "app.py").read_text(encoding="utf-8")
        for name in ("ConsoleHandler", "ProbeHandler"):
            start = source.index("class " + name)
            body = source[start:source.index("\n    def ", start)]
            self.assertRegex(body, r"\n    timeout = [1-9]\d*", name)


if __name__ == "__main__":
    unittest.main()
