# vps-server

[English](../README.md) | **简体中文**

> 译自 `README.md`（v1.0.3）。如有冲突，以英文版为准。

一套一条命令搞定的 Debian/Ubuntu VPS 组合包：一个任何人都能访问、用来证明你的 IP 网页端口可达的公开页面，一个带密码保护、用于测速和连接记录的控制台，一个按需开启的 iperf3 窗口，以及一个 anytls 代理。

## 它做什么

- **向任何人证明可达性。** 端口 **80** 和 **443** 上有一个刻意做得极简、无需登录的页面。把 IP 给别人，如果页面能渲染出来，说明你的网页端口从对方所在的位置是可达的。它会报告对方的源 IP、服务器时钟，以及对方是通过哪个端口和协议连进来的——除此之外不透露主机的任何信息。
- **从浏览器测量吞吐量。** 一个带密码保护、位于持久化随机高位端口上的控制台，用 LibreSpeed 引擎跑上传/下载测试。
- **用 iperf3 按需测量吞吐量和延迟。** 控制台会开启一个限时窗口；`iperf3 -s` 只在窗口期内运行，窗口到期后会自我关闭。测试者能从 iperf3 拿到带宽，在 Linux 客户端上还能从其 `--json` 输出的 `mean_rtt` 字段拿到往返时延——该字段来自内核的 `TCP_INFO`，在读不到它的客户端上会缺失，最典型的就是 Windows 上 Cygwin 环境下的 iperf3。UDP 模式（`-u`）在任何平台上都会额外报告抖动和丢包。
- **记录谁连接过。** 任意端口上的每一次入站 TCP 连接都会被记录，不只是 HTTP——从 `/proc/net/tcp[6]` 读取，存入 SQLite，保留最近 1000 条。
- **提供 anytls 代理服务。** sing-box 配合自签名证书，外加 BBR。安装了该模块后，控制台会新增一个页面，显示节点是否在线，并提供其 Clash 配置条目和带复制按钮的 `anytls://` 链接，因此把节点交给客户端使用不需要再回到终端。

web、iperf3、anytls 这三个模块中的每一个，都可以在安装时选择是否启用。

**非目标：** 不涉及 ACME 或域名（443 端口刻意使用自签名证书）；不提供常驻运行的 iperf3；不提供反向代理或容器化；公开页面永远不会透露主机名、内核版本、运行时长、服务列表或代理参数。本项目不会替代 `vps-webserver` 或 `Anytsl-Serve`——二者都仍独立维护，它们的代码在本项目中是以 vendor 方式引入的，而非被吸收合并。

## 环境要求

- 操作系统：Debian 11+ 或 Ubuntu 20.04+，systemd，以 root 身份运行
- 运行时：Python 3.9+（发行版自带的 `python3` 即可——不需要安装任何 Python 依赖）
- 架构：web 和 iperf3 模块支持任意架构；anytls **仅支持 x86-64**，因为随附的 sing-box 二进制文件是 amd64 架构的
- 端口 80 和 443 必须空闲——如果已有 nginx、Apache、Caddy 或 `vps-webserver` 占用，安装程序会拒绝安装，而不是与其抢占端口
- 外部服务：无。安装只需要你所在发行版的软件包镜像源。

## 安装

```bash
# Always clone a tag, not the default branch — the branch tip may be mid-work.
# Latest release tag: git ls-remote --tags https://github.com/CharlesGool/vps-server.git
git clone --branch v1.0.3 --depth 1 https://github.com/CharlesGool/vps-server.git vps-server
cd vps-server
cp .env.example .env   # optional — every variable has a working default
bash install.sh
```

`install.sh` 会询问要安装哪些模块、界面语言、是否给控制台加密码保护，以及使用哪些端口。

**重新运行它会就地升级。** 它会检测到已有的安装，提示是否保留其配置，并只询问已安装版本没有的那些设置——每个问题都带默认值，所以直接按回车也是有效答案。控制台密码、持久化端口、证书、访客日志以及 anytls 节点的凭据都会保留下来。如果对升级提示回答 `n`，则会重新询问所有设置。

## 快速开始

```bash
bash install.sh                              # interactive: modules, language, password, port
sudo VPSSRV_MODULES=web,iperf3 bash install.sh   # unattended, no prompts
systemctl status vps-server-web              # is it up
bash anytls/setup-anytls.sh status           # anytls node details, if that module is installed
```

然后，从另一台机器上：

```bash
curl -sS  http://<ip>/                     # reachability over plain HTTP
curl -sSk https://<ip>/                    # ... and over TLS (self-signed)
iperf3 -c <ip> -p 5201 --json              # only while a window is open
```

## 验证是否生效

运行 `bash install.sh` 后，你应该会看到一个摘要块，列出每个已安装模块及其端口。然后：

- `systemctl status vps-server-web` 报告 `active (running)`。
- 从**另一台机器**打开 `http://<ip>/` 会渲染出一个标题为 "Reachable" 的页面，显示你自己的公网 IP。打开 `https://<ip>/` 在你接受证书警告后会显示同一个页面，协议这一行显示为 HTTPS。
- 登录 `http://<ip>:<console port>/` 会看到仪表盘，其中 iperf3 控制项存在，窗口处于关闭状态。
- 开启一个 5 分钟的窗口后，在另一台机器上运行 `iperf3 -c <ip> -p 5201 --json` 会报告吞吐量数值，并包含 `mean_rtt`。五分钟后同一条命令会连接失败——这是窗口自我关闭，不是故障。
- 如果安装了 anytls：`systemctl status vps-server-anytls` 报告 `active (running)`。

## 配置

每个变量都有可用的默认值；`.env` 是可选的。最关键的几个：

| 变量 | 含义 | 默认值 | 是否必需 |
|---|---|---|---|
| `VPSSRV_PUBLIC_HTTP_PORT` | 公开可达性页面，明文 | `80` | 否 |
| `VPSSRV_PUBLIC_HTTPS_PORT` | 公开可达性页面，TLS | `443` | 否 |
| `VPSSRV_PUBLIC_ENABLE` | 是否提供公开页面 | `1` | 否 |
| `VPSSRV_CONSOLE_PORT` | 控制台端口；`0` 表示自动生成并记住 | `0` | 否 |
| `VPSSRV_AUTH` | 控制台是否需要密码 | `1` | 否 |
| `VPSSRV_IPERF_PORT` | 开启的 iperf3 窗口监听的端口 | `5201` | 否 |
| `VPSSRV_IPERF_MAX_MINUTES` | 控制台不能超过的上限 | `60` | 否 |
| `VPSSRV_DEFAULT_LANG` | `en` / `zh_cn` / `zh_tw` | `en` | 否 |

完整参考：见 `DESIGN.md` → 配置参考。

## 卸载

```bash
bash uninstall.sh              # removes whichever modules are installed, and the data
KEEP_DATA=1 bash uninstall.sh  # keeps the visitor database and the console password
```

## 许可证

GPL-3.0。本项目随附分发了 sing-box 的二进制文件，该文件是 GPL-3.0 授权的，因此整个合并作品也是 GPL-3.0——详见 `LICENSE`。随附引入的第三方组件、其版本，以及 GPL 要求提供的对应源代码链接，记录在 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) 中。

本项目与 sing-box/SagerNet 或 LibreSpeed 均无关联，也未获得其背书。
