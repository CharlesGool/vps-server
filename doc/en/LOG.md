---
name: project-log-en
description: Project bugs, limitations, decisions, and handoff
metadata:
  version: "2.0.0"
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

- [History](HISTORY.md)
- [Changelog](CHANGELOG.md)

## Bugs

- [x] Successful FRPC saves yielding empty responses, or rename showing Invalid request: fixed in v5.2.2 with a background waiting page and result retries.
- [x] Inconsistent existing-value editing, privacy controls, delete hover colors, fonts and button/filter layouts: fixed in v5.2.2 and confirmed by the operator.
- [x] Installation interrupted by FRPC disconnection during upgrade: v5.2.2 uses a systemd background installer.
- [x] Missing Tailscale archive in Git installs: fixed in v5.2.1.
- [ ] Python 3.9, other target distributions, host reboot recovery and real mobile devices still need independent acceptance.
- [ ] Authenticated Tailscale logout and real Tailnet routing policies were not verified on this test host.
- [ ] Monthly quotas and sustained real-traffic/rate-limit policies were not comprehensively retested for v5.2.2; earlier operator confirmation is not an independent rerun.
- [ ] English/Spanish documentation has not received independent native-language review.
- [x] 2026-10-21 On a vmshell Debian 13 (KVM) host the node meter restarted in a loop, logging only `cannot list nftables tables`, and Singbox was stopped because it depends on the meter. Cause: the host image had no nftables, so the meter fell back to the bundled nft 0.9.8, which cannot read Debian 13 iptables-nft rules; the runtime check only ran `nft --version`, so the install preflight let it through. Fixed in v5.4.0: the checks now read the ruleset and the bundled runtime is Debian 13 nft/iptables with its own glibc.
- [ ] 2026-10-21 The console root terminal is forked from the Web process and inherits the Web unit's `ProtectSystem=strict`, so it cannot install packages with apt or modify `/etc`. A change to run it as a separate systemd-run unit was blocked by the Claude Code permission check and was not made; it awaits the operator's decision.

Unchecked items are acceptance gaps, not reproduced runtime failures.

## Limitations

- Deleted state without a backup cannot be recovered because the original data no longer exists.
- Local interfaces cannot reliably identify a public address behind NAT; this project does not query external public-IP services.
- The structured editor cannot losslessly reconstruct arbitrary complex FRP configuration; unsupported fields must be retained and managed natively.

## Decisions

| Date | Decision | Status | Reason |
| --- | --- | --- | --- |
| 2026-10-21 | The complete offline package bundles Debian 13 nft and iptables-nft with their own glibc, started through the bundled loader; a host nft/iptables that can read the rules is preferred. Replaces the Debian 11 runtime decided on 2026-10-04. | Accepted | The old nft 0.9.8 cannot read rules written by Debian 13 iptables-nft, and newer binaries cannot run directly on an older glibc. |
| 2026-10-13 | Fresh installs serve the console over HTTPS with a self-signed certificate; upgrades keep the previous setting. Session cookies carry `Secure` when HTTPS is on. | Accepted | A self-signed certificate does not prove server identity but keeps passwords and sessions from being read in plaintext. |
| 2026-10-13 | Use `git branch -D` on 10 unmerged old local branches (`archive/*` ×3, `feat/two-stage-setup`, `fix/frpc-unicode-name`, `refactor/feature-modules`, `refactor/feature-modules-repo`, `release/v4.0.0`, `release/v4.1.0-test.1`, `test/host-validation-wip`). Exempts rule 2 of the all-in-one Git rules `Branches and history` ("MUST NOT use `git branch -D`"), limited to these branches, once. | Accepted | The user confirmed these branches are abandoned; their tip SHAs are kept in local private notes. |
| 2026-10-07 | The top-left of the header shows only the project name, not the logo. Exempts rule 2 of the all-in-one Web UI conventions `Page frame and navigation` ("the top left MUST show the project logo and name"), limited to the shared header; the browser tab icon is unchanged. | Accepted | The user explicitly asked for it in the conversation, finding the logo display poor. |
| 2026-10-05 | Rewrite 18 documents from current templates; retain original third-party licenses. | Accepted | The user requested a full rewrite while original license notices remain distribution obligations. |
| 2026-10-05 | Use background tasks for installation and FRPC updates. | Accepted | Service restarts can interrupt the connection carrying installation or save responses. |
| 2026-10-04 | Use a separate layout-1 persistent state root. | Accepted | Replacing code must not delete credentials and settings. |
| 2026-10-04 | Automatically migrate v5.1.0 and earlier layouts. | Rejected | Legacy directories mix state and code, preventing safe assumptions about paths and ownership. |
| 2026-10-04 | Include AnyTLS in the unified Singbox service. | Accepted | This unifies node/policy management and removes duplicate control paths. |
| 2026-10-04 | Include nft runtime and corresponding sources in complete offline packages. | Accepted | Pinned service binaries alone do not supply missing libraries; a base OS remains required. |
| 2026-10-03 | Remove the automated test directory; use change-specific checks and manual acceptance. | Accepted | This follows the operator's explicit request. |
| 2026-09-19 | Use kernel DNAT and project JSON replay for forwarding. | Accepted | This avoids userspace relay overhead and ownership of the host-wide ruleset. |
| 2026-09-12 | Use GPL-3.0-only and retain component notices and the [compliance review](THIRD_PARTY_NOTICES.md#compliance-review). | Accepted | Distribution includes a GPL proxy core and the author publishes this project under that license. |
| 2026-09-21 | End prompt functions with explicit `return 0`. | Accepted | A final empty-value test can silently terminate installation under `set -e`. |
| 2026-09-12 | Separate public and console listeners/routes. | Accepted | The public handler has no management routes and the console retains a separate random port. |
| 2026-09-12 | Use timed iperf3 windows rather than a permanent server. | Accepted | This bounds unplanned continuous bandwidth consumption. |
| 2026-09-12 | Use self-signed public HTTPS without ACME. | Accepted | The page checks IP/port reachability without domain/renewal requirements. |
| 2026-09-12 | Vendor own-project copies without submodules or archiving originals. | Accepted | The three projects remain independent with imported revisions recorded in provenance files. |

## Handoff

The current handoff is maintained in the [Simplified Chinese LOG.md](../LOG.md#交接).
