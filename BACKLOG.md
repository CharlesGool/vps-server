# Backlog

**English** | [简体中文](translated_zh_cn/BACKLOG_zh_cn.md) | [繁體中文](translated_zh_tw/BACKLOG_zh_tw.md)

The requirement list. Everything that was asked for, most important first,
ticked off as it gets done. This is the file that answers "what was I going to
do next?" after a two-week gap, and the place requirements go when a session
ends with work still on the table.

**`STATUS.md`'s `Next:` field is the topmost unticked item, copied verbatim.**
When that step is done, tick it here and promote the next unticked item up
there. The two must never disagree: `Next` is the single line the cross-project
table shows, this file is what actually gets read when resuming.

Each item carries the date it was added, so a year-old open entry is visibly
stale rather than quietly permanent:

```
- [ ] YYYY-MM-DD <what to do> — <where it starts: file, command, or the open question>
- [x] YYYY-MM-DD <a finished one>
```

Write items so they can be started cold. "improve error handling" is a note,
not a backlog item; "wrap the mount call in retry — src/mount.py, the bare
except at the bottom" is one.

---

## Items

- [x] 2026-09-12 Agree the architecture and write `DESIGN.md` — done before any code
- [x] 2026-09-12 Vendor `vps-webserver` v0.4.1 — copy `app.py`, `static/`, `tests/`, `install.sh`, `uninstall.sh`, `systemd/` from the upstream tag; record the tag in `.upstream-version`; rename the `VPSWS_` env prefix to `VPSSRV_` in the same commit
- [x] 2026-09-12 Split `app.py` into two handlers — `ConsoleHandler` keeps every existing route; add `ProbeHandler` serving only `/` and `/favicon.ico`; start the public listeners on 80 and 443 alongside the console listener
- [x] 2026-09-12 Write the public reachability page — source IP, server clock, arrival protocol/port, and nothing about the host; no JavaScript. The stylesheet ended up inlined as `PROBE_CSS` rather than a `static/probe.css` file, so the public listener has no file-serving route at all
- [x] 2026-09-12 Implement the iperf3 window — console route to open/close, `subprocess.Popen("iperf3 -s -p …")`, in-memory deadline, expiry thread, firewall open/withdraw, teardown on `SIGTERM`
- [x] 2026-09-12 Surface the open window on the public page — port and remaining minutes, so a remote tester knows when to connect
- [ ] 2026-09-12 Vendor `Anytsl-Serve` v1.2.0 — `anytls/setup-anytls.sh` plus the sing-box binary and `sing-box.version`; rename the unit to `vps-server-anytls.service` and the binary to `sing-box-vps-server`; record the tag in `anytls/.upstream-version`
- [x] 2026-09-12 Make `install.sh` a module menu — web / anytls / iperf3 independently selectable; refuse when 80 or 443 is already bound; refuse when upstream `sing-box-anytls.service` is running; skip anytls on non-amd64. **Written but never executed** — see the verification item below
- [x] 2026-09-12 Extend `uninstall.sh` to tear down whichever modules it finds — default full removal, `KEEP_DATA=1` to keep the visitor database; anytls is torn down before `$PREFIX` is deleted, since its teardown script lives inside `$PREFIX`. **Written but never executed**
- [x] 2026-09-12 Actually run `install.sh` end to end — done by the operator on a real systemd host with an isolated prefix. The service came up, the summary block was correct, and the deployed instance served the public page on both 18080 and 18443 with the right arrival port, 404'd console routes on the public port, and answered on the console port. Two bugs fell out and are fixed: the closing "to remove" line ignored `PREFIX`/`SERVICE_NAME` (so the teardown silently scanned the defaults and removed nothing), and every usage example said `./script.sh`, which cannot work from a CIFS working copy
- [ ] 2026-09-12 Verify the iperf3 window under systemd sandboxing — the window was only ever exercised from a shell, not from a unit with `NoNewPrivileges`/`ProtectSystem=strict`. The uncertain part is whether `firewall_port()` can still invoke `iptables`. Open a window from the console of an installed instance, check `iptables -S INPUT | grep 5201`, then close it and check the rule is gone. Note this briefly exposes the iperf3 port to the network
- [ ] 2026-09-12 Run `install.sh` with the anytls module — never exercised. Its three renamed constants (unit, config dir, binary path) and the `refuse_if_upstream_running` guard are all unverified. Needs an amd64 host
- [x] 2026-09-12 Tests for the new surface — `ProbeHandler` answers 404 on every console route; the iperf3 window expires and kills its child; the window does not survive a restart. 67 tests pass; `firewall_port` is stubbed in the window tests so the suite never touches the host firewall
- [ ] 2026-09-12 Write `LICENSE` (GPL-3.0), `LICENSES/`, and `THIRD_PARTY_NOTICES.md` — sing-box (GPL-3.0, with SHA-256 and corresponding-source links), LibreSpeed (LGPL-3.0), iperf3 (BSD-3-Clause, distro-installed so not redistributed)
- [ ] 2026-09-12 Translate the six governance docs into `translated_zh_cn/` and `translated_zh_tw/` — currently untranslated template placeholders; dispatch `doc-translator`, one instance per document per language
- [ ] 2026-09-12 End-to-end verification on a real second machine — reach the public page over both 80 and 443 from off-host, open a window and run `iperf3 -c <ip> --json`, confirm `mean_rtt` is present

<!--
Tick, do not delete. A ticked item is the evidence that the requirement was
heard and handled -- deleting it makes the list look like it was always short,
and leaves no way to tell "never asked for" from "asked for and done".

Scope, so this file does not become a second copy of everything:

  here            every requirement, open or ticked
  DECISIONS.md    only what was rejected AND would otherwise be proposed again
                  as a fresh idea; it is a guard against re-proposing, not a
                  decision log -- most choices never belong there
  CHANGELOG.md    what shipped in each version, written for whoever uses the
                  project; this file is the working list behind it
  STATUS.md       the topmost unticked item, plus current state
  the todo tool   steps inside today's session; those are gone tomorrow, which
                  is exactly why they are not written here

Update on events, not "before the session ends" (a session never announces its
end):
  - the user asks for something that is not being worked on right now -- write
    it down at that moment, not at the end
  - an item is finished -- tick it, and move STATUS.md's Next to the next
    unticked one
  - an item stops being wanted -- strike it in place with the reason
    (- [~] ... -- dropped, because X); deleting it silently is how it comes
    back as a proposal in two weeks. Add a DECISIONS.md entry only if the idea
    is one that would return on its own

Keep it to work that is actually intended. A backlog nobody trusts to be real
gets skimmed once and then ignored.

In a public repository the same redaction rule as STATUS.md applies: no Notion
URLs, no local/NAS absolute paths, no internal hostnames. Those live in
../.local-notes.md, outside repo/.
-->
