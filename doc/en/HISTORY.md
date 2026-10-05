---
name: project-history-en
description: Historical Records
metadata:
  version: "2.0.0"
  lang: "en"
---

# Historical Records

## Multi-language

[简体中文](../HISTORY.md) | **English** | [Español](../es/HISTORY.md)

## Documentation

- Project overview: [README](README.md)

- Design rationale: [DESIGN](DESIGN.md)

- Project status: [LOG](LOG.md)
- Historical records: [HISTORY](HISTORY.md)
- Version changelog: [CHANGELOG](CHANGELOG.md)

- Third-party notices: [THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES.md)

## Historical Records

These dated requirement/handoff summaries retain the status at the time, not automatic acceptance of the current version. Exact changes remain in [Git history](https://github.com/CharlesGool/vps-server/commits/main/); formal feature changes are in CHANGELOG.

| Date | Historical status and decisions |
| --- | --- |
| 2026-09-12 | v1.0.0 was released. Separate public/private listeners, timed iperf3, self-signed TLS, vendored code and GPL-3.0-only were accepted; ACME and permanently open iperf3 were rejected. The three original projects continued independently. |
| 2026-09-12—2026-09-22 | Early English records marked module install/uninstall as written but never executed; later operator observations covered both public ports, login/browser tests, LAN iperf3 at 2.8 Gbit/s with expiry refusal, AnyTLS install/reset/removal and upgrade preservation. v1.1.0 forwarding received operator host checks after three-container and 119-test checks. These distinct dated states are not current comprehensive acceptance. |
| 2026-09-19—2026-09-21 | v1.1.0 added kernel forwarding; v1.1.1 fixed documentation tags and v1.1.2 fixed false prompt-function returns under `set -e`. Uninstall does not reset host-wide forwarding, preserving other users such as Docker. |
| 2026-09-22 | The four-protocol branch progressed through 147/150/153/156 isolated checks using a systemctl substitute, not real-host acceptance. Operator approval of the v2 branch was still pending then. |
| 2026-09-22 | Four protocols actually ran in one process; hysteria2/tuic were excluded for differing field/TLS requirements and per-protocol units rejected. AnyTLS remained separate then, superseded by the five-protocol decision on 2026-10-04. Independently reapplied address/public-IP fixes required branch reconciliation; unknown-protocol validation/port overflow were fixed and single-protocol resets retained other credentials. Manual-password support was implemented, still using the Python standard library. |
| 2026-09-27 | v2.0.0 moved to standard directories. At that time 271 tests passed and 8 skipped; English navigation had four warnings. Seven artifacts matched upstream; real-host/systemd and native-language review remained pending, with FRPS/Lucky experimental. |
| 2026-09-28—2026-09-29 | v3.0.0 added node policies/sharing with 311 passed/8 skipped checks. v4.0.0 added Web setup/FRPC with 341 passed/8 skipped. The operator reported working features; host reboots and every real policy combination were not independently witnessed, and tags did not automatically update test hosts. |
| 2026-10-03 | v5.0.0 moved setup to the terminal and split source. Before publication, 377 tests ran with 369 passed/8 skipped; a real-host reinstall after restructuring remained untested. The operator then requested removal of `tests/` and the retired wizard; old counts are not current-version acceptance. |
| 2026-10-04 | Review fixed cycle quota, Unicode passwords, forwarding rollback and uninstall leftovers. A hypothesis about anonymous-request `_db_lock` contention was not reproduced: 60 concurrent requests measured about 0.4–0.6 ms, so no redesign followed. Missing readings no longer trigger premature limits; sustained real quotas still needed coverage. |
| 2026-10-04 | v5.1.0 was published. The operator confirmed uninstall, login, iperf3, node traffic, forwarding and legacy upgrades; SSH was unavailable, so this session did not independently recheck them. v5.1.1-test.1 established layout 1 with isolated checks passed but real-host reinstall/uninstall pending then. |
| 2026-10-04—2026-10-05 | The former v6.0.0 candidate added the terminal, Tailscale, offline assets and unified AnyTLS. `test-6b26f02`, `test-68e7c5f`, `test-f14ab01` and `test-a9e3cdb` refined logs, state and terminal behavior. The operator requested minor version v5.2.0; history was merged into main and v6 was not formally released. |
| 2026-10-05 | v5.2.0 used commit `53a24c6`, package hash `44727d247a39b62cb558fc734d1a8601a1e5c1eef7a9700277d0571d46551e4f`. Broad operator confirmation was not item-by-item independent testing; publication did not deploy. v5.2.1 commit `79bb076` fixed Tailscale/uninstall, hash `4ff4cae467e0b176b50459245fdf639a0e44e89e1230207dfdf28e98dc823a53`; that run did not install/uninstall on the operator VPS. |
| 2026-10-05 | The operator confirmed FRPC settings save in `test-cd085d6`; `test-cd8b114` still had empty responses after successful saves, delete hover issues and misaligned edit actions. Subsequent waiting-page/retry/style fixes were confirmed. v5.2.2 was published and installed from the full package on the designated Debian 13 host, verifying real FRPC restart and invalid-config retention, service state and Web enablement. |
| 2026-10-05 | Earlier gaps for Python 3.9, other distributions, real mobile devices, host reboots and every policy combination were not closed automatically by publication. A logged-out host does not verify authenticated Tailscale logout. Current status is centralized in LOG; old UI/install guides are historical designs only. |
