---
name: project-log-zh-cn
description: 项目决策,限制,缺陷与变更
metadata:
  version: "1.0.0"
  lang: "zh-CN"
---

# vps-server — 项目记录

本文汇总已知缺陷,决策,历史工作,当前验收限制和已发布的变更.对过去测试的陈述不代表此次文档迁移重新运行了测试.

## 多语言

[English](../LOG.md) | **简体中文** | [繁體中文(台灣)](../zh-TW/LOG.md) | [繁體中文(香港)](../zh-HK/LOG.md) | [हिन्दी](../hi/LOG.md) | [Español](../es/LOG.md) | [العربية](../ar/LOG.md) | [Français](../fr/LOG.md)

## 文档

- 项目概览:[README](README.md)

- 设计思路:[DESIGN](DESIGN.md)

- 发布历史:[LOG](LOG.md)

- 第三方声明:[THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES.md)

## 缺陷

- [ ] 2026-09-12 决定是否需要拆分共用的 `_db_lock`:每次公开页面访问都会持有进程级锁并同步写入 SQLite,控制台也共用此锁,原则上匿名请求洪泛可能拖慢鉴权后的页面.**测量未重现此问题**:60 个并发洪泛请求下控制台延迟仍为 0.4–0.6 ms,与空闲时相同.保留此记录以免将已知机制误认成新发现;没有显示有害影响的测量证据,不要重构架构.

先前状态快照未记录其他破坏性问题;启动/停止的信号边界,仅安装 iperf3 的组合及登录限速已在尚待合并/审核的 `feat/hardening-batch` 修复.这不表示当前分支已在真实主机重新验证.

## 限制

- 自动化检查已核对文案键名,占位符及文档结构,但新增译文尚未经过独立的母语审阅.
- 正在使用的源码检出根目录可能含有被 Git 忽略的运行状态(`admin_password.txt`,`console_port.txt`,`data/`,`certs/`)及 Python 缓存(`__pycache__/`).结构检查器会报告这些本地文件;仅包含受版本控制文件的干净导出可通过检查.迁移时应保留运行状态.若 CIFS 工作区挂载固定使用 0644 文件模式和 0755 目录模式,`chmod` 不会改变本地密钥显示的权限;须单独评估挂载访问控制.
- 当前分支的真实主机验收限制见下文.

## 决策

<a id="vps-decisions"></a>

以下按日期排列的决策保留了被否决方案及其代价.历史决策不构成新的法律或发布批准.

| 决策 | 理由,被否决的方案及代价 |
| --- | --- |
| 2026-09-22 — `proxy` 是一个可容纳最多四种入站的 sing-box 进程,而非四份 anytls 副本 | - **已解决,而非否决:** 随附的 sing-box 二进制文件是否支持 vmess/vless/trojan/shadowsocks:实际在一个进程中同时运行了四者(并非仅执行 `sing-box check`);无需第二套后端.尝试过 hysteria2/tuic,但因字段/TLS 要求不同而排除.- **否决:** 模仿 anytls,每种协议各设一个 systemd unit 和配置——要监控四个 unit,多出三份冗余自签名证书,也不利于未来按节点统计流量所需的结构(一个进程,其 `inbounds` 列表即节点列表).- **代价:** 两个独立模块共用随附二进制文件;各自的 `uninstall()` 删除前**必须**检查另一模块的配置(anytls 随附脚本为此增加有记录的本地改动,见 `anytls/.upstream-version`). |
| 2026-09-21 — `prompt_new_settings()` 须显式以 `return 0` 结束,而不能仅从循环末尾自然返回 | - **否决:** 让函数状态取决于最后的 `for` 循环,就像 `install.sh` 中许多其他函数一样.循环末句曾是 `[ -n "$value" ] && export ...`;最后一个设置保留默认值时,该测试为假并成为函数返回状态.直接调用 `prompt_new_settings`(虽位于 `if` 分支内部,但函数自身并不豁免 `set -e`)会在最后一个提示后静默结束整个安装程序:无错误,无文件复制,无 `VERSION` 标记,无服务重启.在 v1.0.4 → v1.1.1 的真实升级中重现;将导出包入 `if`/`fi` 并在末尾显式 `return 0` 后修复.- **不要把末尾的 `return 0` 当作无用代码删除.** 它是修复,而非样板代码. |
| 2026-09-19 — 端口转发使用 iptables DNAT,每次启动从 JSON 重放;不在进程之外写入规则 | - **否决:** 每条规则用一个 `socat` 用户态中继——它更安全(不改 NAT 表或 `ip_forward`),但用户明确选择本项目使用内核级 DNAT+MASQUERADE.- **否决:** 使用 `iptables-persistent` 在内核层跨重启保留规则——这样控制台与系统包会成为同一规则的两个事实来源.改由 `app.py` 每次启动从自身 JSON 重放(见 DESIGN.md 的“端口转发生命周期”),确保只有一个来源.- **否决:** 删除最后一条转发后自动将 `net.ipv4.ip_forward` 恢复为 `0`——该开关作用于整台主机,其他软件(项目测试主机上的 Docker)可能依赖它.- **代价:** 停止 `vps-server-web`(而非重启)会撤销所有转发的内核状态,包括已启用的规则;与 iperf3 窗口同属失败安全设计.不要另建常驻 unit 来“修复”它;该方案已被考虑并否决. |
| 2026-09-12 — 公开页面和控制台使用不同监听器及不同处理器类 | - **否决:** 同一个监听器,以路径前缀和鉴权检查保护控制台路由;鉴权检查可能出错,而不存在的路由不可能被错误放行.- **否决:** 控制台直接放到带密码保护的 80/443 上并放弃随机端口;这会丢掉 `vps-webserver` 刻意保留的隐蔽层.- **代价:** 一个进程内三个监听器,以及两个都需接入访客日志钩子的处理器类.- **不要重新把此方案当成改进.** |
| 2026-09-12 — iperf3 只在操作员开启的限时窗口中运行 | - **否决:** 常驻的公开 `iperf3 -s` 会让陌生人无限期占满上行链路,且无从发现.- **否决:** 常驻并使用 `--authorized-users-path` RSA 鉴权;测试者就得事先通过其他渠道取得凭据,违背“交给对方 IP 即可测速”的初衷.- **代价:** 远程测试者不能无人值守地测速;得先有人开启窗口.公开页面会标出开放的窗口,让测试者知道何时连接. |
| 2026-09-12 — 443 使用自签名证书;没有 ACME 或域名 | - **否决:** 为真实域名运行 certbot / acme.sh;页面只需要回答“能否连接这个 IP”,浏览器警告已经能证明可达性,域名依赖和续期定时器对此无益.- **否决:** 只在 80 提供服务;这无法区分“主机不可达”和“唯独 443 被阻断”,而后者正是值得发现的常见情况.- **代价:** 每次 HTTPS 访问都会弹出证书警告.这是预期行为,不要以 HSTS 或固定证书例外来“修复”. |
| 2026-09-12 — sing-box 二进制文件随仓库分发,因此整个项目为 GPL-3.0 | - **否决:** 安装时下载 sing-box,以缩小仓库并保留 Apache-2.0 许可;`Anytsl-Serve` 已明确为离线安装否决这一方案,重新决策会暗中破坏该目标.- **否决:** 为保留 `vps-webserver` 的 Apache-2.0 而删除 anytls 模块;需求是结合两个项目,而非二选一.- **代价:** git 中约 57 MB,且每次 sing-box 升级还会增长;`vps-webserver` 的 Apache-2.0 代码在此以 GPL-3.0 重新分发. |
| 2026-09-12 — 两个上游项目以随附副本方式引入,不取代原项目,也不使用子模块 | - **否决:** 让 vps-server 取代 `vps-webserver`,`Anytsl-Serve` 并归档二者;三个项目都要继续独立维护和发布.- **否决:** 将两个上游仓库设为 git 子模块;子模块无法携带所需的重命名(unit 名,二进制文件名,`VPSWS_` → `VPSSRV_`),检出也须联网获取另外两个仓库.- **代价:** 相同代码分布于三个仓库并会逐渐偏离.缓解方式:`.upstream-version` 文件记录各随附副本所依据的准确上游标签,刷新副本时**必须**在同一个提交中更新. |

## 当前状态与验收限制

<a id="vps-current-state"></a>

v2.0.0 包含实验性的 frps 和 Lucky 安装路径.它们的行为尚未在真实主机上完成验收;本次发布周期中,新的检出目录布局只经过本地自动化验证.

2026-09-22 的源码快照将 `feat/proxy-protocols` 描述为叠加在尚未合并的 `feat/hardening-batch` 之上.v2.0.0 纳入了这两个分支当前的项目文件树,但 proxy 模块仍待操作员在真实主机上测试.独立应用的地址去重及公网 IP 修复已纳入分支审核.这里不声称已在真实主机验证 proxy 功能;旧容器由于 systemd 未作为 PID 1 运行而使用了 `systemctl` 桩.下文 147/147,150/150,153/153 和 156/156 的测试通过记录以及较早的真实主机检查均为历史记录,不是新验证.

### 分支记录 (2026-09-22 状态快照)

<a id="vps-branch-record-2026-09-22"></a>

原状态记录称功能已实现并自行测试,但操作员审核仍待进行;它叠加于 `feat/hardening-batch`,以使用其独立的 y/n 模块选择器.首次一次性 Docker 验证中 systemd 无法作为 PID 1 启动,因而用桩替换 `systemctl`;实际执行了 sing-box 配置检查,iptables 规则,凭据轮换,了解共享二进制文件的卸载,以及无人值守安装与升级重跑.测试发现并修复两个缺陷:无效 `PROXY_PROTOCOLS` 的验证被吞掉(导致零入站),以及生成端口溢出 sing-box 的 uint16 上限.记录当时新增 19 项测试,147/147 通过;这**不构成**对 proxy 功能的 systemd 或真实主机验证.

随后操作员测试发现 `/anytls` 和 `/proxy` 被人为分成两页,以及多个顶层卡片在 flex 布局中并排出现.分支现在把所有已安装节点的分区置于 `/proxy` 上同一卡片中,`/anytls` 重定向过去,并只使用一个导航入口.由于同时进行代理页面改写,地址去重与删除 `get_ip()` 公网 IP 自动检测的修复从 `main` 重新应用到分支而非合并;分支审核**必须**核对这些独立应用.历史记录称合并 anytls+proxy 的回归测试夹具和重定向测试在 150/150 通过;此后从 `main` 重新应用 iperf3 倒计时和命令示例修复时,153/153 通过.

随后操作员要求将代理的组合重置按钮改为每种协议独立的按钮.`setup-proxy.sh reset <protocol>` 保留其他协议的凭据和端口;终端中不带参数的 `reset` 仍轮换全部协议,但控制台不提供.一次性容器测试轮换四种已装协议中的一种,保留其他协议及完整协议集合,对未知名称予以拒绝且不修改配置.历史记录称新增或重写六项测试,156/156 通过;此处没有新的测试或发布声明.

对较早已发布工作,状态记录了操作员在真实主机检查 v1.1.0 端口转发,此前还使用了可弃置的三容器测试环境及 119/119 单元测试.v1.0.0 之前,记录了操作员在真实主机检查两个端口的公开页面,控制台及浏览器测速,iperf3 在局域网达到 2.8 Gbit/s 并在窗口关闭后拒绝连接,anytls 安装/重置/卸载,升级时保留配置以及三种界面语言.这些是历史观察,不代表当前分支已验收.旧快照将 SQLite 锁的测量列为下一项调查,称无阻断问题,也未给流量统计,初次设置向导,frps,`gdy666/lucky` 功能或高度定制节点定义范围.它们目前分别记录于[缺陷][local-link-001]和[设计目标][local-link-002].

## v2.0.0 仓库布局迁移

此次检出版本将 Web 实现放在 `src/web/app.py`.安装与卸载命令位于 `deploy/install.sh` 和 `deploy/uninstall.sh`;仓库根目录不再保留同名兼容入口.`deploy/systemd/`,`deploy/anytls/` 和 `deploy/proxy/` 存放运行管理代码.amd64 二进制文件,版本信息及上游声明位于 `third_party/sing-box/{sing-box,sing-box.version,LICENSE}`.直接提供给浏览器的第三方资源位于 `static/third_party/`;依赖核验工具位于 `tools/verify_dependencies/`.当前检出版本还包含实验性的 frps,Lucky 安装目录及设置向导工具目录.

已安装文件仍采用 `$PREFIX/app.py`,`$PREFIX/static/`,`$PREFIX/anytls/`,`$PREFIX/proxy/` 和 `$PREFIX/sing-box` 的平铺布局;模块配置仍使用 `/etc/vps-server-anytls/` 和 `/etc/vps-server-proxy/`.以下按日期记录的决策及已完成工作中的旧路径指其历史检出版本,不是当前使用说明.此次离线迁移检查不等于真实主机或 systemd 验证;仍待操作员验收.

## 已完成工作历史

<a id="vps-completed-work"></a>

以下已完成项是旧需求列表按日期记录的实施和验证历史,而非刚运行的测试报告.其余目标见[设计目标][local-link-003];尚未解决的 `_db_lock` 项目在[缺陷][local-link-004]中.

- 已完成:2026-09-12 阻止变更日志页面显示维护者注释.`render_changelog()` 不处理注释,`<!--` 与 `-->` 之间的每行在三种语言页面上都会变成段落.v1.0.0 曾显示该内容,v1.0.1 已修复.

- 已完成:2026-09-12 确定架构并编写 `DESIGN.md`;在编码前完成.

- 已完成:2026-09-12 随附 `vps-webserver` v0.4.1:从上游标签复制 `app.py`,`static/`,`tests/`,`install.sh`,`uninstall.sh`,`systemd/`,在 `.upstream-version` 中记录标签,同一提交将 `VPSWS_` 环境变量前缀改为 `VPSSRV_`.

- 已完成:2026-09-12 把 `app.py` 分为两个处理器:`ConsoleHandler` 保留现有路由;增加 `ProbeHandler`,仅处理 `/` 与 `/favicon.ico`;在控制台监听器之外再启动 80/443 的公开监听器.

- 已完成:2026-09-12 编写公开可达性页面:仅显示源 IP,服务器时钟,到达协议及端口,不泄露主机其他信息,也不使用 JavaScript.样式表最终内联为 `PROBE_CSS`,未使用 `static/probe.css`,公开监听器根本没有文件服务路由.

- 已完成:2026-09-12 实现 iperf3 窗口:控制台开关路由,`subprocess.Popen("iperf3 -s -p …")`,内存中的截止时间,到期线程,防火墙开放和撤销,以及在 `SIGTERM` 时清理.

- 已完成:2026-09-12 在公开页面展示开放的窗口:端口和剩余分钟数,使远程测试者知道何时连接.

- 已完成:2026-09-12 随附 `Anytsl-Serve` v1.2.0:包括 `anytls/setup-anytls.sh`,sing-box 二进制文件及 `sing-box.version`;将 unit 重命名为 `vps-server-anytls.service`,二进制文件名重命名为 `sing-box-vps-server`,在 `anytls/.upstream-version` 中记录标签.

- 已完成:2026-09-12 将 `install.sh` 变成模块选择菜单:web / anytls / iperf3 可独立选择;80/443 被占用或上游 `sing-box-anytls.service` 正在运行时拒绝;在非 amd64 主机跳过 anytls.**已编写但从未执行**,见下文验证项.

- 已完成:2026-09-12 扩展 `uninstall.sh`,移除检测到的模块:默认全部删除,`KEEP_DATA=1` 保留访客数据库;先清理 anytls,再删除 `$PREFIX`,因为其卸载脚本位于 `$PREFIX` 内.**已编写但从未执行.**

- 已完成:2026-09-12 在隔离前缀的真实 systemd 主机上由操作员端到端执行 `install.sh`:服务启动,摘要正确,实例在 18080 和 18443 显示含正确到达端口的公开页面,公开端口上的控制台路由返回 404,控制台端口正常响应.发现并修复两个问题:末尾“卸载方法”没有带上 `PREFIX`/`SERVICE_NAME`,导致卸载默默检查默认路径,什么也没删除;示例用 `./script.sh`,无法在 CIFS 工作副本中运行.

- 已完成:2026-09-12 在真实安装实例中验证 systemd 沙箱下的 iperf3 窗口.`NoNewPrivileges` 和 `ProtectSystem=strict` 不阻碍 `firewall_port()`:开启窗口添加 `-A INPUT -p tcp -m tcp --dport 5201 -j ACCEPT`,关闭时撤销.卸载后未留下 unit,目录,规则,进程或监听器.

- 已完成:2026-09-12 运行 `install.sh` 安装 anytls 模块.首次尝试在 sing-box 安装前失败:CIFS 在引入文件时丢失可执行位,二进制记录为 `100644`,`install_singbox` 要求 `-x`;修正两处后成功安装,三个重命名的常量正确生效,服务启动,`uninstall.sh` 移除了 unit,二进制,配置目录及防火墙规则.

- 已完成:2026-09-12 在控制台展示已安装的 anytls 节点:当时 `/anytls` 页面显示服务是否在线,提供可复制的 Clash 条目和 `anytls://` 链接;只读,节点状态仍由 `setup-anytls.sh` 管理.

- 已完成:2026-09-12 验证 `refuse_if_upstream_running` 的三个分支:上游 unit 运行时以退出码 1 拒绝;不存在时继续;`VPSSRV_ALLOW_DUAL_ANYTLS=1` 时警告后继续.验证时将守卫的服务名指向真实运行中的 unit,而非实际安装 `Anytsl-Serve`,因此分支逻辑已验证,真实主机上的字面命名冲突尚未发生过.

- 已完成:2026-09-12 按 WCAG AA 审计控制台两种配色,修正五处真实错误,最严重的是浅色模式下 iperf “窗口开放”文字与背景对比度仅 1.77:1,在白色背景上几乎不可见.组件颜色现均使用带浅色值的语义令牌,`StylesheetTest` 守护结构.

- 已完成:2026-09-12 用真实标签注入 `VERSION`,不再硬编码.`app.py` 曾设置字面值 `VERSION = "0.1.0"`,违反 `project-management` 的 `references/webui.md` §1:发版时忘记更新,界面会继续显示旧版且不会报错.安装时读取 `git describe --tags --exact-match`(或在 `install.sh` 的复制步骤写入),未打标签时退回 `dev-<short sha>` 而非旧标签.此问题继承自 `vps-webserver`,在颜色工作中阅读 webui.md 时发现;当时因超出范围没有修复.

- 已完成:2026-09-12 让 `install.sh` 识别升级:检测现有安装并询问是否保留配置,重放 unit `Environment=` 行记录的设置,保留 anytls 节点凭据,仅询问旧版本尚未提供的设置.早于 `$PREFIX/.install-state` 的安装通过磁盘推断模块,并明确告知无法计算新增设置的差异.

- 已完成:2026-09-12 增加控制台按钮来轮换 anytls 的端口和密码:`/anytls/reset` 需经服务端验证的确认;它调用 `setup-anytls.sh reset` 而非自行写入节点.

- 已完成:2026-09-12 操作员对旧安装执行真实升级,配置重放成功,anytls 端口与密码保留.发现并修复两项缺陷:`PUBLIC_HTTP_PORT` 在重放前计算,导致摘要打印默认公开端口,冲突检查也错误地检查默认端口;Web 服务的 `ProtectSystem=strict` 令 `/etc` 只读,导致控制台重置按钮失败.

- 已完成:2026-09-12 重装后按下 anytls 重置按钮,并在主机验证:端口已轮换,节点监听新端口,新防火墙规则存在,**旧端口规则已撤销**(没有遗留 ACCEPT),临时 unit 已清理.重复安装四次没有重复规则.

- 已完成:2026-09-12 全面审计安全,Python 并发,shell 正确性和文档/代码偏差:发现并修复 11 处真实缺陷,见审计提交.重要问题包括 `VPSSRV_CONSOLE_PORT=0` 在 `.env.example` 中绑定 0(每次重启控制台换端口);`install.sh` 在检查端口前停止服务(无关冲突也使服务保持停止);更改 anytls 端口但不使用 `reset` 会留下孤立防火墙规则.

- 已完成:2026-09-12 加固 `main()` 在 `app.py` 中的启动/停止边界:`try/finally` 现在包住整个启动流程而非仅 `console.serve_forever()`,从而在 `start_public_listeners()`/`PORTFWD.load()` 中收到信号时也能清理;一旦开始清理便忽略后续 `SIGTERM`/`SIGINT`,避免在 `IPERF_WINDOW.close()` 中收到第二个信号而在撤销防火墙规则前退出;各监听器先 `shutdown()` 再 `server_close()`,解决重启时的 `OSError` 回溯.新增子进程级测试:启动真实 `app.py`,确认能接受连接,发出真实 `SIGTERM`,断言及时干净退出;这是首个测试 `main()` 自身而非直接测试处理器类的用例.

- 已完成:2026-09-12 `VPSSRV_MODULES=iperf3` 单独使用时会默默什么都不安装,现予以明确报错拒绝(iperf3 是控制台按钮;没有 web 就没有控制台可开启窗口).在一次性容器中验证,无人值守流程现在给出错误而不是静默退出 0.

- 已完成:2026-09-12 限制 `/login` 登录尝试频率:新增 `LoginRateLimiter`,某 IP 在时间窗口内失败过多则锁定固定时长;正确登录或等待到期解除锁定.按既定范围,这只是纵深防御:生成的密码本来就极难暴力破解.直接对限速器执行单元测试,并在 HTTP 层确认实际 `/login` 路由锁定后返回 429.

- 已完成:2026-09-12 清理维护者主机上的旧 `--dport 31515` ACCEPT:这来自 `close_firewall` 尚无法通过 `reset` 调用时的安装/卸载流程;执行 `iptables -D INPUT -p tcp --dport 31515 -j ACCEPT`.它不是当前代码树的问题,此处保留记录避免以后误认.

- 已完成:2026-09-12 审计控制台布局:iperf 表单输入框比按钮高约 1 rem,原因是 `.inline-form label` 继承了 `margin-bottom: 1rem` 而 flex `align-items: flex-end` 对齐的是含外边距的盒;磁贴增至四个时仪表盘网格仍固定为两列;键值网格,行内表单及复制行都没有窄屏规则.现无固定像素宽度,触摸目标均达到 WCAG 2.2 的 24 CSS px 最低标准.

- 已完成:2026-09-12 操作员在普通 HTTP 的浏览器中验证复制按钮正常工作;因此 `document.execCommand` 后备路径确实在非安全上下文中执行——默认环境不是安全上下文,`navigator.clipboard` 未定义,实际使用 `document.execCommand` 后备路径,其代码位于 `static/copy.js`.单元测试只涵盖页面标记,不涵盖浏览器行为.

- 已完成:2026-09-12 为新功能编写测试:公开端口上的 `ProbeHandler` 对所有控制台路由返回 404;iperf3 窗口到期会终止子进程,重启后不会恢复.测试中对 `firewall_port` 使用桩,因此测试集不触碰主机防火墙.

- 已完成:2026-09-12 编写 `LICENSE`(GPL-3.0),`LICENSES/`,`THIRD_PARTY_NOTICES.md`:记录 sing-box(GPL-3.0,含 SHA-256 和对应源码链接),LibreSpeed(LGPL-3.0),iperf3(BSD-3-Clause,发行版安装而非本项目重新分发).

- 已完成:2026-09-12 将六份治理文档译至 `translated_zh_cn/` 和 `translated_zh_tw/`:当时仍是未翻译的模板占位文档;安排 `doc-translator`,每种语言的每份文档各一个实例.

- 已完成:2026-09-12 在真实的第二台机器进行端到端验证:从主机外部访问 80 和 443 的公开页面,开启窗口并运行 `iperf3 -c <ip> --json`,确认包含 `mean_rtt`.

- 已完成:2026-09-12 修复 `install_iperf3()` 静默安装失败:它把 `apt-get update -qq && apt-get install -y -qq iperf3` 作为一个 `&&` 链执行并丢弃全部输出,因此单个无关仓库的 `apt-get update` 失败(真实 VPS 上陈旧的第三方 `.list`)便跳过安装,也不提供诊断.现最多重试 `apt-get update` 三次;即使更新未完全成功仍尝试安装;设置 `DEBIAN_FRONTEND=noninteractive`,不再隐藏 apt 输出.在可弃置且支持 systemd 的 Debian 12 容器中完整运行 `install.sh`(修复 v1.0.2 时)验证(不在本机占用 80/443 或启动真实服务):植入相同的故障仓库后 iperf3 安装成功,`vps-server-web.service` 启动,控制台及公开页面均返回 HTTP 200.发布为 v1.0.2.

- 已完成:2026-09-12 修复 v1.0.2 的不完整 iperf3 安装修复:操作员从 v1.0.1 升级 v1.0.2 时遇到真实故障:`apt-get update` 报告成功,但 `security.debian.org` 的 CDN 返回旧软件包索引,随后的 `apt-get install` 下载索引中存在的 `.deb` 却返回 404.只重试 `update` 并不可靠,可能反复访问同一陈旧节点.`install_iperf3()` 现在将更新和安装作为整体最多重试三次;用首次失败后成功的假 apt 测试环境,与 v1.0.2 相同的故障仓库容器环境及全新端到端 `install.sh` 容器安装确认.另修复 README 的 `## Install` 节:自 v1.0.0 起仍包含 `templates/README.md` 未替换的 `<repo-url>`,从未发布的示例标签 `v0.1.0`;改为真实 GitHub URL 和当时的发布标签.发布为 v1.0.3.

- 已完成:2026-09-12 安装摘要打印主机真实地址,不再只显示 `<this-server>` / `<本机地址>` 字面占位符,避免手工改写网址;ZeroTier 或 Tailscale 才能访问的主机也能看到可用地址.`primary_ip()` 通过 `ip -4 route get` 获取内核出站源地址,`other_ips()` 列出其余带接口名称的地址;沿用 `setup-anytls.sh` 的容器/网桥接口过滤,但特意保留常用于访问控制台的 VPN 接口.失败时仍用旧占位符,不使安装失败.在附加第二块网卡的一次性 systemd 容器中验证:三种语言输出及列对齐正确,列出的各地址均返回 HTTP 200;即便完全以桩替换 `ip`,安装仍返回 0.发布为 v1.0.4.

- 已完成:2026-09-19 由控制台管理端口转发:可把本主机的公网 TCP/UDP 端口转发到通过 Tailscale 或局域网可达的设备(即本主机有公网 IP,目标无公网 IP).每条规则使用 iptables DNAT + MASQUERADE,带便于识别的注释;规则持久化为 JSON,服务每次启动都幂等重放,普通重启和系统重启均恢复(内核的规则表自身不会跨重启保存).首次需要时开启 `net.ipv4.ip_forward`,由于主机其他软件也可能依赖它,之后不自动关闭.控制台新 `/portfwd` 页面可增删,启停规则,选择 tcp/udp/both,对照安装占用的其他端口检查冲突.在可弃置的三容器 Docker 测试环境中验证(非已运行 Docker NAT 的当前主机):连接两个网络的“vps”容器代表公网/私网,“target”代表 Tailscale/局域网设备,“client”代表公网访客.实测 TCP 和 UDP 均端到端转发,首个启用规则让 `net.ipv4.ip_forward` 由 `0` 变为 `1`,禁用/启用立即改变可达性,两次杀死并重启进程从 `portfwd.json` 恢复且不产生重复规则,干净的 `SIGTERM` 撤销内核规则同时保留磁盘 `enabled: true` 以供重启恢复;控制台端口冲突及无效目标 IP 均按预期拒绝.119/119 项单元测试通过,含使用 iptables 桩的 `PortForwardManagerTest` 和实际 HTTP 路由测试 `PortForwardConsoleTest`.当时位于尚未合并发布,等待操作员手动测试的 `feat/portfwd`;后续状态快照记录了该测试和 [v1.1.0 发布][local-link-005].

- 已完成:2026-09-21 修复 `install.sh` 在真实升级中静默退出的问题.操作员从 v1.0.4 升级到 v1.1.1 时发现:`v1.1.0` 新增的两个 `VPSSRV_PORTFWD_*` 设置首次触发了升级时询问新设置.`prompt_new_settings()` 的最终 `for` 循环以裸露的 `[ -n "$value" ] && export "$var=$value"` 结束;接受*最后一个*设置的默认值使测试返回假,成为函数返回状态;在 `if` 分支内直接调用的函数本身不豁免 `set -e`,整个安装程序便在最后提示后无错误信息地退出:未复制文件,未写 `VERSION`,未重启服务,主机仍保持旧版而表面上像升级完成.操作员真实主机两次重现(症状与旧 `ActiveEnterTimestamp` 完全相同),经 `bash -x` 追踪及隔离的 bash 测试精确定位 `set -e`,`&&` 和循环的交互.将导出包入 `if`/`fi` 并显式以 `return 0` 结束.在隔离 bash 测试和完整的一次性 systemd 容器复现中验证:先安装真实 v1.0.4,再通过实际 pty 运行交互式 `bash install.sh`(使用 `expect` 而非管道/非交互标准输入,否则会掩盖问题) 升级到 v1.1.1;未修补脚本在操作员遇到的相同位置退出,修补后完成安装,更新 `VERSION` 并重启服务.发布为 v1.1.2.

- 已完成:2026-09-19 参考 vaxilu/x-ui 支持更多代理协议:当时只有 anytls 节点,用户预期新增 vmess/vless/trojan/shadowsocks 等协议不会显著增加开销.须先决定现有随附 sing-box 是否支持,还是需要第二套后端.**已确认支持**:四种协议(shadowsocks 为 2022-blake3-aes-128-gcm)在同一 `sing-box run` 进程中实际同时运行,不仅通过 `check`;hysteria2/tuic 曾尝试但因字段/TLS 要求不同而排除在此次范围之外.新增自有的 `proxy/setup-proxy.sh`:任意四协议子集共用一个 systemd unit,一份 config.json 和 anytls 的 sing-box 二进制文件;`install.sh` 新增带独立 y/n 协议子问题的 `proxy` 模块,`preserve_proxy()` 在升级时保留端口和凭据,anytls/proxy 共用 amd64 架构限制.最初 `/proxy` 为每个已装协议显示端口,UUID/密码,共用 SNI,Clash 条目,链接和二维码,并只有一个“全部重置”按钮;[后续分支记录][local-link-006]说明替换成了独立按钮.`PortForwardManager.reserved_ports()` 也将所有代理端口保留.测试而非代码检查发现并修复两处缺陷:协议验证的 `exit 1` 被命令替换子 shell 吞掉,使无效 `PROXY_PROTOCOLS` 可能产生零入站配置;trojan 的随机端口区间可能超出 sing-box uint16 `listen_port` 的 65535 上限.在一次性 Docker 容器中验证:当时 systemd 不能以 PID 1 启动,故 `systemctl` 用空操作桩替代;其余路径——配置生成,真实 iptables 规则,凭据轮换,考虑共享二进制文件的卸载——均真实执行.包括五次全新安装,扩大缩小协议子集,重置,卸载以及完整无人值守 `install.sh` 安装和升级重跑,确认 `preserve_proxy()` 保持端口,UUID,密码及协议集合.`tests/test_app.py` 新增 19 项单元测试(147/147 通过).构建于 `feat/proxy-protocols`,叠加在未合并的 `feat/hardening-batch`(其 y/n 模块选择器当时尚未进入 `main`)之上;未合并,发布或打标签,仍待操作员审核及真实主机测试.

- 已完成:2026-09-19 增加二维码用于导入节点:anytls 页面各地址块在现有可复制文本链接旁加入可折叠的“扫码添加”二维码.随附 kazuhikoarase/qrcode-generator(MIT,`static/qrcode.js` 和支持多字节标签的 `static/qrcode-utf8.js`),由本项目自己的 `static/qrcode-render.js` 扫描 `[data-qr-text]` 元素,在客户端绘制内联 SVG;可供未来其他节点类型复用.HTTP 层测试确认分享链接正确地 HTML 转义到属性中(原样 `&` 会截断链接),并引用全部三个脚本;另在 Node 下对真实 anytls 分享链接及 Unicode 标签执行相同的随附文件内容,确认生成格式正确的 41×41 模块 QR SVG,并非空白或损坏.在没有 X server 可使用真实浏览器的无界面环境下,这是最接近浏览器的验证.

- 已完成:2026-09-19 模块化安装程序:把 `install.sh` 的 1/2/3/4 数字模块菜单改为三个独立 y/n 问题(web,iperf3,anytls),可逐项勾选而非选择固定预设;无人值守/脚本路径 `VPSSRV_MODULES` 不变.若 web 回答否,跳过 iperf3 问题,因为没有控制台可控制它.在一次性容器中验证全部四种回答组合(默认,仅 web,全部,仅 anytls)及两种无人值守回归情况.

[local-link-001]: #缺陷
[local-link-002]: DESIGN.md#设计目标
[local-link-003]: DESIGN.md#设计目标
[local-link-004]: #缺陷
[local-link-005]: #v110--2026-09-19
[local-link-006]: #分支记录-2026-09-22-状态快照
[local-link-007]: THIRD_PARTY_NOTICES.md

## 交接

- 分支:`feat/node-management`,基于 `feat/ui-redesign`,跟踪正式 GitHub 仓库.未发现临时项目规则.
- 已完成:节点编辑器将连接密钥标为“密码”;“流量与周期”展开时按钮保持原位.每个节点可独立限制上传和下载速度,达到 GiB 流量上限后可选择双向限速 1 Mbps 或停止使用,并可按自定天数,月数或年数重置周期流量.可选有效期到期后停止使用.第一版状态读取时升级到第二版,保留节点 ID,用量和流量上限;旧的绝对到期时间会清除,避免原先限速被解释为停止使用.IP 免密按钮始终显示;未获准的地址点击后,会提示先用密码登录,再到设置中添加内网 IP.修改免密设置仍需密码登录. 每个受管节点的“导入 Clash Meta”左侧现有复制按钮,复制的是局域网订阅 URL.节点卡片按宽度自动排成 1 至 6 列,宽屏最多 6 列;窄卡片中的信息会改为上下排列.
- 检查:308 项自动化测试通过(8 项跳过);Python 编译及差异空白检查通过.Chromium 在测试机上检查未获准 IP 的提示及桌面,390 px 宽度的节点表单;流量编辑按钮展开和收起后位置不变.nft 在只检查模式下接受新的双向限速和流量上限阻断规则.尚未逐一验证各策略下的真实流量. 测试机已有 3 个节点,另在浏览器中临时复制 3 张卡片用于布局检查,没有新增真实节点.Chromium 确认在 390,900,1200,1440,1920,2560 px 时依次显示 1 至 6 列;3840 px 仍为 6 列,没有横向溢出,并确认复制了节点的局域网订阅 URL.
- 部署:指定测试机曾在标准应用目录运行上一候选版本;旧运行文件和节点状态已在仓库外备份.节点状态此前已迁移到第二版.2026-09-27 的检查确认 Web,代理,节点计量和 AnyTLS 服务均在运行并已启用开机启动.尚未实际重启主机.
- 本轮规范对齐(2026-09-28):受管及旧版代理页面,Lucky,frps,iperf3 和端口转发页面在首次显示时遮蔽已保存的凭据与已配置端口.操作员点击显示,复制,导入或二维码后,已鉴权请求才获取对应值;隐藏,收起二维码或离开页面会清除已显示内容.节点编辑器的新端口留空时保留原端口.Lucky 和 frps 页面文字已接入全部八种界面语言.中文文档标点已按当前格式规范调整,代码示例未改动. 安装版本现优先读取部署时的 `VERSION` 标记,再读取随附的 `config/VERSION` 发行版本.
- 本轮检查:309 项自动化测试通过(8 项跳过);文档格式和多语言检查零错误;Python 编译及差异空白检查通过.干净的受版本控制文件导出通过项目结构检查;当前检出目录因 Limitations 已记录的忽略运行文件和缓存而未通过结构检查.Chromium 在本地夹具确认默认遮蔽,显示/隐藏,二维码生成和清除.测试机上验证了局域网登录,遮蔽的节点页面,授权显示凭据,静态脚本交付,四项运行中的服务以及已配置的 Web 监听端口.Chromium 还确认显示后离开再返回会恢复遮蔽.浏览器拒绝读取剪贴板,因此本轮没有核对剪贴板实际内容.
- 本轮部署:更新了指定测试机的标准应用目录,并先在仓库外备份旧版应用文件.仅重启 Web 服务;systemd 开机启用状态仍在.未重启主机,也未进行真实策略流量传输. 并已标记部署的开发修订版本.
- 本轮安全对齐:安全设置须经管理员密码验证,权限固定 10 分钟.验证成功换发会话;仅 IP 免密的会话未经验证不得读取名单或修改设置.权限有效期间修改密码只填写新密码和确认,修改后旧会话全部失效.私有 IPv4 与唯一本地 IPv6 名单共用独立启用开关;每次免密访问都重新检查名单和开关.Clash 导入按钮默认可见,仪表盘增设更新日志和设置入口.
- 本轮安全对齐检查:311 项自动化测试通过(8 项跳过);文档格式和多语言检查零错误;Python 编译及差异空白检查通过.本地链接检查仍报告 20 处原有译文片段错误(未改动基线有 20 处);没有新增损坏链接.Chromium 确认仪表盘的更新日志和设置入口,安全设置页及独立 IP 免密开关,390 px 宽度下清晰可读的 Clash 导入按钮,且页面没有横向溢出.
- 本轮安全对齐部署:指定测试机在备份旧 Web 文件,语言目录,文档和 IP 名单后接收了候选版本;备份权限为 0600.仅重启 Web 服务.登录页显示所部署的开发修订版本,四项服务运行正常,原有 IP 名单文件未改动.尚未实际重启主机,也未从名单内设备实测 IP 免密登录.
- 本轮设置调整:移除了导航栏中重复的管理员登录入口.普通设置页提供外观与语言选项,任何已登录会话(包括仅 IP 免密会话)都可打开.独立安全页及所有安全修改仍需限时管理员密码权限.验证表单收窄卡片并调整按钮间距和对齐. 导航栏在测速前增加仪表盘入口,安全设置改用与其他设置相同的卡片布局.
- 本轮检查:311 项自动化测试通过(8 项跳过);文档格式和多语言检查零错误,Python 编译及差异空白检查通过.Chromium 确认桌面和 390 px 布局无横向溢出,切换语言后主题仍被保留,安全入口独立,验证按钮间距合适,登录后正确返回普通设置.IP 免密权限边界及权限过期后的重定向通过自动化测试;尚未从名单内设备实测免密访问. Chromium 还确认三张设置卡片对齐,并可通过顶部的仪表盘入口返回首页.
- 本轮部署:指定测试机在标准应用目录运行 `dev-5c518c0`.旧版 Web 源码,样式,版本标记,管理员密码文件和 IP 名单均在仓库外留有权限为 0600 的备份;后两项文件未改动.仅重启 Web 服务.Web,proxy,node-meter 和 AnyTLS 服务均运行正常并设为开机启动;控制台仍监听原配置地址和端口.Chromium 已验证局域网登录,普通设置和安全设置.未实际重启主机.
- 当前节点访问管理:原“流量与周期”在八种界面语言中更名为“访问管理”.流量上限,上传和下载限速,达到上限后的行为,重置间隔和有效期均移入独立弹窗.常规卡片宽度下,“访问管理”“随机重置”“删除节点”位于同一行.测速前的导航入口现称“首页”.
- 本轮检查:311 项自动化测试通过(8 项跳过),Python 编译及 diff 空白检查通过.Chromium 确认中英文桌面卡片及 390 px 英文视口中的三按钮同排.窄屏弹窗打开时首个字段获得焦点,滚动设置时仍可见取消和保存按钮.未在测试机提交限制设置.
- 本轮部署:指定测试机在标准应用目录运行 `dev-a785fe5`.旧版 Web 源码,样式,脚本,语言目录和版本标记的权限为 0600 的备份保存在应用目录外.仅重启 Web 服务.Web,proxy,node-meter 和 AnyTLS 服务均运行正常并设为开机启动;控制台在原地址和端口监听,并通过局域网提供新版本.未重启主机.
- 当前规范检查(2026-09-28):译本文档中失效的标题片段已改用各语言一致的固定锚点.proxy 和 anytls 安装摘要现在只列网卡地址及可用的 Tailscale 地址,清除旧的 `public-ip.txt`,且不再进行出站公网 IP 查询.`SERVER_IP` 不再是安装选项.这次源码修改尚未部署到测试机;现有模块仍运行此前版本.
- 本轮检查:安装摘要修改后,311 项自动化测试通过(8 项跳过);Shell 语法,语言目录测试及 diff 空白检查通过.受版本控制文件的干净导出通过项目结构检查.当前工作区结构检查报告包括 `certs/` 在内的五项被忽略的运行状态或缓存,已列入限制.本地链接,译本文档和外部目标仍在最终复核.未发现临时项目规则.测试机上的安装摘要实际输出及主机重启尚未验证.
- 待办:在真实 Android 手机上验证 Clash 导入,验证各新策略的真实流量,名单内设备的 IP 免密访问及主机重启后的启动.下一步:完成文档检查和发布范围审核并推送本分支,然后完成这些验收检查再合并.
## 变更日志

<a id="vps-changelog"></a>

此处仅列已打标签的发布版本.以下条目保留原变更日志的完整历史,并记录 v2.0.0 的发布内容.

### v2.0.0 — 2026-09-27

#### 变更

- 将安装及卸载入口移至 `deploy/install.sh` 和 `deploy/uninstall.sh`,Web 源码移至 `src/web/`,随附依赖移至 `third_party/`,发布元数据移至 `config/`.调用旧检出路径的脚本需要改用新路径;已安装的运行数据仍留在原位置.
- 将原待办事项,状态,决策及变更日志文档整合至 `DESIGN.md` 和 `LOG.md`;把八种语言的文档及本地链接迁移至标准文档布局.界面文字现位于 `lang/` 下,文件名使用 BCP-47 语言标签.

#### 新增

- 纳入四协议 proxy 模块,共用的控制台页面,各协议独立的凭据重置控件,以及浏览器初次设置向导.
- 纳入实验性的 frps 和 Lucky 安装程序及其随附的可执行文件.原始许可证文件与制品散列均记录于第三方组件清单.

#### 验证与限制

- 本地单元测试:271 项通过,8 项跳过.依赖散列,文档及多语言结构检查均通过.文档检查器报告英文文档导航标签有四项警告.
- 2026-09-27,仓库内七个随附构件均与对应的上游发布文件逐字节一致;随附可执行文件的原始许可证文件也与相应发布归档一致.尚未取得独立的法律解释.
- 此次检出版本的真实主机/systemd 验收及独立母语审阅仍待完成.frps 和 Lucky 在本版本中仍属实验性模块.

### v1.1.2 — 2026-09-21

#### Fixed

- 当使用 `install.sh`(历史上也通过 install.sh 重现)从没有新增设置的旧版升级时(例如从 v1.0.4 升级后遇到 v1.1.0 的端口转发设置),安装程序可能在最后一个新增设置提示后静默中止——在复制文件,更新 `VERSION` 或重启服务之前,也无错误信息——使主机停留在旧版,却看似正常完成安装.

### v1.1.1 — 2026-09-20

#### Fixed

- README 安装节的单行快速安装和分步命令仍使用 `--branch v1.0.4`;紧随 v1.1.0 发布后照着执行的用户会安装缺少端口转发的上一版.

### v1.1.0 — 2026-09-19

<a id="vps-release-v1-1-0"></a>

#### Added

- **控制台管理的端口转发.** 新“端口转发”页面可将本机公网 TCP/UDP 端口转发到通过 Tailscale 或局域网可达的设备;适合本机有公网 IP,目标设备没有的情况.控制台可添加,启用,禁用和删除规则;应用前会与安装使用的每个端口(控制台,公开页面,iperf3,anytls)比较以排除冲突.规则通过 `iptables` DNAT + MASQUERADE 实现,服务每次启动都会自动重放,因此重启服务或系统后已启用的转发会立即恢复.首次需要时自动开启 `net.ipv4.ip_forward`.设置 `VPSSRV_PORTFWD_ENABLE=0` 可从安装中完全移除该功能.

### v1.0.4 — 2026-09-12

#### Changed

- 安装程序末尾摘要现在打印主机真实 IP,而不是需要手动替换才能使用网址的 `<this-server>` 占位符.内核实际出站使用的地址出现在公开页面和控制台网址中;多宿主机的其他地址列在下方并标注接口,因此只通过 ZeroTier 或 Tailscale 可访问的节点也能直接看到地址.若无法获取地址,仍使用旧占位符,避免非关键的显示问题导致安装失败.

### v1.0.3 — 2026-09-12

#### Fixed

- v1.0.2 修复后,`install_iperf3()` 仍可能失败:`apt-get update` 虽成功,但 `security.debian.org` CDN 返回陈旧索引,接下来的 `apt-get install` 获取索引刚声明存在的 `.deb` 时返回 404;实际发生于真实主机从 v1.0.1 升级到 v1.0.2.单独重试 `update` 未必奏效,可能再次命中同一陈旧节点.安装程序改为最多重试三次整个“更新然后安装”流程,直至访问同步完成的镜像.
- README 的 `## Install` 节还留着模板占位符:字面值 `<repo-url>` 及本项目从未发布过的示例标签 `v0.1.0`.两者已改为项目真实 GitHub URL 和当时的发布标签.

### v1.0.2 — 2026-09-12

#### Fixed

- `install.sh` 可能静默无法安装 iperf3:更新和安装 apt 包被串成链,所有输出又被隐藏,所以任何无关的故障仓库(真实 VPS 上存在陈旧第三方 `.list`)都让更新失败并跳过安装,无法查明原因.现在会重试更新;即使更新失败也尝试安装;若安装确实失败,不再隐藏 apt 自身的错误输出.

### v1.0.1 — 2026-09-12

#### Fixed

- 三种语言的变更日志页面把 CHANGELOG 文件底部的维护者注释(标出哪些标题应保留英文)当普通段落显示,连转义后的
  `<!--`,`-->` 也显示出来.渲染器完全未处理注释.仅影响显示,其他功能不受影响.

### v1.0.0 — 2026-09-12

首次发布.它结合两个已有项目——带密码保护的 VPS 测速控制台和 sing-box `anytls` 安装程序——并增加两者都没有的功能:按需开启的 iperf3 窗口,以及供任何人检查 Web 端口上的 IP 是否可达的公开页面.

#### Added

- **80 和 443 上无需登录的公开可达性页面.** 把 IP 交给别人,页面能显示即说明对方所在位置可以访问你的 Web 端口.页面仅报告源地址,服务器时钟,到达端口及协议,不透露主机其他信息.刻意同时使用两个端口,以区分“主机不可达”与“仅 443 被阻断”.
- **按需开启的 iperf3 窗口.** 控制台开启限时窗口;`iperf3` 只在窗口期内运行,在当前防火墙中开放其端口,到期,操作员要求或服务停止时同时关闭进程及端口.没有“持续运行”选项,因为公开的 iperf3 服务可能让陌生人耗尽上行带宽.窗口开启时公开页面会予以提示,使测试者知道何时连接.
- **浏览器测速与访客日志.** 控制台通过 LibreSpeed 引擎测量上传/下载,并从内核连接表记录任意端口(不限 HTTP)的全部入站 TCP 连接.
- **anytls 代理模块.** sing-box,自签名证书和 BBR.控制台显示节点端口,密码及 SNI,提供可复制的 Clash 条目和 `anytls://` 链接,也可轮换凭据.
- **模块选择式安装程序.** web,iperf3,anytls 可独立通过交互选择,也可通过 `VPSSRV_MODULES` 无人值守选择.若端口被其他进程占用则拒绝抢占;非 x86-64 主机跳过 anytls,而非安装无法执行的二进制文件.
- **识别升级的重新安装.** 重跑安装程序会检测现有安装,提供保留配置的选项,重放服务 unit 中的设置,保留 anytls 凭据,只询问旧版本尚无的设置.早于该记录机制的安装则从磁盘读取模块列表.
- **三种界面语言:** 英语,简体中文,繁体中文;安装时选择,每次访问可切换,且会记住选择.
- **离线安装.** sing-box 二进制文件随仓库提供,除发行版软件包镜像之外无需网络.

**发布说明(v1.0.0):**

- 整个项目为 GPL-3.0,因为重新分发了 GPL-3.0 的 sing-box 二进制文件.组件许可证及 GPL 所要求的对应源码链接见 [THIRD_PARTY_NOTICES.md][local-link-007].
- 443 上使用自签名 TLS 证书:没有域名或 ACME.浏览器警告仍证明端口可以响应,这正是该页面需要回答的问题.
- iperf3 JSON 输出中的 `mean_rtt` 来自内核 `TCP_INFO`,所以 Linux 客户端能报告往返时延,无法读取该信息的客户端(例如 Windows 上 Cygwin 的 iperf3)只能报告吞吐量.UDP 模式(`-u`)在所有环境下提供抖动和丢包数据.
- anytls 模块仅支持 x86-64;web 和 iperf3 不受架构限制.

## 提交历史

以下按时间顺序保留 Git 提交标题.最后一项记录本次文档提交.

- `b3cc391` docs: add documentation skeleton and agreed design
- `63f1680` feat(web): vendor the web module and add the public page and iperf3 window
- `c0def78` feat(anytls): vendor the anytls module and record third-party licences
- `dc70d9b` feat(install): turn the installer into a module menu
- `fcf7878` fix(install): print a teardown command that actually works
- `6022737` docs: record that the iperf3 window works under systemd sandboxing
- `790b7c6` fix(anytls): install the sing-box binary that was there all along
- `f0862d0` feat(console): add an anytls node page, and stop the iperf buttons competing
- `aa01a30` feat(console): show the anytls port, password and every usable address
- `901cc0c` fix(ui): make the copy button quiet, and every colour survive light mode
- `5c6e65a` feat(anytls): let the console rotate the node's port and password
- `27e2c9d` docs(anytls): keep the upstream tag as the file's last line
- `03bb980` feat(install): carry an existing install's settings across an upgrade
- `33d8488` fix(anytls): run the reset outside this service's sandbox
- `00bf933` fix(anytls): stop a raw iptables line leaking into the install summary
- `c8330ba` fix: eleven defects from a full audit
- `0be4851` docs(backlog): tick the anytls vendoring item, done since c0def78
- `a9d6b1d` fix(ui): align the iperf form, and let the layout survive a narrow screen
- `3843ccb` docs: correct two stale backlog ticks and the mean_rtt claim
- `cc0cf4d` docs: record three more verifications, and what is left
- `8e2ea5e` chore(release): v1.0.0
- `40a4bc3` fix(changelog): stop rendering the maintainer comment to readers
- `bbc7bd1` chore(release): v1.0.1
- `98d3bf7` chore(release): v1.0.2
- `aceecfd` chore(release): v1.0.3
- `e723745` chore(release): v1.0.4
- `4983c10` refactor(docs): migrate docs to doc/ + doc/<lang>/ layout
- `a468514` docs(i18n): scaffold five extended-language placeholders, fix README Install
- `42ffe49` docs(i18n): sync README Install one-liner to zh_cn/zh_tw translations
- `0bbb682` feat(portfwd): console-managed iptables port forwarding
- `2b3caee` docs(backlog): record web-based first-run setup page idea
- `14608c6` chore(release): v1.1.0
- `eace062` chore(release): v1.1.1
- `9e09d8a` fix(install): stop install.sh silently dying mid-upgrade
- `5451526` refactor(project): publish standardized project tree
- `f300ab7` docs(log): record GitHub synchronization
- `53c390c` chore(release): prepare v2.0.0 content
- `f9eb612` docs(release): verify bundled artifact provenance
- `5868549` docs(log): record v2.0.0 publication handoff
- `56c9ed5` docs(readme): translate installation example comments
- `51e89bc` feat(nodes): scaffold numbering and refresh proxy workspace
- `ed58969` feat(nodes): add managed controls and traffic policing
- `d0d6ae7` docs: restore required multilingual sections
- `84b9599` fix(web): show development revision in checkout
- `e986c51` fix(install): create flat entry during in-place install
- `eaceed8` fix(install): stage modules during in-place install
- `5ff2a6b` fix(web): condense mobile navigation
- `2477fcc` docs: record node deployment handoff
- `d31e40f` docs(log): synchronize commit history
- `0696e4b` fix(nodes): keep sustained traffic within 1 Mbps
- `da5f84f` docs(log): record measured node acceptance
- `b74b412` feat(proxy): add Clash Meta import and GiB node controls
- `773eedf` feat(web): unify console and setup interface design
- `9a615ab` feat(nodes): support multiple nodes and in-place editing
- `6c1459d` docs(log): record node management delivery
- `47b3686` feat(console): refine nodes, login and iperf3 port
- `3d69356` docs(log): record GitHub synchronization
- `6e461a3` fix(iperf): clarify finished state
- `a676537` feat(nodes): add per-node switch and compact numbering
- `ab02c17` docs(log): record node switch acceptance
- `860cdc4` feat(auth): add private-IP access and admin settings
- `ad08a80` feat(web): refine access screens and proxy node cards
- `be8b4a5` feat(nodes): add flexible limits and persistent IP login entry
- `b0a9c6c` feat(web): copy Clash links and fit up to six node columns
- `d07b40a` fix(web): mask configured values and align project documents
- `7065e18` fix(web): honor installed version stamp
- `b870053` fix(web): prioritize deployed stamp over stale git metadata
- `81f1e13` feat(auth): align security settings and dashboard access
- `7524ec3` docs(log): record security alignment checks and deployment
- `b1a8f21` feat(web): separate preferences from security settings
- `dd9627f` fix(web): keep security entry visible in settings
- `0fc871a` fix(auth): return to requested settings page after login
- `5c518c0` fix(web): add dashboard link and align security card
- `9db2482` docs(log): record settings review and deployment
- `fdf8fbc` feat(nodes): move access limits into dialog
- `a785fe5` fix(nodes): keep action buttons on one row
- `d03abb7` docs(log): record access dialog and test deployment
- (this commit) fix(standards): align setup addresses and document links
