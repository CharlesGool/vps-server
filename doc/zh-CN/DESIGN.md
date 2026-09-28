---
name: project-design-zh-cn
description: 项目架构与设计约束
metadata:
  version: "1.0.0"
  lang: "zh-CN"
---

# vps-server — Design

## 多语言

[English](../DESIGN.md) | **简体中文** | [繁體中文(台灣)](../zh-TW/DESIGN.md) | [繁體中文(香港)](../zh-HK/DESIGN.md) | [हिन्दी](../hi/DESIGN.md) | [Español](../es/DESIGN.md) | [العربية](../ar/DESIGN.md) | [Français](../fr/DESIGN.md)

## 文档

- 项目概览:[README](README.md)

- 设计思路:[DESIGN](DESIGN.md)

- 发布历史:[LOG](LOG.md)

- 第三方声明:[THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES.md)

## 设计目标

**v2.0.0 已实现的目标(见[验收限制][local-link-001]):**

v2.0.0 也包含实验性的 frps 和 Lucky 安装路径.它们尚未在真实主机上完成行为验收;以下目标描述此前已记录的四个模块.

- 在一台全新的 Debian/Ubuntu VPS 上,安装一套可选择四个模块,提供五种能力的软件包
  (web 模块包括公开页面及私有控制台):
  1. **公开可达性页面** —— 一个刻意做得极简,无需鉴权,在 TCP
     **80 和 443**
     端口上提供服务的页面,让任何只拿到这个 IP 的人都能在浏览器里确认
     这台主机的 Web 端口从他所在的位置是否可达.
  2. **私有控制台** —— 一个运行在持久化随机高位端口的仪表盘,提供浏览器上传/下载测速和近期入站连接日志.可使用管理员密码,或明确加入名单的私有局域网 IP 访问.
  3. **按需开启的 iperf3 窗口** —— 一个带宽/延迟测试端点,
     **默认关闭**;
     操作员从控制台开启一个限时窗口,窗口到期后自动关闭.
  4. **anytls 代理** —— 一个使用自签名证书的 sing-box `anytls` 入站,外加 BBR.
  5. **proxy** —— 可选择任意子集的 sing-box `vmess`/`vless`/`trojan`/`shadowsocks` 入站,共用一个 systemd unit,一份配置,以及 anytls 模块使用的同一个随附 sing-box 二进制文件.详见下文“proxy 模块”.
- 在无法访问该发行版软件包镜像之外任何网络的情况下也能安装.sing-box 二进制文件
  随本仓库一起分发.
- 能与 `vps-webserver` 和 `Anytsl-Serve` 共存于同一台主机上,不与它们在
  systemd unit 名称,安装前缀,环境变量前缀或持久化端口上发生冲突.

**持续跟踪的目标与当前状态:**

- [x] 2026-09-19 按节点统计流量并设置流量上限:五种代理协议分别统计上传与下载.原有达到上限后双向限速 1 Mbps 及每月或指定时间重置的行为已于 2026-09-27 通过真实主机测试.当前分支新增上传与下载独立限速,达到流量上限后选择双向限速 1 Mbps 或停止使用,按天/月/年设置重复周期,以及到期后停止使用的可选有效期.新规则与状态迁移通过自动化检查;测试机已验证界面和迁移,尚未逐一验证真实流量.
- [x] 2026-09-19 基于浏览器的初次配置:当前检出版本使用 `tools/setup_wizard/setup_wizard.py` 提供短时有效的设置向导,触发条件是交互式安装程序未设置 `VPSSRV_MODULES`.向导收集语言,模块,端口及鉴权选择;Shell 安装程序验证结果后才执行所选操作.当前检出版本尚未通过真实主机验收.
- [ ] 2026-09-22 完成显示令牌和连接信息的 frps 控制台支持.当前检出版本已提供 frps 安装选项,但控制台要求仍未限定范围:须确定令牌信息是指鉴权令牌,客户端配置片段还是已连接代理列表.
- [ ] 明确 2026-09-22 状态快照所记录的更广泛的 `gdy666/lucky` 功能请求范围.当前检出版本已提供 Lucky 安装路径,但当时没有记录更广泛的功能列表或验收标准.
- [x] 完成节点控制的实机验收:删除节点后显示编号保持连续,全部删除后新节点从 1 开始,隐藏的 UUID 保持身份不变;名称,端口,凭据和 TLS SNI 可修改;Shadowsocks 的 SNI 显示为不适用;随机重置端口和凭据时保留 SNI.每个节点可单独停用并保留配置和流量记录,再用原端口启用.控制功能已于 2026-09-27 通过真实主机测试.
- [x] 整个 Web UI 已采用统一的浅色设计体系,覆盖控制台,公开连通页和安装向导.2026-09-27 的实现统一了间距和控件样式,提供四种可记忆的主题色,随附字体和图标,清晰的焦点状态以及响应式布局.

共用 SQLite 锁的疑虑是[尚未解决的测量问题][local-link-002],并非要求变更架构.历史已完成工作和验证记录见 [LOG][local-link-003].

**非目标**

- **不是 `vps-webserver` 或 `Anytsl-Serve` 的替代品.** 两者都会继续独立维护,
  独立发版.vps-server 只是把它们的代码内嵌(vendor)进来,而不是导入或取代它们;
  这样做在漂移问题上要承担什么代价,以及如何缓解,见[决策][local-link-004].
- **没有 ACME / Let's Encrypt / 域名.** 443 上的 TLS 是自签名证书.公开页面的
  职责只是回答"你到底能不能连到这个 IP",浏览器的证书警告页面本身就已经回答了
  这个问题.证书续期和域名依赖对这个职责没有任何帮助.
- **没有常驻的 iperf3.** 一个无需鉴权的公开 `iperf3 -s` 会让任何陌生人随心所欲地
  占满这台主机的上行带宽.
- **公开页面不暴露关于主机的任何信息.** 没有主机名,没有内核版本,没有运行时长,
  没有服务清单,没有端口列表,没有 anytls 参数.它只报告:你连上了,它看到的
  源 IP,服务器时钟,以及你是通过哪个端口/协议到达的.
- **没有反向代理,没有 nginx,没有容器.** Python 进程自己终止 TLS,
  就像 `vps-webserver` 已经做的那样.
- **没有多服务器测速选择器.** 只有一台主机,就是这台.

## 架构

Web 服务,anytls 服务和可选的 proxy 服务各自独立运行;Web 服务还会启动临时 iperf3 子进程.控制台和公开页面在一个 Python 进程中使用不同的监听器并共享内存状态.只有经过配置的客户端流量会到达这些服务.

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

图中显示 web 和 anytls unit;可选的 `vps-server-proxy.service` 在第三个进程中运行多个独立入站,共用随附的 sing-box 二进制文件,但不共用其他 unit 的状态.每个模块可分别选择;参见[proxy 模块][local-link-005].

### 为什么公开页面和控制台是两个独立的监听器

它们的安全姿态是完全相反的,把它们合并只会强迫其中一个放弃自己的姿态.
控制台需要鉴权,放在一个不可猜测的端口上,正是为了让它不那么容易被随意发现;
公开页面则**必须**容易被发现,
并且**不得**要求密码.所以:不同的端口,不同的请求处理器,
不同的路由表.一个打到 80/443 上的请求永远到不了控制台的路由,因为
`ProbeHandler` 根本没有那些路由——不是因为某个检查拦下了它.这正是重点所在:
一个鉴权检查可能有 bug,一个不存在的路由不可能有.

公开页面只接受 `GET` 和 `HEAD`,且仅限两个路径(`/` 和 `/favicon.ico`),其余一律
以 404 回应.它不读取查询字符串,不解析请求体,也不设置任何 cookie.

### 在已有安装上升级

`install.sh` 会检测已有的安装,并提供"保留其配置"的选项.选"是"会重放上一次
安装记录下来的内容;选"否"则重新询问所有内容.无论哪种情况,控制台密码,
持久化端口,证书和访客日志都会保留下来——因为安装程序从来不会去动这些文件.

有两份记录,因为它们回答的问题不同:

- **systemd unit 的 `Environment=` 那几行**记录的是"曾经被设置成什么".重放它们
  是为了防止某个只设置过一次的项(比如自定义的公开端口,控制台上的 TLS)
  在下一次升级时悄悄回退到默认值.
- **`$PREFIX/.install-state`** 记录的是已安装版本"当时知道哪些东西":它的版本号,
  它的模块列表,以及它所理解的每一个配置项的名字.unit 本身回答不了这个问题,
  因为它只记录被赋过值的配置项,这说不出当时到底存在哪些配置项.

第二份文件正是用来计算"这个版本新增了什么"的依据:拿这个版本所知道的配置项
减去印记(stamp)里列出的那些.每一个新增项都会附带其 `.env.example` 中的
默认值一并询问,直接按回车即可采用默认值.

一次早于这份印记出现的安装没有这样的列表.安装程序不会把一个猜测当作差异呈现,
而是明说自己无法判断,原样带过 unit 记录的一切,并指向重新询问的路径.模块检测
的降级方式也一样:没有印记时,它就从磁盘上现有的内容推断模块列表——
是否有 Web unit,是否有 anytls unit,是否装了 `iperf3`.

anytls 节点在升级过程中之所以能被保留,是因为安装程序会把它的端口和密码从
`config.json` 里读回来并重新传入.少了这一步,`setup-anytls.sh` 就会给
两者都默认生成新的随机值,导致每一个已配置的客户端都会在一次例行升级中失效——
见下面"已知限制与坑"那一节里的说明,这一点在*刻意*重新安装的情形下依然成立.

### 控制台的 anytls 区域

**现在位于 `/proxy`,而非独立页面**(2026-09-22):下文“proxy 模块”解释为什么 anytls 与 proxy 模块的协议合并到同一页面.`/anytls` 仍可用,但重定向至 `/proxy`,`POST /anytls/reset` 不变;仅删除独立的 `GET /anytls` 页面及其导航链接/仪表盘磁贴.以下内容仍描述该合并页面中的 anytls 分区.


控制台从 `VPSSRV_ANYTLS_CONFIG` 中读取已安装的节点信息,并渲染出它的状态,
外加一份可直接粘贴使用的 Clash 配置条目和 `anytls://` 链接.

它自己写入的东西只有一样:"重置端口和密码"这个按钮,而即便如此它也是委托出去
执行的.控制台本身不会直接去动 `config.json`——它会运行 `setup-anytls.sh reset`,
因为其中的执行顺序很容易出错:旧端口的防火墙规则要先撤销,*然后*才能开放
新端口,否则每次重置都会留下一条对应端口已无人监听的 `ACCEPT` 规则.这部分逻辑
留在拥有该节点的脚本里,而不是分散在两处.这个重置操作要求一个在服务端做校验的
确认复选框——标记上 `required` 拦下的是误点,而不是非浏览器的客户端——因为
轮换凭据会让所有已配置的客户端在拿到新凭据之前统统失效.

它还会**在这个服务自身的沙箱之外**运行,通过 `systemd-run --pipe --wait --collect`
作为一个临时 unit 执行.Web unit 启用了 `ProtectSystem=strict`,只对
`ReadWritePaths=$PREFIX` 开放写权限,因此 `/etc` 对它来说是只读的,而一次重置
需要写 `/etc/vps-server-anytls` 和一个 unit 文件.第一次真正尝试时就恰恰因为这个
原因在中途挂掉了——而且是在它已经撤销了旧端口防火墙规则之后.另一种做法,把
`/etc/systemd/system` 加进 `ReadWritePaths`,会为了让这一个按钮生效而永久放宽
这个长期运行服务的写权限;沙箱的价值比这更高.不使用 systemd-run 时,调用会
直接执行,这是正确的,因为缺少 `systemd-run` 的环境正好也是 `install.sh` 会
省略加固措施的那些环境.

`setup-anytls.sh reset` 还会在动防火墙之前先检查自己是否具备写权限.一次在撤销
旧规则之后才失败的重置,会留下一个跑着却无法进入的节点,这比一个从未启动的节点
还要糟糕.

有两个细节是关键性的(load-bearing).**节点密码在这个控制台分区上是明文显示的**,
这只有在这个页面挂在 `ConsoleHandler`,登录之后才能被接受;`ProbeHandler` 完全没有
通往它的路由,并且有一个测试专门断言公开监听器对 `/anytls` 返回 404,且永远不会
包含这个密码.而且**服务器地址取自请求的 `Host`
  头**,而不是查出来的:不管是
什么地址连到了控制台,同一个地址也能连到节点;在渲染时做一次出站 IP 查询会与
"不发出站请求"这条规则相矛盾,而任何需要不同地址的人都可以在复制之后自己改一下
那一行.

只有使用密码登录的管理员能在设置中加入单个私有局域网 IP.公网 IP 和网段会被拒绝.免密判断直接使用连接对端地址,不相信客户端提供的转发请求头;启用 `VPSSRV_TRUST_PROXY=1` 时,由于未配置可信代理边界,IP 免密会停用.IP 免密可访问普通控制台页面,修改密码或 IP 名单仍须密码登录.同一网关若将多台设备映射到同一个获准的私有 IP,这些设备都会获得访问权. 获准的访客须在登录页选择 IP 免密访问;会话绑定来源 IP,每次请求都会重新检查名单.移出名单后,下次请求立即失去免密访问权.

SNI 根本没有存在 sing-box 的配置里——`setup-anytls.sh` 只把它烘焙进了自签名证书的
CN 字段——所以控制台是从证书里把它读回来的,而不是另外保留一份可能会漂移的
副本.

### proxy 模块

旧需求曾询问随附的 sing-box 二进制文件能否支持 anytls 以外的协议,还是需要使用第二套后端.答案是前者:`vmess`,`vless`,`trojan`,`shadowsocks`(2022-blake3-aes-128-gcm)都通过 `sing-box check`;实际运行验证(并非仅检查配置)表明,四者可以在同一个 `sing-box run` 进程中同时绑定端口并接受连接.因此没有引入第二套后端.

与 anytls 不同,这里是**一个 systemd unit(`vps-server-proxy.service`)和一份 `config.json` 中
多个同时运行的入站**,而不是复制四份 anytls 的结构.理由:只需监控一个 unit,初次安装时共用一份自签名证书,后续新建 TLS 节点各有证书(shadowsocks 不需要证书),也符合未来按节点统计流量的需求——进程的 `inbounds` 数组已经是节点列表.`deploy/proxy/setup-proxy.sh` 是 vps-server 的自有代码,不是随附的上游副本;这四种协议均非源于 Anytsl-Serve.

该模块**与 anytls 共用随附的 sing-box 二进制文件**(`/usr/local/bin/sing-box-vps-server`),避免再携带约 57 MB 的副本.两模块各自的 `uninstall()` 都会在删除文件前检查*另一模块*的配置是否还存在.为此,anytls 随附的 `setup-anytls.sh` 增加了一项有记录的本地改动(见 `deploy/anytls/.upstream-version`):二进制文件不再仅由 anytls 自己持有.

`PROXY_PROTOCOLS`(逗号分隔,默认全部四种)会验证后存入全局数组,而不是通过 `$(...)` 命令替换输出.早期版本使用 `read -ra x <<< "$(fn)"` 调用验证函数:替换子 shell 中的 `exit 1` 只结束该子 shell,主脚本却带着空协议列表继续运行,启动零入站服务.属于与[决策][local-link-006]中的 `prompt_new_settings()` 相同类别的错误.每种协议的端口都从 60000 以下彼此独立,宽度 5000 的区间选择,而非从 60000 起宽度 10000 的区间:后一方案在抽到高位端口时会超出 sing-box 的 `uint16 listen_port` 上限 65535;五次重复的全新安装发现了该问题,首次安装未发现.升级时保留凭据的方式与 anytls 的 `preserve_anytls()` 相同:`preserve_proxy()` 从 `config.json` 中读回每种已装协议的端口,凭据和*协议集合*;重新运行时设置 `VPSSRV_MODULES=proxy` 不会暗中增删协议.

控制台 `/proxy` 页面为每个已装节点显示一个分区,包括端口,UUID 或密码,逐节点 SNI(从各自证书读取),以及每个已检测到地址的 Clash 条目和分享链接(`vmess://`,`vless://`,`trojan://`,`ss://`).**每种协议都有自己的重置按钮**,而非统一的“全部重置”:操作员指出,泄露一个 vmess UUID 不应迫使所有 trojan/vless/shadowsocks 客户端重新配置.`setup-proxy.sh reset <protocol>` 只轮换指定协议的端口和凭据;`load_installed_vars()` 会先从磁盘读回*其他*协议的现有值,保持它们不变.无参数的 `reset` 仍轮换所有已安装协议,但仅供终端/脚本使用,控制台不提供该操作.两种形式都通过沙箱外的 `systemd-run` 执行,与 `anytls_reset()` 相同,因为同样受 `ProtectSystem=strict` 限制.共用 systemd 服务确有代价:重置一种协议仍会重启整个服务,其他协议的*连接*短暂中断,但其凭据不变.

安装程序最初为每种选定协议创建一个入站.之后,受管控制台可以为任何已安装协议创建多个编号节点,逐个删除节点,也允许模块保留但没有监听器.节点 ID 稳定,在可见界面中隐藏;所有表单和 Clash 订阅均按 ID 定位,使同协议的节点彼此独立.连接编辑框在卡片原有信息的位置展开;独立的流量表单支持 GiB 上限,分别设置上传/下载 Mbps 限速,达到上限后的处理方式,重复重置间隔和可选有效期.重置只清零周期流量并解除流量上限处罚,不延长有效期.读取时将第一版节点清单迁移到第二版:旧的绝对到期日期会清除,避免原本的 1 Mbps 限速被误当成停止使用;节点身份,计数,上限及重置计划会保留.新增或删除节点时,在同一把锁下更新 sing-box 配置,节点清单,防火墙和 nft 计量状态,失败时回滚.新建的 TLS 节点拥有独立的自签名证书.控制台的自带字体使用 `font-display: optional`,避免首次显示后再换字体.

`PortForwardManager.reserved_ports()` 将所有已安装代理协议的端口,与 anytls 节点及控制台的端口一样视为保留端口;端口转发规则不能指向代理协议占用的端口.

**控制台 `/proxy` 页面也显示已安装的 anytls 节点.** 操作员认为把 anytls 放在独立页面是人为分割:不论两个独立后端分别提供什么节点,从使用者角度它们都是“代理节点”.`/anytls` 重定向到这里;`POST /anytls/reset` 保持原样,但完成后返回 `/proxy`.两个模块的状态仍完全独立(anytls 自己的 `public-ip.txt`/`SERVER_IP` 不等于 proxy 模块的设置;可以分别配置),重置按钮也独立;只是共享展示页面.

节点页面列出主机网卡地址及可选的 Tailscale 地址,不再显示安装时记录的公网 IP.

### iperf3 窗口生命周期

1. 操作员登录控制台,选择一个时长(默认 10 分钟,上限由 `VPSSRV_IPERF_MAX_MINUTES`
   限定),点击打开.
2. 控制台把 `iperf3 -s -p <port>` 作为子进程启动,在当前生效的防火墙上开放该端口,
   并把截止时间记在内存里.
3. 窗口开启期间,**公开页面**会显示 iperf3 正在接受连接,在哪个端口上,还剩多少
   时间——远端的测试者需要知道这些信息,而且这不属于敏感信息:这个窗口本来就是
   刻意开放的.
4. 到达截止时间(或操作员主动请求关闭,或服务停止)时,子进程会被终止,防火墙
   规则也会被撤销.

这个窗口的状态保存在内存里,不落盘:如果服务挂掉,窗口也就随之消失,这是失败时
更安全的方向.一次重启永远不会把一个已开启的窗口复活.

延迟数据取自 iperf3 自身 `--json` 输出中的(TCP 信息块里的)`mean_rtt` 字段,
是在测试者一侧读到的;服务端不需要为此额外写任何代码.这个字段来自内核的
`TCP_INFO`,因此在 Linux 客户端上存在,在读不到它的客户端上则缺失——例如
Windows 上 Cygwin 下的 iperf3 会报告吞吐量但没有 `mean_rtt`.UDP 模式(`-u`)
在任何环境下都会报告抖动和丢包,当测试者不在 Linux 上时,这是更具可移植性的
方案.

选择的端口单独保存在应用数据目录中.只能在窗口关闭时从控制台修改;保存前会检查是否与已安装服务,端口转发或当前监听端口冲突.

### 端口转发生命周期

一个转发规则会把这台主机上的一个公网 TCP/UDP 端口,转发到一台通过 Tailscale 或
局域网可达的设备上——这样一台拥有公网 IP 的主机就能替一台没有公网 IP 的设备
出面.和 iperf3 窗口不同,这属于配置,而不是对上行带宽的限时租借:它本应在
重启或重新引导之后依然存在,所以实现方式也不一样.

1. 操作员从控制台添加一条规则:协议(tcp/udp/both),一个公网端口,以及一个
   目标 `host:port`.在任何东西触碰 iptables 之前,`PortForwardManager.add()`
   会先拒绝一个已经被本次安装占用的公网端口(控制台,公开页面,iperf3,
   anytls 节点,已安装的 proxy 协议,或另一条转发规则).
2. 规则中的每一个协议都会变成四条 `iptables` 规则,全部打上
   `-m comment --comment vps-server-portfwd-<id>` 标记,以便和表里已有的其他
   规则区分开来:
   - `nat`/`PREROUTING`:把公网端口 DNAT 到 `target_host:target_port`.
   - `nat`/`POSTROUTING`:对发往目标的流量做 MASQUERADE,让回复流量经由这台
     主机路由回来,而不是从目标自己的默认网关出去——这样目标看到的客户端
     就是这台主机.
   - `filter`/`FORWARD`:每个方向各一条 ACCEPT 规则,因为该链上的默认 `DROP`
     策略(例如在 Docker 主机上很常见)否则会悄悄吞掉被转发的流量.
3. `net.ipv4.ip_forward` 会在第一条规则需要它时被打开
   (`_ensure_ip_forward()`),并且永远不会再关闭——原因见[决策][local-link-007]
   (2026-09-19).
4. 规则集保存在 `PORTFWD_STATE_FILE`(JSON)里,而不只是留在内存中.每次
   进程启动都会调用 `PortForwardManager.load()`,它会无条件地先撤销,再重新
   加上每一条已启用规则的 iptables 状态——内核的表在重启之后什么都不会记得,
   而如果这只是一次服务重启,表里可能还留着上一次运行的规则,所以不论是哪种
   情况,这都是唯一需要处理正确的路径.
5. 一次干净的停止(`SIGTERM`,和 iperf3 窗口用的是同一个信号处理器)会调用
   `PortForwardManager.shutdown()`,它会撤销每一条已启用规则的 iptables 状态,
   但不会去动 JSON 里的 `enabled` 标记——重启这个服务,或者重启主机,都**必须**
   通过 `load()` 把它们全部直接带回来.这和 iperf3 窗口是同一个失败安全方向:
   如果管理这份状态的进程没有在运行,这份状态就**不得**
   悄悄地比它活得更久.

`target_host` **必须**是一个字面的 IPv4 地址,不能是主机名:`iptables --to-destination` 只接受地址,而且本项目在请求时不做任何出站 DNS 查询
(见"零第三方运行时依赖"那条决策).一台 Tailscale 设备的 IP 是稳定的,可以在
该设备上用 `tailscale status` 或 `tailscale ip` 查到.

## 设计约束

- 不得将控制台路由放入 `ProbeHandler`;鉴权不能替代独立的公开路由表.
- iperf3 需要有时间限制,并在关闭或停止服务时撤销防火墙规则.
- 每次进程启动时从 JSON 重放持久化的转发;干净停止时撤销运行时规则,不重置主机级 `ip_forward` 开关.
- 升级须保留节点凭据和选定设置;轮换应使用所属模块的配置脚本,在 Web unit 文件系统沙箱外运行.
- 没有有害延迟的证据,不要拆分共用的 `_db_lock`:历史上 60 个并发请求的测量未重现减速.见[缺陷][local-link-008].

## 外部接口

- HTTP/HTTPS:80/443 上的公开监听器只提供可达性页面;操作员控制台使用单独的持久化端口.iperf3 仅在鉴权后开启的限时窗口中监听.
- 控制台读取 `/proc/net/tcp[6]` 记录入站 TCP 连接;公开路由不导出代理凭据.
- `install.sh` 使用发行版包管理器,并可在安装时查询公网 IP;服务运行时不发出出站请求.`setup-anytls.sh` 与 `setup-proxy.sh` 管理 sing-box unit 和证书.iptables 管理临时开放的 iperf3 端口与已启用的转发;systemd 监管服务并在 Web 沙箱外执行凭据重置.

## 技术栈

| 层 | 选择 | 版本 | 原因 |
|---|---|---|---|
| 运行时 | Python,仅标准库 | 3.9+ | 继承自 `vps-webserver`:不需要第三方 Python 包;发行版维护的解释器及标准库仍需要安全更新 |
| HTTP 服务器 | `http.server.ThreadingHTTPServer` | stdlib | 三个监听器各自的请求量都不大;上框架只是死重量 |
| TLS | `ssl` + `openssl` 生成的自签名证书 | stdlib / 发行版 | 没有域名,没有 ACME(见非目标) |
| 存储 | `sqlite3` | stdlib | 访客日志**必须**在重启后保留 |
| 测速引擎 | LibreSpeed,原样内嵌(vendored) | v6.2.1 | LGPL-3.0;已经在 `vps-webserver` 中内嵌并跑通 |
| 二维码渲染 | kazuhikoarase/qrcode-generator,未修改的随附副本 | js2.0.4 | MIT;体积小,无需构建步骤,与 LibreSpeed 一样通过普通 `<script>` 标签使用 |
| 带宽探测 | 发行版提供的 `iperf3` | 本项目未锁定版本 | 测试者在客户端一侧本来就已经普遍具备的事实标准工具 |
| 代理核心 | sing-box,内嵌二进制(amd64) | v1.13.14 | GPL-3.0;直接分发二进制能让安装保持离线可用 |
| Init | systemd | — | 目标操作系统的默认选择 |
| 安装脚本 | Bash | — | 继承自两个上游项目 |

各方案及其被否决的替代方案和理由见[决策][local-link-009],这里不重复.

## 复现要求

### 环境

- 操作系统:Debian 11+ / Ubuntu 20.04+,systemd,以 root 身份运行
- 运行时:Python 3.9+(发行版自带的 python3 即可)
- 架构:anytls 和 proxy 模块**仅限 x86-64**——内嵌的 sing-box 二进制是 amd64 的.
  Web 模块和 iperf3 模块与架构无关.
- 硬件:无需 GPU;磁盘约 150 MB(其中约 57 MB 是 sing-box 二进制),内存
  只需 VPS 通常具备的量即可
- 随附构件完整性检查:在仓库根目录运行 `python3 tools/verify_dependencies/verify_dependencies.py`.它会对照[dependencies.lock.json][local-link-010],通过 SHA-256 在不执行文件的情况下比对五个受版本控制的第三方可分发文件.已记录的版本与上游修订号来自先前项目记录,并非经独立核实的上游身份;LibreSpeed 的准确上游修订号未记录.
- `app.py` 只使用标准库,因此没有第三方 Python 包锁.这个构件锁不是依赖恢复命令,也不是完整的系统包锁;见 [THIRD_PARTY_NOTICES.md][local-link-011].

### 外部依赖

| 项目 | 来源 | 存放位置 |
|---|---|---|
| `iperf3` | 发行版包管理器(`apt-get install iperf3`) | 系统路径 |
| `openssl`,`curl`,`jq`,`iproute2`,`procps`,`iptables`,`ca-certificates` | 发行版包管理器或主机现有安装 | 系统路径 |
| sing-box 二进制 | 随本仓库分发 | `/usr/local/bin/sing-box-vps-server` |
| LibreSpeed 引擎和 qrcode-generator 库 | 随本仓库分发 | `$PREFIX/static/` |
| TLS 证书 | 由安装程序在首次运行时生成 | `$VPSSRV_CERT_DIR` |

安装程序从目标 Debian/Ubuntu 仓库安装缺失的系统包(包括可选的 `iperf3`),不选择精确版本或仓库快照.Python,OpenSSL,shell/系统工具及 systemd 同样由目标系统提供.主机操作员依靠所选发行版持续维护安全更新的软件包渠道.这避免随附这些二进制文件,但不同主机,不同时刻的包版本,散列及传递依赖解析可能不同;**尚未实现严格,完全可复现的依赖
恢复**.要实现它,需要另行批准安装程序修改并选择发行版/仓库快照.锁文件可机读的 `exclusions` 记录了这一边界,而非虚构的锁定.

无需 API 密钥.Web 服务运行时不查询公网 IP;安装程序可能进行可选出站查询,失败仅给出警告.

### 路径与挂载

| 路径 | 由谁提供 | 用途 |
|---|---|---|
| `$PREFIX` | 安装程序,默认 `/opt/vps-server` | 代码,静态资源,持久化端口文件 |
| `$VPSSRV_DATA_DIR` | 安装程序,默认 `$PREFIX/data` | `visitors.db`,`session_secret.txt`,`portfwd.json`, `login-access.json` (私有 IP 免密名单) |
| `$VPSSRV_CERT_DIR` | 安装程序,默认 `$PREFIX/certs` | 443 用的自签名证书和密钥 |
| `/etc/vps-server-anytls/` | 安装程序 | sing-box 的 `config.json` 及其自身的自签名证书 |
| `/etc/vps-server-proxy/` | 安装程序 | sing-box 的 `config.json`(多个入站)及初始自签名证书;新节点证书位于 `/etc/vps-server-nodes/certs/` |

### 配置参考

所有变量都使用 `VPSSRV_` 前缀.这不是装饰性的:`vps-webserver` 占用
`VPSWS_` 前缀,`Anytsl-Serve` 占用 `ANYTLS_` 前缀,三者可能同时装在一台主机上,
如果前缀共用,一个项目的 `.env` 就可能悄悄改动另一个项目的配置.

| 变量 | 含义 | 默认值 | 是否必需 |
|---|---|---|---|
| `PREFIX` | 安装根目录.传给 `install.sh`/`uninstall.sh`,**不**从 `.env` 中读取——因为在还没有安装,也就没有 `.env` 可读之前,就已经需要这个路径了 | `/opt/vps-server` | 否 |
| `VPSSRV_DATA_DIR` | SQLite + 会话密钥 | `$PREFIX/data` | 否 |
| `VPSSRV_HOST` | 所有监听器的绑定地址 | `0.0.0.0` | 否 |
| `VPSSRV_PUBLIC_HTTP_PORT` | 公开可达性页面,明文 | `80` | 否 |
| `VPSSRV_PUBLIC_HTTPS_PORT` | 公开可达性页面,TLS | `443` | 否 |
| `VPSSRV_PUBLIC_ENABLE` | 是否提供公开页面 | `1` | 否 |
| `VPSSRV_CONSOLE_PORT` | 控制台端口;`0` = 生成一次并持久化 | `0` | 否 |
| `VPSSRV_CONSOLE_PORT_FILE` | 生成的控制台端口记在哪里 | `$PREFIX/console_port.txt` | 否 |
| `VPSSRV_CONSOLE_TLS` | 控制台是否走 HTTPS | `0` | 否 |
| `VPSSRV_AUTH` | 控制台是否要求登录 | `1` | 否 |
| `VPSSRV_PASSWORD_FILE` | 明文控制台密码;在设置中修改时需验证当前密码 | `$PREFIX/admin_password.txt` | 否 |
| `VPSSRV_IP_ALLOWLIST_FILE` | 私有 IP 免密名单的可选路径 | `$VPSSRV_DATA_DIR/login-access.json` | 否 |
| `VPSSRV_CERT_DIR` | 自签名证书的位置 | `$PREFIX/certs` | 否 |
| `VPSSRV_TLS_CERT` / `VPSSRV_TLS_KEY` | 改用操作员自备的证书 | — | 否 |
| `VPSSRV_IPERF_PORT` | iperf3 窗口监听的端口 | `5201` | 否 |
| `VPSSRV_IPERF_DEFAULT_MINUTES` | 预填的窗口时长 | `10` | 否 |
| `VPSSRV_IPERF_MAX_MINUTES` | 控制台不可超过的硬上限 | `60` | 否 |
| `VPSSRV_IPERF_ENABLE` | 是否允许开启窗口 | `1` | 否 |
| `VPSSRV_PORTFWD_ENABLE` | 是否显示端口转发页面并允许新增转发 | `1` | 否 |
| `VPSSRV_PORTFWD_MAX_RULES` | 已配置转发规则数量的上限 | `20` | 否 |
| `VPSSRV_TRUST_PROXY` | 记录访客时是否信任 `X-Forwarded-For` | `0` | 否 |
| `VPSSRV_TRACK_CONNECTIONS` | 是否轮询 `/proc/net/tcp[6]` 以记录所有端口的连接 | `1` | 否 |
| `VPSSRV_CONN_POLL_SECONDS` | 轮询间隔 | `5` | 否 |
| `VPSSRV_MAX_TEST_MB` | 单次测速传输量上限,单位 MB | `200` | 否 |
| `VPSSRV_TEST_SECONDS` | 每个方向的测量窗口 | `10` | 否 |
| `VPSSRV_WARMUP_SECONDS` | 每个方向开始时被丢弃的预热时长 | `2` | 否 |
| `VPSSRV_DOWNLOAD_STREAMS` / `VPSSRV_UPLOAD_STREAMS` | 每个方向的并行流数 | `6` / `3` | 否 |
| `VPSSRV_PING_SAMPLES` | 用于计算延迟数值的往返次数 | `20` | 否 |
| `VPSSRV_DEFAULT_LANG` | `en` / `zh_cn` / `zh_tw` / `zh_hk` / `hi` / `es` / `ar` / `fr` | `en` | 否 |
| `ANYTLS_PORT`,`ANYTLS_PASSWORD`,`SNI`,`SERVER_IP` | anytls 模块沿用上游的变量名 | 见 `.env.example` | 否 |
| `VPSSRV_ANYTLS_CONFIG` | 控制台从哪里读取已安装的节点信息 | `/etc/vps-server-anytls/config.json` | 否 |
| `VPSSRV_ANYTLS_SERVICE` | 控制台用来检查节点存活状态的 unit | `vps-server-anytls.service` | 否 |
| `VPSSRV_ANYTLS_SETUP` | 控制台用来轮换该节点凭据所运行的脚本 | `$PREFIX/anytls/setup-anytls.sh` | 否 |
| `PROXY_PROTOCOLS`,`PROXY_SNI`,`SERVER_IP` | proxy 模块自有的脚本级变量;不受随附上游代码的限制,但为保持 anytls 的脚本与控制台之分而保留不带前缀的名称 | 见 `.env.example` | 否 |
| `VPSSRV_PROXY_CONFIG` | 控制台读取已安装节点集合的位置 | `/etc/vps-server-proxy/config.json` | 否 |
| `VPSSRV_PROXY_SERVICE` | 控制台检查节点存活状态的 unit | `vps-server-proxy.service` | 否 |
| `VPSSRV_PROXY_SETUP` | 控制台运行以轮换指定协议凭据的脚本 | `$PREFIX/proxy/setup-proxy.sh` | 否 |

anytls 模块刻意沿用了 `Anytsl-Serve` 的变量名,而不是重命名成
`VPSSRV_ANYTLS_*`:因为内嵌的配置生成器要读这些变量,重命名就意味着要去改动
内嵌的代码,而这正是内嵌(vendoring)策略本来要避免的事.

## 从零安装

1. `git clone <repo>` 并 `cd` 进去——验证:`ls -lh third_party/sing-box/sing-box` 能看到一个约 57 MB 的文件.
2. `bash deploy/install.sh` ——交互式运行会启动临时的浏览器设置向导,收集模块,界面语言,控制台鉴权及端口选项.打开打印的网址并输入一次性令牌;应用经验证的选择后,确认终端摘要列出各模块及端口.
3. `systemctl status vps-server-web` ——验证:`active (running)`.
4. 从另一台机器上打开 `http://<ip>/` ——验证:可达性页面能正常渲染,并显示出
   你自己的源 IP.
5. 从另一台机器上打开 `https://<ip>/` 并接受证书警告——验证:同一个页面,
   协议那一行显示为 HTTPS.
6. 打开 `http://<ip>:<console port>/` 并登录——验证:仪表盘能加载出来,并且
   iperf3 控制项显示窗口处于关闭状态.
7. 从控制台打开一个 5 分钟的 iperf3 窗口,然后在另一台机器上运行
   `iperf3 -c <ip> -p 5201 --json` ——验证:能报告出吞吐量,且输出中存在
   `mean_rtt`.
8. 如果安装了 anytls 模块:`systemctl status vps-server-anytls` ——验证:
   `active (running)`;安装程序的汇总信息里打印出了一行客户端配置.

## 数据设计

访客数据库与 `portfwd.json` 及 `login-access.json`(已启用的转发规则)持久保存在 `$VPSSRV_DATA_DIR`.控制台密码,选定端口,Web 证书和 `.install-state` 位于 `$PREFIX`;sing-box 模块的配置及证书分别位于 `/etc/vps-server-anytls/` 和 `/etc/vps-server-proxy/`.见[路径与挂载][local-link-012].iperf3 截止时间只存于内存,重启后不会保留.

### 数据模型与文件布局

```
<project root>/
├── snapshots/                 # private snapshots; not part of the Git repository
└── repo/                      # Git working tree; paths below are relative to it
    ├── README.md              # entry point for users and documentation navigation
    ├── config/VERSION         # release version used in checkout
    ├── src/web/app.py         # web service implementation
    ├── deploy/
    │   ├── install.sh         # module-selecting installer
    │   ├── uninstall.sh       # module removal
    │   ├── systemd/vps-server-web.service
    │   ├── anytls/setup-anytls.sh
    │   ├── proxy/setup-proxy.sh
    │   ├── frps/setup-frps.sh
    │   └── lucky/setup-lucky.sh
    ├── static/                # first-party UI assets and vendored browser libraries
    │   └── third_party/
    │       ├── librespeed/    # speedtest.js, speedtest_worker.js
    │       └── qrcode/        # qrcode.js, qrcode-utf8.js
    ├── lang/                  # interface catalogs for web, installers, and tools
    ├── third_party/sing-box/
    │   ├── sing-box           # vendored amd64 binary
    │   ├── sing-box.version   # binary version metadata
    │   └── LICENSE            # original upstream notice
    ├── tools/verify_dependencies/verify_dependencies.py # checks config/dependencies.lock.json from repo root
    ├── config/dependencies.lock.json
    ├── config/upstream-version # records: vps-webserver v0.4.1
    ├── deploy/anytls/.upstream-version # records: Anytsl-Serve v1.2.0
    ├── tests/
    ├── LICENSE                # GPL-3.0
    └── doc/
        ├── DESIGN.md          # architecture, constraints, and tracked goals
        ├── LOG.md             # bugs, dated decisions, verification, release history
        ├── THIRD_PARTY_NOTICES.md
        └── <lang>/            # translated docs (seven language directories)
```

这些仅为检出目录路径:安装后,应用程序,代理可执行文件及浏览器资源仍分别位于 `$PREFIX/app.py`,`$PREFIX/sing-box` 和 `$PREFIX/static/`,资源的 HTTP URL 不变.在检出目录中,安装与卸载脚本为 `deploy/install.sh` 和 `deploy/uninstall.sh`;已安装的 Web 入口仍为 `$PREFIX/app.py`.

只有 `repo/` 由 Git 跟踪;`snapshots/` 独立且私有.由[README][local-link-013] 入门,使用 [LOG][local-link-014] 查阅历史验证和发布记录,并参考[第三方声明][local-link-015]了解上游构件.文档不会使快照或已安装主机变成可复现的源码检出.

SQLite 的表结构原样继承自 `vps-webserver`:只有一张 `visits` 表,会裁剪到只保留
最近的 1000 行.`portfwd.json` 是一份扁平的 JSON 规则对象列表(`id`,`label`,
`protocol`,`public_port`,`target_host`,`target_port`,`enabled`,`created`)
——见 `PortForwardManager` 在 `src/web/app.py` 中的实现.

## 已知限制与注意事项

- **绑定 80 和 443 需要 root 权限,并且这两个端口必须原本是空闲的.** 如果 nginx,
  Apache,Caddy,或者另一个 `vps-webserver` 实例已经占用了其中任意一个端口,
  安装程序会直接拒绝安装,而不是去抢占它.安装前请先用
  `ss -lntp '( sport = :80 or sport = :443 )'` 检查一下.
- **公开页面确实是公开的.** 任何猜到或扫描到这个 IP 的人都能看到它,每一次这样
  的访问都会进入访客日志.这是设计上的特性,但也意味着一个被扫描到的 IP 上的
  访客日志会在几小时内被互联网背景噪声塞满.
- **Unit 名称与上游有意不同.** `Anytsl-Serve` 安装的是
  `sing-box-anytls.service`;本项目安装的是 `vps-server-anytls.service`,
  以及一个单独命名的二进制文件,因此两者可以共存.不过如果检测到上游的
  unit 正在运行,安装程序仍然会拒绝继续,因为一台主机上同时存在两个 anytls
  入站,几乎可以肯定是失误而不是本意.
- **`iperf3` 没有锁定版本.** 它来自发行版,版本会随发行版而变化.协议在
  3.x 这条线上一直保持稳定,但如果客户端版本比服务端老很多,可能会在版本
  握手上失败.
- **anytls 和 proxy 仅支持 amd64.** 内嵌的二进制不是多架构的;在 arm64 上,安装程序
  会跳过这个模块并给出说明,而不是安装一个根本跑不起来的二进制.
- **自签名 TLS 意味着每次访问 443 都会有浏览器警告.** 这是预期行为,不值得为了
  "修掉"它而加例外或 HSTS 头.
- **重启会关闭任何已开启的 iperf3 窗口.** 这是有意为之的;见前面的生命周期
  一节.
- **停止服务会撤销每一条端口转发,哪怕它是已启用的
  .** 这是有意为之的,
  和 iperf3 窗口对称;见前面端口转发生命周期一节.`systemctl restart` 或者
  重启主机会把它们直接全部带回来——`systemctl stop` 之后停在那里则不会.
- **`net.ipv4.ip_forward` 会被自动打开,且永远不会再关闭.** 这是一个
  全主机范围的单一开关;主机上的其他软件(比如 Docker)可能已经依赖它,
  所以删掉最后一条转发规则不会去动它.如果主机上没有别的东西需要它,
  就手动关掉它.
- **一条转发规则只覆盖原始 `iptables` 能看到的范围.** 如果 `ufw` 或
  `firewalld` 正在运行,并且自己也有一条默认拒绝的 `FORWARD` 策略,它们的链
  会先于这个功能追加的规则被求值,可能仍然需要为同一个端口单独加一条放行
  规则,流量才能通过.
- **sing-box 二进制超过了 GitHub 建议的文件大小.** 大约 55 MB,超过了
  50 MB 的软限制,因此每次 push 都会打印一条建议使用 Git LFS 的
  "Large files detected" 警告.Push 依然能成功;硬限制是 100 MB.未来
  sing-box 升级版本时可能最终会越过这个界限,到那时该怎么处理(用 LFS,还是
  不再随仓库分发这个二进制)应该是一个刻意做出的决定,而不是发版当天才碰到的
  意外.
- **运行脚本要用 `bash <script>`,不要用 `./<script>`.** 可执行位记录在
  git 索引里,所以一份全新的 clone 会带有这个位——但在 CIFS/SMB 挂载上的工作
  副本不会,在那上面执行 `./install.sh` 会失败,报 "Permission denied".
- **重新内嵌任何可执行文件都会丢失它的权限位.** 维护者的工作副本在 CIFS 上,
  所以在那上面解压出来再 `git add` 的文件,会被记录成 `100644`,即使上游是
  `100755`.这已经在 `sing-box` 二进制上发生过一次,并且弄坏了整个 anytls
  模块.重新内嵌之后,用 `git ls-files -s` 检查一下,并用
  `git update-index --chmod=+x <path>` 恢复这个位——在那个挂载上单独
  `chmod +x` 是没有效果的.
- **直接运行 `setup-anytls.sh` 会轮换它的端口和密码.** 它会把 `ANYTLS_PORT`
  和 `ANYTLS_PASSWORD` 默认成全新的随机值,并在每次运行时重写
  `config.json`,因此手动调用它会让此前配置的所有客户端全部失效.
  `install.sh` 现在已经不会这样做了——升级路径会把这两个值从 `config.json`
  里读回来并传进去——但直接调用仍然会这样.想要保留节点,就要传入当前的值,
  这两个值都能在控制台 `/proxy` 的 anytls 分区上找到:
  `ANYTLS_PORT=<current> ANYTLS_PASSWORD='<current>' bash deploy/anytls/setup-anytls.sh`.
  这是刻意继承下来的上游行为.`setup-anytls.sh reset` 才是有意去轮换它们的,
  控制台上的重置按钮是官方支持的,用来达到这个目的的方式.
- **节点页面列出网卡和 Tailscale 地址.** 旧的安装时公网地址区块已移除:它在 VPS 上重复显示网卡地址,在 NAT 后也可能误导用户.安装程序仍可为设置脚本记录 `public-ip.txt`;控制台不再读取它.
- **`body` 传给 `render_page()` 时** **必须**恰好包含一个顶层元素. `<main>` 使用 `display: flex`,未覆盖 `flex-direction`,因此多个顶层兄弟元素(例如每个协议一个 `<div class="card wide">`)会并排而非上下堆叠.这是 `/proxy` 页面早期版本真实发布过的缺陷,操作员报告为“布局乱了”.每个页面都用一个外层卡片包住全部内容,重复分区则在其内部以 `.node-addr` div 嵌套.
- **拆卸时需要用与安装时相同的 `PREFIX` 和 `SERVICE_NAME`.** 不带任何环境变量
  运行 `uninstall.sh` 会读取默认值,在那些路径上什么都找不到,并报告"成功",
  实际上什么都没删.安装程序结束时打印的那一行会给出填好了具体值的完整命令;
  请照抄那一行,而不是凭记忆自己敲.

## 扩展

### 扩展方法

- **新增一个模块**(安装程序可以选择性安装的其他东西):新增一个
  `deploy/<name>/setup-<name>.sh`,一个 systemd unit(放在 `deploy/systemd/` 中或由配置脚本生成),在
  `deploy/install.sh` 的模块菜单里加一个分支,并在 `deploy/uninstall.sh` 里加一个对应的
  拆卸分支.各模块之间互不调用.
- **新增一个控制台页面**:给 `ConsoleHandler` 加一个路由.不要给
  `ProbeHandler` 加路由——它的路由表几乎为空是一个安全属性,不是疏漏.
- **新增一种语言**:在每个 `lang/<component>/` 目录下添加对应的文案文件,并在 Web 语言选择器,变更日志映射,安装程序,初次设置向导及模块脚本的词条加载器中登记语言代码,然后添加对应的 `doc/<BCP47>/` 文档目录树.
- **新增一种颜色**:在 `:root` 中加一个 token(位于 `static/style.css`),*并且*
  在 `prefers-color-scheme: light` 区块里补上对应的浅色模式的值,然后使用
  这个 token.不要在组件规则里直接写十六进制颜色值——字面量没法跟着主题走,
  所以它只在被人肉眼调出来的那个模式下是对的,在另一个模式下就是错的,而且
  没有任何机制会报告这个问题.任何被用作填充背景的值都需要一个配对的
  `--on-*` 前景色:读起来适合作为文字的值,往往并不是在白色文字背后读起来
  合适的值.提交前请在两种模式下都对照 WCAG AA(4.5:1)检查一遍;
  `tests/test_app.py::StylesheetTest` 会强制检查这里面结构性的那一半,但
  没法判断对比度.
- **刷新一个内嵌的上游依赖**:从上游的 tag 重新拷贝,在同一个 commit 里更新
  对应的 `.upstream-version` 文件,并在 [LOG.md][local-link-016] 里记一笔这次升级.
  绝不要就地手改内嵌代码——一个没有反映回上游的本地改动,会让下一次刷新
  变成一次悄无声息的回退.

[local-link-001]: LOG.md#当前状态与验收限制
[local-link-002]: LOG.md#缺陷
[local-link-003]: LOG.md#已完成工作历史
[local-link-004]: LOG.md#决策
[local-link-005]: #proxy-模块
[local-link-006]: LOG.md#决策
[local-link-007]: LOG.md#决策
[local-link-008]: LOG.md#缺陷
[local-link-009]: LOG.md#决策
[local-link-010]: ../../config/dependencies.lock.json
[local-link-011]: THIRD_PARTY_NOTICES.md
[local-link-012]: #路径与挂载
[local-link-013]: ../../README.md
[local-link-014]: LOG.md
[local-link-015]: THIRD_PARTY_NOTICES.md
[local-link-016]: LOG.md#变更日志
