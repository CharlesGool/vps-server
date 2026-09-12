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
- [x] 2026-09-12 Vendor `Anytsl-Serve` v1.2.0 — `anytls/setup-anytls.sh` plus the sing-box binary and `sing-box.version`; rename the unit to `vps-server-anytls.service` and the binary to `sing-box-vps-server`; record the tag in `anytls/.upstream-version`
- [x] 2026-09-12 Make `install.sh` a module menu — web / anytls / iperf3 independently selectable; refuse when 80 or 443 is already bound; refuse when upstream `sing-box-anytls.service` is running; skip anytls on non-amd64. **Written but never executed** — see the verification item below
- [x] 2026-09-12 Extend `uninstall.sh` to tear down whichever modules it finds — default full removal, `KEEP_DATA=1` to keep the visitor database; anytls is torn down before `$PREFIX` is deleted, since its teardown script lives inside `$PREFIX`. **Written but never executed**
- [x] 2026-09-12 Actually run `install.sh` end to end — done by the operator on a real systemd host with an isolated prefix. The service came up, the summary block was correct, and the deployed instance served the public page on both 18080 and 18443 with the right arrival port, 404'd console routes on the public port, and answered on the console port. Two bugs fell out and are fixed: the closing "to remove" line ignored `PREFIX`/`SERVICE_NAME` (so the teardown silently scanned the defaults and removed nothing), and every usage example said `./script.sh`, which cannot work from a CIFS working copy
- [x] 2026-09-12 Verify the iperf3 window under systemd sandboxing — done on a real installed instance. `NoNewPrivileges` and `ProtectSystem=strict` do not block `firewall_port()`: opening a window added `-A INPUT -p tcp -m tcp --dport 5201 -j ACCEPT` and closing it withdrew the rule. Teardown afterwards left no unit, directory, rule, process or listener behind
- [x] 2026-09-12 Run `install.sh` with the anytls module — done. The first attempt failed before sing-box was installed (the binary was recorded as `100644` because CIFS ate the mode bit during vendoring, and `install_singbox` tested `-x`); after fixing both sides the module installed, the three renamed constants landed where intended, the service came up, and `uninstall.sh` removed the unit, the binary, the config directory and the firewall rule
- [x] 2026-09-12 Show the installed anytls node in the console — `/anytls` reports whether the service is up and offers a copyable Clash entry and `anytls://` link. Read-only; `setup-anytls.sh` still owns the node's state
- [ ] 2026-09-12 Verify `refuse_if_upstream_running` — the only anytls path still unexercised. Start `Anytsl-Serve`'s own `sing-box-anytls.service`, then run this project's anytls install and confirm it refuses with the two-options message instead of quietly adding a second inbound
- [x] 2026-09-12 Audit the console colours against WCAG AA in both schemes — five real failures fixed, the worst being the iperf "window open" line at 1.77:1 in light mode, effectively invisible on white. Every component colour is now a semantic token with a light-mode value; `StylesheetTest` guards the structure
- [ ] 2026-09-12 Inject `VERSION` from the real tag instead of hard-coding it — `app.py` sets `VERSION = "0.1.0"` as a literal, which `project-management`'s `references/webui.md` §1 forbids and lists as a common error: forget it at release time and the UI keeps claiming the previous version, with nothing reporting it. Read `git describe --tags --exact-match` at install time (or bake it into `install.sh`'s copy step) and fall back to `dev-<short sha>` rather than to a stale tag. Inherited from `vps-webserver`; found while reading webui.md for the colour work, not fixed then because it was out of scope
- [x] 2026-09-12 Make `install.sh` upgrade-aware — it detects an existing install, offers to keep its configuration, replays the settings recorded in the unit's `Environment=` lines, preserves the anytls node's credentials, and asks only about settings the installed version predates. Installs made before `$PREFIX/.install-state` existed are handled by inferring the module list from disk and saying plainly that the new-settings diff cannot be computed
- [x] 2026-09-12 Add a console button to rotate the anytls port and password — `/anytls/reset` with a server-validated confirmation; it calls `setup-anytls.sh reset` rather than writing the node itself
- [x] 2026-09-12 Run an actual upgrade over an older install — done by the operator. The upgrade path worked: settings replayed, the anytls node kept its port and password. Two bugs surfaced and are fixed: the summary printed the default public port instead of the replayed one because `PUBLIC_HTTP_PORT` was derived before the replay (the port-conflict check had the same stale value, so it was guarding the wrong port), and the console's reset button failed outright because the web service's `ProtectSystem=strict` makes `/etc` read-only to it
- [x] 2026-09-12 Click the anytls reset button once after reinstalling — done, and verified on the host afterwards: the port rotated, the node listens on the new one, the new firewall rule is present, the **old port's rule was withdrawn** (no leaked ACCEPT), and the transient unit was reaped. Four repeat installs left no duplicate rules
- [x] 2026-09-12 Full audit across security, Python concurrency, shell correctness and doc/code drift — eleven real defects found and fixed; see the audit commit. The largest were `VPSSRV_CONSOLE_PORT=0` in `.env.example` binding port 0 (a console that moved on every restart), `install.sh` stopping the service before checking ports (leaving it stopped on an unrelated conflict), and an orphaned firewall rule whenever the anytls port changed outside `reset`
- [ ] 2026-09-12 Decide whether the shared `_db_lock` needs decoupling — every public-page hit takes a process-wide lock and does a synchronous SQLite write, and the console shares that lock, so in principle anonymous flooding can slow an authenticated page. **Measured and not reproduced**: 60 concurrent flooders left console latency at 0.4–0.6 ms, identical to idle. Recorded so the mechanism is not rediscovered as new; do not rearchitect without a measurement that shows harm
- [ ] 2026-09-12 Harden `main()`'s startup/shutdown edges in `app.py` — the `try/finally` wraps only `console.serve_forever()`, so a signal arriving during listener setup skips cleanup, and a second `SIGTERM` during `IPERF_WINDOW.close()` can escape before the firewall rule is withdrawn. Also call `shutdown()` before `server_close()` on the two threaded public listeners, which currently logs an `OSError` traceback on every restart
- [ ] 2026-09-12 `VPSSRV_MODULES=iperf3` on its own silently installs nothing — it misses the `web` check and takes the anytls-only early exit, which does not handle iperf3, then exits 0. Either reject the combination or install iperf3 there
- [ ] 2026-09-12 Consider rate-limiting `/login` — not a vulnerability today (the generated password is `secrets.token_urlsafe(15)`), but there is no backoff at all. Defensive depth, not a fix
- [ ] 2026-09-12 Clean the stale `--dport 31515` ACCEPT left on the maintainer's host by an install/uninstall cycle from before `close_firewall` was reachable from `reset` — `iptables -D INPUT -p tcp --dport 31515 -j ACCEPT`. Not a code bug in the current tree; recorded so it is not mistaken for one later
- [x] 2026-09-12 Audit the console layout — the iperf form's input sat a rem above its button because `.inline-form label` inherited `margin-bottom: 1rem` and flex `align-items: flex-end` aligns margin boxes; the dashboard grid was pinned to two columns while the tile count grew to four; the key/value grid, the inline forms and the copy rows had no narrow-screen rules at all. No fixed pixel widths anywhere, and every touch target clears the WCAG 2.2 minimum of 24 CSS px
- [ ] 2026-09-12 Check the copy buttons in a browser over plain HTTP — `navigator.clipboard` is undefined outside a secure context, which is the default setup, so the `document.execCommand` fallback in `static/copy.js` is the path that actually runs. Unit tests cover the page markup, not the browser behaviour
- [x] 2026-09-12 Tests for the new surface — `ProbeHandler` answers 404 on every console route; the iperf3 window expires and kills its child; the window does not survive a restart. tests cover it; `firewall_port` is stubbed in the window tests so the suite never touches the host firewall
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
