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
**In progress:** All three modules install, run and uninstall cleanly on a
real host, verified by the operator: the public page answers on 80 and 443,
the console works, the browser speed test works, the iperf3 window measures
2.8 Gbit/s over LAN and refuses connections once it closes itself, the anytls
node comes up and its teardown removes the unit, binary, config directory and
firewall rule, and all three UI languages render. 78 tests pass. The console
now also has an anytls page that shows the node's status and offers a
copyable Clash entry and share link.
**Next:** Reinstall and press the anytls reset button once. It failed on its
first real attempt because the web service runs with `ProtectSystem=strict`
and `/etc` is read-only to it; the reset now runs in a transient unit via
`systemd-run`, which is verified to work on a real host, but the reset itself
has never completed end to end.
**Known issues:** The copy buttons on `/anytls` have not been clicked in a
browser. `navigator.clipboard` does not exist outside a secure context and
the console is plain HTTP by default, so the `document.execCommand` fallback
is the path that really runs; the tests cover the markup, not the browser.
The six governance documents are still untranslated template placeholders in
`translated_zh_cn/` and `translated_zh_tw/`; they get translated as part of
the v0.1.0 release checklist.
**Blocked on:** nothing.
