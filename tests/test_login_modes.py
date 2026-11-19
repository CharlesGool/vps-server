"""Login modes: password only, certificate only, either, both (state and rules, no TLS)."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "web"))
import client_cert as cc  # noqa: E402


def make(tmp, *, ca=True, certs=1, state=None):
    directory = Path(tmp)
    if ca:
        (directory / "client-ca.pem").write_text("ca")
    document = dict(state or {})
    document["certs"] = [{"serial": f"{i + 1:02x}" * 4, "name": f"d{i}", "created": 1} for i in range(certs)]
    (directory / "client-auth.json").write_text(json.dumps(document))
    return cc.ClientAuth(directory)


class LoginModeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def rules(self, auth):
        return auth.mode(), auth.required(), auth.password_login_allowed(), auth.cert_login_allowed()

    def test_truth_table(self):
        table = {"password": ("password", False, True, False), "cert": ("cert", True, False, True),
                 "either": ("either", False, True, True), "both": ("both", True, True, False)}
        for mode, expected in table.items():
            auth = make(tempfile.mkdtemp(), state={"login_mode": mode})
            self.assertEqual(self.rules(auth), expected, mode)

    def test_older_installs_keep_their_behaviour(self):
        self.assertEqual(self.rules(make(tempfile.mkdtemp(), state={"required": True})), ("cert", True, False, True))
        self.assertEqual(self.rules(make(tempfile.mkdtemp(), state={"required": False})), ("either", False, True, True))
        self.assertEqual(self.rules(make(tempfile.mkdtemp(), state={})), ("either", False, True, True))

    def test_nothing_can_be_demanded_before_a_ca_exists(self):
        for mode in ("cert", "both"):
            auth = make(tempfile.mkdtemp(), ca=False, state={"login_mode": mode})
            self.assertEqual(self.rules(auth), ("password", False, True, False), mode)

    def test_unknown_stored_mode_falls_back_to_the_legacy_flag(self):
        auth = make(tempfile.mkdtemp(), state={"login_mode": "root", "required": True})
        self.assertEqual(auth.mode(), "cert")

    def test_set_mode_persists_and_keeps_required_in_step(self):
        auth = make(self.tmp, state={})
        for mode in cc.LOGIN_MODES:
            auth.set_mode(mode)
            fresh = cc.ClientAuth(self.tmp)
            self.assertEqual(fresh.mode(), mode)
            saved = json.loads((Path(self.tmp) / "client-auth.json").read_text())
            self.assertEqual(saved["required"], mode in ("cert", "both"))

    def test_certificate_modes_need_an_active_certificate(self):
        auth = make(self.tmp, certs=0, state={})
        for mode in ("cert", "both"):
            with self.assertRaises(cc.ClientCertError) as caught:
                auth.set_mode(mode)
            self.assertEqual(caught.exception.code, "client_cert_need_current")
        auth.set_mode("password")
        auth.set_mode("either")
        revoked = make(tempfile.mkdtemp(), certs=1, state={})
        revoked.revoke(revoked.certificates()[0]["serial"])
        with self.assertRaises(cc.ClientCertError):
            revoked.set_mode("cert")

    def test_only_revoked_records_can_be_deleted(self):
        auth = make(self.tmp, certs=2, state={})
        active, other = (item["serial"] for item in auth.certificates())
        with self.assertRaises(cc.ClientCertError):
            auth.delete(active)                        # an active certificate must be revoked first
        with self.assertRaises(cc.ClientCertError):
            auth.delete("ffffffff")
        auth.revoke(active)
        auth.delete(active)
        self.assertEqual([item["serial"] for item in cc.ClientAuth(self.tmp).certificates()], [other])

    def test_invalid_modes_are_refused(self):
        auth = make(self.tmp, state={})
        for bad in ("", "Password", "certificate", None, 3):
            with self.assertRaises(cc.ClientCertError):
                auth.set_mode(bad)
        self.assertEqual(auth.mode(), "either")

    def test_legacy_set_required_maps_to_modes(self):
        auth = make(self.tmp, state={})
        auth.set_required(True)
        self.assertEqual(auth.mode(), "cert")
        auth.set_required(False)
        self.assertEqual(auth.mode(), "either")

    def test_recovery_command_goes_to_password_only(self):
        auth = make(self.tmp, state={"login_mode": "both"})
        self.assertTrue(auth.required())
        sys.argv = ["client_cert.py", "disable"]
        import os
        os.environ["VPSSRV_CERT_DIR"] = os.environ["VPSSRV_STATE_DIR"] = self.tmp
        try:
            self.assertEqual(cc.main(["disable"]), 0)
        finally:
            os.environ.pop("VPSSRV_CERT_DIR", None)
            os.environ.pop("VPSSRV_STATE_DIR", None)
        fresh = cc.ClientAuth(self.tmp)
        self.assertEqual(self.rules(fresh), ("password", False, True, False))


if __name__ == "__main__":
    unittest.main()
