---
name: project-design
description: Project architecture and design constraints
metadata:
  version: "1.0.0"
  lang: "en"
---

# vps-server — Design

## Multi-language

**English** | [简体中文](zh-CN/DESIGN.md) | [繁體中文 (台灣)](zh-TW/DESIGN.md) | [繁體中文 (香港)](zh-HK/DESIGN.md) | [हिन्दी](hi/DESIGN.md) | [Español](es/DESIGN.md) | [العربية](ar/DESIGN.md) | [Français](fr/DESIGN.md)

## Documentation

- Project overview: [README](../README.md)

- Design rationale: [DESIGN](DESIGN.md)

- Release history: [LOG](LOG.md)

- Third-party notices: [THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES.md)

## Design Goals

<a id="vps-design-goals"></a>

**Implemented goals in v2.0.0 (see [acceptance limits][local-link-001]):**

Version 2.0.0 also contains experimental frps and Lucky installer paths.
Their host behavior has not been accepted on a real host; the goals below
describe the four previously documented modules.

- Install, on a fresh Debian/Ubuntu VPS, a single bundle with four selectable
  modules providing five capabilities (the web module includes the public page
  and private console):
  1. **Public reachability page** — a deliberately minimal page served on TCP
     **80 and 443** with no authentication, so that anyone given only the IP can
     confirm in a browser whether this host's web ports are reachable from where
     they are.
  2. **Private console** — a dashboard on a persisted random high port,
     providing browser-based up/download speed testing and a log of recently
     observed inbound connections. It accepts an admin password or an
     explicitly allowed private LAN IP.
  3. **On-demand iperf3 window** — a bandwidth/latency test endpoint that is
     **off by default**; an operator opens a time-boxed window from the console,
     and it closes itself when the window expires.
  4. **anytls proxy** — a sing-box `anytls` inbound with a self-signed
     certificate, plus BBR.
  5. **proxy** — any subset of sing-box `vmess`/`vless`/`trojan`/`shadowsocks`
     inbounds, sharing one systemd unit, one config, and the same vendored
     sing-box binary the anytls module uses. See "The proxy module" below.
- Be installable with no outbound network access beyond the distro package
  mirror. The sing-box binary ships in the repository.
- Coexist on the same host with `vps-webserver` and `Anytsl-Serve` without
  colliding on systemd unit names, install prefixes, environment variable
  prefixes, or persisted ports.

**Tracked goals and current status:**

- [x] 2026-09-19 Per-node traffic accounting and data caps: the five proxy protocols track upload/download independently. The original 1 Mbps response to a cap and the monthly or one-time reset passed live-host tests on 2026-09-27. The current branch adds separate upload/download speed caps, a choice of 1 Mbps throttling or blocking after the traffic cap, recurring cycles measured in days, calendar months or years, and an optional validity duration that blocks traffic on expiry. The new policy rules and state migration have automated checks; the current test host has verified the UI and migration, while live transfer through every policy combination remains unverified.
- [x] 2026-09-19 Browser-based first-run setup: this checkout uses a short-lived setup wizard in `tools/setup_wizard/setup_wizard.py` when the interactive installer has no `VPSSRV_MODULES` value. It collects language, modules, ports, and authentication choices; the shell installer performs the selected actions only after validating the result. This checkout has not been accepted on a real host.
- [ ] 2026-09-22 Complete frps console support for tokens and connection information. The installer now offers frps on this checkout, but the console requirement remains unscoped: decide whether token information means an auth token, client config snippet, or connected-proxy list.
- [ ] Scope the broader `gdy666/lucky` feature request recorded in the 2026-09-22 status snapshot. The checkout now offers a Lucky install path, but no broader feature list or acceptance criteria were recorded.
- [x] Complete live-host acceptance of the node controls: display numbers stay contiguous after deletion and restart at 1 when all nodes are removed, while hidden UUIDs preserve identity; names, ports, credentials, and TLS SNI are editable; Shadowsocks shows SNI as not applicable; random port and credential reset leaves SNI unchanged. Each node can be disabled without deleting its configuration or traffic record and re-enabled on the same port. The controls passed live-host tests on 2026-09-27.
- [x] Redesign the full Web UI with one accessible design system across the console, public reachability page, and setup wizard. The shared spacing, control styles, bundled fonts and icons, visible focus, and responsive layouts remain in use. Ordinary Settings now offers eight persistent accent choices and separate persistent light and dark modes; the selected accent survives a mode switch.

The shared SQLite-lock concern is a [known unresolved measurement question][local-link-002], not a mandate to change the architecture. Historical completed work and verification records are in [LOG][local-link-003].

**Non-goals**

- **Not a replacement for `vps-webserver` or `Anytsl-Serve`.** Both remain
  independently maintained and independently released. vps-server vendors their
  code rather than importing or superseding it; see [Decisions][local-link-004] for the
  drift trade-off this accepts and the mitigation.
- **No ACME / Let's Encrypt / domain names.** TLS on 443 is a self-signed
  certificate. The public page's job is to answer "can you reach this IP at
  all", which a browser warning page already answers. Certificate renewal and
  a domain dependency buy nothing for that job.
- **No always-on iperf3.** An unauthenticated public `iperf3 -s` lets any
  stranger saturate the host's uplink for as long as they like.
- **The public page exposes nothing about the host.** No hostname, no kernel
  version, no uptime, no service inventory, no port list, no anytls parameters.
  It reports only: you reached it, the source IP it saw, the server clock, and
  which of the two ports/protocols you arrived on.
- **No reverse proxy, no nginx, no containers.** The Python process terminates
  TLS itself, as `vps-webserver` already does.
- **No multi-server speedtest selector.** One host, this host.

## Architecture

The web service, anytls service, and optional proxy service run as separate processes; the web service also spawns a transient iperf3 child. The console and public page use separate listeners within one Python process and share in-memory state. Only configured client traffic reaches these services.

```
                       ┌──────────────────────── vps-server-web.service ───────┐
  anyone, no auth      │                                                       │
  :80  ──────────────► │  public listener (HTTP)  ──┐                          │
  :443 ──────────────► │  public listener (HTTPS) ──┤                          │
                       │                            ├─► ProbeHandler           │
                       │                            │   (reachability page)    │
                       │                            │                          │
  operator, password   │                            │                          │
  :<random> ─────────► │  console listener  ───────►│   ConsoleHandler         │
                       │                            │   ├─ LibreSpeed endpoints│
                       │                            │   ├─ visitor log         │
                       │                            │   └─ iperf3 window ctl ──┼──┐
                       │                            │                          │  │
                       │  connection poller ◄───────┴── /proc/net/tcp[6]       │  │
                       │  (all ports, not just HTTP)                           │  │
                       └───────────────────────────────────────────────────────┘  │
                                                                                   │
  tester with iperf3      :5201 ◄────────────── iperf3 -s  (child process, ────────┘
  client                                         killed when window expires)

                       ┌─── vps-server-anytls.service ───┐
  proxy client ──────► │  sing-box, anytls inbound, TLS  │
  :<random>            │  self-signed cert               │
                       └─────────────────────────────────┘
```

The diagram shows the web and anytls units; the optional `vps-server-proxy.service` runs multiple independent inbounds in a third process, sharing the vendored sing-box binary but not either unit's state. Each module can be selected separately; see [The proxy module][local-link-005].

### Why the public page and the console are separate listeners

They have opposite security postures, and merging them would force one of the
two to give up its own. The console is authenticated and on an unguessable port
precisely so that it is not casually discoverable; the public page **MUST** be
trivially discoverable and **MUST NOT** ask for a password. So: different ports,
different request handlers, different route tables. A request arriving on 80/443
can never reach a console route, because `ProbeHandler` has no such routes — not
because a check rejected it. That is the point; an authorization check can be
bugged, an absent route cannot. Password-authenticated administrators can add
individual private LAN IPs in Settings. Public IPs, shared-address space such as Tailscale IPv4, and
network ranges are rejected. IP admission uses the connection peer, never a
client-supplied forwarding header, and is disabled when `VPSSRV_TRUST_PROXY=1`
because that mode has no configured trusted-proxy boundary. IP admission opens
ordinary console pages after the visitor chooses IP access on the login page.
The resulting session is bound to the connection peer and the allowlist is
rechecked on every request. Security Settings requires administrator-password
verification recorded for the session and expires after ten minutes. An IP-only
session completes that challenge and receives a new password-authenticated
session; changing the password invalidates all existing sessions. The ordinary
Settings page holds appearance and language choices without a second password
check. Its separate Security page requires the short-lived verification before
showing the allowlist or changing security controls. The allowlist
accepts only individual RFC 1918 IPv4 or unique-local IPv6 addresses and has a
separate enable switch. A gateway that maps several devices to one allowed
private IP gives all those devices the same access.

The public page accepts `GET` and `HEAD` on exactly two paths (`/` and
`/favicon.ico`) and answers everything else with 404. It reads no query string,
parses no request body, and sets no cookie.

### Upgrading over an existing install

`install.sh` detects an existing install and offers to keep its configuration.
Saying yes replays what the previous install recorded; saying no re-asks
everything. Either way the console password, the persisted port, the
certificates and the visitor log survive — those are files the installer never
touches.

Two records, because they answer different questions:

- **The systemd unit's `Environment=` lines** say what was *set*. Replaying
  them is what stops a setting chosen once — a custom public port, TLS on the
  console — from silently reverting to its default on the next upgrade.
- **`$PREFIX/.install-state`** says what the installed version *knew about*:
  its version, its module list, and the names of every setting it understood.
  The unit cannot answer this, because it only records settings that were
  given a value, which says nothing about which settings existed.

That second file is how "what is new in this version" is computed: the
settings this version knows minus the ones the stamp lists. Each one is
offered with its `.env.example` default, and pressing Enter accepts it.

An install that predates the stamp has no such list. Rather than presenting a
guess as a diff, the installer says it cannot tell, carries forward everything
the unit recorded, and points at the re-ask path. Module detection degrades
the same way: with no stamp it infers the module list from what is on disk —
the web unit, the anytls unit, whether `iperf3` is installed.

The anytls node is preserved across an upgrade by reading its port and
password back out of `config.json` and passing them in. Without that step
`setup-anytls.sh` would default both to fresh randoms and every configured
client would break on a routine upgrade — see the gotcha below, which still
applies to a *deliberate* re-install.

### The console's anytls section

**Lives on `/proxy` now, not its own page** (2026-09-22) — see "The proxy
module" below for why anytls and the proxy module's protocols were merged
onto one page. `/anytls` still exists as a redirect to `/proxy`, and
`POST /anytls/reset` is unchanged; only the standalone `GET /anytls` page
and its own nav link/dashboard tile are gone. Everything below still
describes how the anytls section of that merged page behaves.

The console reads the installed node out of `VPSSRV_ANYTLS_CONFIG` and renders
its status plus a ready-to-paste Clash entry and `anytls://` link.

It writes exactly one thing: the "reset port and password" button, and even
that delegates. The console does not touch `config.json` itself — it runs
`setup-anytls.sh reset`, because the ordering that matters there is easy to
get wrong: the old port's firewall rule has to be withdrawn *before* the new
port is opened, or every reset leaves an `ACCEPT` behind for a port nobody is
listening on. That logic lives with the script that owns the node, not in two
places. The reset requires a confirmation checkbox validated on the server —
`required` in the markup stops a mis-click, not a client that is not a
browser — because rotating the credentials breaks every configured client
until they are given the new ones.

It also runs **outside this service's sandbox**, as a transient unit via
`systemd-run --pipe --wait --collect`. The web unit has
`ProtectSystem=strict` with only `ReadWritePaths=$PREFIX`, so `/etc` is
read-only to it, and a reset has to write `/etc/vps-server-anytls` and a unit
file. The first real attempt died halfway through for exactly that reason —
after it had already withdrawn the old port's firewall rule. The alternative,
adding `/etc/systemd/system` to `ReadWritePaths`, would widen the long-running
service's write access permanently so that one button works; the sandbox is
worth more than that. Without `systemd-run` the call is made directly, which
is correct because the environments that lack it are the same ones where
`install.sh` omits the hardening.

`setup-anytls.sh reset` also checks that it can write before it touches the
firewall. A reset that fails after withdrawing the old rule leaves a running
node with no way in, which is worse than one that never started.

Two details are load-bearing. The **node password is on that console section in clear**,
which is acceptable only because the page lives on `ConsoleHandler`, behind
the login; `ProbeHandler` has no route to it, and a test asserts the public
listener 404s `/anytls` and never contains the password. And the **server
address is taken from the request's `Host` header** rather than looked up:
whatever address reached the console reaches the node, an outbound IP-lookup
at render time would contradict the no-outbound-requests rule, and anyone who
needs a different address edits the line after copying.

The SNI is not stored in sing-box's config at all — `setup-anytls.sh` only
bakes it into the self-signed certificate's CN — so the console reads it back
from the certificate rather than keeping a second copy that could drift.

### The proxy module

<a id="vps-proxy-module"></a>

The former backlog asked whether the already-vendored sing-box binary covers more
protocols than anytls, or whether a second backend would be needed. It does:
`vmess`, `vless`, `trojan` and `shadowsocks` (2022-blake3-aes-128-gcm) each
pass `sing-box check`, and — confirmed by actually running it, not just
validating the config — all four bind their ports and accept connections
simultaneously in one `sing-box run` process. No second backend was added.

Unlike anytls, this is **one systemd unit (`vps-server-proxy.service`) with
multiple simultaneous inbounds in one `config.json`**, not four clones of the
anytls shape. Reasons: one unit to monitor instead of four, one certificate at initial install
and separate certificates for new TLS nodes (shadowsocks needs none), and it is
the shape a later per-node traffic-accounting feature would want anyway — one
process whose `inbounds` array is already the node list. `deploy/proxy/setup-proxy.sh`
is first-party to vps-server, not vendored from anywhere, since none of these
four protocols come from Anytsl-Serve.

It **shares the vendored sing-box binary with the anytls module**
(`/usr/local/bin/sing-box-vps-server`) rather than carrying a second ~57 MB
copy. Both modules' `uninstall()` check whether the *other* module's config
still exists before deleting that binary — anytls's own vendored
`setup-anytls.sh` gained this check as a local, documented deviation (see
`deploy/anytls/.upstream-version`) specifically because the binary is no longer
anytls's alone to delete.

`PROXY_PROTOCOLS` (comma-separated, default all four) is validated into a
global array, not echoed through `$(...)` command substitution — an early
version validated it inside a function called as `read -ra x <<< "$(fn)"`,
and `exit 1` inside that substitution's subshell only killed the subshell:
the parent script silently continued with an empty protocol list and started
a service with zero inbounds. Same class of bug as the `prompt_new_settings()`
entry in [Decisions][local-link-006]. Each protocol's port comes from a distinct
5000-wide range under 60000 (not 10000-wide from 60000, which overflowed
sing-box's `uint16 listen_port` past 65535 on whichever install happened to
roll a high port — caught by five repeated fresh installs, not by the first
one). Preserving credentials across an upgrade works the same way as anytls's
`preserve_anytls()`: `preserve_proxy()` reads every installed protocol's port
and credential back out of `config.json`, plus the protocol *set* itself, so
`VPSSRV_MODULES=proxy` on a re-run does not silently drop or add a protocol.

The installer initially creates one inbound per selected protocol. The managed
console can then create multiple numbered nodes for any installed protocol,
delete individual nodes, and leave a module installed with zero listeners.
Node IDs remain stable and hidden in the visible UI; every form and Clash
subscription targets the ID, so repeated protocols stay independent. A node's
connection editor replaces its visible facts in the same card. The separate
traffic form accepts a GiB cap, Mbps upload/download limits, cap response,
recurring reset interval and optional validity duration. A reset clears period
usage and lifts quota enforcement; it does not renew the validity duration.
The version-one inventory is converted to version two on read: old absolute
expiry dates are cleared so their former 1 Mbps meaning cannot silently become
a block, while identities, counters, caps and schedules remain intact. Adding or deleting a node
changes the sing-box config, inventory, firewall and nft accounting under one
lock, with rollback on failure. Newly created TLS nodes get their own
self-signed certificate. The console uses `font-display: optional` for its
bundled fonts to avoid a late font swap after first paint.

The console's `/proxy` page renders one section per installed node —
port, UUID or password (whichever the protocol uses), the shared SNI (read
back from the certificate CN, same trick as anytls), and a Clash entry plus
share link (`vmess://`, `vless://`, `trojan://`, `ss://`) per detected
address. **Each protocol has its own reset button**, not one shared "reset
everything" button — an operator pointed out that a combined button forces
rotating protocols nobody asked to touch, e.g. a leaked vmess UUID
shouldn't mean re-configuring every trojan/vless/shadowsocks client too.
`setup-proxy.sh reset <protocol>` rotates only that one's port and
credential; `load_installed_vars()` reads every *other* protocol's current
values back from disk first, so they survive untouched. `reset` with no
argument still rotates everything currently installed — kept for the
terminal/scriptable path, not exposed anywhere in the console UI. Both
forms run via the same outside-the-sandbox `systemd-run` pattern
`anytls_reset()` uses, for the same `ProtectSystem=strict` reason. One real
cost of the shared systemd service (see above): resetting one protocol
still restarts the whole service, so every other protocol's *connections*
drop briefly even though their credentials don't change.

`PortForwardManager.reserved_ports()` treats every installed proxy protocol's
port the same way it already treats the anytls node's port and the console's
own: reserved, so a port-forward rule cannot be pointed at a port a proxy
protocol already owns.

**The console's `/proxy` page also shows the anytls node**, if installed —
an operator reported having anytls on its own separate page as an artificial
split, since both are "proxy nodes" from their point of view regardless of
which of the two independent backends serves each one. `/anytls` redirects
here; `POST /anytls/reset` is unchanged, just redirects back to `/proxy`
afterwards. The two modules keep independent configurations and reset
buttons; only the page they render onto is shared. The page lists host
interface and optional Tailscale addresses without a separate public-IP lookup.

### iperf3 window lifecycle

1. Operator authenticates to the console, picks a duration (default 10 min,
   capped by `VPSSRV_IPERF_MAX_MINUTES`), clicks open.
2. The console spawns `iperf3 -s -p <port>` as a child process, opens the port in
   whichever firewall is active, and records the deadline in memory.
3. While the window is open, the **public page** shows that iperf3 is accepting
   connections, on which port, and how much time is left — the remote tester
   needs to know this, and it is not sensitive: the window is deliberately open.
4. At the deadline (or on operator request, or on service stop) the child is
   terminated and the firewall rule withdrawn.

The window is held in memory, not on disk: if the service dies, the window is
gone, which is the safe direction to fail. A restart never resurrects an open
window. The selected port is persisted separately in the app's data directory.
It can be changed from the console only while the window is closed; the new
port is checked against installed service and forwarding ports and active
listeners before it is saved.

Latency is read from iperf3's own `--json` output (`mean_rtt` in the TCP info
block) on the tester's side; the server needs no extra code for it. That field
comes from the kernel's `TCP_INFO`, so it is present on a Linux client and
absent on one that cannot read it — iperf3 under Cygwin on Windows reports
throughput but no `mean_rtt`. UDP mode (`-u`) reports jitter and loss
everywhere, and is the portable answer when the tester is not on Linux.

### Port forwarding lifecycle

A forward relays a public TCP/UDP port on this host to a device reached over
Tailscale or the LAN — the way a box with a public IP can stand in for one
that has none. Unlike the iperf3 window this is configuration, not a timed
loan of the uplink: it is meant to still be there after a restart or a
reboot, so it is built differently.

1. Operator adds a rule from the console: protocol (tcp/udp/both), a public
   port, and a target `host:port`. `PortForwardManager.add()` rejects a
   public port already used by this install (console, public page, iperf3,
   the anytls node, or another forward) before anything touches iptables.
2. Each protocol in the rule becomes four `iptables` rules, all tagged with
   `-m comment --comment vps-server-portfwd-<id>` so they can be told apart
   from anything else already in the tables:
   - `nat`/`PREROUTING`: DNAT the public port to `target_host:target_port`.
   - `nat`/`POSTROUTING`: MASQUERADE traffic bound for the target, so replies
     route back through this host rather than out the target's own default
     gateway — the target sees this host as the client.
   - `filter`/`FORWARD`: one ACCEPT rule in each direction, since a default
     `DROP` policy on that chain (common on a Docker host, for instance)
     would otherwise silently eat the forwarded traffic.
3. `net.ipv4.ip_forward` is turned on the first time any rule needs it
   (`_ensure_ip_forward()`), and never turned back off — see [Decisions][local-link-007]
   (2026-09-19) for why.
4. The rule set lives in `PORTFWD_STATE_FILE` (JSON), not just in memory.
   Every process start calls `PortForwardManager.load()`, which withdraws
   then re-adds every enabled rule's iptables state unconditionally — the
   kernel's tables remember nothing across a reboot, and may still hold last
   run's rules if this is only a service restart, so this is the one path
   that has to be correct whichever case it is.
5. A clean stop (`SIGTERM`, same signal handler the iperf3 window uses) calls
   `PortForwardManager.shutdown()`, which withdraws every enabled rule's
   iptables state but leaves the JSON `enabled` flag untouched — restarting
   the service, or the host, **MUST** bring every one of them straight back via
   `load()`. This is the same fail-safe direction as the iperf3 window: if
   the process managing the state is not running, the state **MUST NOT**
   silently outlive it.

`target_host` **MUST** be a literal IPv4 address, not a hostname: `iptables --to-destination` takes an address, and this project makes no outbound DNS
lookup at request time (see the "Zero third-party runtime dependencies"
decision). A Tailscale device's IP is stable and shown in `tailscale status`
or `tailscale ip` on that device.

## Design Constraints

- Keep console routes out of `ProbeHandler`; authentication is not a substitute for the separate public route table.
- Keep iperf3 time-boxed and remove the firewall rule on close or shutdown.
- Reapply persisted forwards from JSON at process start; withdraw runtime rules at a clean stop without resetting the host-wide `ip_forward` toggle.
- Preserve node credentials and selected settings on upgrade; use the owning setup scripts for rotation, outside the web unit's filesystem sandbox.
- Do not decouple the shared `_db_lock` without evidence of harmful latency: the historical 60-flooder measurement did not reproduce a slowdown. See [Bugs][local-link-008].

## External Interfaces

- HTTP/HTTPS: public listeners on 80/443 expose only the reachability page; the operator console uses a separate persisted port. iperf3 listens only within an authenticated time-boxed window.
- The console reads `/proc/net/tcp[6]` to log inbound TCP connections; it does not export proxy secrets on public routes.
- `install.sh` uses the distro package manager and does not look up a public IP. The service makes no outbound public-IP request at runtime. `setup-anytls.sh` and `setup-proxy.sh` manage sing-box units and certificates. iptables manages temporary iperf3 exposure and enabled forwards; systemd supervises services and runs credential resets outside the web sandbox.

## Tech stack

| Layer | Choice | Version | Why |
|---|---|---|---|
| Runtime | Python, standard library only | 3.9+ | Inherited from `vps-webserver`: no third-party Python packages; the distro-managed interpreter and libraries still require security updates |
| HTTP server | `http.server.ThreadingHTTPServer` | stdlib | Three listeners of a few requests each; a framework would be dead weight |
| TLS | `ssl` + `openssl`-generated self-signed cert | stdlib / distro | No domain, no ACME (see non-goals) |
| Store | `sqlite3` | stdlib | Visitor log **MUST** survive restarts |
| Speedtest engine | LibreSpeed, vendored unmodified | v6.2.1 | LGPL-3.0; already vendored and working in `vps-webserver` |
| QR code rendering | kazuhikoarase/qrcode-generator, vendored unmodified | js2.0.4 | MIT; small, no build step, plain `<script>` tag like LibreSpeed |
| Bandwidth probe | `iperf3` from the distro | not pinned by this project | The de-facto tool testers already have on the client side |
| Proxy core | sing-box, vendored binary (amd64) | v1.13.14 | GPL-3.0; shipping the binary keeps install offline-capable |
| Init | systemd | — | Target OS default |
| Installer | Bash | — | Inherited from both upstreams |

Rejected alternatives and the reasoning behind each choice live in
[Decisions][local-link-009] — do not restate them here.

## Reproduction requirements

<a id="vps-reproduction-requirements"></a>

### Environment

- OS: Debian 11+ / Ubuntu 20.04+, systemd, run as root
- Runtime: Python 3.9+ (distro python3 is sufficient)
- Architecture: **x86-64 only** for the anytls and proxy modules — both point
  at the same vendored amd64 sing-box binary. The web and iperf3 modules are
  architecture-independent.
- Hardware: no GPU; ~150 MB disk (of which ~57 MB is the sing-box binary), any
  amount of RAM a VPS normally has
- Vendored artifact integrity check: from the repository root, run
  `python3 tools/verify_dependencies/verify_dependencies.py`. This compares the five tracked third-party
  distributables with [config/dependencies.lock.json][local-link-010] using
  SHA-256 without executing them. The recorded version and upstream revision
  fields are prior project records, not independently verified upstream
  identities. LibreSpeed's exact upstream revision is not recorded.
- There is no third-party Python package lock because `app.py` uses the standard
  library. This artifact lock is not a dependency restore command or a complete
  system-package lock; see [THIRD_PARTY_NOTICES.md][local-link-011].

### External dependencies

| Item | Source | Placed at |
|---|---|---|
| `iperf3` | distro package manager (`apt-get install iperf3`) | system path |
| `openssl`, `curl`, `jq`, `iproute2`, `procps`, `iptables`, `ca-certificates` | distro package manager or existing host installation | system path |
| sing-box binary | ships in this repository | `/usr/local/bin/sing-box-vps-server` |
| LibreSpeed engine and qrcode-generator library | ship in this repository | `$PREFIX/static/` |
| TLS certificates | generated on first run by the installer | `$VPSSRV_CERT_DIR` |

The installer installs missing system packages (including optional `iperf3`)
from the target Debian/Ubuntu package repositories without selecting exact
versions or repository snapshots. Python, OpenSSL, shell/system tools and
systemd are also provided by the target OS. The host operator relies on the
chosen distro's security-maintained package channels for updates. This avoids
bundling their binaries, but package versions, hashes and transitive resolution
can differ across hosts and time; **a strict, fully reproducible dependency
restore is not achieved**. Achieving one would require a separately approved
installer change and a selected distribution/repository snapshot. The lock's
machine-readable `exclusions` records this boundary, not a fictitious pin.

No API keys. The web service makes no outbound public-IP lookup at runtime.
The installer does not perform an outbound public-IP lookup.

### Paths & mounts

<a id="vps-paths-mounts"></a>

| Path | Provided by | Purpose |
|---|---|---|
| `$PREFIX` | installer, default `/opt/vps-server` | Code, static assets, persisted port files |
| `$VPSSRV_DATA_DIR` | installer, default `$PREFIX/data` | `visitors.db`, `session_secret.txt`, `portfwd.json`, private-IP allowlist `login-access.json` |
| `$VPSSRV_CERT_DIR` | installer, default `$PREFIX/certs` | Self-signed cert and key for 443 |
| `/etc/vps-server-anytls/` | installer | sing-box `config.json` and its own self-signed cert |
| `/etc/vps-server-proxy/` | installer | sing-box `config.json` (multiple inbounds) and its initial self-signed cert; new node certs live under `/etc/vps-server-nodes/certs/` |

### Configuration reference

<a id="vps-configuration-reference"></a>

All variables use the `VPSSRV_` prefix. This is not cosmetic: `vps-webserver`
owns `VPSWS_` and `Anytsl-Serve` owns `ANYTLS_`, and all three may be installed
on one host, where a shared prefix would let one project's `.env` silently
reconfigure another.

| Variable | Meaning | Default | Required |
|---|---|---|---|
| `PREFIX` | Install root. Passed to `install.sh`/`uninstall.sh`, **not** read from `.env` — the path is needed before there is an install to read a `.env` from | `/opt/vps-server` | no |
| `VPSSRV_DATA_DIR` | SQLite + session secret | `$PREFIX/data` | no |
| `VPSSRV_HOST` | Bind address for all listeners | `0.0.0.0` | no |
| `VPSSRV_PUBLIC_HTTP_PORT` | Public reachability page, plaintext | `80` | no |
| `VPSSRV_PUBLIC_HTTPS_PORT` | Public reachability page, TLS | `443` | no |
| `VPSSRV_PUBLIC_ENABLE` | Serve the public page at all | `1` | no |
| `VPSSRV_CONSOLE_PORT` | Console port; `0` = generate once and persist | `0` | no |
| `VPSSRV_CONSOLE_PORT_FILE` | Where the generated console port is remembered | `$PREFIX/console_port.txt` | no |
| `VPSSRV_CONSOLE_TLS` | Serve the console over HTTPS | `0` | no |
| `VPSSRV_AUTH` | Require login on the console | `1` | no |
| `VPSSRV_PASSWORD_FILE` | Plaintext console password; Settings verifies the current password before changing it | `$PREFIX/admin_password.txt` | no |
| `VPSSRV_IP_ALLOWLIST_FILE` | Optional path for the private-IP allowlist | `$VPSSRV_DATA_DIR/login-access.json` | no |
| `VPSSRV_CERT_DIR` | Self-signed cert location | `$PREFIX/certs` | no |
| `VPSSRV_TLS_CERT` / `VPSSRV_TLS_KEY` | Use an operator-supplied cert instead | — | no |
| `VPSSRV_IPERF_PORT` | Port the iperf3 window listens on | `5201` | no |
| `VPSSRV_IPERF_DEFAULT_MINUTES` | Pre-filled window duration | `10` | no |
| `VPSSRV_IPERF_MAX_MINUTES` | Hard cap the console cannot exceed | `60` | no |
| `VPSSRV_IPERF_ENABLE` | Allow opening windows at all | `1` | no |
| `VPSSRV_PORTFWD_ENABLE` | Show the port-forwarding page and allow new forwards | `1` | no |
| `VPSSRV_PORTFWD_MAX_RULES` | Ceiling on configured forwards | `20` | no |
| `VPSSRV_TRUST_PROXY` | Honour `X-Forwarded-For` when recording visitors | `0` | no |
| `VPSSRV_TRACK_CONNECTIONS` | Poll `/proc/net/tcp[6]` for all-port connection logging | `1` | no |
| `VPSSRV_CONN_POLL_SECONDS` | Poll interval | `5` | no |
| `VPSSRV_MAX_TEST_MB` | Cap on a single speedtest transfer, in MB | `200` | no |
| `VPSSRV_TEST_SECONDS` | Measurement window per direction | `10` | no |
| `VPSSRV_WARMUP_SECONDS` | Discarded warmup at the start of each direction | `2` | no |
| `VPSSRV_DOWNLOAD_STREAMS` / `VPSSRV_UPLOAD_STREAMS` | Parallel streams per direction | `6` / `3` | no |
| `VPSSRV_PING_SAMPLES` | Round trips used for the latency figure | `20` | no |
| `VPSSRV_DEFAULT_LANG` | `en` / `zh_cn` / `zh_tw` / `zh_hk` / `hi` / `es` / `ar` / `fr` | `en` | no |
| `ANYTLS_PORT`, `ANYTLS_PASSWORD`, `SNI` | The anytls module keeps these upstream names | see `.env.example` | no |
| `VPSSRV_ANYTLS_CONFIG` | Where the console reads the installed node from | `/etc/vps-server-anytls/config.json` | no |
| `VPSSRV_ANYTLS_SERVICE` | Unit the console checks for node liveness | `vps-server-anytls.service` | no |
| `VPSSRV_ANYTLS_SETUP` | Script the console runs to rotate the node's credentials | `$PREFIX/anytls/setup-anytls.sh` | no |
| `PROXY_PROTOCOLS`, `PROXY_SNI` | The proxy module's own script-level knobs — first-party, so no vendoring constraint, but kept unprefixed to match anytls's script-vs-console distinction | see `.env.example` | no |
| `VPSSRV_PROXY_CONFIG` | Where the console reads the installed node set from | `/etc/vps-server-proxy/config.json` | no |
| `VPSSRV_PROXY_SERVICE` | Unit the console checks for node liveness | `vps-server-proxy.service` | no |
| `VPSSRV_PROXY_SETUP` | Script the console runs to rotate the selected protocol's credentials | `$PREFIX/proxy/setup-proxy.sh` | no |

The anytls module deliberately keeps `Anytsl-Serve`'s variable names rather than
renaming them to `VPSSRV_ANYTLS_*`: the vendored config generator reads them, and
renaming would mean patching vendored code, which is what the vendoring policy
exists to avoid.

## Setup from scratch

1. `git clone <repo>` and `cd` into it — verify: `ls -lh third_party/sing-box/sing-box` shows the ~57 MB binary.
2. `bash deploy/install.sh` — an interactive run starts a temporary browser
   setup wizard for modules, UI language, console authentication, and ports.
   Open the printed URL and enter its one-time token; after applying the
   validated selection, verify the terminal summary lists each module and port.
3. `systemctl status vps-server-web` — verify: `active (running)`.
4. From another machine, open `http://<ip>/` — verify: the reachability page
   renders and shows your own source IP.
5. From another machine, open `https://<ip>/` and accept the certificate warning
   — verify: the same page, with the protocol line reading HTTPS.
6. Open `http://<ip>:<console port>/`, log in — verify: the dashboard loads and
   shows the iperf3 control with the window closed.
7. Open a 5-minute iperf3 window from the console, then from another machine run
   `iperf3 -c <ip> -p 5201 --json` — verify: throughput is reported and
   `mean_rtt` is present in the output.
8. If the anytls module was installed: `systemctl status vps-server-anytls` —
   verify: `active (running)`; the installer's summary printed a client config
   line.

## Data Design

The visitor database, `portfwd.json` (enabled forwarding rules), and
`login-access.json` (private-IP allowlist) persist under `$VPSSRV_DATA_DIR`.
The console password, selected port, web certificates and
`.install-state` live under `$PREFIX`; the sing-box module configs and their
certificates live in `/etc/vps-server-anytls/` and `/etc/vps-server-proxy/`.
See [Paths & mounts][local-link-012]. The iperf3 deadline stays in memory
and does not survive restart.

### Data model / file layout

```
<project root>/
├── snapshots/                 # private snapshots; not part of the Git repository
└── repo/                      # Git working tree; paths below are relative to it
    ├── README.md              # entry point for users and documentation navigation
    ├── config/VERSION         # release version used in checkout
    ├── src/web/app.py         # web service implementation
    ├── deploy/
    │   ├── install.sh         # module-selecting installer
    │   ├── uninstall.sh       # module removal
    │   ├── systemd/vps-server-web.service
    │   ├── anytls/setup-anytls.sh
    │   ├── proxy/setup-proxy.sh
    │   ├── frps/setup-frps.sh
    │   └── lucky/setup-lucky.sh
    ├── static/                # first-party UI assets and vendored browser libraries
    │   └── third_party/
    │       ├── librespeed/    # speedtest.js, speedtest_worker.js
    │       └── qrcode/        # qrcode.js, qrcode-utf8.js
    ├── lang/                  # interface catalogs for web, installers, and tools
    ├── third_party/sing-box/
    │   ├── sing-box           # vendored amd64 binary
    │   ├── sing-box.version   # binary version metadata
    │   └── LICENSE            # original upstream notice
    ├── tools/verify_dependencies/verify_dependencies.py # checks config/dependencies.lock.json from repo root
    ├── config/dependencies.lock.json
    ├── config/upstream-version # records: vps-webserver v0.4.1
    ├── deploy/anytls/.upstream-version # records: Anytsl-Serve v1.2.0
    ├── tests/
    ├── LICENSE                # GPL-3.0
    └── doc/
        ├── DESIGN.md          # architecture, constraints, and tracked goals
        ├── LOG.md             # bugs, dated decisions, verification, release history
        ├── THIRD_PARTY_NOTICES.md
        └── <lang>/            # translated docs (seven language directories)
```

These are checkout paths only: installation still places the application,
proxy executable, and browser assets under `$PREFIX/app.py`, `$PREFIX/sing-box`,
and `$PREFIX/static/`. Existing HTTP asset URLs are unchanged. In the checkout,
the installer and uninstaller are `deploy/install.sh` and `deploy/uninstall.sh`;
the installed web entry point remains `$PREFIX/app.py`.

Only `repo/` is tracked by Git; `snapshots/` is separate and private. Start at
[README][local-link-013], use [LOG][local-link-014] for historical verification and
release history, and consult [third-party notices][local-link-015] for
upstream assets. Documentation does not make a snapshot or installed host a
reproducible source checkout.

SQLite schema is inherited unchanged from `vps-webserver`: one `visits` table,
trimmed to the most recent 1000 rows. `portfwd.json` is a flat JSON list of
rule objects (`id`, `label`, `protocol`, `public_port`, `target_host`,
`target_port`, `enabled`, `created`) — see `PortForwardManager` in `src/web/app.py`.

## Known limitations & gotchas

- **Binding 80 and 443 requires root and an otherwise-free port.** If nginx,
  Apache, Caddy, or another `vps-webserver` instance already holds either port,
  the installer refuses rather than fighting for it. Check with
  `ss -lntp '( sport = :80 or sport = :443 )'` before installing.
- **The public page is genuinely public.** Anyone who guesses or scans the IP
  sees it, and every such hit lands in the visitor log. That is the feature, but
  it also means the visitor log on a scanned IP fills with internet background
  noise within hours.
- **Unit names differ from upstream on purpose.** `Anytsl-Serve` installs
  `sing-box-anytls.service`; this project installs `vps-server-anytls.service`
  and a separately-named binary, so both can exist. The installer still refuses
  to proceed if the upstream unit is running, because two anytls inbounds on one
  host is almost certainly a mistake rather than an intent.
- **`iperf3` is not version-pinned.** It comes from the distro, so its version
  varies by release. The wire protocol has been stable across the 3.x line, but
  a client much older than the server can fail the version handshake.
- **amd64 only for anytls and proxy.** The vendored binary is not multi-arch; on arm64 the
  installer skips the module with an explanation rather than installing a binary
  that cannot execute.
- **Self-signed TLS means a browser warning on 443, every time.** This is
  expected and is not worth "fixing" with an exception or an HSTS header.
- **A restart closes any open iperf3 window.** Intentional; see the lifecycle
  section.
- **Stopping the service withdraws every port forward, even the enabled
  ones.** Intentional and symmetric with the iperf3 window; see the port
  forwarding lifecycle section. `systemctl restart` or a reboot brings them
  straight back — `systemctl stop` left stopped does not.
- **`net.ipv4.ip_forward` is turned on automatically and never back off.**
  It is a single host-wide toggle; other software on the box (Docker, for
  one) may already depend on it, so removing the last forward does not touch
  it. Turn it off by hand if nothing else on the host needs it.
- **A forward only covers what raw `iptables` can see.** If `ufw` or
  `firewalld` is active with a default-deny `FORWARD` policy of its own, its
  chains are evaluated ahead of the rule this feature appends, and may still
  need their own allow rule for the same port before traffic gets through.
- **The sing-box binary is past GitHub's recommended file size.** At ~55 MB it
  is over the 50 MB soft limit, so every push prints a "Large files detected"
  warning suggesting Git LFS. Pushes still succeed; the hard limit is 100 MB.
  A future sing-box bump could eventually cross that, and the answer then is a
  decision to make deliberately (LFS, or stop shipping the binary), not a
  surprise on release day.
- **Run the scripts with `bash <script>`, not `./<script>`.** The executable
  bit is recorded in the git index, so a fresh clone has it — but a working
  copy on a CIFS/SMB mount does not, and `./install.sh` there fails with
  "Permission denied".
- **Re-vendoring anything executable loses its mode bit.** The maintainer's
  working copy is on CIFS, so a file extracted there and then `git add`ed is
  recorded as `100644` even when upstream had `100755`. This already happened
  once to the `sing-box` binary and broke the whole anytls module. After
  re-vendoring, check with `git ls-files -s` and restore the bit with
  `git update-index --chmod=+x <path>` — `chmod +x` alone is a no-op on that
  mount.
- **Running `setup-anytls.sh` directly rotates its port and password.**
  It defaults `ANYTLS_PORT` and `ANYTLS_PASSWORD` to fresh randoms and
  rewrites `config.json` every run, so invoking it by hand invalidates every
  client configured against the previous values. `install.sh` no longer does
  this — the upgrade path reads both back out of `config.json` and passes
  them in — but a direct call still will. To keep the node, pass the current
  values, both of which are on the console's anytls section of `/proxy`:
  `ANYTLS_PORT=<current> ANYTLS_PASSWORD='<current>' bash deploy/anytls/setup-anytls.sh`.
  Upstream behaviour, inherited deliberately. `setup-anytls.sh reset` rotates
  them on purpose, and the console's reset button is the supported way to ask
  for that.
- **The node page lists interface and Tailscale addresses.** The former
  install-time public-address block was removed because it duplicated a VPS
  interface address and could be misleading behind NAT. Setup scripts remove
  a `public-ip.txt` left by an older installation; the console does not read it.
- **`body` fed into `render_page()`** **MUST** be exactly one top-level element.
  `<main>` is `display: flex` with no `flex-direction` override, so more than
  one top-level sibling (e.g. one `<div class="card wide">` per protocol)
  lays out side by side instead of stacked — a real, shipped bug in an
  earlier version of the `/proxy` page, reported by an operator as "layout
  is messed up". Every page wraps everything in one outer card and nests
  repeated sections as `.node-addr` divs inside it instead.
- **Teardown needs the same `PREFIX` and `SERVICE_NAME` the install used.**
  `uninstall.sh` with no environment reads the defaults, finds nothing at
  those paths, and reports success having removed nothing. The installer's
  closing line prints the exact command with the values filled in; use that
  rather than typing it from memory.

## Extension

### How to extend

- **A new module** (something else the installer can optionally set up): add a
  `deploy/<name>/setup-<name>.sh`, its systemd unit (shipped in `deploy/systemd/` or generated
  by its setup script), a branch in `deploy/install.sh`'s module menu, and a teardown
  branch in `deploy/uninstall.sh`. Modules do not call each other.
- **A new console page**: add a route to `ConsoleHandler`. Do not add routes to
  `ProbeHandler` — its route table being nearly empty is a security property,
  not an oversight.
- **A new language**: add matching catalogs under every `lang/<component>/`
  directory, register the code in the web selector and changelog mapping,
  installer, setup wizard, and module script loaders, then add a matching
  `doc/<BCP47>/` tree.
- **A new colour**: add a token to `:root` in `static/style.css` *and* a
  light-mode value in the `prefers-color-scheme: light` block, then use the
  token. Never write a hex into a component rule — a literal cannot follow the
  theme, so it is correct in whichever mode it was eyeballed in and wrong in
  the other, with nothing to report it. Anything used as a filled background
  needs a paired `--on-*` foreground: the value that reads well as text is
  rarely the value that reads well behind white text. Check both modes against
  WCAG AA (4.5:1) before committing; `tests/test_app.py::StylesheetTest`
  enforces the structural half of this but cannot judge a ratio.
- **Refreshing a vendored upstream**: re-copy from the upstream tag, update the
  matching `.upstream-version` file in the same commit, and note the bump in
  [LOG.md][local-link-016]. Never hand-edit vendored code in place — a local edit that is
  not reflected upstream makes the next refresh a silent regression.

[local-link-001]: LOG.md#current-state-and-acceptance-limits
[local-link-002]: LOG.md#bugs
[local-link-003]: LOG.md#completed-work-history
[local-link-004]: LOG.md#decisions
[local-link-005]: #the-proxy-module
[local-link-006]: LOG.md#decisions
[local-link-007]: LOG.md#decisions
[local-link-008]: LOG.md#bugs
[local-link-009]: LOG.md#decisions
[local-link-010]: ../config/dependencies.lock.json
[local-link-011]: THIRD_PARTY_NOTICES.md
[local-link-012]: #paths--mounts
[local-link-013]: ../README.md
[local-link-014]: LOG.md
[local-link-015]: THIRD_PARTY_NOTICES.md
[local-link-016]: LOG.md#changelog
