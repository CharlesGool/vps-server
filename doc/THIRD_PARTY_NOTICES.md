---
name: project-third-party-notices
description: 第三方署名与合规声明
metadata:
  version: "2.0.0"
  lang: "zh-CN"
---

# 第三方声明

## 多语言

**简体中文** | [English](en/THIRD_PARTY_NOTICES.md) | [Español](es/THIRD_PARTY_NOTICES.md)

## 文档

- 项目概览: [README](../README.md)

- 设计思路: [DESIGN](DESIGN.md)

- 项目状态: [LOG](LOG.md)
- 历史记录: [HISTORY](HISTORY.md)
- 变更日志: [CHANGELOG](CHANGELOG.md)

- 第三方声明: [THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES.md)

## 第三方声明

本清单记录分发的组件身份和义务, 保留上游原文, 不把系统软件包误列为固定依赖. [固定摘要](../config/dependencies.lock.json)覆盖 15 个构件.

### 组件清单

| 组件名称 | 版本或哈希 | 上游地址 | 许可证类型 | 使用方式 | 版权归属 | 发布合规义务 | 核验日期 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| frps | 0.71.0 | [frps](https://github.com/fatedier/frp) | Apache-2.0 | 独立服务二进制. | fatedier/frp contributors | 保留许可;官方归档没有 NOTICE. | 2026-09-27 |
| frpc | 0.71.0 | [frpc](https://github.com/fatedier/frp) | Apache-2.0 | 实例客户端二进制. | fatedier/frp contributors | 保留版权及完整许可. | 2026-10-04 |
| Lucky | 2.27.2 | [Lucky](https://github.com/gdy666/lucky) | MIT | 独立管理服务. | gdy (2022) | 保留版权及完整许可. | 2026-09-27 |
| sing-box | 1.13.14 / `25a600db24f7680ad9806ce5427bd0ab8afe1114` | [sing-box](https://github.com/SagerNet/sing-box) | GPL-3.0-or-later | 独立代理核心. | nekohasekai (2022) | 保留源码获取方式及上游名称/关联条件. | 2026-09-27 |
| LibreSpeed | 6.2.1 | [LibreSpeed](https://github.com/librespeed/speedtest) | LGPL-3.0 | 浏览器测速引擎. | LibreSpeed contributors | 保留 LGPL/GPL 原文, 提供对应源码, 可替换客户端文件. | 2026-09-27 |
| qrcode-generator | js2.0.4 / `83b7e8fe3fddd3b0368dbafd6ce56995bd25e3c8` | [qrcode-generator](https://github.com/kazuhikoarase/qrcode-generator) | MIT | 客户端二维码库. | Kazuhiko Arase (2009) | 保留版权及完整许可. | 2026-09-27 |
| Inter | Fontsource 5.3.0 | [Inter](https://github.com/fontsource/font-files/tree/main/fonts/google/inter) | OFL-1.1 | 随附字体, 400/600/700. | The Inter Project Authors (2016) | 保留 OFL 和版权, 遵循保留字体名条件. | 2026-09-27 |
| Noto Sans SC | Fontsource 5.3.0 | [Noto Sans SC](https://github.com/fontsource/font-files/tree/main/fonts/google/noto-sans-sc) | OFL-1.1 | 随附字体, 400/700. | Google Inc. | 保留 OFL 和版权. | 2026-09-27 |
| Lucide | main, 2026-09-27 | [Lucide](https://github.com/lucide-icons/lucide) | ISC | 随附 SVG 图标. | Lucide Icons and Contributors; Cole Bemis | 保留版权及完整许可. | 2026-09-27 |
| xterm.js / Fit Addon | 6.0.0 / 0.11.0 | [xterm.js / Fit Addon](https://github.com/xtermjs/xterm.js) | MIT | 终端渲染与尺寸适配. | The xterm.js authors; SourceLair; Christopher Jeffrey | 保留两份许可和版权原文. | 2026-10-05 |
| iperf3 | 3.22 | [iperf3](https://github.com/esnet/iperf) | BSD-3-Clause | 原源码静态构建, TCP/UDP 测试. | The Regents of the University of California / Lawrence Berkeley National Laboratory | 保留版权及完整许可. | 2026-10-04 |
| Tailscale | 1.102.4 | [Tailscale](https://pkgs.tailscale.com/stable/tailscale_1.102.4_amd64.tgz) | BSD-3-Clause | 官方静态客户端/守护进程归档. | Tailscale Inc & contributors (2020) | 保留 LICENSE, PATENTS 和依赖原始声明/许可. | 2026-10-04 |
| nftables + 10 libraries | Debian 11 amd64, nftables 0.9.8-3.1+deb11u2 | [nftables + 10 libraries](https://deb.debian.org/debian/) | 各包 copyright: GPL/LGPL/BSD 等. | 私有运行库, 只进入完整离线包. | 各包上游作者, 见归档原文. | 同时分发完整对应源码, 补丁和包版权原文. | 2026-10-04 |

核验日期为既有出处核验日期;2026-10-05 发布重新校验固定构件, 未重做全部上游溯源. 未修改 frp, Lucky, Singbox, LibreSpeed 和二维码库的上游构件. Inter/Noto 使用 Fontsource 包版本, 不冒充字体内部版本. 本项目无第三方 Python 包, 图像数据集或模型权重. Python, systemd, OpenSSL, iptables 等由系统提供, 不随锁文件锁定, 其许可和安全更新由发行版渠道管理.

新增的 Vue 前端使用 Vue 3.5.43, vue-i18n 11.4.13, Reka UI 2.11.0, Tailwind CSS 4.3.3, clsx 2.1.1 和 tailwind-merge 3.7.0 (MIT), @lucide/vue 1.52.0 (ISC), class-variance-authority 0.7.1 (Apache-2.0). 精确依赖及下载来源见 [npm 锁文件](../web/package-lock.json). 用途为共享界面组件和编译后的浏览器资源;版权归属以上游原文为准. 核验日期: 2026-10-06. 分发时保留版权和许可原文;构建脚本把依赖许可和带版本/源码下载地址的清单复制到 `web/dist/licenses/`, 安装及离线包均保留该目录. 构建工具的许可也一并附带, 不表示这些工具在 VPS 运行.

### 许可证文本

- [frp](../third_party/frp/LICENSE)
- [Lucky](../third_party/lucky/LICENSE)
- [sing-box](../third_party/sing-box/LICENSE)
- [GPL-3.0](../LICENSE)
- [LibreSpeed LGPL-3.0](../src/web/static/licenses/LGPL-3.0.txt)
- [qrcode-generator MIT](../src/web/static/licenses/MIT.txt)
- [Inter OFL](../src/web/static/licenses/OFL-Inter.txt)
- [Noto Sans SC OFL](../src/web/static/licenses/OFL-Noto-Sans-SC.txt)
- [Lucide ISC](../src/web/static/licenses/Lucide-ISC.txt)
- [xterm.js MIT](../src/web/static/third_party/xterm/LICENSE-xterm)
- [Fit Addon MIT](../src/web/static/third_party/xterm/LICENSE-addon-fit)
- [iperf3](../third_party/iperf3/LICENSE)
- [Tailscale LICENSE](../third_party/tailscale/LICENSE)
- [Tailscale PATENTS](../third_party/tailscale/PATENTS)
- [Tailscale dependencies](../third_party/tailscale/DEPENDENCY_NOTICES.md)
- [Tailscale license manifest](../third_party/tailscale/license-manifest.json)

Tailscale 的 80 份依赖许可, freetype 许可和 3 份 NOTICE 共 84 个正文文件保存在 `third_party/tailscale/licenses/`, 由上方许可清单固定来源和摘要. freetype 在上游依赖清单中仍为 Unknown, 本项目补充固定修订的原始 BSD 风格正文, 不改写上游清单. nftables 运行归档保留每个包的 `usr/share/doc/<package>/copyright`, 具体包名与摘要见 [component.txt](../third_party/nft/component.txt).

### 源代码提供

- sing-box: [v1.13.14 源码](https://github.com/SagerNet/sing-box/tree/25a600db24f7680ad9806ce5427bd0ab8afe1114), [源码归档](https://github.com/SagerNet/sing-box/archive/refs/tags/v1.13.14.tar.gz).
- LibreSpeed: [v6.2.1 源码](https://github.com/librespeed/speedtest/tree/v6.2.1).
- iperf3: [3.22 源码归档](https://downloads.es.net/pub/iperf/iperf-3.22.tar.gz), SHA-256 `1c0d0fb02c52626111d6e132db80edfbf27bbaff8bd9245df2a371dcb0b35a92`.
- Tailscale: [v1.102.4 源码](https://github.com/tailscale/tailscale/tree/v1.102.4).

完整 Release 包同时提供 `third_party/nft/nft-runtime-bullseye.tar.gz` 和 `third_party/nft/nft-sources-bullseye.tar.gz`, 分别固定为 SHA-256 `42eeb9496a173777df2e46d67b32b631e5eb31bbc1a74d2a0fa335f32a46c9eb` 与 `fce6ca6c5050ff7715c5bd9fedb0160c942e3e5ede7d2702c02f01d920ac6e83`. 源码归档含 11 个二进制包对应的 10 组上游原始源码, Debian 补丁和源包描述, 各文件按 [source-manifest.json](../third_party/nft/source-manifest.json). 构建脚本从 Debian 官方仓库下载并验证, 源码检出本身不含这两个 nft 归档. 使用源包描述和补丁可恢复 Debian 对应源码树, 包含构建所需的打包文件;目标机仅调用私有运行库, 不替换系统 nft.

iperf3 源码未修改, 在 Ubuntu 22.04 x86-64 以 `./configure --enable-static-bin --disable-shared --without-sctp && make -j2` 构建并 strip, 不含 SCTP/OpenSSL 认证;旧系统静态解析兼容性仍需验收.

### 合规审查

2026-10-05 发布审查记录: 15 个固定构件摘要及 84 份 Tailscale 声明/许可通过核验, nft 对应源码与运行包共同分发, 原始许可证未改写. [许可决策](LOG.md#决策)记录本项目 GPL-3.0-only 选择. 分发分析如下:

- sing-box 以独立进程及可执行文件分发, 没有把它静态链接进 Python 服务;独立进程不免除其 GPL 源码与声明义务. 保留上游名称条件, 本项目无关联或背书.
- LibreSpeed JavaScript 可独立替换, 原 LGPL/GPL 文本随客户端提供. `speedtest-ui.js` 为本项目衔接代码, Python 端点为协议原创实现, 不复制 PHP 后端.
- nft 仅重新打包未修改的 Debian 构件, 原版权文件和完整对应源包同包提供;分离路径不免除各包义务.
- Tailscale 保留原始依赖声明, 专利授权和补充原文;许可身份核对不能证明所有环境兼容性.

以上为项目文件与分发方式审查, 尚无独立法律解释. 本作者 `vps-webserver v0.4.1` 的导入代码在此从 Apache-2.0 重新授权为 GPL-3.0-only, 出处见 [config/upstream-version](../config/upstream-version). Anytsl-Serve 的最初选型仅说明 sing-box 来源, 独立 AnyTLS 脚本已退役.
