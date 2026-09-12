---
project: vps-server
version: unreleased
status: active
branch: main
updated: 2026-09-12
---

# Status

**English** | [简体中文](translated_zh_cn/STATUS_zh_cn.md) | [繁體中文](translated_zh_tw/STATUS_zh_tw.md)

**Notion:** private mirror (not published)
**Repo:** private
**Snapshots:** maintained privately (not published)
**In progress:** The web module is vendored from `vps-webserver` v0.4.1 and both
new capabilities work: the public reachability page answers on its own listeners
and 404s every console route, and the iperf3 window opens, self-closes, and
leaves no child process behind. 67 tests pass, and both features were driven
end-to-end against a real `iperf3` client. Still to do: `install.sh` does not
yet know about modules or the new ports, and the anytls module is not vendored.
**Next:** Vendor `Anytsl-Serve` v1.2.0 — copy `install-anytls.sh` to
`anytls/setup-anytls.sh` along with the sing-box binary and `sing-box.version`,
rename the unit to `vps-server-anytls.service` and the binary to
`sing-box-vps-server` so both projects can coexist on one host, and record the
tag in `anytls/.upstream-version`.
**Known issues:** `install.sh` and `uninstall.sh` are still the vendored
single-module versions; they install the web service but know nothing about the
public ports, the module menu, or anytls.
**Blocked on:** The GitHub remote does not exist yet — `gh repo create` was
blocked by this environment's safety classifier, so the operator has to run it
by hand. Until then every commit exists only on this machine.
