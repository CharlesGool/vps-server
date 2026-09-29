---
name: project-log
description: Project decisions, limitations, bugs, and changes
metadata:
  version: "1.0.0"
  lang: "en"
---

# vps-server — Log

This record collects known bugs, decisions, historical work, current acceptance limits, and released changes. Statements of past tests are not tests rerun for this documentation migration.

## Multi-language

**English** | [简体中文](zh-CN/LOG.md) | [繁體中文 (台灣)](zh-TW/LOG.md) | [繁體中文 (香港)](zh-HK/LOG.md) | [हिन्दी](hi/LOG.md) | [Español](es/LOG.md) | [العربية](ar/LOG.md) | [Français](fr/LOG.md)

## Documentation

- Project overview: [README](../README.md)

- Design rationale: [DESIGN](DESIGN.md)

- Release history: [LOG](LOG.md)

- Third-party notices: [THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES.md)

## Bugs

- [ ] 2026-09-12 Decide whether the shared `_db_lock` needs decoupling — every public-page hit takes a process-wide lock and does a synchronous SQLite write, and the console shares that lock, so in principle anonymous flooding can slow an authenticated page. **Measured and not reproduced**: 60 concurrent flooders left console latency at 0.4–0.6 ms, identical to idle. Recorded so the mechanism is not rediscovered as new; do not rearchitect without a measurement that shows harm

No other breaking issue is recorded in the prior status snapshot; the startup/shutdown signal edges, iperf3-only installer combination, and login rate limiting were fixed on `feat/hardening-batch`, which still requires merge/review. This is not a claim that the current branch was revalidated on a real host.

## Limitations

- Automated checks verify catalog keys, placeholders, and document structure, but the new translations have not had independent native-language review.
- A live source checkout may contain ignored runtime state (`admin_password.txt`, `console_port.txt`, `data/`, `certs/`) and Python cache (`__pycache__/`) at its root. The structure checker reports these local files; a clean export of versioned project files passes. Preserve the runtime state during migration. On a CIFS working copy mounted with fixed 0644 file and 0755 directory modes, `chmod` does not change the displayed modes of local secrets; the mount's access control requires separate assessment.
- Current branch host acceptance limits are recorded below.

## Decisions

<a id="vps-decisions"></a>

The dated decisions below preserve both rejected alternatives and their costs. A historical decision is not a new legal or release approval.

| Decisions | Reasons, rejected alternatives, and costs |
| --- | --- |
| 2026-09-22 — `proxy` is one sing-box process with up to four inbounds, not four clones of anytls | - **Resolved, not rejected:** whether the vendored sing-box binary covers   vmess/vless/trojan/shadowsocks — confirmed by actually running all four   simultaneously in one process (not just `sing-box check`); no second   backend needed. hysteria2/tuic tried and left out (different field/TLS   requirements). - **Rejected:** one systemd unit + config per protocol, mirroring anytls's   own shape exactly — four units to monitor, three redundant self-signed   certs, and it fights the shape a future per-node traffic-accounting   feature would want (one process whose `inbounds` list is already the node   list). - **Cost:** the shared vendored binary is now used by two independent   modules; each module's `uninstall()` **MUST** check the other's config exists   before deleting it (anytls's vendored script gained this as a documented   local deviation — see `anytls/.upstream-version`). |
| 2026-09-21 — `prompt_new_settings()` ends with an explicit `return 0`, not just falling off the loop | - **Rejected:** letting the function's exit status fall out of its final `for`   loop, as most other functions in `install.sh` do — the loop's last   statement used to be a bare `[ -n "$value" ] && export ...`, so leaving the   *last* prompted setting at its default made that test false, which became   the function's own return status. Called bare (`prompt_new_settings` inside   an `if`-body, not itself exempt from `set -e`) that silently killed the   whole installer right after the last prompt — no error, no file copy, no   `VERSION` stamp, no service restart. Reproduced live on v1.0.4 → v1.1.1 and   fixed by wrapping the export in `if`/`fi` and adding an explicit trailing   `return 0`, so the function's exit status no longer depends on which   setting happened to be prompted last. - **Do not remove the trailing `return 0` as apparent dead code.** It is the   fix, not boilerplate. |
| 2026-09-19 — Port forwards are iptables DNAT, reapplied from JSON at every start; nothing written outside the process | - **Rejected:** a per-rule `socat` userspace relay — safer (no NAT table or   `ip_forward` changes), but the user explicitly chose kernel-level   DNAT+MASQUERADE for this project instead. - **Rejected:** `iptables-persistent` to survive a reboot at the kernel level   — that makes the console and a system package two sources of truth for the   same rules. `app.py` reapplies from its own JSON on every start instead   (DESIGN.md, "Port forwarding lifecycle"), so there is exactly one. - **Rejected:** auto-reverting `net.ipv4.ip_forward` to `0` once the last   forward is removed — it is host-wide, and other software (this project's   own test host runs Docker) may depend on it staying on. - **Cost:** stopping `vps-server-web` (not restarting it) withdraws every   forward's kernel state, even enabled ones — same fail-safe direction as the   iperf3 window. Do not move the rules into a separate always-on unit to   "fix" this; that was considered and rejected above. |
| 2026-09-12 — The public page and the console are separate listeners with separate handler classes | - **Rejected:** One listener serving both, with console routes gated behind a path prefix plus an auth check — an auth check can be bugged into allowing; a route that does not exist cannot. - **Rejected:** Putting the console itself on 80/443 behind the password and dropping the random port — that discards the obscurity layer `vps-webserver` deliberately chose. - **Cost:** Three listeners in one process, and two handler classes that each need the visitor-logging hook wired in separately. - **Do not re-add this as an improvement.** |
| 2026-09-12 — iperf3 runs only inside an operator-opened, time-boxed window | - **Rejected:** An always-on public `iperf3 -s` — any stranger can saturate the uplink indefinitely and nothing surfaces that it is happening. - **Rejected:** Always-on with `--authorized-users-path` RSA authentication — credentials would have to be handed over out of band before anyone can test, which defeats the point of "give someone the IP and let them measure". - **Cost:** A remote tester cannot test unattended; someone has to open a window first. The public page advertises an open window so the tester knows when to connect. |
| 2026-09-12 — Port 443 uses a self-signed certificate; no ACME, no domain | - **Rejected:** certbot / acme.sh against a real domain — the page exists to answer "can you reach this IP", and a browser warning page already proves reachability. A domain dependency and a renewal timer buy nothing for that question. - **Rejected:** Serving only port 80 — that cannot distinguish "the host is unreachable" from "443 specifically is blocked", which is the common case worth detecting. - **Cost:** Every HTTPS visit shows a certificate warning. Expected; do not "fix" it with HSTS or a pinned exception. |
| 2026-09-12 — The sing-box binary ships in the repository, so the whole project is GPL-3.0 | - **Rejected:** Downloading sing-box at install time to keep the repo small and the licence Apache-2.0 — `Anytsl-Serve` already rejected exactly this to keep installation working without GitHub access; re-deciding it here would silently undo that goal. - **Rejected:** Dropping the anytls module to preserve `vps-webserver`'s Apache-2.0 — the brief was to combine the two projects, not to pick one. - **Cost:** ~57 MB in git, growing with every sing-box bump; and `vps-webserver`'s Apache-2.0 code is redistributed here under GPL-3.0. |
| 2026-09-12 — Upstream projects are vendored, not superseded and not submoduled | - **Rejected:** Letting vps-server replace `vps-webserver` and `Anytsl-Serve` and archiving both — all three are to stay independently maintained and independently released. - **Rejected:** git submodules pointing at the two upstream repos — a submodule cannot carry the renames this project needs (unit names, binary name, `VPSWS_` → `VPSSRV_`), and a clone would then need network access to two more repos. - **Cost:** The same code lives in three repositories and will drift. Mitigation: `.upstream-version` files record the exact upstream tag each vendored tree came from, and **MUST** be updated in the same commit as any refresh. |

## Current state and acceptance limits

<a id="vps-current-state"></a>

Version 2.0.0 includes experimental frps and Lucky install paths. Their
behavior has not been accepted on a real host; the new checkout layout has
only local automated verification in this release cycle.

The 2026-09-22 source snapshot described `feat/proxy-protocols` stacked on
unmerged `feat/hardening-batch`. Version 2.0.0 incorporates their current
project tree, but the operator's real-host test of the proxy module is still
pending. The independently applied address-deduplication and public-IP fixes
were part of the branch review. No live-host verification of the proxy feature
is claimed here; the old container used a stub `systemctl` because systemd did
not run as PID 1. The recorded 147/147, 150/150, 153/153 and 156/156 suite
results and earlier real-host checks below are historical, not new validation.

### Branch record (2026-09-22 status snapshot)

<a id="vps-branch-record-2026-09-22"></a>

The original status described the feature as implemented and self-tested while
operator review was pending, stacked on `feat/hardening-batch` for its independent
y/n module picker. In the first disposable Docker verification, systemd could
not run as PID 1, so `systemctl` was stubbed; real sing-box config checks,
iptables rules, credential rotation, shared-binary-aware uninstall, and an
unattended install plus upgrade re-run were exercised. Two bugs found in those
tests were fixed: swallowed invalid `PROXY_PROTOCOLS` validation (zero inbounds)
and a generated port overflowing sing-box's uint16 limit. The record reports
19 new tests and 147/147 passing at that point; it does **not** constitute
systemd or real-host verification of the proxy feature.

Later operator testing found an artificial split between `/anytls` and `/proxy`,
and multiple top-level cards appearing side by side in the flex layout. The
branch now puts all installed node sections inside one card on `/proxy`, redirects
`/anytls` there, and uses one navigation entry. Address deduplication and
removal of `get_ip()` public-IP auto-detection were reapplied from `main` to
this branch, rather than merged, because of the concurrent proxy-page rewrite;
branch review **MUST** reconcile the independent applications. The historical
record reports a combined anytls+proxy regression fixture and redirect tests
at 150/150 passing, then an iperf3 countdown/command-example fix reapplied
from `main` at 153/153 passing.

A subsequent operator request changed the combined proxy reset button into
one button per protocol. `setup-proxy.sh reset <protocol>` preserves the other
protocols' credentials and ports; bare `reset` still rotates all protocols
from a terminal, not from the console. Disposable-container checks rotated
one of four installed protocols, preserved the others and the full protocol
set, and rejected an unknown name without changing the config. The historical
record reports six added/rewritten tests and 156/156 passing; no new test
or release claim is made here.

For earlier released work, the status recorded a real-host operator check of
v1.1.0 port forwarding after the disposable three-container harness and
119/119 unit tests. Before v1.0.0, it recorded operator real-host checks of
the public page on both ports, console and browser test, iperf3 reaching
2.8 Gbit/s over LAN and refusing connections after its window closed, anytls
install/reset/teardown, upgrade preservation, and all three interface
languages. These are historical observations, not current-branch acceptance.
The old snapshot called the SQLite-lock measurement the next investigation,
reported no blocking issue, and did not scope the traffic accounting, first-run
wizard, frps, `gdy666/lucky` features, or highly customizable nodes. Their
current destinations are [Bugs][local-link-001] and [Design Goals][local-link-002].

## v2.0.0 checkout layout migration

This checkout moves web implementation to `src/web/app.py`. Installation and removal commands live at
`deploy/install.sh` and `deploy/uninstall.sh`;
`deploy/systemd/`, `deploy/anytls/`, and `deploy/proxy/` own operational source.
The amd64 binary, version metadata, and upstream notice now live at
`third_party/sing-box/{sing-box,sing-box.version,LICENSE}`. Directly served vendor
assets remain under `static/third_party/`; the dependency verifier lives in `tools/verify_dependencies/`.
Installed layouts are still flat (`$PREFIX/app.py`, `$PREFIX/static/`,
`$PREFIX/anytls/`, `$PREFIX/proxy/`, `$PREFIX/sing-box`) and module settings
still use `/etc/vps-server-anytls/` and `/etc/vps-server-proxy/`.
The earlier path names in dated decisions and completed work below describe
their historical checkout, not current instructions. Offline migration checks
are not real-host/systemd validation; operator acceptance remains pending.

## Completed work history

<a id="vps-completed-work"></a>

These checked items are the former backlog's dated implementation and verification record, not a newly executed test report. For remaining goals, see [Design Goals][local-link-003]; the unresolved `_db_lock` item remains under [Bugs][local-link-004].

- Completed: 2026-09-12 Stop the changelog page rendering the maintainer comment — `render_changelog()` had no comment handling, so every line between `<!--` and `-->` became a paragraph on the page in all three languages. Shipped visible in v1.0.0, fixed in v1.0.1

- Completed: 2026-09-12 Agree the architecture and write `DESIGN.md` — done before any code

- Completed: 2026-09-12 Vendor `vps-webserver` v0.4.1 — copy `app.py`, `static/`, `tests/`, `install.sh`, `uninstall.sh`, `systemd/` from the upstream tag; record the tag in `.upstream-version`; rename the `VPSWS_` env prefix to `VPSSRV_` in the same commit

- Completed: 2026-09-12 Split `app.py` into two handlers — `ConsoleHandler` keeps every existing route; add `ProbeHandler` serving only `/` and `/favicon.ico`; start the public listeners on 80 and 443 alongside the console listener

- Completed: 2026-09-12 Write the public reachability page — source IP, server clock, arrival protocol/port, and nothing about the host; no JavaScript. The stylesheet ended up inlined as `PROBE_CSS` rather than a `static/probe.css` file, so the public listener has no file-serving route at all

- Completed: 2026-09-12 Implement the iperf3 window — console route to open/close, `subprocess.Popen("iperf3 -s -p …")`, in-memory deadline, expiry thread, firewall open/withdraw, teardown on `SIGTERM`

- Completed: 2026-09-12 Surface the open window on the public page — port and remaining minutes, so a remote tester knows when to connect

- Completed: 2026-09-12 Vendor `Anytsl-Serve` v1.2.0 — `anytls/setup-anytls.sh` plus the sing-box binary and `sing-box.version`; rename the unit to `vps-server-anytls.service` and the binary to `sing-box-vps-server`; record the tag in `anytls/.upstream-version`

- Completed: 2026-09-12 Make `install.sh` a module menu — web / anytls / iperf3 independently selectable; refuse when 80 or 443 is already bound; refuse when upstream `sing-box-anytls.service` is running; skip anytls on non-amd64. **Written but never executed** — see the verification item below

- Completed: 2026-09-12 Extend `uninstall.sh` to tear down whichever modules it finds — default full removal, `KEEP_DATA=1` to keep the visitor database; anytls is torn down before `$PREFIX` is deleted, since its teardown script lives inside `$PREFIX`. **Written but never executed**

- Completed: 2026-09-12 Actually run `install.sh` end to end — done by the operator on a real systemd host with an isolated prefix. The service came up, the summary block was correct, and the deployed instance served the public page on both 18080 and 18443 with the right arrival port, 404'd console routes on the public port, and answered on the console port. Two bugs fell out and are fixed: the closing "to remove" line ignored `PREFIX`/`SERVICE_NAME` (so the teardown silently scanned the defaults and removed nothing), and every usage example said `./script.sh`, which cannot work from a CIFS working copy

- Completed: 2026-09-12 Verify the iperf3 window under systemd sandboxing — done on a real installed instance. `NoNewPrivileges` and `ProtectSystem=strict` do not block `firewall_port()`: opening a window added `-A INPUT -p tcp -m tcp --dport 5201 -j ACCEPT` and closing it withdrew the rule. Teardown afterwards left no unit, directory, rule, process or listener behind

- Completed: 2026-09-12 Run `install.sh` with the anytls module — done. The first attempt failed before sing-box was installed (the binary was recorded as `100644` because CIFS ate the mode bit during vendoring, and `install_singbox` tested `-x`); after fixing both sides the module installed, the three renamed constants landed where intended, the service came up, and `uninstall.sh` removed the unit, the binary, the config directory and the firewall rule

- Completed: 2026-09-12 Show the installed anytls node in the console — `/anytls` reports whether the service is up and offers a copyable Clash entry and `anytls://` link. Read-only; `setup-anytls.sh` still owns the node's state

- Completed: 2026-09-12 Verify `refuse_if_upstream_running` — all three branches exercised: an active upstream unit refuses with exit 1, an absent one proceeds, and `VPSSRV_ALLOW_DUAL_ANYTLS=1` warns then proceeds. Verified by pointing the guard's service name at a unit that really is running rather than by installing `Anytsl-Serve`, so the branch logic is proven and the literal collision has still never happened on a host

- Completed: 2026-09-12 Audit the console colours against WCAG AA in both schemes — five real failures fixed, the worst being the iperf "window open" line at 1.77:1 in light mode, effectively invisible on white. Every component colour is now a semantic token with a light-mode value; `StylesheetTest` guards the structure

- Completed: 2026-09-12 Inject `VERSION` from the real tag instead of hard-coding it — `app.py` sets `VERSION = "0.1.0"` as a literal, which `project-management`'s `references/webui.md` §1 forbids and lists as a common error: forget it at release time and the UI keeps claiming the previous version, with nothing reporting it. Read `git describe --tags --exact-match` at install time (or bake it into `install.sh`'s copy step) and fall back to `dev-<short sha>` rather than to a stale tag. Inherited from `vps-webserver`; found while reading webui.md for the colour work, not fixed then because it was out of scope

- Completed: 2026-09-12 Make `install.sh` upgrade-aware — it detects an existing install, offers to keep its configuration, replays the settings recorded in the unit's `Environment=` lines, preserves the anytls node's credentials, and asks only about settings the installed version predates. Installs made before `$PREFIX/.install-state` existed are handled by inferring the module list from disk and saying plainly that the new-settings diff cannot be computed

- Completed: 2026-09-12 Add a console button to rotate the anytls port and password — `/anytls/reset` with a server-validated confirmation; it calls `setup-anytls.sh reset` rather than writing the node itself

- Completed: 2026-09-12 Run an actual upgrade over an older install — done by the operator. The upgrade path worked: settings replayed, the anytls node kept its port and password. Two bugs surfaced and are fixed: the summary printed the default public port instead of the replayed one because `PUBLIC_HTTP_PORT` was derived before the replay (the port-conflict check had the same stale value, so it was guarding the wrong port), and the console's reset button failed outright because the web service's `ProtectSystem=strict` makes `/etc` read-only to it

- Completed: 2026-09-12 Click the anytls reset button once after reinstalling — done, and verified on the host afterwards: the port rotated, the node listens on the new one, the new firewall rule is present, the **old port's rule was withdrawn** (no leaked ACCEPT), and the transient unit was reaped. Four repeat installs left no duplicate rules

- Completed: 2026-09-12 Full audit across security, Python concurrency, shell correctness and doc/code drift — eleven real defects found and fixed; see the audit commit. The largest were `VPSSRV_CONSOLE_PORT=0` in `.env.example` binding port 0 (a console that moved on every restart), `install.sh` stopping the service before checking ports (leaving it stopped on an unrelated conflict), and an orphaned firewall rule whenever the anytls port changed outside `reset`

- Completed: 2026-09-12 Harden `main()`'s startup/shutdown edges in `app.py` — the `try/finally` now wraps the whole startup sequence, not just `console.serve_forever()`, so a signal during `start_public_listeners()`/`PORTFWD.load()` still triggers cleanup; further `SIGTERM`/`SIGINT` are ignored once teardown begins, so a second signal mid-`IPERF_WINDOW.close()` cannot escape before the firewall rule is withdrawn; every listener gets `shutdown()` before `server_close()`, which was the source of the `OSError` traceback on restart. Verified with a new subprocess-level test that starts the real `app.py`, confirms it accepts a connection, sends a real `SIGTERM`, and asserts a prompt clean exit — the first test to exercise `main()` itself rather than the handler classes directly

- Completed: 2026-09-12 `VPSSRV_MODULES=iperf3` on its own silently installs nothing — fixed by rejecting the combination outright with a clear message (iperf3 is a console button; without web there is no console to open it from). Verified in a disposable container: the unattended path now dies with the new message instead of silently exiting 0

- Completed: 2026-09-12 Rate-limit `/login` — added `LoginRateLimiter`: an IP that fails too many times within a window is locked out for a fixed duration, cleared by a correct login or by waiting it out. Defensive depth only, as scoped — the generated password was already far out of brute-force reach. Verified with unit tests against the limiter directly and an HTTP-level test confirming the real `/login` route returns 429 once locked out

- Completed: 2026-09-12 Clean the stale `--dport 31515` ACCEPT left on the maintainer's host by an install/uninstall cycle from before `close_firewall` was reachable from `reset` — `iptables -D INPUT -p tcp --dport 31515 -j ACCEPT`. Not a code bug in the current tree; recorded so it is not mistaken for one later

- Completed: 2026-09-12 Audit the console layout — the iperf form's input sat a rem above its button because `.inline-form label` inherited `margin-bottom: 1rem` and flex `align-items: flex-end` aligns margin boxes; the dashboard grid was pinned to two columns while the tile count grew to four; the key/value grid, the inline forms and the copy rows had no narrow-screen rules at all. No fixed pixel widths anywhere, and every touch target clears the WCAG 2.2 minimum of 24 CSS px

- Completed: 2026-09-12 Check the copy buttons in a browser over plain HTTP — confirmed working by the operator, so the `document.execCommand` fallback does run in a non-secure context — `navigator.clipboard` is undefined outside a secure context, which is the default setup, so the `document.execCommand` fallback in `static/copy.js` is the path that actually runs. Unit tests cover the page markup, not the browser behaviour

- Completed: 2026-09-12 Tests for the new surface — `ProbeHandler` answers 404 on every console route; the iperf3 window expires and kills its child; the window does not survive a restart. tests cover it; `firewall_port` is stubbed in the window tests so the suite never touches the host firewall

- Completed: 2026-09-12 Write `LICENSE` (GPL-3.0), `LICENSES/`, and `THIRD_PARTY_NOTICES.md` — sing-box (GPL-3.0, with SHA-256 and corresponding-source links), LibreSpeed (LGPL-3.0), iperf3 (BSD-3-Clause, distro-installed so not redistributed)

- Completed: 2026-09-12 Translate the six governance docs into `translated_zh_cn/` and `translated_zh_tw/` — currently untranslated template placeholders; dispatch `doc-translator`, one instance per document per language

- Completed: 2026-09-12 End-to-end verification on a real second machine — reach the public page over both 80 and 443 from off-host, open a window and run `iperf3 -c <ip> --json`, confirm `mean_rtt` is present

- Completed: 2026-09-12 Fix `install_iperf3()` silently failing to install iperf3 — it ran `apt-get update -qq && apt-get install -y -qq iperf3` as one `&&` chain with all output discarded, so a single unrelated repo failing `apt-get update` (a stale third-party `.list`, seen on a real VPS) skipped the install attempt entirely and gave no diagnostic. Fixed to retry `apt-get update` up to 3 times, attempt the install regardless of whether update fully succeeded, set `DEBIAN_FRONTEND=noninteractive`, and stop swallowing apt's output. Verified with a full end-to-end `install.sh` run in a disposable, systemd-enabled Debian 12 container (not this live host, to avoid binding 80/443 and starting real services here) with the exact broken-repo scenario seeded: iperf3 installed, `vps-server-web.service` came up active, and both the console and the public listener answered HTTP 200. Shipped as v1.0.2

- Completed: 2026-09-12 Fix v1.0.2's iperf3 install fix being incomplete — the operator hit a live failure upgrading a real host from v1.0.1 to v1.0.2: `apt-get update` reported success but `security.debian.org`'s CDN handed back a stale package index, so `apt-get install` 404'd fetching a `.deb` the index had just claimed existed. Retrying `update` alone (v1.0.2's fix) doesn't reliably clear this, since the retry can hit the same stale edge. `install_iperf3()` now retries the whole update-then-install pair together, up to 3 times — confirmed against a fake-apt harness that fails once then succeeds, and against the same broken-repo Docker/container repros used for v1.0.2, plus a fresh full end-to-end `install.sh` container run. Also fixed the README's `## Install` section, which had carried the unfilled `templates/README.md` placeholders (`<repo-url>`, an example `v0.1.0` tag never actually released) since v1.0.0 — replaced with the real GitHub URL and the current release tag. Shipped as v1.0.3

- Completed: 2026-09-12 Print the machine's real addresses in the installer's closing summary — it emitted a literal `<this-server>` / `<本机地址>` placeholder, so the public-page and console URLs had to be hand-edited before they were usable, and on a box reachable only over ZeroTier or Tailscale there was nothing to tell the operator which address to try. `primary_ip()` takes the source address from `ip -4 route get`, which is the one the kernel would actually use to leave the box; `other_ips()` lists the rest, each labelled with its interface, reusing `setup-anytls.sh`'s container/bridge interface filter but deliberately keeping VPN interfaces since those are often how the console is reached. Every failure path falls back to the old placeholder rather than failing the install. Verified in a disposable systemd container with a second interface attached: correct output and column alignment in all three languages, every printed address answered HTTP 200, and stubbing `ip` out entirely still exited 0. Shipped as v1.0.4

- Completed: 2026-09-19 Console-managed port forwarding — let the console forward a public TCP/UDP port on this host to a device reached over Tailscale or the LAN (the "this box has a public IP, that device does not" case). Implementation: iptables DNAT + MASQUERADE per rule, tagged with a comment for identification, rules persisted as JSON and reapplied idempotently every time the service starts (a plain restart or a reboot both replay from that file — the kernel's own tables remember nothing on their own). `net.ipv4.ip_forward` is turned on the first time it is needed and deliberately never turned back off automatically, since other software on the host may also depend on it. New `/portfwd` console page: add/enable/disable/delete, protocol tcp/udp/both, public-port collision check against every other listener this install already owns. Verified in a disposable three-container Docker harness (not this live host, which already runs Docker's own iptables/NAT state — same reasoning as every other full end-to-end test in this file): a "vps" container with two attached networks stood in for the public/private split, a "target" container stood in for the Tailscale/LAN device, and a "client" container stood in for a public visitor. Confirmed live: TCP and UDP both forward end to end; `net.ipv4.ip_forward` flips from `0` to `1` automatically on the first enabled rule; disable/enable toggles reachability immediately; killing and restarting the process twice in a row reapplies from `portfwd.json` with no duplicate iptables rules; a clean `SIGTERM` withdraws every rule's kernel state while leaving `enabled: true` on disk, so a restart brings it straight back; public-port collisions (tried against the console's own port) and an invalid target IP are both rejected with the right message. 119/119 unit tests pass, including new `PortForwardManagerTest` (mocked iptables) and `PortForwardConsoleTest` (live HTTP against the routes) classes. At the time of this work record it was built on `feat/portfwd`, not yet merged or released, and awaiting the operator's manual test; the subsequent status snapshot records that test and the [v1.1.0 release][local-link-005].

- Completed: 2026-09-21 Fix `install.sh` silently dying on a real upgrade, discovered by the operator upgrading a real host from v1.0.4 to v1.1.1 (`v1.1.0`'s two new `VPSSRV_PORTFWD_*` settings were the first time an upgrade actually had a genuinely new setting to prompt for). `prompt_new_settings()`'s final `for` loop ended with a bare `[ -n "$value" ] && export "$var=$value"`; accepting the *last* prompted setting's default made that test false, which became the function's own exit status, which — called bare inside an `if`-body, not itself exempt from `set -e` — killed the whole installer right after the last prompt with zero error output: no file copy, no `VERSION` stamp, no service restart, leaving the box silently stuck on the old version while looking like the upgrade had completed. Reproduced twice on the operator's real host (identical symptom, identical stale `ActiveEnterTimestamp` both times) and root-caused precisely with `bash -x` tracing plus an isolated bash reproduction of the exact `set -e`/`&&`/loop interaction. Fixed by wrapping the export in `if`/`fi` and adding an explicit trailing `return 0`. Verified two ways: an isolated bash snippet proving the exact failure/fix mechanics, and a full live repro in a disposable systemd container — installed real v1.0.4, then drove an actual interactive `bash install.sh` session over a real pty (via `expect`, not a piped/non-interactive stdin, which would have masked the bug) upgrading to v1.1.1: the unpatched script died at the exact same line as the operator's; the patched script completed, restamped `VERSION`, and restarted the service. Shipped as v1.1.2.

- Completed: 2026-09-19 Support more proxy protocols, following vaxilu/x-ui's lead — anytls is the only node type today; the user does not expect real extra overhead from adding more (e.g. vmess/vless/trojan/shadowsocks). Needs a decision first on whether sing-box (already vendored) covers the wanted protocols or whether a second backend is needed. **Resolved: it does** — confirmed by actually running vmess/vless/trojan/shadowsocks(2022-blake3-aes-128-gcm) simultaneously in one `sing-box run` process, not just passing `check`; hysteria2/tuic were tried and rejected (different field/TLS requirements, out of scope for this round). New `proxy/setup-proxy.sh` module (first-party, not vendored): one systemd unit + one config.json for any subset of the four protocols, sharing the vendored sing-box binary with anytls; `install.sh` gained a `proxy` module with its own y/n sub-prompts per protocol, upgrade-safe credential/port preservation (`preserve_proxy()`), and an amd64 arch guard shared with anytls. The first implementation gave `/proxy` one section per installed protocol (port, UUID/password, shared SNI, Clash entry, share link, QR) and a single "reset all" button; the [later branch record][local-link-006] documents the per-protocol buttons that replaced it. `PortForwardManager.reserved_ports()` now also reserves every installed proxy port. Two real bugs found by testing (not inspection) and fixed: protocol validation's `exit 1` was swallowed by a command-substitution subshell (config could end up with zero inbounds on an invalid `PROXY_PROTOCOLS`); trojan's random port range overflowed sing-box's uint16 `listen_port` past 65535. Verified in a disposable Docker container (systemd itself would not boot as PID 1 in this session's Docker setup, so `systemctl` is stubbed to a no-op there; every other code path — config generation, real iptables rules, credential rotation, uninstall's shared-binary awareness — ran for real): 5 repeated fresh installs, narrowing/widening the protocol subset, reset, uninstall, and a full `install.sh` unattended install + upgrade re-run confirming `preserve_proxy()` keeps ports/UUIDs/passwords/protocol-set identical across a re-run. 19 new unit tests added to `tests/test_app.py` (147/147 passing). Built on `feat/proxy-protocols`, stacked on the unmerged `feat/hardening-batch` (its y/n module picker didn't exist on `main` yet); not merged, released, or tagged — the operator's own review and a real-host test are still pending.

- Completed: 2026-09-19 QR code to add a node — each address block on the anytls page now has a collapsible "Scan to add" QR code of that address's share link, next to the existing copyable text link. Implementation: vendored kazuhikoarase/qrcode-generator (MIT, `static/qrcode.js` + `static/qrcode-utf8.js` for multi-byte labels) rendered client-side as inline SVG by this project's own `static/qrcode-render.js`, which scans for `[data-qr-text]` elements — reusable for any node type added later. Verified: HTTP-level test confirms the share link is HTML-escaped correctly into the attribute (a raw `&` would truncate it) and that all three scripts are referenced; separately ran the exact vendored file content under Node against a real anytls share link (including a Unicode label) and confirmed it produces a well-formed 41×41-module QR SVG, not a blank/broken one — the closest to real-browser verification available in this headless environment (no X server for an actual browser here).

- Completed: 2026-09-19 Modular installer — replaced `install.sh`'s numbered 1/2/3/4 module menu with three independent y/n questions (web, iperf3, anytls), each ticked on its own rather than picked from a fixed preset list; `VPSSRV_MODULES` is unchanged as the unattended/scriptable path. iperf3 is skipped from the prompts entirely when web is answered no, since the console it would control would not exist. Verified in a disposable container across all four answer combinations (defaults, web-only, full, anytls-only) plus both unattended regressions.

[local-link-001]: #bugs
[local-link-002]: DESIGN.md#design-goals
[local-link-003]: DESIGN.md#design-goals
[local-link-004]: #bugs
[local-link-005]: #v110--2026-09-19
[local-link-006]: #branch-record-2026-09-22-status-snapshot
[local-link-007]: THIRD_PARTY_NOTICES.md

## Handoff

- Page-transition test deployment (2026-09-29): patched the designated test host's installed `test-1810c3d` Web files with the scoped route-animation removal from commit `83064ca`, and deployed the candidate as `test-83064ca` under `/root/apps/vps-server`. The host artifact is derived from the existing installed build plus this patch; the repository still has unrelated uncommitted work. A mode-0600 recovery archive at `/root/apps/.deploy-backups/vps-server-before-route-removal-20260929T1350Z.tar.gz` passed archive listing, and the transferred candidate SHA-256 matched. The first start check ran before the listener was ready, so the automatic rollback restored the original files and active service; the second attempt waited for readiness and succeeded. Web is active and enabled for boot on HTTPS `0.0.0.0:49903`; the workstation received 200 for Login and the style sheet, and 404 for the removed script. An authenticated session opened Home, Settings, and Chinese Changelog with `test-83064ca`, no route script or Appearance switch, and the candidate removal note; sign-out followed by Settings redirected to Login. The deployed app, CSS, and LOG hashes match the candidate, the existing Web-password hash stayed unchanged, and the recent Web journal showed no traceback or error. Local automated checks before deployment passed 338 tests with 8 skipped. Browser Back/Forward and a real mobile browser remain unverified because local Playwright lacks Chrome; no host reboot was performed. Next action: check those browser paths on an available device, then continue the separate `release/v4.0.0` work. No temporary project rules were found.
- Page-transition removal (2026-09-29): on `release/v4.0.0`, removed the route-animation script, automatic View Transitions styles, Appearance Beta switch, and its unused translations. Normal links remain; resize, theme, and local control feedback remain. This follows the owner's explicit request after repeated visual defects. The shared Web UI rule now permits an owner-requested application omission and requires navigation and authorization checks. Python compilation, Git whitespace, document format and local-link checks passed; the current worktree ran 338 tests with 8 skipped. A local HTTP session checked login, Home, Settings, Changelog, Back links, absence of the script and switch, a 404 for the removed script, and redirection to Login when revisiting Settings after sign-out. Browser Back and Forward could not be inspected because Playwright's Chrome executable is unavailable in this environment. At this source checkpoint, the designated test host had not yet been updated; the later test deployment is recorded above. Browser Back and Forward still require a browser with Chrome installed. No temporary project rules were found.
- Test deployment (2026-09-29): installed source `598a386` as `test-598a386` on the designated LAN test host under the standard application directory. The prior `dev-2c0e4d7` Web files and application-directory data were preserved in a mode-0600 archive outside the application directory; the external node inventory was not part of that archive or the file-copy scope. The existing administrator password and install-state file remained byte-identical. The host's Git checkout had pre-existing local modifications and was not reset. Only the Web service was stopped and restarted. Immediately afterward, Web, proxy, node-meter, and AnyTLS were active and enabled for boot; public 80/443 and the existing console listener were present. The transferred manifest and installed Web entry-point hashes matched the source candidate. An actual host reboot was not performed.
- Test deployment checks: 315 automated tests passed with 8 skipped before transfer; the focused candidate-version test passed again after its final source adjustment. The package manifest passed checksum verification before and after installation, and the staged Python entry point compiled. LAN HTTP access to Login and the public page returned 200; the host's public HTTP and self-signed HTTPS pages returned 200. Authenticated HTTP requests opened Dashboard, FRPS / FRPC, Changelog, and Settings; protected access redirected before login and after logout. The in-app Changelog heading and the login badge both showed `test-598a386`, with FRP changes included in its test notes. Chromium on the LAN opened the Dashboard, FRP, Settings, and Changelog at 390 px without horizontal overflow. FRPS is not installed on this host, so the FRP page displays its not-installed state; live client connection data was not verified. The recent Web journal contained no error or traceback. Real mobile rendering, a reboot, live policy transfers, and allowlisted-device IP admission remain unverified.
- Concurrent node activity during review: repeated node-control apply operations changed the external node inventory from its prior running configuration to zero nodes, stopping proxy and AnyTLS normally. A later read found one node and AnyTLS running again. The Web deployment and smoke checks did not send node-management requests. The operator chose to keep the current node state; no backup restoration was attempted. Proxy and AnyTLS status depends on the currently enabled nodes and may change during review.
- Next action: review the updated interface on the test host, especially the FRP empty state and page-motion switch. The future Web module-management page remains design backlog.
- Current work (2026-09-29): a read-only FRPS / FRPC console page groups local FRPS service details, interface addresses, and a revealable, copyable FRPC connection template. The Dashboard links to it; the authenticated header is limited to Home, Changelog, Settings, and Sign out, and child pages have a Back control. Ordinary and Security Settings use section navigation, with a separate action to enter the protected area. Each page has a distinct tab symbol in the shared project frame. Appearance offers an optional Beta page transition; responsive resize motion is separate. Protected pages hide before browser history caching and require a fresh server request when revisited after sign-out. The server does not claim to observe a remote FRPC process. A later Web setup page with independent module enable/disable and install choices is tracked in DESIGN, separate from the existing installation wizard.
- Checks at the source-change checkpoint: 314 automated tests passed (8 skipped); Python compilation, JavaScript syntax, and Git whitespace checks passed. Document formatting and local-link checks had zero errors; the existing three CJK-navigation warnings and five external URLs remain. Multilingual static checks passed with zero errors. Project structure passed on a clean export of versioned and new source files; the live checkout still reports the five ignored runtime entries documented under Limitations. Local Chromium verified Dashboard to FRP navigation, explicit Back, browser Back/Forward, FRP masked values, desktop and 390 px layouts without horizontal overflow, Settings section navigation, and sign-out followed by browser Back returning to Login after a fresh server request. An iPhone user-agent emulation starts page motion off and accepts explicit opt-in. Real iOS and Android devices remain untested; subsequent host deployment is recorded above.
- Next action: review the FRP view and page motion on the designated test host, including a real mobile browser. The future Web setup page remains design backlog and is not implemented. No temporary project rules were found.
- Branch: `main`, tracking the official GitHub repository. No temporary project rules were found.
- Completed: the node editor labels its secret as a password; the traffic editor keeps its trigger in place when expanded. Each node accepts independent upload/download Mbps limits, a 1 Mbps throttle or block response to a GiB traffic cap, recurring resets every chosen number of days/months/years, and an optional validity duration that blocks traffic on expiry. Version-one state upgrades on read while preserving node IDs, usage and cap; old absolute expiry dates are cleared rather than reinterpreted as blocking. The IP access button is always present and directs unlisted sources to password login and private-IP allowlist settings. Every managed node has a copy button immediately before Clash Meta import; it copies the LAN subscription URL. The node grid automatically fits one to six columns, caps the count at six on wider screens, and stacks facts inside narrow cards. Password authentication remains required to edit access settings.
- Checks: 308 automated tests passed (8 skipped); Python compilation and diff whitespace checks passed. Chromium checked the unlisted-IP message and the expanded node form at desktop and 390 px width on the test host; the traffic editor trigger kept the same position when toggled. With three existing nodes and three browser-only clones, Chromium confirmed one through six columns at 390, 900, 1200, 1440, 1920 and 2560 px respectively, six columns at 3840 px, no horizontal overflow, and successful copying of a node's LAN subscription URL. Nft accepted the directional-limit and cap-block rules in check-only mode. A real traffic transfer through every policy combination remains unverified.
- Deployment: the designated test host was running the previous candidate under the standard application directory; its previous runtime files and node state were backed up outside the repository. The node state migrated to schema version two earlier. At the 2026-09-27 check, the Web, proxy, node-meter and AnyTLS services were active and enabled for boot. An actual host reboot has not been performed.
- Current standard alignment (2026-09-28): managed and legacy proxy pages, Lucky, frps, iperf3, and port forwarding now mask stored credentials and configured ports on first render. Authorized requests fetch a value only when the operator chooses Show, Copy, Import, or QR; Hide, QR collapse, and leaving the page clear revealed content. The node editor keeps the current port when its new port field is blank. Lucky and frps page text is localized in all eight supported UI languages. An installed build now prefers its deployment `VERSION` stamp over the bundled `config/VERSION` release. Chinese document punctuation was normalized to the current document format rule without changing code examples.
- Checks for this alignment: 309 automated tests passed (8 skipped), document format and multilingual checks passed with zero errors, Python compilation and diff whitespace checks passed, and the project structure checker passed on a clean export of tracked files. The checkout structure checker reports ignored runtime files and caches already recorded in Limitations. Chromium confirmed default masking, Show/Hide, QR creation and clearing on a local fixture. On the test host, LAN login, masked node pages, authorized credential reveal, static script delivery, four active services, and the configured Web listener were verified. Chromium also confirmed reveal and re-masking after navigation on the host. The browser denied clipboard read permission, so actual clipboard contents were not verified in this run.
- Deployment: updated the designated test host under the standard application directory after backing up the previous application files outside the repository. Restarted only the Web service and stamped the deployed development revision; its systemd boot enablement remains in place. No host reboot or live policy transfer was performed.
- Current security alignment: Security Settings now requires administrator-password verification with a fixed ten-minute permission. A completed challenge rotates the session; IP-only sessions cannot read the allowlist or change settings without that challenge. Password changes need only the new value and confirmation during the permission window and invalidate old sessions. Private IPv4 and unique-local IPv6 entries share an enable switch; each IP admission rechecks the list and switch. The Clash import button has a visible default state, and Changelog and Settings links are dashboard tiles.
- Checks for this alignment: 311 automated tests passed (8 skipped); document format and multilingual checks had zero errors; Python compilation and diff whitespace checks passed. The local link checker still reports 20 inherited translated-fragment errors (20 on the unchanged baseline); no new broken link was introduced. Chromium confirmed the dashboard Changelog and Settings tiles, the Security Settings page and its separate IP access control, a readable Clash import button on a 390 px viewport, and no page-level horizontal overflow.
- Deployment of this alignment: the designated test host received this candidate after a mode-0600 backup of its previous Web files, catalogs, documents, and IP allowlist. Only the Web service was restarted. Its login page reported the deployed development revision, four services were active, and the existing IP allowlist file remained unchanged. An actual host reboot and a live IP admission from an allowlisted device have not been tested.
- Current settings work: removed the duplicate administrator sign-in navigation link. Ordinary Settings now contains appearance and language choices and opens for any authenticated session, including IP-only access. Its separate Security page and every security write still require the short-lived administrator-password permission. The verification form uses a narrower card and a spaced, aligned submit button. The navigation has a Dashboard link before Speed test, and Security uses the same card layout as the other settings.
- Checks for this work: 311 automated tests passed (8 skipped); document format and multilingual checks had zero errors, and Python compilation and diff whitespace checks passed. Chromium confirmed desktop and 390 px layouts, no horizontal overflow, a persisted theme after changing language, the aligned three-card Settings grid, Dashboard navigation, a spaced verification button, and the correct return to ordinary Settings after login. The IP-only boundary and expired-permission redirects passed automated tests; a live IP admission remains untested.
- Deployment for this work: the designated test host runs `dev-5c518c0` under the standard application directory. Its previous Web source, styles, version stamp, administrator-password file, and IP allowlist were preserved in mode-0600 backups outside the repository; the latter two files were not changed. Only the Web service was restarted. The Web, proxy, node-meter, and AnyTLS services were active and enabled for boot; the console listened on its existing configured address and port. LAN login and the ordinary and Security Settings pages worked in Chromium. An actual reboot was not performed.
- Current node access work: the former Limits and cycle editor is named Access management in all eight interface languages. Its traffic cap, directional speed limits, cap response, reset interval, and validity controls now open in a separate dialog; the card footer keeps Access management, Random reset, and Delete node on one row at normal card widths. The navigation label before Speed test is now Home.
- Checks for this work: 311 automated tests passed (8 skipped), Python compilation and diff whitespace checks passed. Chromium confirmed a single footer row in Chinese and English at desktop card width and English at a 390 px viewport. The dialog opened with its first field focused and kept Cancel and Save visible while its controls scrolled on the narrow viewport. No limits were submitted on the test host.
- Deployment for this work: the designated test host runs `dev-a785fe5` under the standard application directory. A mode-0600 backup of the previous Web source, styles, script, catalogs, and version stamp remains outside the application directory. Only the Web service was restarted. The Web, proxy, node-meter, and AnyTLS services were active and enabled for boot; the console listened on its existing address and port and served the new version over LAN. No host reboot was performed.
- Current standards review (2026-09-28): translated documents now use stable shared section anchors where their old heading fragments did not resolve. The proxy and anytls setup summaries now list only interface and optional Tailscale addresses, remove legacy `public-ip.txt`, and make no outbound public-IP lookup. `SERVER_IP` is no longer a setup option. Two obsolete Fontsource links were replaced with reachable upstream source pages.
- Checks for this review: 311 automated tests passed (8 skipped) after the setup-summary change; shell syntax, locale-catalog tests, and diff whitespace checks passed. All 32 documents had zero format errors, with four warnings for language names in English navigation. The multilingual checker had zero errors, and the local-link checker had zero errors; all 13 distinct external destinations were opened or checked at their redirect target. A clean export of tracked files passed the project structure checker. The checkout structure checker reports five ignored runtime/cache entries, including `certs/`; this is recorded under Limitations. No temporary project rules were found.
- Deployment for this review: the designated test host runs `dev-2b7983f` under the standard application directory. Its previous scripts, catalogs, documents, and version stamp remain in a mode-0600 backup outside the application directory; persistent node data and access settings were not changed. Only the Web service was restarted. Web, proxy, node-meter, and AnyTLS were active and enabled for boot; the console listened on its existing `0.0.0.0:31080` and served the new version over LAN. Isolated host fixtures confirmed both setup summaries list interface and Tailscale addresses, omit a supplied public address, and remove an obsolete public-address file. An actual host reboot and a production setup run were not performed.
- Publication: reviewed outgoing commits `2b7983f` and `933bafa` against the prior `origin/feat/node-management`; the formal repository is public. No live credentials, private host addresses, or local deployment paths were found in the outgoing changes. Both commits were pushed to that branch; `main` was not changed.
- Current Web appearance alignment (2026-09-28): ordinary Settings now offers all eight prescribed accent colors and separate light/dark modes. Both choices persist in local storage, restore before CSS loads, and remain independent when toggled. The existing shared components use semantic color variables in both modes; the narrow header now wraps its brand and version at high zoom. All eight UI catalogs include the new option labels. No temporary project rules were found.
- Checks for this alignment: 311 automated tests passed (8 skipped); Python and JavaScript syntax, document format, multilingual catalogs, local links, and diff whitespace passed with zero errors. The document checker retained two proper-name warnings in English navigation. Chromium confirmed theme and mode persistence after reload and language change, all 16 color/mode combinations had at least 4.5:1 contrast for body, muted, and primary-button text, and the Arabic Settings page had no horizontal overflow at 390, 320, or 195 CSS px (the last approximates 200% zoom at 390 px). The desktop Settings layout and dark mobile layout were visually inspected.
- Deployment for this alignment: the designated test host runs `dev-abe8f0d` from the standard application directory. The previous runtime application, styles, theme script, catalogs, documents, and version were backed up outside that directory with mode 0600. The deployed root `app.py` and source copy, styles, theme script, catalogs, and documents now match this revision. Only the Web service was restarted; persistent data and access settings were not changed. The LAN login response includes the new theme choices, mode bootstrap, and version, and the theme script is served. Web, proxy, node-meter, and AnyTLS were active and enabled for boot; the console remained on its existing listener. An actual reboot and a live policy transfer were not performed.
- Release publication (2026-09-28): the operator reported that functional testing passed and explicitly requested a major release. `v3.0.0` tags `4e26aea` on the official public repository's `main` branch; the GitHub Release is published, the tagged source is exported to the standard sibling snapshot, and the complete Changelog is synchronized to the existing `My Projects/vps-server` Notion child page. The repository description was updated. The three executable blobs over 10 MB are unchanged from `v2.0.0`; no new large blob or Release asset was needed. The test host remains on its previously deployed development build; this publication did not upgrade it.
- Checks and remaining work: 311 automated tests passed (8 skipped); shell and Python syntax, dependency hashes, 32 document formats, multilingual structure, local links, clean-export project structure, diff whitespace, the final archive's `3.0.0` version, remote `main` and tag targets, Release state, snapshot file hashes, and Notion parent/title/content all passed. Four existing document warnings concern language names in English navigation. An actual host reboot, Android Clash import on a real phone, live transfer through every policy, and IP admission from an allowlisted device were not independently witnessed in this release preparation. Next action: verify those behaviors on the target when practical; no further publication step is pending.
- Current Web UI standard alignment (2026-09-28): the login header now repeats the console brand as a home link. The login card uses the shared dimensions and puts a Changelog version link and pre-login language selector in its footer. Password entry on login, Security verification and password change, and managed and legacy node forms starts masked and has an independent accessible Show/Hide button. The old login-only visibility script was replaced with one shared script. No dependency was added.
- Checks: 311 automated tests passed (8 skipped); Python compilation, JavaScript syntax, and diff whitespace passed. Chromium verified the login page at 390 and 195 CSS px without horizontal overflow, the language menu and change to Simplified Chinese, and password visibility with retained value and focus. Security password fields were checked independently on a local fixture. The designated test host was not changed for this UI alignment. Remaining live checks are the host reboot, Android Clash import, live transfers through every policy, and allowlisted-device IP admission. Next action: deploy this UI alignment to the designated test host when requested and complete the remaining live checks when practical.
- Test deployment (2026-09-28): deployed the Web UI from `c312456` as `dev-c312456` to the designated LAN test host under the standard application directory. Backed up the previous Web files outside the application directory with mode 0600, then replaced the root and source Web entry points, style sheet, password-control script, version stamp, and English project documents. Removed the superseded login-only script and restarted only `vps-server-web.service`. Node state, visitor data, and the existing Web password were left untouched. The Web service and proxy, node-meter, and AnyTLS services were active afterward; Web remained enabled at boot and listening on its existing `0.0.0.0:31080` port. Local and deployed source hashes matched. From the workstation, login, the new script, style sheet, and favicon returned HTTP 200; the login HTML reported `dev-c312456`, and Chromium visually checked the 390 px login layout. No Web service error appeared in the recent journal. A host reboot and authenticated review of the node forms were not performed. Next action: obtain the operator's visual feedback and address any issue found; the remaining live checks above are unchanged.
- Current version and Changelog work: development builds now show curated post-`v3.0.0` notes from this file above the formal release history, using the deployed version stamp as the heading. Other UI languages label the English-only test notes while retaining their localized formal release entries. Clicking the login-page version link now returns to Changelog after password verification. The `v3.0.0` tag and Release remain unchanged; this is a development build.
- Checks: 313 automated tests passed (8 skipped), including the version-link return and development-note visibility; document format and local links had zero errors, and multilingual structure had zero errors. Python compilation and diff whitespace checks passed. The designated test host still runs `dev-c312456` at this point. Next action: deploy this change with a stamp matching its committed source, verify the login version and authenticated Changelog over LAN, then record the host result.
- Version and Changelog test deployment (2026-09-28): installed `2c0e4d7` as `dev-2c0e4d7` on the designated LAN test host, after preserving the previous Web entry points, documents, language catalogs, and version stamp in a mode-0600 backup outside the application directory. Restarted only the Web service; node state, visitor data, and the existing Web password were unchanged. The Web, proxy, node-meter, and AnyTLS services were active afterward; Web remained enabled at boot on its existing `0.0.0.0:31080` listener. From the workstation, the login page returned HTTP 200 and reported `dev-2c0e4d7`. An authenticated request on the host verified that the Chinese Changelog shows the current test-build notes above the localized `v3.0.0` release entry, and excludes Handoff text. The login-version link returns to Changelog after password verification. Deployed source and catalog hashes matched this commit, and the recent Web journal had no errors. A host reboot was not performed. Next action: review the updated page with the operator; the earlier live node, Clash, and IP-admission checks remain open.

## Development Updates

The current test build includes these changes after `v3.0.0`. This section is
shown above formal releases in the Web Changelog and does not announce a new
release.

#### Changed

- The authenticated header now keeps global navigation; function entry cards live on the Dashboard and child pages include a Back control.
- Ordinary and Security Settings now have responsive section navigation. The ordinary Security label only scrolls to its entry card; Enter Security starts the protected route.
- Page-specific tab icons share the project frame and use the function's symbol.
- The FRPS / FRPC page shows local server details and a copyable client connection template while keeping ports and tokens masked until requested.
- Appearance now offers a Beta page-transition switch; the interface also animates responsive window reflow. Protected pages are rechecked on browser history return so sign-out does not expose a cached console view.
- Test candidates show their `test-` identifier next to the project name and above their development notes in the Web Changelog.
- The login page uses the shared project header. Its footer links the running version to Changelog and offers language selection before sign-in.
- Login, administrator verification, password change, and proxy-node forms each provide an independent Show/Hide control that preserves entered text and focus.

## Changelog

<a id="vps-changelog"></a>

Only tagged releases are listed here. The following entries retain the complete
former changelog history and record the current release content.

### v3.0.0 — 2026-09-28

#### Added

- Managed AnyTLS, VMess, VLESS, Trojan, and Shadowsocks nodes can be created, edited, disabled, reset, and deleted individually. Display numbers stay contiguous; hidden UUIDs preserve identity. Connection details can be copied or imported into Clash Meta for Android by link or QR code.
- Each node tracks upload and download traffic and supports a GiB cap, separate directional speed limits, recurring resets in days, months, or years, and an optional validity period. A reached cap can throttle both directions to 1 Mbps or block access; an expired validity period blocks access.
- Password-free access is available to an explicit private-IP allowlist. Security Settings requires a recent administrator-password check, including for IP-only sessions, before exposing or changing credentials and access rules.

#### Changed

- Unified the console and login layouts, responsive node cards, dashboard navigation, and settings. Ordinary Settings now offers eight persistent accent colors and independent light/dark modes. Stored credentials and configured ports are masked until an authorized reveal or use.
- The iperf3 view separates service state from its editable port. Installer upgrades preserve the runtime web entry point and staged modules. Proxy setup summaries list interface and optional Tailscale addresses without public-IP lookup. Translated document fragments and third-party source links were repaired.

#### Verification and limits

- The operator reports that functional testing passed. The local suite passed 311 tests (8 skipped); the designated test host served the new login and theme assets with Web, proxy, node-meter, and AnyTLS services active and enabled for boot. An actual reboot and every live policy transfer were not independently witnessed in this release preparation.
- No new or changed blob over 10 MB was added. The existing sing-box (57,995,520 bytes), frps (20,332,728 bytes), and Lucky (10,883,644 bytes) executables have the same Git blob IDs as in `v2.0.0`; provenance and license records remain in [THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES.md). frps and Lucky remain experimental.

### v2.0.0 — 2026-09-27

#### Changed

- Moved installer and removal entry points to `deploy/install.sh` and
  `deploy/uninstall.sh`, web source to `src/web/`, bundled dependencies to
  `third_party/`, and release metadata to `config/`. Scripts that called the
  old checkout paths need the new paths; installed runtime data stays in its
  existing locations.
- Consolidated the former backlog, status, decision, and changelog documents
  into `DESIGN.md` and `LOG.md`; migrated all eight language sets and local
  links to the standard document layout. Interface text now lives under
  `lang/` with BCP-47 file names.

#### Added

- Included the four-protocol proxy module, its shared console page and
  per-protocol credential reset controls, plus the browser setup wizard.
- Included experimental frps and Lucky installers and their bundled
  executables. Their original license files and artifact hashes are recorded
  in the third-party inventory.

#### Verification and limits

- Local unit suite: 271 tests passed, 8 skipped. Dependency hashes,
  document checks, and multilingual structure checks passed. The document
  checker reported four navigation-label warnings in English documents.
- Repository copies of all seven bundled artifacts matched the corresponding
  upstream release files on 2026-09-27; the original license files for the
  bundled executables matched those release archives. Independent legal
  interpretation was not obtained.
- Real-host/systemd acceptance and independent native-language review remain
  outstanding. frps and Lucky are experimental in this version.

### v1.1.2 — 2026-09-21

#### Fixed

- Upgrading with `install.sh` from a version that predates a newly-added
  setting (as v1.1.0's port-forwarding settings did to anyone on v1.0.4)
  could silently abort right after the last new-setting prompt — before
  copying any files, updating `VERSION`, or restarting the service — with
  no error message, leaving the host on the old version while the install
  appeared to finish normally.

### v1.1.1 — 2026-09-20

#### Fixed

- README's Install section still cloned `--branch v1.0.4` in both the
  one-line quick install and the step-by-step command — anyone following it
  right after v1.1.0 shipped would have installed the previous release,
  missing port forwarding entirely.

### v1.1.0 — 2026-09-19

<a id="vps-release-v1-1-0"></a>

#### Added

- **Console-managed port forwarding.** A new "Port forward" page lets you
  forward a public TCP/UDP port on this host to a device reached over
  Tailscale or the LAN — useful when this box has a public IP and the target
  device does not. Add, enable, disable and delete rules from the console;
  each one is checked against every port this install already uses (console,
  public page, iperf3, anytls) before it is applied. Rules are backed by
  `iptables` DNAT + MASQUERADE and are reapplied automatically every time the
  service starts, so a restart or a reboot brings every enabled forward
  straight back rather than losing it. `net.ipv4.ip_forward` is turned on
  automatically the first time it is needed. Set `VPSSRV_PORTFWD_ENABLE=0` to
  remove the feature from an install entirely.

### v1.0.4 — 2026-09-12

#### Changed

- The installer's closing summary now prints the machine's real IP addresses
  instead of a literal `<this-server>` placeholder that had to be substituted
  by hand before the URLs were usable. The address the kernel would actually
  use to leave the box goes on the public-page and console lines; on a
  multi-homed machine every other address is listed below them, each labelled
  with its interface, so a node reachable only over ZeroTier or Tailscale is
  visible rather than guessed at. If no address can be read the old
  placeholder is printed as before, which keeps an otherwise-good install
  from failing over cosmetics.

### v1.0.3 — 2026-09-12

#### Fixed

- `install_iperf3()` could still fail even after v1.0.2's fix. `apt-get update`
  can report success while `security.debian.org`'s CDN hands back a stale
  package index, so the very next `apt-get install` 404s trying to fetch a
  `.deb` the index just claimed exists — seen live on a real host upgrading
  from v1.0.1 to v1.0.2. A single retry of `update` alone did not reliably
  fix this, since the retry could hit the same stale edge. The installer now
  retries the whole update-then-install pair together, up to 3 times, which
  recovers once a later attempt lands on a synced mirror.
- The README's `## Install` section still had unfilled template
  placeholders — a literal `<repo-url>` and a `v0.1.0` example tag that this
  project has never actually had a release named. Both now read the real
  values: the project's actual GitHub URL and its current release tag.

### v1.0.2 — 2026-09-12

#### Fixed

- `install.sh` could silently fail to install iperf3: it chained the apt
  update and install steps together with all output discarded, so one
  unrelated broken repository — a stale third-party `.list` file, which is
  what happened on a real VPS — made the update step fail and skipped
  installing iperf3 entirely, with no way to see why. It now retries the
  update, attempts the install regardless of whether the update succeeded,
  and no longer hides apt's own error output when the install genuinely
  fails.

### v1.0.1 — 2026-09-12

#### Fixed

- The changelog page showed the maintainer comment from the bottom of the
  CHANGELOG file — the one naming which headings stay in English — as ordinary
  paragraphs, escaped `<!--` and `-->` included, in all three languages. The
  renderer had no comment handling at all. Display only; nothing else was
  affected.

### v1.0.0 — 2026-09-12

First release. It combines two existing projects — a password-protected VPS
speed-test console and a sing-box `anytls` installer — and adds two
capabilities neither had: an on-demand iperf3 window and a public page that
lets anyone check whether your IP answers on the web.

#### Added

- **Public reachability page on ports 80 and 443, with no login.** Hand
  someone the IP; if the page renders, your web ports are reachable from where
  they are. It reports their source address, the server clock, and which port
  and protocol they arrived on — and nothing else about the host. Serving both
  ports is deliberate: it distinguishes "the host is unreachable" from "443
  specifically is blocked".
- **On-demand iperf3 window.** The console opens a time-boxed window; `iperf3`
  runs only inside it, opens its port in whichever firewall is active, and
  shuts both down when the window expires — on request, or when the service
  stops. There is no "leave it running" option, because an open iperf3 server
  lets any stranger saturate the uplink. While a window is open the public
  page advertises it, so the tester knows when to connect.
- **Browser speed test and visitor log**, from the console: up/download
  measurement using the LibreSpeed engine, and a record of every inbound TCP
  connection on any port — not just HTTP — read from the kernel's connection
  table.
- **anytls proxy module.** sing-box with a self-signed certificate, plus BBR.
  The console shows the node's port, password and SNI, offers its Clash entry
  and `anytls://` link with copy buttons, and can rotate the credentials.
- **Module-selecting installer.** web, iperf3 and anytls are chosen
  independently, interactively or through `VPSSRV_MODULES` for unattended
  runs. It refuses rather than fighting for a port another process holds, and
  skips anytls on non-x86-64 rather than installing a binary that cannot run.
- **Upgrade-aware re-install.** Re-running the installer detects the existing
  install, offers to keep its configuration, replays the settings recorded in
  the service unit, preserves the anytls node's credentials, and asks only
  about settings the installed version did not have. Installs predating that
  bookkeeping are handled by reading the module list off the disk.
- **Three interface languages** — English, Simplified Chinese, Traditional
  Chinese — chosen at install time, switchable per visit, and remembered.
- **Offline installation.** The sing-box binary ships in the repository, so
  installing needs nothing beyond your distribution's package mirror.

**Release notes (v1.0.0):**

- The whole project is GPL-3.0, because it redistributes the GPL-3.0 sing-box
  binary. Component licences and the corresponding-source links the GPL
  requires are in [THIRD_PARTY_NOTICES.md][local-link-007].
- TLS on 443 is a self-signed certificate: no domain, no ACME. A browser
  warning still proves the port answers, which is the question that page
  exists to settle.
- `mean_rtt` in iperf3's JSON output comes from the kernel's `TCP_INFO`, so a
  Linux client reports round-trip time and one that cannot read it — iperf3
  under Cygwin on Windows, for instance — reports throughput only. UDP mode
  (`-u`) gives jitter and loss everywhere.
- x86-64 only for the anytls module. The web and iperf3 modules are
  architecture-independent.

## Commit History

The following entries preserve the Git commit subjects in chronological order. The final entry names this documentation commit.

- `b3cc391` docs: add documentation skeleton and agreed design
- `63f1680` feat(web): vendor the web module and add the public page and iperf3 window
- `c0def78` feat(anytls): vendor the anytls module and record third-party licences
- `dc70d9b` feat(install): turn the installer into a module menu
- `fcf7878` fix(install): print a teardown command that actually works
- `6022737` docs: record that the iperf3 window works under systemd sandboxing
- `790b7c6` fix(anytls): install the sing-box binary that was there all along
- `f0862d0` feat(console): add an anytls node page, and stop the iperf buttons competing
- `aa01a30` feat(console): show the anytls port, password and every usable address
- `901cc0c` fix(ui): make the copy button quiet, and every colour survive light mode
- `5c6e65a` feat(anytls): let the console rotate the node's port and password
- `27e2c9d` docs(anytls): keep the upstream tag as the file's last line
- `03bb980` feat(install): carry an existing install's settings across an upgrade
- `33d8488` fix(anytls): run the reset outside this service's sandbox
- `00bf933` fix(anytls): stop a raw iptables line leaking into the install summary
- `c8330ba` fix: eleven defects from a full audit
- `0be4851` docs(backlog): tick the anytls vendoring item, done since c0def78
- `a9d6b1d` fix(ui): align the iperf form, and let the layout survive a narrow screen
- `3843ccb` docs: correct two stale backlog ticks and the mean_rtt claim
- `cc0cf4d` docs: record three more verifications, and what is left
- `8e2ea5e` chore(release): v1.0.0
- `40a4bc3` fix(changelog): stop rendering the maintainer comment to readers
- `bbc7bd1` chore(release): v1.0.1
- `98d3bf7` chore(release): v1.0.2
- `aceecfd` chore(release): v1.0.3
- `e723745` chore(release): v1.0.4
- `4983c10` refactor(docs): migrate docs to doc/ + doc/<lang>/ layout
- `a468514` docs(i18n): scaffold five extended-language placeholders, fix README Install
- `42ffe49` docs(i18n): sync README Install one-liner to zh_cn/zh_tw translations
- `0bbb682` feat(portfwd): console-managed iptables port forwarding
- `2b3caee` docs(backlog): record web-based first-run setup page idea
- `14608c6` chore(release): v1.1.0
- `eace062` chore(release): v1.1.1
- `9e09d8a` fix(install): stop install.sh silently dying mid-upgrade
- `5451526` refactor(project): publish standardized project tree
- `f300ab7` docs(log): record GitHub synchronization
- `53c390c` chore(release): prepare v2.0.0 content
- `f9eb612` docs(release): verify bundled artifact provenance
- `5868549` docs(log): record v2.0.0 publication handoff
- `56c9ed5` docs(readme): translate installation example comments
- `51e89bc` feat(nodes): scaffold numbering and refresh proxy workspace
- `ed58969` feat(nodes): add managed controls and traffic policing
- `d0d6ae7` docs: restore required multilingual sections
- `84b9599` fix(web): show development revision in checkout
- `e986c51` fix(install): create flat entry during in-place install
- `eaceed8` fix(install): stage modules during in-place install
- `5ff2a6b` fix(web): condense mobile navigation
- `2477fcc` docs: record node deployment handoff
- `d31e40f` docs(log): synchronize commit history
- `0696e4b` fix(nodes): keep sustained traffic within 1 Mbps
- `da5f84f` docs(log): record measured node acceptance
- `b74b412` feat(proxy): add Clash Meta import and GiB node controls
- `773eedf` feat(web): unify console and setup interface design
- `9a615ab` feat(nodes): support multiple nodes and in-place editing
- `6c1459d` docs(log): record node management delivery
- `47b3686` feat(console): refine nodes, login and iperf3 port
- `3d69356` docs(log): record GitHub synchronization
- `6e461a3` fix(iperf): clarify finished state
- `a676537` feat(nodes): add per-node switch and compact numbering
- `ab02c17` docs(log): record node switch acceptance
- `860cdc4` feat(auth): add private-IP access and admin settings
- `ad08a80` feat(web): refine access screens and proxy node cards
- `be8b4a5` feat(nodes): add flexible limits and persistent IP login entry
- `b0a9c6c` feat(web): copy Clash links and fit up to six node columns
- `d07b40a` fix(web): mask configured values and align project documents
- `7065e18` fix(web): honor installed version stamp
- `b870053` fix(web): prioritize deployed stamp over stale git metadata
- `81f1e13` feat(auth): align security settings and dashboard access
- `7524ec3` docs(log): record security alignment checks and deployment
- `b1a8f21` feat(web): separate preferences from security settings
- `dd9627f` fix(web): keep security entry visible in settings
- `0fc871a` fix(auth): return to requested settings page after login
- `5c518c0` fix(web): add dashboard link and align security card
- `9db2482` docs(log): record settings review and deployment
- `fdf8fbc` feat(nodes): move access limits into dialog
- `a785fe5` fix(nodes): keep action buttons on one row
- `d03abb7` docs(log): record access dialog and test deployment
- `2b7983f` fix(standards): align setup addresses and document links
- `933bafa` docs(log): finish standards audit handoff
- `e2778a5` docs(log): record formal branch publication
- `abe8f0d` feat(web): align appearance with current theme standard
- `2d624db` docs(log): record appearance deployment
- `4e26aea` chore(release): prepare v3.0.0 content
- `444924c` docs(log): record v3.0.0 publication
- `c312456` fix(web): align login and password controls with current standard
- `25f1f9e` docs(log): record Web UI test deployment
- `2c0e4d7` feat(web): show current test build updates
- `4d0db36` docs(log): record version and Changelog deployment
- `95ca649` feat(web): align navigation and add FRP information
- `598a386` fix(web): display test candidate version and notes
- `5559417` docs(log): record FRP test deployment
- `9f4ab98` docs(log): clarify concurrent node state
- `83064ca` fix(web): remove page transition animation
- (this commit) docs(log): record route-animation test deployment
