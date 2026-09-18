# Backlog

**English** | [简体中文](zh_cn/BACKLOG.md) | [繁體中文](zh_tw/BACKLOG.md)

## Documentation

- Project overview: [README](../README.md)
- Design rationale: [DESIGN](DESIGN.md)
- Release history: [CHANGELOG](CHANGELOG.md)
- Current state: [STATUS](STATUS.md)
- Rejected ideas: [DECISIONS](DECISIONS.md)
- Third-party notices: [THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES.md)

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

- [x] 2026-09-12 Stop the changelog page rendering the maintainer comment — `render_changelog()` had no comment handling, so every line between `<!--` and `-->` became a paragraph on the page in all three languages. Shipped visible in v1.0.0, fixed in v1.0.1

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
- [x] 2026-09-12 Verify `refuse_if_upstream_running` — all three branches exercised: an active upstream unit refuses with exit 1, an absent one proceeds, and `VPSSRV_ALLOW_DUAL_ANYTLS=1` warns then proceeds. Verified by pointing the guard's service name at a unit that really is running rather than by installing `Anytsl-Serve`, so the branch logic is proven and the literal collision has still never happened on a host
- [x] 2026-09-12 Audit the console colours against WCAG AA in both schemes — five real failures fixed, the worst being the iperf "window open" line at 1.77:1 in light mode, effectively invisible on white. Every component colour is now a semantic token with a light-mode value; `StylesheetTest` guards the structure
- [x] 2026-09-12 Inject `VERSION` from the real tag instead of hard-coding it — `app.py` sets `VERSION = "0.1.0"` as a literal, which `project-management`'s `references/webui.md` §1 forbids and lists as a common error: forget it at release time and the UI keeps claiming the previous version, with nothing reporting it. Read `git describe --tags --exact-match` at install time (or bake it into `install.sh`'s copy step) and fall back to `dev-<short sha>` rather than to a stale tag. Inherited from `vps-webserver`; found while reading webui.md for the colour work, not fixed then because it was out of scope
- [x] 2026-09-12 Make `install.sh` upgrade-aware — it detects an existing install, offers to keep its configuration, replays the settings recorded in the unit's `Environment=` lines, preserves the anytls node's credentials, and asks only about settings the installed version predates. Installs made before `$PREFIX/.install-state` existed are handled by inferring the module list from disk and saying plainly that the new-settings diff cannot be computed
- [x] 2026-09-12 Add a console button to rotate the anytls port and password — `/anytls/reset` with a server-validated confirmation; it calls `setup-anytls.sh reset` rather than writing the node itself
- [x] 2026-09-12 Run an actual upgrade over an older install — done by the operator. The upgrade path worked: settings replayed, the anytls node kept its port and password. Two bugs surfaced and are fixed: the summary printed the default public port instead of the replayed one because `PUBLIC_HTTP_PORT` was derived before the replay (the port-conflict check had the same stale value, so it was guarding the wrong port), and the console's reset button failed outright because the web service's `ProtectSystem=strict` makes `/etc` read-only to it
- [x] 2026-09-12 Click the anytls reset button once after reinstalling — done, and verified on the host afterwards: the port rotated, the node listens on the new one, the new firewall rule is present, the **old port's rule was withdrawn** (no leaked ACCEPT), and the transient unit was reaped. Four repeat installs left no duplicate rules
- [x] 2026-09-12 Full audit across security, Python concurrency, shell correctness and doc/code drift — eleven real defects found and fixed; see the audit commit. The largest were `VPSSRV_CONSOLE_PORT=0` in `.env.example` binding port 0 (a console that moved on every restart), `install.sh` stopping the service before checking ports (leaving it stopped on an unrelated conflict), and an orphaned firewall rule whenever the anytls port changed outside `reset`
- [ ] 2026-09-12 Decide whether the shared `_db_lock` needs decoupling — every public-page hit takes a process-wide lock and does a synchronous SQLite write, and the console shares that lock, so in principle anonymous flooding can slow an authenticated page. **Measured and not reproduced**: 60 concurrent flooders left console latency at 0.4–0.6 ms, identical to idle. Recorded so the mechanism is not rediscovered as new; do not rearchitect without a measurement that shows harm
- [ ] 2026-09-12 Harden `main()`'s startup/shutdown edges in `app.py` — the `try/finally` wraps only `console.serve_forever()`, so a signal arriving during listener setup skips cleanup, and a second `SIGTERM` during `IPERF_WINDOW.close()` can escape before the firewall rule is withdrawn. Also call `shutdown()` before `server_close()` on the two threaded public listeners, which currently logs an `OSError` traceback on every restart
- [ ] 2026-09-12 `VPSSRV_MODULES=iperf3` on its own silently installs nothing — it misses the `web` check and takes the anytls-only early exit, which does not handle iperf3, then exits 0. Either reject the combination or install iperf3 there
- [ ] 2026-09-12 Consider rate-limiting `/login` — not a vulnerability today (the generated password is `secrets.token_urlsafe(15)`), but there is no backoff at all. Defensive depth, not a fix
- [x] 2026-09-12 Clean the stale `--dport 31515` ACCEPT left on the maintainer's host by an install/uninstall cycle from before `close_firewall` was reachable from `reset` — `iptables -D INPUT -p tcp --dport 31515 -j ACCEPT`. Not a code bug in the current tree; recorded so it is not mistaken for one later
- [x] 2026-09-12 Audit the console layout — the iperf form's input sat a rem above its button because `.inline-form label` inherited `margin-bottom: 1rem` and flex `align-items: flex-end` aligns margin boxes; the dashboard grid was pinned to two columns while the tile count grew to four; the key/value grid, the inline forms and the copy rows had no narrow-screen rules at all. No fixed pixel widths anywhere, and every touch target clears the WCAG 2.2 minimum of 24 CSS px
- [x] 2026-09-12 Check the copy buttons in a browser over plain HTTP — confirmed working by the operator, so the `document.execCommand` fallback does run in a non-secure context — `navigator.clipboard` is undefined outside a secure context, which is the default setup, so the `document.execCommand` fallback in `static/copy.js` is the path that actually runs. Unit tests cover the page markup, not the browser behaviour
- [x] 2026-09-12 Tests for the new surface — `ProbeHandler` answers 404 on every console route; the iperf3 window expires and kills its child; the window does not survive a restart. tests cover it; `firewall_port` is stubbed in the window tests so the suite never touches the host firewall
- [x] 2026-09-12 Write `LICENSE` (GPL-3.0), `LICENSES/`, and `THIRD_PARTY_NOTICES.md` — sing-box (GPL-3.0, with SHA-256 and corresponding-source links), LibreSpeed (LGPL-3.0), iperf3 (BSD-3-Clause, distro-installed so not redistributed)
- [x] 2026-09-12 Translate the six governance docs into `translated_zh_cn/` and `translated_zh_tw/` — currently untranslated template placeholders; dispatch `doc-translator`, one instance per document per language
- [x] 2026-09-12 End-to-end verification on a real second machine — reach the public page over both 80 and 443 from off-host, open a window and run `iperf3 -c <ip> --json`, confirm `mean_rtt` is present

- [x] 2026-09-12 Fix `install_iperf3()` silently failing to install iperf3 — it ran `apt-get update -qq && apt-get install -y -qq iperf3` as one `&&` chain with all output discarded, so a single unrelated repo failing `apt-get update` (a stale third-party `.list`, seen on a real VPS) skipped the install attempt entirely and gave no diagnostic. Fixed to retry `apt-get update` up to 3 times, attempt the install regardless of whether update fully succeeded, set `DEBIAN_FRONTEND=noninteractive`, and stop swallowing apt's output. Verified with a full end-to-end `install.sh` run in a disposable, systemd-enabled Debian 12 container (not this live host, to avoid binding 80/443 and starting real services here) with the exact broken-repo scenario seeded: iperf3 installed, `vps-server-web.service` came up active, and both the console and the public listener answered HTTP 200. Shipped as v1.0.2

- [x] 2026-09-12 Fix v1.0.2's iperf3 install fix being incomplete — the operator hit a live failure upgrading a real host from v1.0.1 to v1.0.2: `apt-get update` reported success but `security.debian.org`'s CDN handed back a stale package index, so `apt-get install` 404'd fetching a `.deb` the index had just claimed existed. Retrying `update` alone (v1.0.2's fix) doesn't reliably clear this, since the retry can hit the same stale edge. `install_iperf3()` now retries the whole update-then-install pair together, up to 3 times — confirmed against a fake-apt harness that fails once then succeeds, and against the same broken-repo Docker/container repros used for v1.0.2, plus a fresh full end-to-end `install.sh` container run. Also fixed the README's `## Install` section, which had carried the unfilled `templates/README.md` placeholders (`<repo-url>`, an example `v0.1.0` tag never actually released) since v1.0.0 — replaced with the real GitHub URL and the current release tag. Shipped as v1.0.3

- [x] 2026-09-12 Print the machine's real addresses in the installer's closing summary — it emitted a literal `<this-server>` / `<本机地址>` placeholder, so the public-page and console URLs had to be hand-edited before they were usable, and on a box reachable only over ZeroTier or Tailscale there was nothing to tell the operator which address to try. `primary_ip()` takes the source address from `ip -4 route get`, which is the one the kernel would actually use to leave the box; `other_ips()` lists the rest, each labelled with its interface, reusing `setup-anytls.sh`'s container/bridge interface filter but deliberately keeping VPN interfaces since those are often how the console is reached. Every failure path falls back to the old placeholder rather than failing the install. Verified in a disposable systemd container with a second interface attached: correct output and column alignment in all three languages, every printed address answered HTTP 200, and stubbing `ip` out entirely still exited 0. Shipped as v1.0.4

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
