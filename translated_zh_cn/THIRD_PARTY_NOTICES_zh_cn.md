# 第三方声明

[English](../THIRD_PARTY_NOTICES.md) | **简体中文**

> 译自 `THIRD_PARTY_NOTICES.md`（v1.0.3）。如有冲突，以英文版为准；许可证与 NOTICE 原文以其各自的原始文本为准。

本项目本身以 GPL-3.0 授权（见 [`LICENSE`](../LICENSE)）。之所以选择 GPL-3.0 而非更宽松的许可证，是因为本项目重新分发了 sing-box 可执行文件，而该文件是 GPL-3.0 授权的；组合作品也必须采用相同许可证。从 `vps-webserver`（上游为 Apache-2.0）搬运来的代码，在本项目中以 GPL-3.0 重新分发——Apache-2.0 允许这样做，反过来则不被允许。

本项目没有第三方 Python 包。`app.py` 仅使用标准库，因此没有需要审计的锁定文件，也没有需要持续打补丁的依赖。

---

## sing-box

本仓库在仓库根目录以 `sing-box` 文件名重新分发了未经修改的官方 sing-box 可执行文件。它被安装为 `/usr/local/bin/sing-box-vps-server`。

- 组件：`sing-box`
- 上游项目：https://github.com/SagerNet/sing-box
- 上游版权声明：Copyright (C) 2022 by nekohasekai <contact-sagernet@sekai.icu>
- 版本：`v1.13.14`
- 源码版本：`25a600db24f7680ad9806ce5427bd0ab8afe1114`
- 分发的构件：`sing-box-1.13.14-linux-amd64.tar.gz`
- 仓库内二进制文件的 SHA-256：`68aeab83cc4ab2659a5b92232261a20746ccdafc3b3d1e19b2d63247eec3bbf7`
- 许可证：GNU GPL 第 3 版或其任意后续版本，另附上游的名称/关联条件；详见 [`LICENSES/sing-box-LICENSE`](../LICENSES/sing-box-LICENSE)

本仓库中的可执行文件已与官方上游 Release 归档中的可执行文件逐字节比对，确认未经修改。

### 对应源码

该确切二进制文件所对应的完整源码可免费获取，地址如下：

- 打了标签的源码树：https://github.com/SagerNet/sing-box/tree/v1.13.14
- 确切的源码版本：https://github.com/SagerNet/sing-box/tree/25a600db24f7680ad9806ce5427bd0ab8afe1114
- 源码归档：https://github.com/SagerNet/sing-box/archive/refs/tags/v1.13.14.tar.gz

本项目所使用的官方二进制 Release 为：

- https://github.com/SagerNet/sing-box/releases/download/v1.13.14/sing-box-1.13.14-linux-amd64.tar.gz

本项目是独立项目，与 sing-box 或 SagerNet 的作者没有关联，也未获得其背书。

---

## LibreSpeed

浏览器测速功能使用了 LibreSpeed 自身的客户端引擎，未经修改地搬运至本项目。

- 组件：LibreSpeed 客户端引擎 —— `static/speedtest.js`、`static/speedtest_worker.js`
- 上游项目：https://github.com/librespeed/speedtest
- 版本：`v6.2.1`
- 许可证：GNU LGPL 第 3 版；全文见 [`static/licenses/LGPL-3.0.txt`](../static/licenses/LGPL-3.0.txt)
- 是否修改：否。这两个文件与上游发行版逐字节一致。

`static/speedtest-ui.js` 是本项目自己编写的胶水代码，不属于 LibreSpeed 的一部分。`app.py` 中的服务端接口（`/speedtest/garbage`、`/speedtest/empty`、`/speedtest/getip`）重新实现了 LibreSpeed 文档中记载的客户端/服务端约定，属于原创代码，并非派生自上游的 PHP 后端。

LGPL-3.0 允许与本 GPL-3.0 作品组合使用。

---

## iperf3

- 组件：`iperf3`
- 上游项目：https://github.com/esnet/iperf
- 许可证：BSD 3-Clause
- 是否修改：否
- **未随本项目重新分发。** `iperf3` 由 `install.sh` 从操作系统的软件包仓库安装，并作为独立程序跨进程边界调用。本仓库不包含任何 iperf3 的代码或二进制文件，因此附带于"重新分发"行为的 BSD 署名要求在此并未触发。之所以仍将其列出，是因为本项目在运行时依赖它，读者应当了解其来源。

---

## 搬运自本作者自有项目的代码

不属于第三方代码，但因其并非源自本仓库，其来源对后续更新而言仍需记录：

- `app.py`、`static/speedtest-ui.js`、`static/style.css`、`static/visitors.js`、
  `tests/`、`install.sh`、`uninstall.sh`、`systemd/` —— 来自 `vps-webserver`
  v0.4.1（上游为 Apache-2.0，在此重新授权为 GPL-3.0）。详见 `.upstream-version`。
- `anytls/setup-anytls.sh`、`sing-box`、`anytls/sing-box.version` —— 来自
  `Anytsl-Serve` v1.2.0（上游为 GPL-3.0）。详见 `anytls/.upstream-version`。

---

本项目不包含任何第三方字体、图标、图像、数据集或模型权重。服务在运行时不会发起任何出站请求；唯一可选的出站调用是安装过程中的一次公网 IP 查询，若失败则降级为警告，不影响安装继续进行。
