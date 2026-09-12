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
**In progress:** Documentation skeleton is committed and the design is agreed. No
code yet — `app.py`, `install.sh`, and the vendored upstream trees are all still
to be written.
**Next:** Vendor `vps-webserver` v0.4.1 into the repo — copy `app.py`,
`static/`, `tests/`, `install.sh`, `uninstall.sh`, `systemd/` from the upstream
tag, record the tag in `.upstream-version`, and rename the `VPSWS_` environment
prefix to `VPSSRV_` in the same commit.
**Known issues:** none yet.
**Blocked on:** nothing.
