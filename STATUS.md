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
**Next:** Install the anytls module on an amd64 host and check its three
renamed constants land — `systemctl status vps-server-anytls`,
`/etc/vps-server-anytls/config.json`, `/usr/local/bin/sing-box-vps-server` —
then confirm `refuse_if_upstream_running` actually refuses while
`sing-box-anytls.service` is up, and that `uninstall.sh` removes all of it.
**Known issues:** The anytls module has never been installed, so its three
renamed constants and the `refuse_if_upstream_running` guard are unexercised.
The six governance documents are still untranslated template placeholders in
`translated_zh_cn/` and `translated_zh_tw/`; they get translated as part of
the v0.1.0 release checklist.
**Blocked on:** nothing.
