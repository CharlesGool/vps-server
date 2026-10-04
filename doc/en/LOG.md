---
name: project-log-en
description: Current project status, decisions, and handoff
metadata:
  version: "1.0.0"
  lang: "en"
---

# Log

## Multi-language

[简体中文](../LOG.md) | **English** | [Español](../es/LOG.md)

## Documentation

- Project overview: [README](README.md)

- Design rationale: [DESIGN](DESIGN.md)

- Project status: [LOG](LOG.md)
- Historical records: [HISTORY](HISTORY.md)
- Version changelog: [CHANGELOG](CHANGELOG.md)

- Third-party notices: [THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES.md)


## Records

- [Historical records](HISTORY.md)
- [Version changelog](CHANGELOG.md)

## Bugs

- [x] 2026-10-04 [P1] FRPS editing always returned "FRP update failed": the operator's target-host `PORTS.md` had a Web entry but no entry for the current FRPS port. The old helper required that entry before invoking the setup script, so both token-only and port edits were rejected. Source now registers the configured FRPS port under the registry lock, preserves checks against other services' entries, and removes a new reservation on failure. Isolated checks passed, and the operator subsequently reported passing a manual test. This session did not independently verify the host over SSH. The intended formal fix version is `v5.1.1`; it is not yet published.

- [ ] 2026-10-04 [P1] Deleting the old installation directory loses the console port and some state: the operator confirmed deleting the old `$PREFIX` before placing source there, with no directory backup. The old console port is no longer reachable; the old password has not been tested. The old layout stored the administrator password, random port, certificates, and `data/` inside `$PREFIX`. The installer still recognizes the residual systemd unit as an existing installation and may then regenerate missing state. Source cannot recover deleted data without a backup. The proposed v5.1.1 layout moves state outside the installation directory and refuses an installation with missing state before changing services. A fresh installation and later reinstall on the target host remain unverified.

- [x] 2026-10-04 Complete uninstall missed FRPC instance data and `PORTS.md` entries: `3335a7f` first added cleanup, but the operator reproduced an old template without an ownership marker being classified `unowned`. FRPC configuration and registrations remained, and a Web-only reinstall listed the old client. Source change `01b76ba` includes console-recognizable instances with old templates in a default complete uninstall. Isolated local checks passed; the operator confirmed cleanup on the test host after rerunning it. Fixed in `v5.1.0`; this session did not independently connect to the host.

- [x] 2026-10-04 [P1] A non-ASCII administrator password could be saved but could not log in: `src/web/features/auth.py` accepted Chinese in `change_admin_password`, while old login and Security verification called `hmac.compare_digest` with strings. Isolated checks reproduced a TypeError. Source now compares UTF-8 bytes while preserving password validation and session invalidation. The operator confirmed login; fixed in `v5.1.0`.
- [x] 2026-10-04 [P1] A cycle reset did not refresh kernel quota: the old `src/web/node_meter.py` policy fingerprint omitted cycle identity. Isolated checks cleared usage from 600 against a 1000-byte quota without changing the fingerprint. Source now rebuilds on a cycle change. The operator confirmed node and traffic behavior; fixed in `v5.1.0`.
- [ ] 2026-10-04 [P1] Python 3.9 compatibility has not been tested: the old `src/web/node_inventory.py` used `int | None` without postponed annotations, conflicting with the README's 3.9+ claim. Source now postpones annotation evaluation. Python 3.9 is unavailable locally; only syntax and import on a newer Python were checked. Installation and Web startup still need verification on a Python 3.9 target.
- [x] 2026-10-04 [P2] A port-forward application failure was reported as success: old add/set_enabled/load paths ignored a False result from `portfwd_rule_apply`. Injected failure returned success while retaining enabled=true. Source now rolls back or reports that application failed. The operator confirmed port forwarding; fixed in `v5.1.0`.
- [x] 2026-10-04 [P2] Diagnostic exceptions were discarded: the old `_dispatch` returned a generic 500 without a stack log, and node helper errors were discarded. Source now logs sanitized operation stages and error types while keeping generic client errors. Isolated local checks passed; fixed in `v5.1.0`. Real failure cases remain unverified.

- [ ] 2026-09-12 Decide whether the shared `_db_lock` needs decoupling: every public-page hit takes a process-wide lock and does a synchronous SQLite write, and the console shares that lock, so in principle anonymous flooding can slow an authenticated page. **Measured and not reproduced**: 60 concurrent flooders left console latency at 0.4–0.6 ms, identical to idle. Keep this record so the mechanism is not rediscovered as new; do not rearchitect without a measurement showing harm.

Still to verify are installation and reinstallation of the new state layout on the target host, Python 3.9 installation and Web startup, and the `_db_lock` performance concern without demonstrated harm. Earlier branch status is in [Historical records](HISTORY.md).

## Limitations

- Automated checks cover interface key names, placeholders, and document structure, but the new translations have not had independent native-language review.
- Before migration, Simplified Chinese source and older translations of four core documents lived in different paths; no complete single synchronization baseline can be recovered. This release resynchronizes English and Spanish against current Simplified Chinese. The next update can use this synchronization commit as its incremental baseline. Other older translations and English-only test records remain in Git history; the boundary is in [HISTORY](HISTORY.md).
- During standardization on 2026-10-03, ignored runtime state and caches at the source checkout root were moved intact to `private/local-runtime-prestandardization-20261003/`. The current worktree passed the structure check. On a CIFS worktree mounted with fixed 0644 file and 0755 directory modes, `chmod` does not change displayed local secret modes; assess mount access controls separately.
- The new bundled iperf3 3.22 was built locally from upstream source. It was checked as a static ELF on Ubuntu 22.04 x86-64 and ran `--version`. Address resolution and real TCP/UDP traffic on Debian 11 and Ubuntu 20.04 targets have not been accepted. The build omits SCTP and OpenSSL authentication.
- FRPC, FRPS, and iperf3 install offline from a complete source checkout. Other modules may still need the distro package repository when foundational system packages such as Python, OpenSSL, or nftables are missing.
- `third_party/frp/frpc` is 16,593,080 bytes, blob `e2a8dc5b1bd2d995ec49896d20e1b2a4a8252ada`. It was already public at `origin/main` commit `f306f6e` before this task and was not changed here. It remains to preserve the accepted offline installation from a complete checkout. Future new or modified large files still require the GitHub Release asset process.
- The real-host acceptance limits for the current branch are in the Simplified Chinese handoff below.

## Decisions

<a id="vps-decisions"></a>

The dated decisions below preserve both rejected alternatives and their costs. A historical decision is not a new legal or release approval.

| Decisions | Reasons, rejected alternatives, and costs |
| --- | --- |
| 2026-10-04 — Establish persistent state layout `1` in v5.1.1 | New installations store the password, port, certificates, runtime data, installation record, and `.env` under `/var/lib/vps-server`; later versions retain readability of this layout. The installer rejects an old layout or missing critical state before changing services, without generating replacement values. **Rejected:** Automatic migration from v5.1.0 and earlier directories; the user asked for backward compatibility starting with the new standard, not for earlier layouts. **Cost:** Older installations need an operator backup and an explicit fresh install. Deleted old data without a backup cannot be recovered. |
| 2026-10-03 — Remove `tests/` from this project and accept features manually | The operator explicitly requested removal of the automated test directory during source review and simplification; `tests/` was removed from source and the test-host install. The cost is losing those regression checks after changes. Structure, syntax, and build checks still run, followed by manual acceptance of enabled modules. Old tests remain in Git history. |
| 2026-09-22 — `proxy` is one sing-box process with up to four inbounds, not four clones of anytls | - **Resolved, not rejected:** whether the vendored sing-box binary covers   vmess/vless/trojan/shadowsocks — confirmed by actually running all four   simultaneously in one process (not just `sing-box check`); no second   backend needed. hysteria2/tuic tried and left out (different field/TLS   requirements). - **Rejected:** one systemd unit + config per protocol, mirroring anytls's   own shape exactly — four units to monitor, three redundant self-signed   certs, and it fights the shape a future per-node traffic-accounting   feature would want (one process whose `inbounds` list is already the node   list). - **Cost:** the shared vendored binary is now used by two independent   modules; each module's `uninstall()` **MUST** check the other's config exists   before deleting it (anytls's vendored script gained this as a documented   local deviation — see `anytls/.upstream-version`). |
| 2026-09-21 — `prompt_new_settings()` ends with an explicit `return 0`, not just falling off the loop | - **Rejected:** letting the function's exit status fall out of its final `for`   loop, as most other functions in `install.sh` do — the loop's last   statement used to be a bare `[ -n "$value" ] && export ...`, so leaving the   *last* prompted setting at its default made that test false, which became   the function's own return status. Called bare (`prompt_new_settings` inside   an `if`-body, not itself exempt from `set -e`) that silently killed the   whole installer right after the last prompt — no error, no file copy, no   `VERSION` stamp, no service restart. Reproduced live on v1.0.4 → v1.1.1 and   fixed by wrapping the export in `if`/`fi` and adding an explicit trailing   `return 0`, so the function's exit status no longer depends on which   setting happened to be prompted last. - **Do not remove the trailing `return 0` as apparent dead code.** It is the   fix, not boilerplate. |
| 2026-09-19 — Port forwards are iptables DNAT, reapplied from JSON at every start; nothing written outside the process | - **Rejected:** a per-rule `socat` userspace relay — safer (no NAT table or   `ip_forward` changes), but the user explicitly chose kernel-level   DNAT+MASQUERADE for this project instead. - **Rejected:** `iptables-persistent` to survive a reboot at the kernel level   — that makes the console and a system package two sources of truth for the   same rules. `app.py` reapplies from its own JSON on every start instead   (DESIGN.md, "Port forwarding lifecycle"), so there is exactly one. - **Rejected:** auto-reverting `net.ipv4.ip_forward` to `0` once the last   forward is removed — it is host-wide, and other software (this project's   own test host runs Docker) may depend on it staying on. - **Cost:** stopping `vps-server-web` (not restarting it) withdraws every   forward's kernel state, even enabled ones — same fail-safe direction as the   iperf3 window. Do not move the rules into a separate always-on unit to   "fix" this; that was considered and rejected above. |
| 2026-09-12 — The public page and the console are separate listeners with separate handler classes | - **Rejected:** One listener serving both, with console routes gated behind a path prefix plus an auth check — an auth check can be bugged into allowing; a route that does not exist cannot. - **Rejected:** Putting the console itself on 80/443 behind the password and dropping the random port — that discards the obscurity layer `vps-webserver` deliberately chose. - **Cost:** Three listeners in one process, and two handler classes that each need the visitor-logging hook wired in separately. - **Do not re-add this as an improvement.** |
| 2026-09-12 — iperf3 runs only inside an operator-opened, time-boxed window | - **Rejected:** An always-on public `iperf3 -s` — any stranger can saturate the uplink indefinitely and nothing surfaces that it is happening. - **Rejected:** Always-on with `--authorized-users-path` RSA authentication — credentials would have to be handed over out of band before anyone can test, which defeats the point of "give someone the IP and let them measure". - **Cost:** A remote tester cannot test unattended; someone has to open a window first. The public page advertises an open window so the tester knows when to connect. |
| 2026-09-12 — Port 443 uses a self-signed certificate; no ACME, no domain | - **Rejected:** certbot / acme.sh against a real domain — the page exists to answer "can you reach this IP", and a browser warning page already proves reachability. A domain dependency and a renewal timer buy nothing for that question. - **Rejected:** Serving only port 80 — that cannot distinguish "the host is unreachable" from "443 specifically is blocked", which is the common case worth detecting. - **Cost:** Every HTTPS visit shows a certificate warning. Expected; do not "fix" it with HSTS or a pinned exception. |
| 2026-09-12 — The sing-box binary ships in the repository, so the whole project is GPL-3.0 | - **Rejected:** Downloading sing-box at install time to keep the repo small and the licence Apache-2.0 — `Anytsl-Serve` already rejected exactly this to keep installation working without GitHub access; re-deciding it here would silently undo that goal. - **Rejected:** Dropping the anytls module to preserve `vps-webserver`'s Apache-2.0 — the brief was to combine the two projects, not to pick one. - **Cost:** ~57 MB in git, growing with every sing-box bump; and `vps-webserver`'s Apache-2.0 code is redistributed here under GPL-3.0. |
| 2026-09-12 — Upstream projects are vendored, not superseded and not submoduled | - **Rejected:** Letting vps-server replace `vps-webserver` and `Anytsl-Serve` and archiving both — all three are to stay independently maintained and independently released. - **Rejected:** git submodules pointing at the two upstream repos — a submodule cannot carry the renames this project needs (unit names, binary name, `VPSWS_` → `VPSSRV_`), and a clone would then need network access to two more repos. - **Cost:** The same code lives in three repositories and will drift. Mitigation: `.upstream-version` files record the exact upstream tag each vendored tree came from, and **MUST** be updated in the same commit as any refresh. |

<a id="development-updates"></a>

## Development Updates

- FRPS editing registers this project's current port when its `PORTS.md` entry is missing, while continuing to reject ports owned by other services. A failed port change removes the new reservation; the operator reports that this correction passed manual testing.
- New installations store the password, console port, certificates, runtime data, and installation record under `/var/lib/vps-server`. Later versions retain layout `1`; old layouts are not migrated automatically, and the installer stops before changing services if state is missing.
- The new layout has passed only isolated local checks. Fresh installation on the target host, reinstall and uninstall after replacing the program directory, a Python 3.9 runtime, reboot recovery, and real mobile devices still need acceptance.

## Handoff

The current handoff, including completed checks, remaining release steps, blockers, and the next action, is maintained in the [Simplified Chinese LOG.md](../LOG.md#交接).
