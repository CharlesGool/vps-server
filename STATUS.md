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
**Repo:** private, pushed
**Snapshots:** maintained privately (not published)
**In progress:** All three modules are in the tree, the remote exists and is
pushed, and `install.sh` has now been run end to end on a real systemd host:
the service came up and the deployed instance served the public page on both
its ports, 404'd console routes on the public port, and answered on the
console port. Two installer bugs surfaced in that run and are fixed — the
teardown hint dropped `PREFIX`/`SERVICE_NAME`, and the usage examples used
`./script.sh`, which cannot work from a CIFS working copy. 67 tests pass.
**Next:** Verify the iperf3 window from inside a systemd unit rather than from
a shell — specifically whether `firewall_port()` can still invoke `iptables`
under `NoNewPrivileges` and `ProtectSystem=strict`. Open a window from an
installed instance's console, check `iptables -S INPUT | grep 5201`, close it,
check the rule is gone.
**Known issues:** The anytls module has never been installed, so its three
renamed constants and the `refuse_if_upstream_running` guard are unexercised.
The iperf3 window has only been driven from a shell, never from under systemd
sandboxing. The six governance documents are still untranslated template
placeholders in `translated_zh_cn/` and `translated_zh_tw/`; they get
translated as part of the v0.1.0 release checklist.
**Blocked on:** nothing.
