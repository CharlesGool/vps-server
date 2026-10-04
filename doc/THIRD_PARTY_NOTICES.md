---
name: project-third-party-notices
description: 第三方署名与合规声明
metadata:
  version: "1.0.0"
  lang: "zh-CN"
---

# 第三方声明

## 多语言

**简体中文** | [English](en/THIRD_PARTY_NOTICES.md) | [Español](es/THIRD_PARTY_NOTICES.md)

## 文档

- 项目概览:[README](../README.md)

- 设计思路:[DESIGN](DESIGN.md)

- 项目状态: [LOG](LOG.md)
- 历史记录: [HISTORY](HISTORY.md)
- 变更日志: [CHANGELOG](CHANGELOG.md)

- 第三方声明:[THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES.md)

## 第三方声明

下表列出随附组件及由操作系统提供的组件.原有九个仓库构件在 [dependencies.lock.json][local-link-001] 中记录了 SHA-256;从仓库根目录运行 `python3 tools/verify_dependencies/verify_dependencies.py` 可离线比较字节.Tailscale 归档随当前源码提供并由锁文件验证;nftables 归档进入生成的离线包,构建器按固定摘要验证,来源和许可证见各自的 `component.txt`.原有七个构件的 2026-09-27 核验记录保持不变;新增 FRPC 和 iperf3 的来源记录见下表.这些检查确认构件身份,不证明跨发行版兼容性或完整系统依赖闭包.

| 组件/资源 | 版本/散列 | 来源 | 所记录的许可证 | 用途 | 署名/原始许可证路径 | 待审核的发布义务 | 核验日期 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| frps | `v0.71.0`; binary SHA-256 `b95dee2bf29a021c562565cdf2116376b9fa7590361bd36ef57041a04d0e6654` | [fatedier/frp](https://github.com/fatedier/frp) | Apache-2.0,依据上游许可证 | 随附的 frps 可执行文件 | [included license](../third_party/frp/LICENSE); [artifact record](../third_party/frp/component.txt) | 保留随附的 Apache-2.0 许可证;官方二进制归档中没有 NOTICE 文件 | 2026-09-27:归档,二进制文件及许可证一致 |
| frpc | `v0.71.0`;二进制文件 SHA-256 `f79fff8de3089ec711ff8bdd4b73e00dfe491a1c3d754983c8b0f8d58c21b068` | [fatedier/frp](https://github.com/fatedier/frp) | 上游许可证为 Apache-2.0 | 随仓库分发的 frpc 可执行文件,安装前验证 | [随附许可证](../third_party/frp/LICENSE);[资源记录](../third_party/frp/component.txt) | 随源码分发相同的上游许可证,并保留资源校验和 | 2026-10-04:随附客户端二进制文件与上游归档成员一致 |
| Lucky | `v2.27.2`; binary SHA-256 `7d3193cf969e8ed041761544b41786bcc368d46b9cf4d4d679a5bc215bd3357a` | [gdy666/lucky](https://github.com/gdy666/lucky) | MIT,依据上游许可证 | 随附的 Lucky 可执行文件 | [included license](../third_party/lucky/LICENSE); [artifact record](../third_party/lucky/component.txt) | 保留随附的 MIT 版权及许可声明 | 2026-09-27:归档,二进制文件及许可证一致 |
| sing-box | `v1.13.14`;修订号 `25a600db24f7680ad9806ce5427bd0ab8afe1114`;二进制 SHA-256 `68aeab83cc4ab2659a5b92232261a20746ccdafc3b3d1e19b2d63247eec3bbf7` | [SagerNet/sing-box](https://github.com/SagerNet/sing-box) | GPL 第 3 版或更高版本,另附上游命名条件(据声明所述) | 供 anytls 和 proxy 共用的随附可执行文件 | [上游声明][local-link-002];[GPL 全文][local-link-003] | 保留对应源码链接及上游名称/关联条件 | 2026-09-27:归档,二进制文件,许可证及标签修订号一致 |
| LibreSpeed | `v6.2.1` | [LibreSpeed](https://github.com/librespeed/speedtest) | LGPL-3.0,依据上游许可证 | 随附的浏览器引擎 | [原始 LGPL 文本][local-link-006]和[GPL 文本][local-link-007] | 保留许可证文本并确保上游源码可获得 | 2026-09-27:两个标签文件及许可证一致 |
| qrcode-generator | `js2.0.4`;修订号 `83b7e8fe3fddd3b0368dbafd6ce56995bd25e3c8` | [kazuhikoarase/qrcode-generator](https://github.com/kazuhikoarase/qrcode-generator) | MIT,依据上游许可证 | 随附的客户端二维码库 | [原始 MIT 文本][local-link-008] | 保留必要的版权与许可声明 | 2026-09-27:两个标签文件及许可证一致 |
| Inter | `5.3.0` | [Fontsource Inter](https://github.com/fontsource/font-files/blob/main/fonts/google/inter/README.md) | SIL OFL 1.1 | 随附的拉丁界面字体,400/600/700 字重 | [license](../src/web/static/licenses/OFL-Inter.txt) | 保留随附的许可证及版权声明 | 2026-09-27 |
| Noto Sans SC | `5.3.0` | [Fontsource Noto Sans SC](https://github.com/fontsource/font-files/blob/main/fonts/google/noto-sans-sc/README.md) | SIL OFL 1.1 | 随附的 CJK 界面字体,400/700 字重 | [license](../src/web/static/licenses/OFL-Noto-Sans-SC.txt) | 保留随附的许可证及版权声明 | 2026-09-27 |
| Lucide icons | `main` 2026-09-27 | [lucide-icons/lucide](https://github.com/lucide-icons/lucide) | ISC | 随附的界面 SVG 图标 | [license](../src/web/static/licenses/Lucide-ISC.txt) | 保留随附的许可证及版权声明 | 2026-09-27 |
| xterm.js 与 Fit Addon | `@xterm/xterm` 6.0.0,`@xterm/addon-fit` 0.11.0;JavaScript SHA-256 分别为 `14903579ff54664cd72f8e8699e6961a6272c21863ec1c3b118cdc8af5d4a972`,`ba3ea256ce0620a0992a197d6c9baea64823fc93d8da07a9e366ca9943c18527` | [xtermjs/xterm.js](https://github.com/xtermjs/xterm.js) | MIT,依据 npm 归档随附许可证 | 离线浏览器终端渲染和尺寸适配 | [xterm 许可证](../src/web/static/third_party/xterm/LICENSE-xterm);[Fit Addon 许可证](../src/web/static/third_party/xterm/LICENSE-addon-fit);[构件记录](../src/web/static/third_party/xterm/component.txt) | 随同静态文件保留两份上游版权及许可声明 | 2026-10-05:npm 固定版本归档成员逐字节复制并记录 SHA-256 |
| iperf3 | `3.22`;随附二进制 SHA-256 `f1924a042ef4074b5974b8985a235ad2fcb45d52d02cec46b0dfb45e269b9bf2` | [ESnet/iperf](https://github.com/esnet/iperf) | BSD-3-Clause | 从官方源码本地构建的 x86-64 Linux 静态可执行文件 | [上游 LICENSE](../third_party/iperf3/LICENSE);[构建记录](../third_party/iperf3/component.txt) | 随二进制保留版权和完整许可声明;目标发行版兼容性仍待验收 | 2026-10-04:官方源码摘要,本地构建与本机执行已核对 |
| Tailscale | `1.102.4`;官方 amd64 静态归档 SHA-256 `50748df1045e60b5b695f19f4c56b0da36c019948b440fb456b6584a50f0d8b9` | [官方 Linux 发布包](https://pkgs.tailscale.com/stable/) | BSD-3-Clause,依据上游 LICENSE | 当前源码和离线包随附归档,目标机安装客户端和守护进程 | [上游许可证](../third_party/tailscale/LICENSE);[依赖清单](../third_party/tailscale/DEPENDENCY_NOTICES.md);[专利授权](../third_party/tailscale/PATENTS);[构件记录](../third_party/tailscale/component.txt) | 随离线包保留上游许可,专利授权和对应版本依赖清单;随附依赖许可证正文和来源摘要清单 | 2026-10-04:官方归档摘要与本机运行版本一致;上游标签中的声明文件已随附 |
| nftables 及 10 个运行库 | Debian 11 amd64 `nftables 0.9.8-3.1+deb11u2`;运行归档 SHA-256 `42eeb9496a173777df2e46d67b32b631e5eb31bbc1a74d2a0fa335f32a46c9eb`;对应源码归档 SHA-256 `fce6ca6c5050ff7715c5bd9fedb0160c942e3e5ede7d2702c02f01d920ac6e83` | [Debian 官方软件包仓库](https://deb.debian.org/debian/) | 各包许可证见归档内 `usr/share/doc/<package>/copyright` | v5.2.0 离线包中供节点计量使用的私有 nft 运行时,不安装到系统软件包数据库 | [包名与 SHA-256 记录](../third_party/nft/component.txt);[源码清单](../third_party/nft/source-manifest.json) | 随同一离线包提供对应原始源码及 Debian 打包补丁;跨发行版兼容性仍待目标机验收 | 2026-10-04:各 `.deb` 与源码文件均和 Debian 索引散列匹配;本机解析配额语法通过 |

现有项目记录将本项目的许可证标为 GPL-3.0([LICENSE][local-link-009]),并将重新分发 GPL 许可的 sing-box 可执行文件作为选择该许可证的理由;[决策][local-link-010]保留了其理由及被否决的替代方案.先前记录称 `vps-webserver` 上游采用 Apache-2.0,在本项目中以 GPL-3.0 重新分发.本清单记录了为 v2.0.0 核验的文件与条款;不提供独立的法律意见.

本项目没有第三方 Python 包.`src/web/app.py` 使用标准库,因此没有 Python 包锁.上述随附构件的锁文件没有锁定由操作系统提供的 Python 或其他系统包:其版本和安全更新由目标 Debian/Ubuntu 发行版的软件包渠道管理.安装程序不选择精确的包版本或仓库快照;完整可复现的系统依赖闭包仍未解决(见[复现要求][local-link-011]).

---

## sing-box

本仓库以 `third_party/sing-box/sing-box` 路径重新分发 sing-box 可执行文件.2026-09-27,其字节及随附的上游许可证与官方 v1.13.14 发布归档一致.安装路径为 `/usr/local/bin/sing-box-vps-server`.

- 组件:`sing-box`
- 上游项目:https://github.com/SagerNet/sing-box
- Copyright (C) 2022 by nekohasekai <contact-sagernet@sekai.icu>
- 版本:`v1.13.14`
- 源码修订号:`25a600db24f7680ad9806ce5427bd0ab8afe1114`
- 分发构件:`sing-box-1.13.14-linux-amd64.tar.gz`
- 仓库内二进制文件 SHA-256:`68aeab83cc4ab2659a5b92232261a20746ccdafc3b3d1e19b2d63247eec3bbf7`
- 许可证:GNU GPL 第 3 版或任何后续版本,另附上游名称/关联条件;参见 [`third_party/sing-box/LICENSE`][local-link-012]

下载的发布归档 SHA-256 为 `f48703461a15476951ac4967cdad339d986f4b8096b4eb3ff0829a500502d697`.仓库内的二进制文件和许可证与解压出的对应文件逐字节一致.

### 对应源码

2026-09-27,v1.13.14 标签解析到源码修订号 `25a600db24f7680ad9806ce5427bd0ab8afe1114`.以下上游源码链接与随附的可执行文件一同提供:

- 已打标签的源码树:https://github.com/SagerNet/sing-box/tree/v1.13.14
- 准确的源码修订号:https://github.com/SagerNet/sing-box/tree/25a600db24f7680ad9806ce5427bd0ab8afe1114
- 源码归档:https://github.com/SagerNet/sing-box/archive/refs/tags/v1.13.14.tar.gz

先前项目记录引用的上游 Release 归档为:

- https://github.com/SagerNet/sing-box/releases/download/v1.13.14/sing-box-1.13.14-linux-amd64.tar.gz

本项目独立于 sing-box 和 SagerNet 的作者,与其没有关联,也未获其背书.

---

## LibreSpeed

浏览器测速使用随附的 LibreSpeed 客户端引擎.2026-09-27,两个随附的 JavaScript 文件及许可证与上游 v6.2.1 标签文件逐字节一致.

- 组件:LibreSpeed 客户端引擎——`src/web/static/third_party/librespeed/speedtest.js`,`src/web/static/third_party/librespeed/speedtest_worker.js`
- 上游项目:https://github.com/librespeed/speedtest
- 版本:`v6.2.1`
- 许可证:GNU LGPL 第 3 版;全文见 [`src/web/static/licenses/LGPL-3.0.txt`][local-link-013]
- 核验:两个文件及原始许可证与 v6.2.1 标签一致;本清单没有记录准确的标签提交.

`src/web/static/speedtest-ui.js` 是本项目自己的衔接代码,不属于 LibreSpeed.`src/web/app.py` 中的服务端端点(`/speedtest/garbage`,`/speedtest/empty`,`/speedtest/getip`)重新实现了 LibreSpeed 文档所述的客户端/服务端约定;它们是原创代码,不是上游 PHP 后端的派生代码.

LGPL-3.0 全文已随附,上游源码已提供链接;本清单不提供关于组合使用的独立法律意见.

---

## qrcode-generator

控制台 `/proxy` 页面使用这个随附的客户端库,将分享链接渲染为可扫描的二维码.2026-09-27,两个随附的 JavaScript 文件及原始许可证与上游 js2.0.4 标签文件逐字节一致.

- 组件:`src/web/static/third_party/qrcode/qrcode.js`,`src/web/static/third_party/qrcode/qrcode-utf8.js`
- 上游项目:https://github.com/kazuhikoarase/qrcode-generator
- Copyright (c) 2009 Kazuhiko Arase
- 版本:`js2.0.4`
- 源码修订号:`83b7e8fe3fddd3b0368dbafd6ce56995bd25e3c8`
- 许可证:MIT;全文见 [`src/web/static/licenses/MIT.txt`][local-link-014]
- 核验:两个文件与上游 `js/dist/qrcode.js` 和 `js/dist/qrcode_UTF8.js` 一致;原始 MIT 许可证也一致.

`src/web/static/qrcode-render.js` 是本项目自己的衔接代码(查找 `[data-qr-text]` 元素并填入渲染后的 SVG),不属于随附的库.

MIT 版权及许可声明与客户端库一同随附.

---

## iperf3

- 组件:`iperf3`
- 上游项目:https://github.com/esnet/iperf
- 许可证:BSD 3-Clause
- 来源:[官方 3.22 源码包](https://downloads.es.net/pub/iperf/iperf-3.22.tar.gz), SHA-256:`1c0d0fb02c52626111d6e132db80edfbf27bbaff8bd9245df2a371dcb0b35a92`.
- 构建:在 Ubuntu 22.04 x86-64 上运行 `./configure --enable-static-bin --disable-shared --without-sctp && make -j2`,随后对 `src/iperf3` 运行 `strip`;源码未修改,二进制 SHA-256 见上表.
- 分发: `third_party/iperf3/iperf3`,BSD-3-Clause 版权和完整许可声明随同放在 [`third_party/iperf3/LICENSE`](../third_party/iperf3/LICENSE).安装后使用 `$PREFIX/vendor/iperf3/iperf3`.
- 边界:构建不含 SCTP 和 OpenSSL 身份验证;glibc 静态链接的地址解析在较旧发行版上仍需实际验收.项目的限时 TCP/UDP 测试不使用这两项可选能力.

---

## nftables 离线运行时及对应源码

完整离线包同时包含 `third_party/nft/nft-runtime-bullseye.tar.gz` 和 `third_party/nft/nft-sources-bullseye.tar.gz`.前者是从 11 个 Debian 11 amd64 `.deb` 中按原字节提取的可执行文件,动态库与 `usr/share/doc/<package>/copyright`;后者包含这 11 个二进制包对应的 10 组完整上游源码归档,Debian 打包补丁和源包描述文件.各文件名,大小和 SHA-256 由[源码清单](../third_party/nft/source-manifest.json)固定;构建机通过[资源获取脚本](../tools/build_offline/fetch_assets.py)从 Debian 官方仓库下载并校验.目标机安装不需要下载或安装 `.deb`.

本项目没有修改这些源码或 `.deb` 中的构件字节;重新打包只改变放置路径.需要重建时,可从源包描述文件及补丁恢复 Debian 11 的对应源码树.目标机上的私有 nftables 运行时不替换系统已有的 `nft` 命令,仅由节点计量辅助程序调用.Debian 13 测试机已验证命令执行,其他支持的发行版尚未实机验收.

---

## Tailscale 客户端声明

随附的 Tailscale v1.102.4 静态归档来自官方 Linux 发布站点,目标机只提取客户端与守护进程.本项目保留该标签的原始 [BSD-3-Clause 许可证](../third_party/tailscale/LICENSE),[专利授权](../third_party/tailscale/PATENTS) 和 [CLI/守护进程依赖清单](../third_party/tailscale/DEPENDENCY_NOTICES.md).依赖清单对应的 80 份上游许可证,freetype 许可证正文及三份原始 NOTICE 文件已保存在 `third_party/tailscale/licenses/`,来源与 SHA-256 见[许可清单](../third_party/tailscale/license-manifest.json).核对正文中的版权,再分发条件与声明保留要求后,随包提供原文,依赖清单,专利授权及源码来源;Apache-2.0 的声明与例外保留在所获取原文中.原始依赖清单将 freetype 标为 Unknown,本项目补充其固定源码修订的 BSD 风格许可原文,不改写上游清单.该检查不构成独立法律解释.

---

## 随附本作者其他项目的代码

不属于第三方,但这些代码并非源自本仓库,其来源对未来更新仍有意义:

- `src/web/app.py`, `src/web/static/speedtest-ui.js`,`src/web/static/style.css`,`src/web/static/visitors.js`,
  `deploy/install.sh`,`deploy/uninstall.sh`,`deploy/systemd/`——来自 `vps-webserver`
  v0.4.1(上游 Apache-2.0,在此重新授权为 GPL-3.0).见 `config/upstream-version`.
- `third_party/sing-box/sing-box`,`third_party/sing-box/sing-box.version` 最初沿用
  `Anytsl-Serve` 的选型;独立 AnyTLS 安装脚本已从 v5.2.0 中移除.二进制上游及许可见上表.

---

随附的第三方字体和图标列于上表.没有包含第三方图像数据集或模型权重.Tailscale 归档随源码保存;离线包构建时在联网构建机下载并校验 nftables 资源;目标机安装不下载 FRPC 或其他可执行文件,也不查询公网 IP 地址.

[local-link-001]: ../config/dependencies.lock.json
[local-link-002]: ../third_party/sing-box/LICENSE
[local-link-003]: ../LICENSE
[local-link-004]: #对应源码
[local-link-005]: LOG.md#决策
[local-link-006]: ../src/web/static/licenses/LGPL-3.0.txt
[local-link-007]: ../LICENSE
[local-link-008]: ../src/web/static/licenses/MIT.txt
[local-link-009]: ../LICENSE
[local-link-010]: LOG.md#决策
[local-link-011]: DESIGN.md#复现要求
[local-link-012]: ../third_party/sing-box/LICENSE
[local-link-013]: ../src/web/static/licenses/LGPL-3.0.txt
[local-link-014]: ../src/web/static/licenses/MIT.txt
