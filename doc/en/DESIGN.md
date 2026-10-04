---
name: project-design-en
description: Project architecture and design constraints
metadata:
  version: "1.0.0"
  lang: "en"
---

# vps-server — Design — Design

## Multi-language

[简体中文](../DESIGN.md) | **English** | [Español](../es/DESIGN.md)

## Documentation

- Project overview: [README](README.md)

- Design rationale: [DESIGN](DESIGN.md)

- Project status: [LOG](LOG.md)
- Historical records: [HISTORY](HISTORY.md)
- Version changelog: [CHANGELOG](CHANGELOG.md)

- Third-party notices: [THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES.md)

## Design Goals

<a id="vps-design-goals"></a>

**Implemented goals in the current release (see [acceptance limits][local-link-001]):**

The current installer installs only the Web console by default. Select other server modules with the module variable or later in Settings → Modules. Install FRPC separately. The historical goals below retain their original scope and validation record.

- Install, on a fresh Debian/Ubuntu VPS, a console and network modules that can be enabled as needed (the web module includes the public page
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
  4. **Unified proxy** — one sing-box service hosts AnyTLS, VMess, VLESS,
     Trojan, and Shadowsocks.
  5. **Tailscale** — local Linux client status, preferences, device list,
     and logs.
- The complete offline package includes service binaries and a private nftables
  runtime for node accounting; target installation does not download source or
  system packages.
- Coexist on the same host with `vps-webserver` and `Anytsl-Serve` without
  colliding on systemd unit names, install prefixes, environment variable
  prefixes, or persisted ports.

**Tracked goals and current status:**

- [ ] 2026-10-04 v6 target-host acceptance: unified-proxy migration must preserve old node IDs, ports, credentials, certificates, and accounting state. The complete offline package must install on supported Debian/Ubuntu hosts without Git or repository network access. Joining Tailscale still requires a reachable control server.
- [x] 2026-09-19 Per-node traffic accounting and data caps: the five proxy protocols track upload/download independently. The original 1 Mbps response to a cap and the monthly or one-time reset passed live-host tests on 2026-09-27. The current branch adds separate upload/download speed caps, a choice of 1 Mbps throttling or blocking after the traffic cap, recurring cycles measured in days, calendar months or years, and an optional validity duration that blocks traffic on expiry. The new policy rules and state migration have automated checks; the current test host has verified the UI and migration, while live transfer through every policy combination remains unverified.
- [x] 2026-09-19 Browser-based first-run setup was previously provided by `tools/setup_wizard/setup_wizard.py` and has been retired. v5.0.0 installation runs directly in the terminal and installs only the Web console when `VPSSRV_MODULES` is unset.
- [x] 2026-09-22 Provide FRPS / FRPC connection information in the authenticated console. The page reports the local FRPS unit state, bind address, interface addresses, port, and auth token; sensitive values are fetched only on Show or Copy. A FRPC connection template uses the installed server values and a replaceable server-address placeholder. The server has no visibility into FRPC running on another device.
- [x] 2026-09-29 Manage host-local FRP configuration. A signed-in operator can change the FRPS bind port and token, edit and verify local FRPC instances, and start or stop those instances without recent administrator-password verification. The instance page reveals saved IP and token values only on request. A transient root helper performs fixed operations outside the Web unit's read-only system sandbox. It reserves changed local listener ports in `~/apps/PORTS.md` before starting them, releases ended assignments, restores the previous configuration on validation or service failure, and does not modify FRPC instances on other devices. The Modules page now installs a checksum-pinned FRPC binary and `frpc@.service` template separately from FRPS; it determines installation from those files, rather than from the presence of an instance configuration. Module uninstall stops instances and retains their configurations; complete `deploy/uninstall.sh` without `KEEP_DATA=1` removes this project's instance configurations and recovery copies.
- The FRPS edit helper holds the port registry lock. If an older installation lacks an entry for the current FRPS port, it registers that port from the existing configuration; it refuses the edit if another service owns the port. It reserves a new port before changing the configuration, removes that reservation if saving fails, and releases the old registration after success. A token-only edit keeps the current port registration.
- [x] 2026-09-29 Present FRPS and local FRPC controls as operator cards. FRPS uses the node page's inline edit pattern and a service switch. Each FRPC instance has a masked target IP, socket-derived connection indicator, and a separate Test connection action that makes a proxy-free FRPC login with saved credentials. Its page shows the server fields and every proxy's type, local IP, local port, and remote port; editing opens only after the operator chooses Edit, and saving returns to that instance. The field editor accepts only simple token-authenticated TCP/UDP configuration it can represent and leaves unsupported TOML unchanged. A target card represents a host-local instance, and the initial connection indicator requires an established socket owned by that instance's systemd main process to its configured server and port.

FRPC card review, 2026-09-29: the four operator screenshots showed the old connection template, masked facts without a direct reveal, an advanced TOML panel, and a server card without a test action. Chromium on the deployed `test-d09835d` build at 390 and 1440 CSS px checked the instance list, masked and revealed server facts, collapsed and open Edit controls, proxy facts, connection-test states, and a save returning to the same instance. The redundant panels are absent, both reveals load on request, all four proxy facts are visible, and neither viewport has horizontal overflow. The interface retains the project's existing card styling; real mobile hardware and proxy traffic were outside this browser review.
- [x] 2026-09-29 Add console module management. The former browser setup flow is historical. The Settings → Modules page can install an omitted module from the installed, version-matched source payload or enable and disable an installed module. A transient systemd job runs the installer outside the Web service; explicit module choices preserve existing credentials. Systemd service switches retain configuration; the public listener switches affect only their selected port so the control panel remains reachable.

The retired first-run listener registered its random port in `~/apps/PORTS.md` before serving and removed the registration on shutdown; its temporary password admitted only one browser session. The current Modules page is under ordinary Settings and uses the signed-in session. It submits fixed module names and actions to a separate privileged systemd job. The job records progress outside Web, allowing Web to restart during installation. Disabling proxy modules retains nodes and credentials; disabled units stay stopped when node controls are used. The iperf3 and public-page switches restart Web to apply listener changes while keeping the console available.
- [ ] Scope the broader `gdy666/lucky` feature request recorded in the 2026-09-22 status snapshot. The checkout now offers a Lucky install path, but no broader feature list or acceptance criteria were recorded.
- [ ] v6 Tailscale target-host acceptance: the console now provides Linux client overview, ordinary settings, device list, and runtime logs. The Web management port and node relay port are also registered in `PORTS.md`. These behaviors still need test-host confirmation; OpenWrt-specific dnsmasq forwarding does not apply to this Debian/Ubuntu project.
- [x] Complete live-host acceptance of the node controls: display numbers stay contiguous after deletion and restart at 1 when all nodes are removed, while hidden UUIDs preserve identity; names, ports, credentials, and TLS SNI are editable; Shadowsocks shows SNI as not applicable; random port and credential reset leaves SNI unchanged. Each node can be disabled without deleting its configuration or traffic record and re-enabled on the same port. The controls passed live-host tests on 2026-09-27.
- [x] Apply one accessible design system to the console and public reachability page. The browser setup wizard is retired. The shared spacing, control styles, bundled fonts and icons, visible focus, and responsive layouts remain in use. Ordinary Settings now offers eight persistent accent choices and separate persistent light and dark modes; the selected accent survives a mode switch.

The console login page uses the same project brand and home link as the rest of the interface. Its card footer links the running version to Changelog and offers language selection before authentication. Theme controls remain in ordinary Settings. Every editable password field starts masked and has its own accessible Show/Hide control; changing visibility preserves the value and focus and never submits the form.
The authenticated header holds Home, Changelog, Settings, and Sign out; function links live on the Dashboard. Child pages include a Back link. Ordinary and Security Settings use side navigation at desktop widths and a scrolling row at narrow widths. Selecting the Security group in ordinary Settings moves to its entry card; opening the protected page uses its separate action and administrator challenge. Each page uses a related but distinct tab icon.
Page changes use ordinary browser navigation without route animation or a page-motion setting, as requested on 2026-09-29. Window resizing freezes and then moves visible controls to the new layout. Protected pages hide before entering browser history and require a fresh server request when revisited; a completed sign-out cannot reveal a cached console page.
For a development build, the Web Changelog displays the current test-build notes from `LOG.md` above the tagged release history. The running version comes from its deployed `VERSION` stamp; translated release history remains localized, and test-build notes fall back to English when a translation is unavailable.

The shared SQLite-lock concern is a [known unresolved measurement question][local-link-002]. Historical completed work and verification records are in [HISTORY][local-link-003].

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

Web, the unified proxy, and optional Tailscale each run as separate services; AnyTLS is an inbound protocol of the unified proxy. Web also spawns a transient iperf3 child. The console and public page use separate listeners within one Python process and share in-memory state. Only configured client traffic reaches these services.

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

                       ┌─── vps-server-proxy.service ────────┐
  proxy client ──────► │  one sing-box process, five protocols  │
  :<node port>        │  AnyTLS is an inbound protocol          │
                       └────────────────────────────────────────┘
```

The proxy module has one sing-box configuration and one service. The shared `vps-server-node-meter.service` manages node accounting. The old AnyTLS service is retired only after a backed-up upgrade migration succeeds.

### Feature modules

`src/web/app.py` owns process configuration, authentication boundaries,
listener setup, and compatibility names used by existing callers. The
`ConsoleHandler` composes feature mixins from `src/web/features/`; each mixin
contains the routes, page HTML, and actions for its feature. Service functions
in the same modules take a `context` argument. The entry point passes its
module as that context, so existing test overrides and public Python imports
continue to work. A consuming project can provide a different context with
the settings, service functions, and standard-library facilities referenced
by the selected feature. Handler mixins also expect the host handler's HTTP
helpers (send_html, redirect, read_body, and render_page) as applicable.
The feature modules do not import this application's entry point.

| Feature | Backend module | Frontend source |
| --- | --- | --- |
| Login and access | `features/auth.py` | `src/web/static/password-fields.js`, `src/web/static/styles/login.css` |
| Settings | `features/settings.py` | `src/web/static/access-settings.js`, `src/web/static/settings-sections.js`, `src/web/static/styles/settings.css` |
| Home and module control | `features/modules.py` | `src/web/static/module-controls.js`, `src/web/static/module-status.js`, `src/web/static/styles/dashboard.css`, `src/web/static/styles/modules.css` |
| Browser speed test | `features/speedtest.py` | `src/web/static/speedtest-ui.js`, `src/web/static/styles/speedtest.css` |
| iperf3 window and outbound test | `features/iperf.py`, `features/iperf_client.py` | `src/web/static/iperf-countdown.js`, `src/web/static/styles/iperf.css` |
| FRPS and FRPC | `features/frp.py` | `src/web/static/frp-editor.js`, `src/web/static/styles/frp.css` |
| Proxy nodes and AnyTLS | `features/proxy.py`, `features/proxy_service.py` | `src/web/static/node-controls.js`, `src/web/static/private-values.js`, `src/web/static/styles/proxy.css`, `src/web/static/styles/nodes.css` |
| Port forwarding | `features/portfwd.py` | Shared form styles in `src/web/static/styles/forms.css` |
| Recent visitors | `features/visitors.py` | `src/web/static/visitors.js`, `src/web/static/styles/visitors.css` |
| Changelog | `features/changelog.py` | `src/web/static/styles/changelog.css` |
| Lucky status | `features/lucky.py` | Shared card styles |
| Tailscale status, settings, and devices | `features/tailscale.py`, `tailscale_control.py` | `src/web/static/styles/modules.css`, shared private-value controls |
| Public reachability page | `features/public.py` | `src/web/static/styles/public.css`, embedded into the response |

`features/system.py` contains shared host command and firewall helpers;
`features/ui.py` contains shared rendering helpers. The existing node
controllers and FRP/module helpers remain separate under `src/web/` and can
be reused without the HTTP handler. JavaScript files attach to their own
page elements; shared scripts handle theme, copying, password visibility, and
selection controls. Ordered CSS source files under `src/web/static/styles/` build
`src/web/static/style.css` with `python3 tools/build_styles/build_styles.py`. The build preserves
the former rule order and does not add a runtime CSS dependency. The Web
installer keeps the Python package, `features/`, and `static/` under
`$PREFIX/src/web/`. The root `$PREFIX/app.py` compatibility entry point calls
the package's `main()`. In the v6 candidate, persistent data lives in the separate state
root; older flat code files are not the current runtime entry point. Reusing a
feature in another project requires its context adapter and
the shared styles or scripts it references; the routes are not a standalone
package with an independent authentication policy.


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
client-supplied forwarding header, and is disabled when VPSSRV_TRUST_PROXY=1
because that mode has no configured trusted-proxy boundary. IP admission opens
ordinary console pages after the visitor chooses IP access on the login page.
The resulting session is bound to the connection peer and the allowlist is
rechecked on every request. Security Settings requires administrator-password
verification recorded for the session and expires after ten minutes. An IP-only
session completes that challenge and receives a new password-authenticated
session; changing the password invalidates all existing sessions. The session
store is persisted in a private file so restarting the Web service for
listener or iperf3 changes does not require another login. Expired sessions
are discarded on load and password changes clear the store. The ordinary
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

The `v6.0.0` candidate establishes persistent state layout `1`. Program files remain at
`$PREFIX`; the default state root is `/var/lib/vps-server`. It holds the
password, console port, certificates, runtime data, installation record, and
`.env`. `/etc/vps-server/state-dir` records the location of the state root.
Root manages that directory with mode `0700`. Later installers **MUST**
continue to read layout `1` and preserve its state when replacing program
files.

The installer identifies a supported installation using `.layout-version`,
`install-state`, and `paths.json` in the state root. If those files are
missing or inconsistent, or a critical password, session key, or port file
is missing, it refuses the upgrade before changing services. Installations
using the layout from v5.1.0 or earlier are not migrated automatically. The
operator has to back up old data and explicitly perform a fresh install; deleted
data without a backup cannot be recovered. A normal upgrade runs the installer
from a separate source directory. You **MUST NOT** delete `$PREFIX` as a way to preserve
data. If only the code directory is replaced, the retained state root can
still be read by later versions using the same layout.

In-app settings and module management use the state root. Entries that read
old paths such as `$PREFIX/data` directly have been changed to use unified
state paths. Proxy configuration and node inventory live under
`/etc/vps-server-proxy/` and `/etc/vps-server-nodes/`; the former
`/etc/vps-server-anytls/` is an upgrade-migration input only. Tailscale device
identity is under the state root at `tailscale/`, while FRP configuration
remains under `/etc/frp/`. `PORTS.md` is in the installation directory's parent.
Custom persistent paths are recorded in `paths.json`; a later installer
rejects an unannounced path change for the operator to resolve manually.

### Complete uninstall

Before removing `$PREFIX`, `deploy/uninstall.sh` calls
`src/web/uninstall_cleanup.py`. It handles FRPC when the global unit matches
this project's template, a project binary ownership marker exists, or a
complete uninstall finds named instances the console can recognize. It stops
instances first, then removes applicable templates and binaries that match
the pinned SHA-256. A complete uninstall removes `frpc-*.toml`, corresponding
Unicode aliases, and `.deleted-frpc-*.toml` recovery copies; `KEEP_DATA=1`
retains them. The uninstaller locks the sibling `.ports.lock`, validates
`PORTS.md` with the `console_port.py` format, and atomically releases
entries named `vps-server` while retaining other projects' entries. Recognizable
instances and their `frpc-*.toml` files are included even when an old FRPC template differs from the
current project template. Without recognizable instances or confirmed
ownership, global FRPC files and registrations remain. A binary checksum
failure stops cleanup.

`KEEP_DATA=1` retains `$PREFIX` and `$VPSSRV_STATE_DIR`. After cleaning up
services and ports, a default complete uninstall removes only a state root
marked with layout `1`. Paths customized outside that root are not removed
automatically, to avoid deleting another application's data.

### Unified proxy module

<a id="vps-proxy-module"></a>

`/proxy` shows AnyTLS, VMess, VLESS, Trojan, and Shadowsocks nodes; `/anytls`
redirects old bookmarks to the same page. The five protocols share
`/etc/vps-server-proxy/config.json`, `vps-server-proxy.service`,
`/usr/local/bin/sing-box-vps-server`, and the install and uninstall entry
points. A stable ID connects each managed node to its configuration, traffic
policy, and Clash share. New TLS nodes each receive a self-signed certificate;
Shadowsocks needs none.

`proxy_migration.py` checks and merges `/etc/vps-server-anytls/config.json`
from an old installation. It first archives the old configuration, node
inventory, accounting state, and service files. It then switches while keeping
node IDs, ports, credentials, and certificates. The old unit is retired only
after the new configuration passes sing-box validation and service state is
restored. A fully successful install removes the old configuration directory.
Failure restores the old service and files, leaving the archive under the
state root's `data/` directory.

Node creation, editing, enabling, disabling, deletion, and reset update the
configuration, inventory, firewall, accounting, and `PORTS.md` under the
`node_control.py` lock. Public ports are checked against listeners and the
registry before an operation; a failure withdraws a new registration. Disabling
or deleting a node releases only this project's registrations. Traffic caps
count (upload + download) × 2, so the kernel quota uses half that cap as its
raw accounting threshold. Accounting gaps do not cause early throttling.
Monthly cycles reset at 00:00 UTC on the first day of each month; daily and
yearly cycles retain their prior rules.

The node page masks interface addresses, ports, and credentials by default;
authenticated private-value endpoints handle Show and Copy requests. If the
managed inventory is missing or inconsistent with configuration, the page
requests migration or repair instead of using the old editor. See
[HISTORY](HISTORY.md#retired-anytls-console) for the former independent-module
design and its retirement.

### Tailscale module

The offline package contains the official Linux amd64 static archive. The
installer checks its digest, creates `vps-server-tailscale.service` and a
private state directory, and registers the fixed UDP port in `PORTS.md` before
starting the service. The Tailscale console uses a local socket and fixed CLI
arguments to read status, preferences, connectivity, devices, and the systemd
journal. Private addresses and account names are masked by default. An auth
key is passed to the CLI only through a temporary root-owned file and deleted
after the command; it is not stored in project state. Ordinary settings use
Linux `tailscale set`; they do not simulate OpenWrt dnsmasq forwarding or
router-firewall options. Binary installation can be offline, but joining a
Tailnet requires access to the selected control server.

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

The console can also initiate an iperf3 client test toward an operator-entered
IP address. The operator starts iperf3 server mode on the target; this console does
not control the remote service. The client helper accepts only IP literals,
validates the port, protocol, direction, duration (at most 30 seconds), and
rate limit (at most 1,000 Mbit/s), then runs iperf3 with a fixed argument
list and a process timeout. A lock permits only one outbound test at a time.
The reverse option makes the target send traffic to this host. The page reports the
JSON summary, including UDP jitter and loss or TCP retransmits when iperf3
provides them. The result is held in memory for the redirect back to the
page, available once to the same session for up to two minutes, and is never
written to disk.
The existing inbound test window remains independent.

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

- **MUST NOT** put console routes in `ProbeHandler`; authentication is not a substitute for the separate public route table.
- Keep iperf3 time-boxed and remove the firewall rule on close or shutdown.
- Reapply persisted forwards from JSON at process start; withdraw runtime rules at a clean stop without resetting the host-wide `ip_forward` toggle.
- Preserve node credentials and selected settings on upgrade; use the owning setup scripts for rotation, outside the web unit's filesystem sandbox.
- From v6.0.0 onward, later versions **MUST** keep persistent state layout `1` readable and **MUST NOT** move the default persistent state back into `$PREFIX`. The installer **MUST NOT** automatically migrate layouts from v5.1.0 or earlier and **MUST** refuse an old service or missing critical state before changing services. The operator **MUST** transfer changed custom state paths manually; the installer **MUST NOT** silently reset them.
- Do not decouple the shared `_db_lock` without evidence of harmful latency: the historical 60-flooder measurement did not reproduce a slowdown. See [Bugs][local-link-008].

## External Interfaces

- HTTP/HTTPS: public listeners on 80/443 expose only the reachability page; the operator console uses a separate persisted port. iperf3 listens only within an authenticated time-boxed window.
- The console reads `/proc/net/tcp[6]` to log inbound TCP connections; it does not export proxy secrets on public routes.
- `install.sh` uses bundled binaries and a private nftables runtime; it does not call a package mirror or look up a public IP on the target. `setup-proxy.sh` manages the unified sing-box unit and certificates. Where present, iptables manages temporary iperf3 exposure and enabled forwards; systemd supervises services and runs restricted node-operation helpers outside the Web sandbox.

## Tech stack

| Layer | Choice | Version | Why |
|---|---|---|---|
| Runtime | Python, standard library only | 3.9+ | Inherited from `vps-webserver`: no third-party Python packages; the distro-managed interpreter and libraries still require security updates |
| HTTP server | `http.server.ThreadingHTTPServer` | stdlib | Three listeners of a few requests each; a framework would be dead weight |
| TLS | Python `ssl` + self-signed certificates generated by bundled sing-box | stdlib / sing-box | No domain, no ACME (see non-goals) |
| Store | `sqlite3` | stdlib | Visitor log **MUST** survive restarts |
| Speedtest engine | LibreSpeed, vendored unmodified | v6.2.1 | LGPL-3.0; already vendored and working in `vps-webserver` |
| QR code rendering | kazuhikoarase/qrcode-generator, vendored unmodified | js2.0.4 | MIT; small, no build step, plain `<script>` tag like LibreSpeed |
| Bandwidth probe | bundled x86-64 Linux `iperf3` | 3.22 | The de-facto tool testers already have on the client side |
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
- Architecture: the entire project supports x86-64 Linux only. Bundled FRPC,
  FRPS, iperf3, sing-box, Lucky, Tailscale, and nftables executables target this platform.
- Hardware: no GPU; allow at least 1 GiB of disk for the complete offline package, extracted source, and installed program together; any
  amount of RAM a VPS normally has
- Vendored artifact integrity check: from the repository root, run
  `python3 tools/verify_dependencies/verify_dependencies.py`. This compares the nine tracked third-party
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
| `iperf3` | static artifact distributed with this repository | `$PREFIX/vendor/iperf3/iperf3` |
| `frpc`,`frps` | distributed with this repository | `third_party/frp/`, copied during module installation |
| nftables and runtime libraries | Official Debian 11 packages included in the offline package | `$PREFIX/vendor/nft/`, without writing to the system package database |
| Tailscale client | Official Linux static archive included when building the offline package | `/usr/local/bin/tailscale-vps-server` and `tailscaled-vps-server` |
| Bash, systemd, Python, tar, coreutils | Base environment of a supported OS | system path |
| sing-box binary | ships in this repository | `/usr/local/bin/sing-box-vps-server` |
| LibreSpeed engine and qrcode-generator library | ship in this repository | `$PREFIX/src/web/static/` |
| TLS certificates | generated on first run by the installer | `$VPSSRV_CERT_DIR` |

FRPC, FRPS, and iperf3 install from this repository without downloads. The
installer installs other missing system packages
from the target Debian/Ubuntu package repositories without selecting exact
versions or repository snapshots. Python, OpenSSL, shell/system tools and
systemd are also provided by the target OS. The host operator relies on the
chosen distro's security-maintained package channels for updates. Package
versions, hashes and transitive resolution
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
| `$PREFIX` | installer, default `~/apps/vps-server` for the root account | Replaceable program code, static assets, and bundled artifacts |
| `$VPSSRV_STATE_DIR` | installer, default `/var/lib/vps-server` | Layout marker, installation record, path inventory, password, port, certificates, and runtime data |
| `$VPSSRV_DATA_DIR` | installer, default `$VPSSRV_STATE_DIR/data` | `visitors.db`, `session_secret.txt`, `portfwd.json`, `login-access.json` |
| `$VPSSRV_CERT_DIR` | installer, default `$VPSSRV_STATE_DIR/certs` | Web self-signed certificate and key |
| `/etc/vps-server/state-dir` | installer | Records the state root location for separate helpers |
| `/etc/vps-server-proxy/` | installer | sing-box `config.json` (multiple inbounds) and its initial self-signed cert; new node certs live under `/etc/vps-server-nodes/certs/` |
| `$VPSSRV_STATE_DIR/tailscale/` | Tailscale daemon | Device identity and local connection state |

### Configuration reference

<a id="vps-configuration-reference"></a>

All variables use the `VPSSRV_` prefix. This is not cosmetic: `vps-webserver`
owns `VPSWS_` and `Anytsl-Serve` owns `ANYTLS_`, and all three may be installed
on one host, where a shared prefix would let one project's `.env` silently
reconfigure another.

| Variable | Meaning | Default | Required |
|---|---|---|---|
| `PREFIX` | Program installation root, set in install/uninstall commands and not read from `.env` | root home `apps/vps-server` | no |
| `VPSSRV_STATE_DIR` | Persistent state root, set in the command environment before first install; `.env` cannot move it | `/var/lib/vps-server` | no |
| `VPSSRV_DATA_DIR` | SQLite, session key, and feature state | `$VPSSRV_STATE_DIR/data` | no |
| `VPSSRV_HOST` | Bind address for all listeners | `0.0.0.0` | no |
| `VPSSRV_PUBLIC_HTTP_PORT` | Public reachability page, plaintext | `80` | no |
| `VPSSRV_PUBLIC_HTTPS_PORT` | Public reachability page, TLS | `443` | no |
| `VPSSRV_PUBLIC_ENABLE` | Serve the public page on first install | `0` | no |
| `VPSSRV_CONSOLE_PORT` | Console port; `0` = generate once and persist | `0` | no |
| `VPSSRV_CONSOLE_PORT_FILE` | Where the generated console port is remembered | `$VPSSRV_STATE_DIR/console_port.txt` | no |
| `VPSSRV_CONSOLE_TLS` | Serve the console over HTTPS | `0` | no |
| `VPSSRV_AUTH` | Require login on the console | `1` | no |
| `VPSSRV_PASSWORD_FILE` | Plaintext console password; Settings verifies the current password before changing it | `$VPSSRV_STATE_DIR/admin_password.txt` | no |
| `VPSSRV_IP_ALLOWLIST_FILE` | Optional path for the private-IP allowlist | `$VPSSRV_DATA_DIR/login-access.json` | no |
| `VPSSRV_CERT_DIR` | Self-signed cert location | `$VPSSRV_STATE_DIR/certs` | no |
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
| `VPSSRV_DEFAULT_LANG` | `en` / `zh_cn` / `es` | `en` | no |
| `PROXY_PROTOCOLS`, `PROXY_SNI` | Initial protocols and TLS name for the unified proxy, including AnyTLS | see `.env.example` | no |
| `VPSSRV_PROXY_CONFIG` | Where the console reads the installed node set from | `/etc/vps-server-proxy/config.json` | no |
| `VPSSRV_PROXY_SERVICE` | Unit the console checks for node liveness | `vps-server-proxy.service` | no |

Old `ANYTLS_*` and `VPSSRV_ANYTLS_*` values are read only for upgrade migration;
new configurations no longer create an independent AnyTLS service.

## Setup from scratch

1. `git clone <repo>` and `cd` into it. Verify that `ls -lh third_party/sing-box/sing-box` shows a file of about 57 MB.
2. Run `bash deploy/install.sh`. A fresh run installs the Web console and prints its address and password. Select other server modules with `VPSSRV_MODULES` or later in Settings → Modules.
3. Run `systemctl status vps-server-web` and verify `active (running)`.
4. Enable public HTTP on Home, then open `http://<ip>/` from another machine. Verify that the reachability page shows that machine's source IP.
5. Enable public HTTPS on Home, then open `https://<ip>/` from another machine and accept the certificate warning. Verify that the page shows HTTPS as its protocol.
6. Open `http://<ip>:<console port>/` and sign in. Verify that the dashboard loads and shows the iperf3 window closed.
7. Open a five-minute iperf3 window in the console and run `iperf3 -c <ip> -p 5201 --json` from another machine. Verify throughput and `mean_rtt` in the result.
8. If the proxy module was installed, run `systemctl status vps-server-proxy` and verify the unified service runs. After creating an AnyTLS node in the console, check its port and configuration.

## Data Design

The signed-in Settings page lists installed runtime modules. A serialized
root helper installs and removes optional modules. `data/module-job.json`
stores job status, `data/module-job.log` stores current output, and
`data/module-history.log` appends operation history. The Modules page shows
installation/removal progress briefly only on the page that started the job;
it collapses 30 seconds after the last output, and a completion notice does
not reappear after reload or return. The separate `/settings/logs` page reads
module history and journals for Web, node metering, Singbox, FRPS, FRPC, Lucky,
and Tailscale. Service-log scope depends on the host journal settings.

Home feature switches are independent of module installation state. Host ports
used by public Web listeners, proxy nodes, Tailscale, FRPS, FRPC, and port
forwarding are registered in `PORTS.md` beside the installation directory.
Runtime switches and node operations share `.ports.lock` and atomic writes;
failures roll back new registrations, and stopping or deleting releases only
this project's entries. The FRPC group switch records running instances before
stopping them and restores only those instances when re-enabled. The Proxy
nodes group controls only the unified sing-box service. Home links to FRPS at
`/frps`, the FRPC list at `/frpc`, and Tailscale at `/tailscale`; the old `/frp`
bookmark redirects to the FRPC list.

The visitor database, `portfwd.json`, and `login-access.json` persist under
`$VPSSRV_DATA_DIR`. Recent Visitors can clear the visitor database through
an authenticated session and CSRF check; the clear request itself is not
written back, while later visits and devices still connected are recorded
again. The console password, selected port, Web certificate, and
`install-state` are under `$VPSSRV_STATE_DIR`; the program directory can be
replaced independently. Sing-box configuration and certificates live under
`/etc/vps-server-proxy/`. See [Paths and mounts][local-link-012]. The iperf3
deadline is in memory only and does not survive restart.

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
    │   ├── proxy/setup-proxy.sh
    │   ├── frps/setup-frps.sh
    │   ├── lucky/setup-lucky.sh
    │   └── tailscale/setup-tailscale.sh
    ├── src/web/static/        # first-party UI assets and vendored browser libraries
    │   └── third_party/
    │       ├── librespeed/    # speedtest.js, speedtest_worker.js
    │       └── qrcode/        # qrcode.js, qrcode-utf8.js
    ├── lang/                  # interface catalogs for web, installers, and tools
    ├── third_party/sing-box/
    │   ├── sing-box           # vendored amd64 binary
    │   ├── sing-box.version   # binary version metadata
    │   └── LICENSE            # original upstream notice
    ├── third_party/tailscale/  # pinned static-client metadata and license
    ├── third_party/nft/        # pinned Debian runtime metadata
    ├── tools/build_offline/    # checked offline asset and archive builder
    ├── tools/verify_dependencies/verify_dependencies.py # checks config/dependencies.lock.json from repo root
    ├── config/dependencies.lock.json
    ├── config/upstream-version # records: vps-webserver v0.4.1
    ├── LICENSE                # GPL-3.0
    └── doc/
        ├── DESIGN.md          # architecture, constraints, and tracked goals
        ├── LOG.md             # current status, bugs, decisions, and handoff
        ├── HISTORY.md         # historical work and prior handoffs
        ├── CHANGELOG.md       # formal version changes
        ├── THIRD_PARTY_NOTICES.md
        ├── en/               # English translation
        └── es/               # Spanish translation
```

These are checkout paths. Installation places Web code and browser assets at
`$PREFIX/src/web/` and the proxy executable at `$PREFIX/sing-box`. The
compatibility entry point `$PREFIX/app.py` remains systemd's `ExecStart`,
but only calls `src.web.app.main()`. HTTP asset URLs do not change. The
checkout's installer and uninstaller are `deploy/install.sh` and
`deploy/uninstall.sh`. In the v6 candidate the persistent state root is separate from
the installation directory; earlier in-directory data is not migrated
automatically.

Only `repo/` is tracked by Git; `snapshots/` is separate and private. Start at
[README][local-link-013], use [HISTORY][local-link-014] for historical verification and
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
- **Service names are isolated from upstream.** The unified proxy unit is
  `vps-server-proxy.service`; the Tailscale unit is
  `vps-server-tailscale.service`, leaving any existing standard Tailscale unit
  untouched.
- **The complete offline package supports only x86-64 Linux.** Its sing-box,
  Tailscale, and nftables artifacts are amd64. The installer rejects other
  architectures before changing state. Cross-distribution operation still
  needs target-host acceptance.
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
  installer and module script loaders, then add a matching
  `doc/<BCP47>/` tree.
- **A new colour**: add a token to `:root` in `src/web/static/style.css` *and* a
  light-mode value in the `prefers-color-scheme: light` block, then use the
  token. Never write a hex into a component rule — a literal cannot follow the
  theme, so it is correct in whichever mode it was eyeballed in and wrong in
  the other, with nothing to report it. Anything used as a filled background
  needs a paired `--on-*` foreground: the value that reads well as text is
  rarely the value that reads well behind white text. Check both modes against
  WCAG AA (4.5:1) before committing; the old style test covered only part of
  the structure and could not judge a ratio.
- **Refreshing a vendored upstream**: re-copy from the upstream tag, update the
  matching `.upstream-version` file in the same commit, and note the bump in
  [CHANGELOG.md][local-link-016]. Never hand-edit vendored code in place — a local edit that is
  not reflected upstream makes the next refresh a silent regression.

[local-link-001]: ../LOG.md#交接
[local-link-002]: LOG.md#bugs
[local-link-003]: HISTORY.md#completed-work-history-historical
[local-link-004]: LOG.md#decisions
[local-link-005]: #vps-proxy-module
[local-link-006]: LOG.md#decisions
[local-link-007]: LOG.md#decisions
[local-link-008]: LOG.md#bugs
[local-link-009]: LOG.md#decisions
[local-link-010]: ../../config/dependencies.lock.json
[local-link-011]: THIRD_PARTY_NOTICES.md
[local-link-012]: #paths--mounts
[local-link-013]: ../../README.md
[local-link-014]: HISTORY.md
[local-link-015]: THIRD_PARTY_NOTICES.md
[local-link-016]: CHANGELOG.md
