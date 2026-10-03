---
name: project-third-party-notices-en
description: Third-party attribution and compliance notices
metadata:
  version: "1.0.0"
  lang: "en"
---

# Third-party notices

## Multi-language

[简体中文](../THIRD_PARTY_NOTICES.md) | **English** | [Español](../es/THIRD_PARTY_NOTICES.md)

## Documentation

- Project overview: [README](README.md)

- Design rationale: [DESIGN](DESIGN.md)

- Project status: [LOG](LOG.md)
- Historical records: [HISTORY](HISTORY.md)
- Version changelog: [CHANGELOG](CHANGELOG.md)

- Third-party notices: [THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES.md)


## Third-Party-Notice

The table inventories bundled and OS-supplied components. The nine bundled
artifacts have checkout SHA-256 values in [config/dependencies.lock.json][local-link-001];
run `python3 tools/verify_dependencies/verify_dependencies.py` from the repository
root to compare them offline. The 2026-09-27 checks of the original seven
artifacts remain unchanged. The FRPC binary added on 2026-10-04 matches its
v0.71.0 upstream archive member byte for byte. The new iperf3 binary was
built locally from a checked SHA-256 upstream 3.22 source archive; its binary
hash establishes only the identity of this repository's artifact. Included
license paths are listed below.
These checks establish artifact identity, not a legal opinion or a fully
reproducible system dependency closure.

| Component / resource | Version / hash | Source | License as recorded | How used | Attribution / original license path | Release obligations to review | Verified on |
| --- | --- | --- | --- | --- | --- | --- | --- |
| frps | `v0.71.0`; binary SHA-256 `b95dee2bf29a021c562565cdf2116376b9fa7590361bd36ef57041a04d0e6654` | [fatedier/frp](https://github.com/fatedier/frp) | Apache-2.0, per upstream license | Bundled frps executable | [included license](../../third_party/frp/LICENSE); [artifact record](../../third_party/frp/component.txt) | Keep the included Apache-2.0 license; no NOTICE file was in the official binary archive | 2026-09-27: archive, binary, and license matched |
| frpc | `v0.71.0`; binary SHA-256 `f79fff8de3089ec711ff8bdd4b73e00dfe491a1c3d754983c8b0f8d58c21b068` | [fatedier/frp](https://github.com/fatedier/frp) | Apache-2.0, per upstream license | Bundled frpc executable, verified before installation | [included license](../../third_party/frp/LICENSE); [artifact record](../../third_party/frp/component.txt) | Distribute the same upstream license with the source and retain the asset checksum | 2026-10-04: bundled client binary matched the upstream archive member |
| Lucky | `v2.27.2`; binary SHA-256 `7d3193cf969e8ed041761544b41786bcc368d46b9cf4d4d679a5bc215bd3357a` | [gdy666/lucky](https://github.com/gdy666/lucky) | MIT, per upstream license | Bundled Lucky executable | [included license](../../third_party/lucky/LICENSE); [artifact record](../../third_party/lucky/component.txt) | Keep the included MIT copyright and license notice | 2026-09-27: archive, binary, and license matched |
| sing-box | `v1.13.14`; revision `25a600db24f7680ad9806ce5427bd0ab8afe1114`; binary SHA-256 `68aeab83cc4ab2659a5b92232261a20746ccdafc3b3d1e19b2d63247eec3bbf7` | [SagerNet/sing-box](https://github.com/SagerNet/sing-box) | GPL version 3 or later plus upstream naming condition (as stated in notice) | Vendored executable, shared by anytls and proxy | [upstream notice][local-link-002]; [GPL full text][local-link-003] | Keep corresponding source links and upstream name/association condition | 2026-09-27: archive, binary, license, and tag revision matched |
| LibreSpeed | `v6.2.1` | [LibreSpeed](https://github.com/librespeed/speedtest) | LGPL-3.0 per upstream license | Vendored browser engine | [original LGPL text][local-link-006] and [GPL text][local-link-007] | Keep license text and upstream source available | 2026-09-27: two tag files and license matched |
| qrcode-generator | `js2.0.4`; revision `83b7e8fe3fddd3b0368dbafd6ce56995bd25e3c8` | [kazuhikoarase/qrcode-generator](https://github.com/kazuhikoarase/qrcode-generator) | MIT per upstream license | Vendored client-side QR library | [original MIT text][local-link-008] | Keep required attribution and license notice | 2026-09-27: two tag files and license matched |
| Inter | `5.3.0` | [Fontsource Inter](https://github.com/fontsource/font-files/blob/main/fonts/google/inter/README.md) | SIL OFL 1.1 | Bundled Latin interface font, weights 400/600/700 | [included license](../../src/web/static/licenses/OFL-Inter.txt) | Keep the included OFL and copyright notice | 2026-09-27: upstream npm package |
| Noto Sans SC | `5.3.0` | [Fontsource Noto Sans SC](https://github.com/fontsource/font-files/blob/main/fonts/google/noto-sans-sc/README.md) | SIL OFL 1.1 | Bundled CJK interface font, weights 400/700 | [included license](../../src/web/static/licenses/OFL-Noto-Sans-SC.txt) | Keep the included OFL and copyright notice | 2026-09-27: upstream npm package |
| Lucide icons | Upstream `main` on 2026-09-27 | [lucide-icons/lucide](https://github.com/lucide-icons/lucide) | ISC | Bundled interface SVG icons | [included license](../../src/web/static/licenses/Lucide-ISC.txt) | Keep the included copyright and license notice | 2026-09-27: upstream SVG files |
| iperf3 | `3.22`; bundled binary SHA-256 `f1924a042ef4074b5974b8985a235ad2fcb45d52d02cec46b0dfb45e269b9bf2` | [ESnet/iperf](https://github.com/esnet/iperf) | BSD-3-Clause | Locally built x86-64 Linux static executable from official source | [upstream LICENSE](../../third_party/iperf3/LICENSE); [build record](../../third_party/iperf3/component.txt) | Retain copyright and the full license with the binary; target-distro compatibility awaits acceptance | 2026-10-04: official source digest, local build, and local execution checked |

The existing project record identifies GPL-3.0 for this project ([LICENSE][local-link-009]) and records the redistribution of a GPL-licensed sing-box executable as its reason; [Decisions][local-link-010] retains the rationale and rejected alternatives. The prior record describes `vps-webserver` as Apache-2.0 upstream and redistributed here under GPL-3.0. This inventory records the files and terms checked for v2.0.0; it does not provide an independent legal opinion.

There are no third-party Python packages. `src/web/app.py` uses the standard library,
so there is no Python package lock. The vendored-artifact lock above does not
pin OS-supplied Python or other system packages: their versions and
security updates are managed through the target Debian/Ubuntu distribution's
package channels. The installer does not select exact package versions or a
repository snapshot; a fully reproducible system dependency closure remains
unresolved (see [Reproduction requirements][local-link-011]).

---

## sing-box

This repository redistributes a sing-box executable as `third_party/sing-box/sing-box` in the
repository checkout. On 2026-09-27 its bytes and included upstream license
matched the official v1.13.14 release archive.
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

The downloaded release archive SHA-256 was
`f48703461a15476951ac4967cdad339d986f4b8096b4eb3ff0829a500502d697`.
The repository binary and license matched its extracted members byte for byte.

### Corresponding source

The v1.13.14 tag resolved to source revision
`25a600db24f7680ad9806ce5427bd0ab8afe1114` on 2026-09-27. The
following upstream source links accompany the bundled executable:

- Tagged source tree: https://github.com/SagerNet/sing-box/tree/v1.13.14
- Exact source revision: https://github.com/SagerNet/sing-box/tree/25a600db24f7680ad9806ce5427bd0ab8afe1114
- Source archive: https://github.com/SagerNet/sing-box/archive/refs/tags/v1.13.14.tar.gz

The upstream Release archive cited in the prior project record is:

- https://github.com/SagerNet/sing-box/releases/download/v1.13.14/sing-box-1.13.14-linux-amd64.tar.gz

This project is independent and is not affiliated with or endorsed by the
sing-box or SagerNet authors.

---

## LibreSpeed

The browser speed test uses a vendored LibreSpeed client engine. On
2026-09-27, its two bundled JavaScript files and license matched the upstream
v6.2.1 tag files byte for byte.

- Component: LibreSpeed client engine — `src/web/static/third_party/librespeed/speedtest.js`, `src/web/static/third_party/librespeed/speedtest_worker.js`
- Upstream project: https://github.com/librespeed/speedtest
- Version: `v6.2.1`
- License: GNU LGPL version 3; full text at [`src/web/static/licenses/LGPL-3.0.txt`][local-link-013]
- Verification: both files and the original license matched the v6.2.1 tag;
  the exact tag commit is not recorded in this inventory.

`src/web/static/speedtest-ui.js` is this project's own glue code and is not part of
LibreSpeed. The server-side endpoints in `src/web/app.py` (`/speedtest/garbage`,
`/speedtest/empty`, `/speedtest/getip`) reimplement LibreSpeed's documented
client/server contract; they are original code, not derived from the upstream
PHP backend.

The LGPL-3.0 text is bundled and the upstream source is linked; this inventory
does not provide an independent legal opinion about the combination.

---

## qrcode-generator

The console's `/proxy` page renders share links as scannable QR codes using
this vendored client-side library. On 2026-09-27, its two bundled JavaScript
files and original license matched the upstream js2.0.4 tag files byte for byte.

- Component: `src/web/static/third_party/qrcode/qrcode.js`, `src/web/static/third_party/qrcode/qrcode-utf8.js`
- Upstream project: https://github.com/kazuhikoarase/qrcode-generator
- Copyright (c) 2009 Kazuhiko Arase
- Version: `js2.0.4`
- Source revision: `83b7e8fe3fddd3b0368dbafd6ce56995bd25e3c8`
- License: MIT; full text at [`src/web/static/licenses/MIT.txt`][local-link-014]
- Verification: both files matched upstream `js/dist/qrcode.js` and
  `js/dist/qrcode_UTF8.js`; the original MIT license matched too.

`src/web/static/qrcode-render.js` is this project's own glue code (finds
`[data-qr-text]` elements and fills them with the rendered SVG) and is not
part of the vendored library.

The MIT copyright and license notice is bundled with the client library.

---

## iperf3

- Component: `iperf3`
- Upstream project: https://github.com/esnet/iperf
- License: BSD 3-Clause
- Source: [official 3.22 archive](https://downloads.es.net/pub/iperf/iperf-3.22.tar.gz),
  SHA-256 `1c0d0fb02c52626111d6e132db80edfbf27bbaff8bd9245df2a371dcb0b35a92`.
- Build: on Ubuntu 22.04 x86-64, run
  `./configure --enable-static-bin --disable-shared --without-sctp && make -j2`,
  then `strip` `src/iperf3`. Source was unmodified; see the binary SHA-256 above.
- Distribution: `third_party/iperf3/iperf3`, with BSD-3-Clause copyright and
  full license in [`third_party/iperf3/LICENSE`](../../third_party/iperf3/LICENSE).
  Installed at `$PREFIX/vendor/iperf3/iperf3`.
- Limits: the build omits SCTP and OpenSSL authentication. Static glibc
  address resolution on older target distributions still needs acceptance;
  this project's time-limited TCP/UDP test uses neither optional feature.

---

## Vendored from this author's own projects

Not third-party, but recorded here because the code did not originate in this
repository and its provenance matters for updates:

- `src/web/app.py`, `src/web/static/speedtest-ui.js`, `src/web/static/style.css`, `src/web/static/visitors.js`,
  `tests/`, `deploy/install.sh`, `deploy/uninstall.sh`, `deploy/systemd/` (with root installer entries) — from `vps-webserver`
  v0.4.1 (Apache-2.0 upstream, relicensed GPL-3.0 here). See `config/upstream-version`.
- `deploy/anytls/setup-anytls.sh`, `third_party/sing-box/sing-box`, `third_party/sing-box/sing-box.version` — from
  `Anytsl-Serve` v1.2.0 (GPL-3.0 upstream). See `deploy/anytls/.upstream-version`.

---

The bundled third-party fonts and icons are listed in the table above. No
third-party image datasets or model weights are included. Installation can
install bundled FRPC without a download. An optional public-IP lookup can
still be requested; failures produce a warning.

[local-link-001]: ../../config/dependencies.lock.json
[local-link-002]: ../../third_party/sing-box/LICENSE
[local-link-003]: ../../LICENSE
[local-link-004]: #corresponding-source
[local-link-005]: LOG.md#decisions
[local-link-006]: ../../src/web/static/licenses/LGPL-3.0.txt
[local-link-007]: ../../LICENSE
[local-link-008]: ../../src/web/static/licenses/MIT.txt
[local-link-009]: ../../LICENSE
[local-link-010]: LOG.md#decisions
[local-link-011]: DESIGN.md#reproduction-requirements
[local-link-012]: ../../third_party/sing-box/LICENSE
[local-link-013]: ../../src/web/static/licenses/LGPL-3.0.txt
[local-link-014]: ../../src/web/static/licenses/MIT.txt
