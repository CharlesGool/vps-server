---
name: project-third-party-notices
description: Third-party attribution and compliance notices
metadata:
  version: "1.0.0"
  lang: "en"
---

# Third-party notices

This document records bundled and OS-supplied third-party components, source claims, and release-review limits.

## Multi-language

**English** | [简体中文](zh-CN/THIRD_PARTY_NOTICES.md) | [繁體中文 (台灣)](zh-TW/THIRD_PARTY_NOTICES.md) | [繁體中文 (香港)](zh-HK/THIRD_PARTY_NOTICES.md) | [हिन्दी](hi/THIRD_PARTY_NOTICES.md) | [Español](es/THIRD_PARTY_NOTICES.md) | [العربية](ar/THIRD_PARTY_NOTICES.md) | [Français](fr/THIRD_PARTY_NOTICES.md)

## Documentation

- Project overview: [README](../README.md)

- Design rationale: [DESIGN](DESIGN.md)

- Release history: [LOG](LOG.md)

- Third-party notices: [THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES.md)

## Third-Party-Notice

The table inventories the components and source claims already documented here.
The seven vendored third-party artifacts have locally computed SHA-256
values in [config/dependencies.lock.json][local-link-001]; run
`python3 tools/verify_dependencies/verify_dependencies.py` from the repository root to compare checkout
bytes offline. That check does not establish upstream identity, original
license terms, or release compliance. No date of a new upstream license or
distribution review is asserted. Before distribution, verify recorded artifact
versions, original license texts, copyright, applicable source-provision
obligations and any separation analysis against the artifacts to be
distributed. No release approval is implied by this table.

| Component / resource | Version / hash | Source | License as recorded | How used | Attribution / original license path | Release obligations to review | Verified on |
| --- | --- | --- | --- | --- | --- | --- | --- |
| frps | `v0.71.0`; binary SHA-256 `b95dee2bf29a021c562565cdf2116376b9fa7590361bd36ef57041a04d0e6654` | [fatedier/frp](https://github.com/fatedier/frp) | Apache-2.0, per bundled license | Bundled frps executable | [included license](../third_party/frp/LICENSE); [artifact record](../third_party/frp/component.txt) | Keep the included Apache-2.0 license and review any release NOTICE obligations | Repository artifact hash verified; upstream identity pending |
| Lucky | `v2.27.2`; binary SHA-256 `7d3193cf969e8ed041761544b41786bcc368d46b9cf4d4d679a5bc215bd3357a` | [gdy666/lucky](https://github.com/gdy666/lucky) | MIT, per bundled license | Bundled Lucky executable | [included license](../third_party/lucky/LICENSE); [artifact record](../third_party/lucky/component.txt) | Keep the included MIT copyright and license notice | Repository artifact hash verified; upstream identity pending |
| sing-box | `v1.13.14`; revision `25a600db24f7680ad9806ce5427bd0ab8afe1114`; binary SHA-256 `68aeab83cc4ab2659a5b92232261a20746ccdafc3b3d1e19b2d63247eec3bbf7` | [SagerNet/sing-box](https://github.com/SagerNet/sing-box) | GPL version 3 or later plus upstream naming condition (as stated in notice) | Vendored executable, shared by anytls and proxy | [upstream notice][local-link-002]; [GPL full text][local-link-003] | Corresponding source and naming condition; review [recorded source links][local-link-004] and [Decisions][local-link-005] | Not recorded; reverify before distribution |
| LibreSpeed | `v6.2.1` as previously recorded | [LibreSpeed](https://github.com/librespeed/speedtest) | LGPL-3.0 as previously recorded | Vendored browser engine | Not recorded here; [original LGPL text][local-link-006] and [GPL text][local-link-007] | Review library combination and source availability | Not recorded; reverify before distribution |
| qrcode-generator | `js2.0.4`; revision `83b7e8fe3fddd3b0368dbafd6ce56995bd25e3c8` | [kazuhikoarase/qrcode-generator](https://github.com/kazuhikoarase/qrcode-generator) | MIT as previously recorded | Vendored client-side QR library | [original MIT text][local-link-008] | Keep required attribution and license notices | Not recorded; reverify before distribution |
| iperf3 | Distro package; version not pinned | [ESnet/iperf](https://github.com/esnet/iperf) | BSD-3-Clause as previously recorded | Invoked as separate OS-installed program; not redistributed here | Not recorded; OS package supplies original license | Reassess if bundled or redistributed later | Not recorded; reverify before distribution |

The existing project record identifies GPL-3.0 for this project ([LICENSE][local-link-009]) and records the redistribution of a GPL-licensed sing-box executable as its reason; [Decisions][local-link-010] retains the rationale and rejected alternatives. The prior record describes `vps-webserver` as Apache-2.0 upstream and redistributed here under GPL-3.0. These are historical project claims, not a new legal determination; review obligations and compatibility before a release.

There are no third-party Python packages. `src/web/app.py` uses the standard library,
so there is no Python package lock. The vendored-artifact lock above does not
pin OS-supplied Python, iperf3, or other system packages: their versions and
security updates are managed through the target Debian/Ubuntu distribution's
package channels. The installer does not select exact package versions or a
repository snapshot; a fully reproducible system dependency closure remains
unresolved (see [Reproduction requirements][local-link-011]).

---

## sing-box

This repository redistributes a sing-box executable as `third_party/sing-box/sing-box` in the
repository checkout. Its upstream-release identity was asserted in the prior
project record but was not independently rechecked in this local hash audit.
It is installed as `/usr/local/bin/sing-box-vps-server`.

- Component: `sing-box`
- Upstream project: https://github.com/SagerNet/sing-box
- Copyright (C) 2022 by nekohasekai <contact-sagernet@sekai.icu>
- Version: `v1.13.14`
- Source revision: `25a600db24f7680ad9806ce5427bd0ab8afe1114`
- Distributed artifact: `sing-box-1.13.14-linux-amd64.tar.gz`
- Repository binary SHA-256: `68aeab83cc4ab2659a5b92232261a20746ccdafc3b3d1e19b2d63247eec3bbf7`
- License: GNU GPL version 3 or any later version, plus the upstream
  name/association condition; see [`third_party/sing-box/LICENSE`][local-link-012]

The prior project record reports a byte-for-byte comparison with the upstream
Release archive. This audit verified only the repository binary's SHA-256;
release equivalence still requires an independent upstream comparison.

### Corresponding source

The prior project record identifies the following corresponding-source links
for the claimed release; this audit did not verify their contents against the
repository binary. Confirm correspondence and source-provision obligations
before redistribution:

- Tagged source tree: https://github.com/SagerNet/sing-box/tree/v1.13.14
- Exact source revision: https://github.com/SagerNet/sing-box/tree/25a600db24f7680ad9806ce5427bd0ab8afe1114
- Source archive: https://github.com/SagerNet/sing-box/archive/refs/tags/v1.13.14.tar.gz

The upstream Release archive cited in the prior project record is:

- https://github.com/SagerNet/sing-box/releases/download/v1.13.14/sing-box-1.13.14-linux-amd64.tar.gz

This project is independent and is not affiliated with or endorsed by the
sing-box or SagerNet authors.

---

## LibreSpeed

The browser speed test uses a vendored LibreSpeed client engine. The recorded
version and upstream equivalence were not independently verified in this audit.

- Component: LibreSpeed client engine — `static/third_party/librespeed/speedtest.js`, `static/third_party/librespeed/speedtest_worker.js`
- Upstream project: https://github.com/librespeed/speedtest
- Version: `v6.2.1`
- License: GNU LGPL version 3; full text at [`static/licenses/LGPL-3.0.txt`][local-link-013]
- Prior project record: both files were described as byte-identical to the
  upstream release; only local checkout hashes were verified in this audit.
  The exact upstream source revision is not recorded.

`static/speedtest-ui.js` is this project's own glue code and is not part of
LibreSpeed. The server-side endpoints in `src/web/app.py` (`/speedtest/garbage`,
`/speedtest/empty`, `/speedtest/getip`) reimplement LibreSpeed's documented
client/server contract; they are original code, not derived from the upstream
PHP backend.

The prior record assessed LGPL-3.0 combination with this GPL-3.0 work; confirm the release obligations before distribution.

---

## qrcode-generator

The console's `/proxy` page renders each anytls address's share link as a scannable QR code
using this vendored client-side library. The recorded version and upstream
equivalence were not independently verified in this audit.

- Component: `static/third_party/qrcode/qrcode.js`, `static/third_party/qrcode/qrcode-utf8.js`
- Upstream project: https://github.com/kazuhikoarase/qrcode-generator
- Copyright (c) 2009 Kazuhiko Arase
- Version: `js2.0.4`
- Source revision: `83b7e8fe3fddd3b0368dbafd6ce56995bd25e3c8`
- License: MIT; full text at [`static/licenses/MIT.txt`][local-link-014]
- Prior project record: both files were described as byte-identical to upstream
  `js/dist/qrcode.js` and `js/dist/qrcode_UTF8.js`; only local checkout hashes
  were verified in this audit.

`static/qrcode-render.js` is this project's own glue code (finds
`[data-qr-text]` elements and fills them with the rendered SVG) and is not
part of the vendored library.

The prior record assessed MIT combination with this GPL-3.0 work; confirm notice obligations before distribution.

---

## iperf3

- Component: `iperf3`
- Upstream project: https://github.com/esnet/iperf
- License: BSD 3-Clause
- Modified: no
- **Not redistributed.** `iperf3` is installed from the operating system's
  package repository by `install.sh` and is invoked as a separate program over
  a process boundary. No iperf3 code or binary ships in this repository, so the
  BSD attribution requirement, which attaches to redistribution, is not
  triggered here according to the prior record; reassess if distribution changes. It is listed because the project depends on it at runtime.

---

## Vendored from this author's own projects

Not third-party, but recorded here because the code did not originate in this
repository and its provenance matters for updates:

- `src/web/app.py`, `static/speedtest-ui.js`, `static/style.css`, `static/visitors.js`,
  `tests/`, `deploy/install.sh`, `deploy/uninstall.sh`, `deploy/systemd/` (with root installer entries) — from `vps-webserver`
  v0.4.1 (Apache-2.0 upstream, relicensed GPL-3.0 here). See `config/upstream-version`.
- `deploy/anytls/setup-anytls.sh`, `third_party/sing-box/sing-box`, `third_party/sing-box/sing-box.version` — from
  `Anytsl-Serve` v1.2.0 (GPL-3.0 upstream). See `deploy/anytls/.upstream-version`.

---

No third-party fonts, icons, images, datasets, or model weights are included.
At runtime the service makes no outbound request; the only optional outbound
call is a public-IP lookup during installation, which degrades to a warning
if it fails.

[local-link-001]: ../config/dependencies.lock.json
[local-link-002]: ../third_party/sing-box/LICENSE
[local-link-003]: ../LICENSE
[local-link-004]: #corresponding-source
[local-link-005]: LOG.md#decisions
[local-link-006]: ../static/licenses/LGPL-3.0.txt
[local-link-007]: ../LICENSE
[local-link-008]: ../static/licenses/MIT.txt
[local-link-009]: ../LICENSE
[local-link-010]: LOG.md#decisions
[local-link-011]: DESIGN.md#reproduction-requirements
[local-link-012]: ../third_party/sing-box/LICENSE
[local-link-013]: ../static/licenses/LGPL-3.0.txt
[local-link-014]: ../static/licenses/MIT.txt
