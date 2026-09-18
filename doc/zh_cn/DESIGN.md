# vps-server — Design

[English](../DESIGN.md) | **简体中文** | [繁體中文](../zh_tw/DESIGN.md)

## 文档说明

- 项目概览：[README](README.md)
- 发布历史：[CHANGELOG](CHANGELOG.md)
- 当前状态：[STATUS](STATUS.md)
- 需求列表：[BACKLOG](BACKLOG.md)
- 被否决的方案：[DECISIONS](DECISIONS.md)
- 第三方声明：[THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES.md)

> 译自 `DESIGN.md`（v1.0.4）。如有冲突，以英文版为准。

> 本文档的成功标准：另一个人，在另一台机器上，能凭这份文档重建出这个项目。假设读者看不到你的机器。

## 目标与非目标

**目标**

- 在一台全新的 Debian/Ubuntu VPS 上，安装一个提供四项能力的单一软件包，
  每一项在安装时都可独立选择：
  1. **公开可达性页面** —— 一个刻意做得极简、无需鉴权、在 TCP **80 和 443**
     端口上提供服务的页面，让任何只拿到这个 IP 的人都能在浏览器里确认
     这台主机的 Web 端口从他所在的位置是否可达。
  2. **私有控制台** —— 一个有密码保护的仪表盘，运行在一个持久化的随机高位端口上，
     提供基于浏览器的上传/下载测速功能，以及最近观测到的入站连接日志。
  3. **按需开启的 iperf3 窗口** —— 一个带宽/延迟测试端点，**默认关闭**；
     操作员从控制台开启一个限时窗口，窗口到期后自动关闭。
  4. **anytls 代理** —— 一个使用自签名证书的 sing-box `anytls` 入站，外加 BBR。
- 在无法访问该发行版软件包镜像之外任何网络的情况下也能安装。sing-box 二进制文件
  随本仓库一起分发。
- 能与 `vps-webserver` 和 `Anytsl-Serve` 共存于同一台主机上，不与它们在
  systemd unit 名称、安装前缀、环境变量前缀或持久化端口上发生冲突。

**非目标**

- **不是 `vps-webserver` 或 `Anytsl-Serve` 的替代品。** 两者都会继续独立维护、
  独立发版。vps-server 只是把它们的代码内嵌（vendor）进来，而不是导入或取代它们；
  这样做在漂移问题上要承担什么代价、以及如何缓解，见 `DECISIONS.md`。
- **没有 ACME / Let's Encrypt / 域名。** 443 上的 TLS 是自签名证书。公开页面的
  职责只是回答"你到底能不能连到这个 IP"，浏览器的证书警告页面本身就已经回答了
  这个问题。证书续期和域名依赖对这个职责没有任何帮助。
- **没有常驻的 iperf3。** 一个无需鉴权的公开 `iperf3 -s` 会让任何陌生人随心所欲地
  占满这台主机的上行带宽。
- **公开页面不暴露关于主机的任何信息。** 没有主机名、没有内核版本、没有运行时长、
  没有服务清单、没有端口列表、没有 anytls 参数。它只报告：你连上了、它看到的
  源 IP、服务器时钟，以及你是通过哪个端口/协议到达的。
- **没有反向代理，没有 nginx，没有容器。** Python 进程自己终止 TLS，
  就像 `vps-webserver` 已经做的那样。
- **没有多服务器测速选择器。** 只有一台主机，就是这台。

## 架构

两个进程加一个临时子进程。彼此之间没有任何网络通信；控制台和公开页面是同一个
Python 进程里的两个监听器，在内存中共享状态。

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

                       ┌─── vps-server-anytls.service ───┐
  proxy client ──────► │  sing-box, anytls inbound, TLS  │
  :<random>            │  self-signed cert               │
                       └─────────────────────────────────┘
```

这两个 systemd unit 是相互独立的：任何一个都可以在不安装另一个的情况下安装，
彼此也不会重启对方。

### 为什么公开页面和控制台是两个独立的监听器

它们的安全姿态是完全相反的，把它们合并只会强迫其中一个放弃自己的姿态。
控制台需要鉴权、放在一个不可猜测的端口上，正是为了让它不那么容易被随意发现；
公开页面则必须容易被发现，且不能要求密码。所以：不同的端口、不同的请求处理器、
不同的路由表。一个打到 80/443 上的请求永远到不了控制台的路由，因为
`ProbeHandler` 根本没有那些路由——不是因为某个检查拦下了它。这正是重点所在：
一个鉴权检查可能有 bug，一个不存在的路由不可能有。

公开页面只在两个路径（`/` 和 `/favicon.ico`）上接受 `GET` 和 `HEAD`，其余一律
以 404 回应。它不读取查询字符串，不解析请求体，也不设置任何 cookie。

### 在已有安装上升级

`install.sh` 会检测已有的安装，并提供"保留其配置"的选项。选"是"会重放上一次
安装记录下来的内容；选"否"则重新询问所有内容。无论哪种情况，控制台密码、
持久化端口、证书和访客日志都会保留下来——因为安装程序从来不会去动这些文件。

有两份记录，因为它们回答的问题不同：

- **systemd unit 的 `Environment=` 那几行**记录的是"曾经被设置成什么"。重放它们
  是为了防止某个只设置过一次的项（比如自定义的公开端口、控制台上的 TLS）
  在下一次升级时悄悄回退到默认值。
- **`$PREFIX/.install-state`** 记录的是已安装版本"当时知道哪些东西"：它的版本号、
  它的模块列表，以及它所理解的每一个配置项的名字。unit 本身回答不了这个问题，
  因为它只记录被赋过值的配置项，这说不出当时到底存在哪些配置项。

第二份文件正是用来计算"这个版本新增了什么"的依据：拿这个版本所知道的配置项
减去印记（stamp）里列出的那些。每一个新增项都会附带其 `.env.example` 中的
默认值一并询问，直接按回车即可采用默认值。

一次早于这份印记出现的安装没有这样的列表。安装程序不会把一个猜测当作差异呈现，
而是明说自己无法判断，原样带过 unit 记录的一切，并指向重新询问的路径。模块检测
的降级方式也一样：没有印记时，它就从磁盘上现有的内容推断模块列表——
是否有 Web unit、是否有 anytls unit、是否装了 `iperf3`。

anytls 节点在升级过程中之所以能被保留，是因为安装程序会把它的端口和密码从
`config.json` 里读回来并重新传入。少了这一步，`setup-anytls.sh` 就会给
两者都默认生成新的随机值，导致每一个已配置的客户端都会在一次例行升级中失效——
见下面"已知限制与坑"那一节里的说明，这一点在*刻意*重新安装的情形下依然成立。

### 控制台的 anytls 页面

控制台从 `VPSSRV_ANYTLS_CONFIG` 中读取已安装的节点信息，并渲染出它的状态，
外加一份可直接粘贴使用的 Clash 配置条目和 `anytls://` 链接。

它自己写入的东西只有一样："重置端口和密码"这个按钮，而即便如此它也是委托出去
执行的。控制台本身不会直接去动 `config.json`——它会运行 `setup-anytls.sh reset`，
因为其中的执行顺序很容易出错：旧端口的防火墙规则必须先撤销，*然后*才能开放
新端口，否则每次重置都会留下一条对应端口已无人监听的 `ACCEPT` 规则。这部分逻辑
留在拥有该节点的脚本里，而不是分散在两处。这个重置操作要求一个在服务端做校验的
确认复选框——标记上 `required` 拦下的是误点，而不是非浏览器的客户端——因为
轮换凭据会让所有已配置的客户端在拿到新凭据之前统统失效。

它还会**在这个服务自身的沙箱之外**运行，通过 `systemd-run --pipe --wait --collect`
作为一个临时 unit 执行。Web unit 启用了 `ProtectSystem=strict`，只对
`ReadWritePaths=$PREFIX` 开放写权限，因此 `/etc` 对它来说是只读的，而一次重置
需要写 `/etc/vps-server-anytls` 和一个 unit 文件。第一次真正尝试时就恰恰因为这个
原因在中途挂掉了——而且是在它已经撤销了旧端口防火墙规则之后。另一种做法，把
`/etc/systemd/system` 加进 `ReadWritePaths`，会为了让这一个按钮生效而永久放宽
这个长期运行服务的写权限；沙箱的价值比这更高。不使用 `systemd-run` 时，调用会
直接执行，这是正确的，因为缺少 `systemd-run` 的环境正好也是 `install.sh` 会
省略加固措施的那些环境。

`setup-anytls.sh reset` 还会在动防火墙之前先检查自己是否具备写权限。一次在撤销
旧规则之后才失败的重置，会留下一个跑着却无法进入的节点，这比一个从未启动的节点
还要糟糕。

有两个细节是关键性的（load-bearing）。**节点密码在这个页面上是明文显示的**，
这只有在这个页面挂在 `ConsoleHandler`、登录之后才能被接受；`ProbeHandler` 完全没有
通往它的路由，并且有一个测试专门断言公开监听器对 `/anytls` 返回 404、且永远不会
包含这个密码。而且**服务器地址取自请求的 `Host` 头**，而不是查出来的：不管是
什么地址连到了控制台，同一个地址也能连到节点；在渲染时做一次出站 IP 查询会与
"不发出站请求"这条规则相矛盾，而任何需要不同地址的人都可以在复制之后自己改一下
那一行。

SNI 根本没有存在 sing-box 的配置里——`setup-anytls.sh` 只把它烘焙进了自签名证书的
CN 字段——所以控制台是从证书里把它读回来的，而不是另外保留一份可能会漂移的
副本。

### iperf3 窗口的生命周期

1. 操作员登录控制台，选择一个时长（默认 10 分钟，上限由 `VPSSRV_IPERF_MAX_MINUTES`
   限定），点击打开。
2. 控制台把 `iperf3 -s -p <port>` 作为子进程启动，在当前生效的防火墙上开放该端口，
   并把截止时间记在内存里。
3. 窗口开启期间，**公开页面**会显示 iperf3 正在接受连接、在哪个端口上、还剩多少
   时间——远端的测试者需要知道这些信息，而且这不属于敏感信息：这个窗口本来就是
   刻意开放的。
4. 到达截止时间（或操作员主动请求关闭、或服务停止）时，子进程会被终止，防火墙
   规则也会被撤销。

这个窗口的状态保存在内存里，不落盘：如果服务挂掉，窗口也就随之消失，这是失败时
更安全的方向。一次重启永远不会把一个已开启的窗口复活。

延迟数据取自 iperf3 自身 `--json` 输出中的（TCP 信息块里的）`mean_rtt` 字段，
是在测试者一侧读到的；服务端不需要为此额外写任何代码。这个字段来自内核的
`TCP_INFO`，因此在 Linux 客户端上存在，在读不到它的客户端上则缺失——例如
Windows 上 Cygwin 下的 iperf3 会报告吞吐量但没有 `mean_rtt`。UDP 模式（`-u`）
在任何环境下都会报告抖动和丢包，当测试者不在 Linux 上时，这是更具可移植性的
方案。

## 技术栈

| 层 | 选择 | 版本 | 原因 |
|---|---|---|---|
| 运行时 | Python，仅标准库 | 3.9+ | 继承自 `vps-webserver`：不用第三方包意味着在全新 VPS 上没有依赖解析，也没有需要持续打补丁的东西 |
| HTTP 服务器 | `http.server.ThreadingHTTPServer` | stdlib | 三个监听器各自的请求量都不大；上框架只是死重量 |
| TLS | `ssl` + `openssl` 生成的自签名证书 | stdlib / 发行版 | 没有域名、没有 ACME（见非目标） |
| 存储 | `sqlite3` | stdlib | 访客日志必须能扛过重启 |
| 测速引擎 | LibreSpeed，原样内嵌（vendored） | v6.2.1 | LGPL-3.0；已经在 `vps-webserver` 中内嵌并跑通 |
| 带宽探测 | 发行版自带的 `iperf3` | 随发行版锁定 | 测试者在客户端一侧本来就已经普遍具备的事实标准工具 |
| 代理核心 | sing-box，内嵌二进制（amd64） | v1.13.14 | GPL-3.0；直接分发二进制能让安装保持离线可用 |
| Init | systemd | — | 目标操作系统的默认选择 |
| 安装脚本 | Bash | — | 继承自两个上游项目 |

被拒绝的替代方案及其取舍理由都留在 `DECISIONS.md` 里——这里不重复。

## 复现要求

### 环境

- 操作系统：Debian 11+ / Ubuntu 20.04+，systemd，以 root 身份运行
- 运行时：Python 3.9+（发行版自带的 python3 即可）
- 架构：anytls 模块**仅限 x86-64**——内嵌的 sing-box 二进制是 amd64 的。
  Web 模块和 iperf3 模块与架构无关。
- 硬件：无需 GPU；磁盘约 150 MB（其中约 57 MB 是 sing-box 二进制），内存
  只需 VPS 通常具备的量即可
- 依赖恢复命令：无。因为没有 Python 依赖，所以也没有 Python 锁文件；见
  `THIRD_PARTY_NOTICES.md`。

### 外部依赖

| 项目 | 来源 | 存放位置 |
|---|---|---|
| `iperf3` | 发行版包管理器（`apt-get install iperf3`） | 系统路径 |
| `openssl`、`curl`、`jq`、`iproute2` | 发行版包管理器 | 系统路径 |
| sing-box 二进制 | 随本仓库分发 | `/usr/local/bin/sing-box-vps-server` |
| LibreSpeed 引擎 | 随本仓库分发 | `$PREFIX/static/` |
| TLS 证书 | 由安装程序在首次运行时生成 | `$VPSSRV_CERT_DIR` |

不需要任何 API key。服务在运行时不发起任何出站请求，唯一的例外是安装过程中
可选的公网 IP 查询，失败时会降级为一条警告。

### 路径与挂载

| 路径 | 由谁提供 | 用途 |
|---|---|---|
| `$PREFIX` | 安装程序，默认 `/opt/vps-server` | 代码、静态资源、持久化端口文件 |
| `$VPSSRV_DATA_DIR` | 安装程序，默认 `$PREFIX/data` | `visitors.db`、`session_secret.txt` |
| `$VPSSRV_CERT_DIR` | 安装程序，默认 `$PREFIX/certs` | 443 用的自签名证书和密钥 |
| `/etc/vps-server-anytls/` | 安装程序 | sing-box 的 `config.json` 及其自身的自签名证书 |

### 配置参考

所有变量都使用 `VPSSRV_` 前缀。这不是装饰性的：`vps-webserver` 占用
`VPSWS_` 前缀，`Anytsl-Serve` 占用 `ANYTLS_` 前缀，三者可能同时装在一台主机上，
如果前缀共用，一个项目的 `.env` 就可能悄悄改动另一个项目的配置。

| 变量 | 含义 | 默认值 | 是否必需 |
|---|---|---|---|
| `PREFIX` | 安装根目录。传给 `install.sh`/`uninstall.sh`，**不**从 `.env` 中读取——因为在还没有安装、也就没有 `.env` 可读之前，就已经需要这个路径了 | `/opt/vps-server` | 否 |
| `VPSSRV_DATA_DIR` | SQLite + 会话密钥 | `$PREFIX/data` | 否 |
| `VPSSRV_HOST` | 所有监听器的绑定地址 | `0.0.0.0` | 否 |
| `VPSSRV_PUBLIC_HTTP_PORT` | 公开可达性页面，明文 | `80` | 否 |
| `VPSSRV_PUBLIC_HTTPS_PORT` | 公开可达性页面，TLS | `443` | 否 |
| `VPSSRV_PUBLIC_ENABLE` | 是否提供公开页面 | `1` | 否 |
| `VPSSRV_CONSOLE_PORT` | 控制台端口；`0` = 生成一次并持久化 | `0` | 否 |
| `VPSSRV_CONSOLE_PORT_FILE` | 生成的控制台端口记在哪里 | `$PREFIX/console_port.txt` | 否 |
| `VPSSRV_CONSOLE_TLS` | 控制台是否走 HTTPS | `0` | 否 |
| `VPSSRV_AUTH` | 控制台是否要求登录 | `1` | 否 |
| `VPSSRV_PASSWORD_FILE` | 明文的控制台密码，操作员可编辑 | `$PREFIX/admin_password.txt` | 否 |
| `VPSSRV_CERT_DIR` | 自签名证书的位置 | `$PREFIX/certs` | 否 |
| `VPSSRV_TLS_CERT` / `VPSSRV_TLS_KEY` | 改用操作员自备的证书 | — | 否 |
| `VPSSRV_IPERF_PORT` | iperf3 窗口监听的端口 | `5201` | 否 |
| `VPSSRV_IPERF_DEFAULT_MINUTES` | 预填的窗口时长 | `10` | 否 |
| `VPSSRV_IPERF_MAX_MINUTES` | 控制台不可超过的硬上限 | `60` | 否 |
| `VPSSRV_IPERF_ENABLE` | 是否允许开启窗口 | `1` | 否 |
| `VPSSRV_TRUST_PROXY` | 记录访客时是否信任 `X-Forwarded-For` | `0` | 否 |
| `VPSSRV_TRACK_CONNECTIONS` | 是否轮询 `/proc/net/tcp[6]` 以记录所有端口的连接 | `1` | 否 |
| `VPSSRV_CONN_POLL_SECONDS` | 轮询间隔 | `5` | 否 |
| `VPSSRV_MAX_TEST_MB` | 单次测速传输量上限，单位 MB | `200` | 否 |
| `VPSSRV_TEST_SECONDS` | 每个方向的测量窗口 | `10` | 否 |
| `VPSSRV_WARMUP_SECONDS` | 每个方向开始时被丢弃的预热时长 | `2` | 否 |
| `VPSSRV_DOWNLOAD_STREAMS` / `VPSSRV_UPLOAD_STREAMS` | 每个方向的并行流数 | `6` / `3` | 否 |
| `VPSSRV_PING_SAMPLES` | 用于计算延迟数值的往返次数 | `20` | 否 |
| `VPSSRV_DEFAULT_LANG` | `en` / `zh_cn` / `zh_tw` | `en` | 否 |
| `ANYTLS_PORT`、`ANYTLS_PASSWORD`、`SNI`、`SERVER_IP` | anytls 模块沿用上游的变量名 | 见 `.env.example` | 否 |
| `VPSSRV_ANYTLS_CONFIG` | 控制台从哪里读取已安装的节点信息 | `/etc/vps-server-anytls/config.json` | 否 |
| `VPSSRV_ANYTLS_SERVICE` | 控制台用来检查节点存活状态的 unit | `vps-server-anytls.service` | 否 |
| `VPSSRV_ANYTLS_SETUP` | 控制台用来轮换该节点凭据所运行的脚本 | `$PREFIX/anytls/setup-anytls.sh` | 否 |

anytls 模块刻意沿用了 `Anytsl-Serve` 的变量名，而不是重命名成
`VPSSRV_ANYTLS_*`：因为内嵌的配置生成器要读这些变量，重命名就意味着要去改动
内嵌的代码，而这正是内嵌（vendoring）策略本来要避免的事。

## 从零开始搭建

1. `git clone <repo>` 并 `cd` 进去——验证：`ls sing-box` 能看到一个约 57 MB 的文件。
2. `bash install.sh` ——安装程序会询问要安装哪些模块、界面语言、是否给控制台加
   密码保护，以及各端口。验证：它会打印一个汇总区块，列出每个已安装的模块及其
   端口。
3. `systemctl status vps-server-web` ——验证：`active (running)`。
4. 从另一台机器上打开 `http://<ip>/` ——验证：可达性页面能正常渲染，并显示出
   你自己的源 IP。
5. 从另一台机器上打开 `https://<ip>/` 并接受证书警告——验证：同一个页面，
   协议那一行显示为 HTTPS。
6. 打开 `http://<ip>:<console port>/` 并登录——验证：仪表盘能加载出来，并且
   iperf3 控制项显示窗口处于关闭状态。
7. 从控制台打开一个 5 分钟的 iperf3 窗口，然后在另一台机器上运行
   `iperf3 -c <ip> -p 5201 --json` ——验证：能报告出吞吐量，且输出中存在
   `mean_rtt`。
8. 如果安装了 anytls 模块：`systemctl status vps-server-anytls` ——验证：
   `active (running)`；安装程序的汇总信息里打印出了一行客户端配置。

## 数据模型 / 文件布局

```
repo/
├── install.sh                 # module-selecting installer (web / anytls / iperf3)
├── uninstall.sh               # removes the modules it finds
├── app.py                     # the web service: console + public listeners
├── static/                    # LibreSpeed engine (vendored) + own UI assets
├── systemd/
│   └── vps-server-web.service # the anytls unit is not here: setup-anytls.sh
│                              # writes it at install time, so it is never
│                              # shipped and never stale
├── anytls/
│   ├── setup-anytls.sh        # vendored from Anytsl-Serve, renamed units/paths
│   ├── sing-box.version       # which sing-box release the binary below is
│   └── .upstream-version      # records: Anytsl-Serve v1.2.0
├── sing-box                   # vendored amd64 binary
├── .upstream-version          # records: vps-webserver v0.4.1
├── tests/
├── LICENSE                    # GPL-3.0
├── LICENSES/                  # upstream licence texts
└── <the six governance docs + two translated_* trees>
```

SQLite 的表结构原样继承自 `vps-webserver`：只有一张 `visits` 表，会裁剪到只保留
最近的 1000 行。

## 已知限制与坑

- **绑定 80 和 443 需要 root 权限，并且这两个端口必须原本是空闲的。** 如果 nginx、
  Apache、Caddy，或者另一个 `vps-webserver` 实例已经占用了其中任意一个端口，
  安装程序会直接拒绝安装，而不是去抢占它。安装前请先用
  `ss -lntp '( sport = :80 or sport = :443 )'` 检查一下。
- **公开页面确实是公开的。** 任何猜到或扫描到这个 IP 的人都能看到它，每一次这样
  的访问都会进入访客日志。这是设计上的特性，但也意味着一个被扫描到的 IP 上的
  访客日志会在几小时内被互联网背景噪声塞满。
- **Unit 名称与上游有意不同。** `Anytsl-Serve` 安装的是
  `sing-box-anytls.service`；本项目安装的是 `vps-server-anytls.service`，
  以及一个单独命名的二进制文件，因此两者可以共存。不过如果检测到上游的
  unit 正在运行，安装程序仍然会拒绝继续，因为一台主机上同时存在两个 anytls
  入站，几乎可以肯定是失误而不是本意。
- **`iperf3` 没有锁定版本。** 它来自发行版，版本会随发行版而变化。协议在
  3.x 这条线上一直保持稳定，但如果客户端版本比服务端老很多，可能会在版本
  握手上失败。
- **anytls 仅支持 amd64。** 内嵌的二进制不是多架构的；在 arm64 上，安装程序
  会跳过这个模块并给出说明，而不是安装一个根本跑不起来的二进制。
- **自签名 TLS 意味着每次访问 443 都会有浏览器警告。** 这是预期行为，不值得为了
  "修掉"它而加例外或 HSTS 头。
- **重启会关闭任何已开启的 iperf3 窗口。** 这是有意为之的；见前面的生命周期
  一节。
- **sing-box 二进制超过了 GitHub 建议的文件大小。** 大约 55 MB，超过了
  50 MB 的软限制，因此每次 push 都会打印一条建议使用 Git LFS 的
  "Large files detected" 警告。Push 依然能成功；硬限制是 100 MB。未来
  sing-box 升级版本时可能最终会越过这个界限，到那时该怎么处理（用 LFS，还是
  不再随仓库分发这个二进制）应该是一个刻意做出的决定，而不是发版当天才碰到的
  意外。
- **运行脚本要用 `bash <script>`，不要用 `./<script>`。** 可执行位记录在
  git 索引里，所以一份全新的 clone 会带有这个位——但在 CIFS/SMB 挂载上的工作
  副本不会，在那上面执行 `./install.sh` 会失败，报 "Permission denied"。
- **重新内嵌任何可执行文件都会丢失它的权限位。** 维护者的工作副本在 CIFS 上，
  所以在那上面解压出来再 `git add` 的文件，即使上游是 `100755`，也会被记录成
  `100644`。这已经在 `sing-box` 二进制上发生过一次，并且弄坏了整个 anytls
  模块。重新内嵌之后，用 `git ls-files -s` 检查一下，并用
  `git update-index --chmod=+x <path>` 恢复这个位——在那个挂载上单独
  `chmod +x` 是没有效果的。
- **直接运行 `setup-anytls.sh` 会轮换它的端口和密码。** 它会把 `ANYTLS_PORT`
  和 `ANYTLS_PASSWORD` 默认成全新的随机值，并在每次运行时重写
  `config.json`，因此手动调用它会让此前配置的所有客户端全部失效。
  `install.sh` 现在已经不会这样做了——升级路径会把这两个值从 `config.json`
  里读回来并传进去——但直接调用仍然会这样。想要保留节点，就要传入当前的值，
  这两个值都能在控制台的 anytls 页面上找到：
  `ANYTLS_PORT=<current> ANYTLS_PASSWORD='<current>' bash anytls/setup-anytls.sh`。
  这是刻意继承下来的上游行为。`setup-anytls.sh reset` 才是有意去轮换它们的，
  控制台上的重置按钮是官方支持的、用来达到这个目的的方式。
- **控制台的公网地址区块只有在安装过 anytls 之后才会出现。**
  `public-ip.txt` 是由 `setup-anytls.sh` 写入的，因此早于这个文件存在的安装
  会一直只显示接口地址，直到这个模块被重新安装为止。这是拒绝在渲染时做出站
  查询所必须付出的代价。
- **拆卸时需要用与安装时相同的 `PREFIX` 和 `SERVICE_NAME`。** 不带任何环境变量
  运行 `uninstall.sh` 会读取默认值，在那些路径上什么都找不到，并报告"成功"，
  实际上什么都没删。安装程序结束时打印的那一行会给出填好了具体值的完整命令；
  请照抄那一行，而不是凭记忆自己敲。

## 如何扩展

- **新增一个模块**（安装程序可以选择性安装的其他东西）：新增一个
  `<name>/setup-<name>.sh`、一个 `systemd/vps-server-<name>.service`，在
  `install.sh` 的模块菜单里加一个分支，并在 `uninstall.sh` 里加一个对应的
  拆卸分支。各模块之间互不调用。
- **新增一个控制台页面**：给 `ConsoleHandler` 加一个路由。不要给
  `ProbeHandler` 加路由——它的路由表几乎为空是一个安全属性，不是疏漏。
- **新增一种语言**：扩展 `app.py` 里的 `STRINGS` 表和 `install.sh` 里的
  `msg()` 表，然后新增一个 `translated_<lang>/` 目录树。
- **新增一种颜色**：在 `static/style.css` 的 `:root` 里加一个 token，*并且*
  在 `prefers-color-scheme: light` 区块里补上对应的浅色模式的值，然后使用
  这个 token。不要在组件规则里直接写十六进制颜色值——字面量没法跟着主题走，
  所以它只在被人肉眼调出来的那个模式下是对的，在另一个模式下就是错的，而且
  没有任何机制会报告这个问题。任何被用作填充背景的值都需要一个配对的
  `--on-*` 前景色：读起来适合作为文字的值，往往并不是在白色文字背后读起来
  合适的值。提交前请在两种模式下都对照 WCAG AA（4.5:1）检查一遍；
  `tests/test_app.py::StylesheetTest` 会强制检查这里面结构性的那一半，但
  没法判断对比度。
- **刷新一个内嵌的上游依赖**：从上游的 tag 重新拷贝，在同一个 commit 里更新
  对应的 `.upstream-version` 文件，并在 `CHANGELOG.md` 里记一笔这次升级。
  绝不要就地手改内嵌代码——一个没有反映回上游的本地改动，会让下一次刷新
  变成一次悄无声息的回退。
</content>
</invoke>
