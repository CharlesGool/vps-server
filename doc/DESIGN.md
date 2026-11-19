---
name: project-design
description: 项目架构与设计约束
metadata:
  version: "2.0.0"
  lang: "zh-CN"
---

# vps-server — 设计

## 多语言

**简体中文** | [English](en/DESIGN.md) | [Español](es/DESIGN.md)

## 文档

- 项目概览: [README](../README.md)

- 设计思路: [DESIGN](DESIGN.md)

- 项目状态: [LOG](LOG.md)
- 历史记录: [HISTORY](HISTORY.md)
- 变更日志: [CHANGELOG](CHANGELOG.md)

- 第三方声明: [THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES.md)

## 设计目标

- [x] 用一个认证控制台管理按需启用的网络工具和独立服务.
- [x] 将可替换代码与持久状态分离, 在同一数据布局内保留配置升级.
- [x] 通过受限的权限辅助程序执行服务, 端口和网络规则变更, 提供可查询的后台任务结果.
- [x] 支持简体中文, 英语和西班牙语, 并随附固定摘要的客户端资源.

非目标: 通用容器平台, 任意 FRP 配置编辑器, 自动查找公网 IP, 完全锁定目标操作系统软件包.

## 架构

浏览器通过 Python 标准库 HTTP 服务访问页面与认证接口. `src/web/features/` 按功能提供处理器;独立 systemd 服务运行 Singbox, FRPS, FRPC, Caddy 和 Tailscale. Web 服务使用系统保护选项, 把有限的特权操作交给 root 辅助程序;浏览器终端经过单独的密码验证后运行 root PTY.

安装器在语言选择后启动 `vps-server-install` 后台任务, 前台跟随任务的 `summary.log`, 只显示关键步骤, 地址密码和失败原因. 停止任何服务前检查 Python 版本和主机基础组件的最低版本(`core` 检查: Bash, systemd, SQLite, Python 使用的 OpenSSL 库, 基础命令);各模块的主机条件(nft 能读取规则表, `/dev/net/tun`, 已有 tailscaled, iptables 与 `ss`/`ip`)由 `src/web/host_checks.py` 统一判断, 安装器, 控制台模块任务和未安装模块卡片共用同一结果代码. 控制台安装模块时以 `VPSSRV_MODULE_ONLY=1` 只安装所选模块, Web 和其他模块保持运行. FRPC 保存/重命名先返回等待页, 后台验证并应用配置, 延迟重启实例;状态查询在隧道中断后重试, 成功与失败均以实际任务结果为准.

| 目录 | 职责 |
| --- | --- |
| `.local/` | Git 忽略的维护资料, 历史快照与私有笔记;不参与部署. |
| `.github/` | 持续集成检查和 Actions 依赖更新配置. |
| `src/` | Python 后端, 功能处理器与固定静态资源. |
| `web/` | Vue 单页控制台: 页面, 共享组件和项目组件, 设计标记, 测试与前端构建配置. |
| `deploy/` | 安装, 卸载, 模块配置脚本与 systemd 模板. |
| `config/` | 版本, 固定依赖摘要及导入来源记录. |
| `lang/` | 界面与安装器翻译;配置值 `zh_cn` 对应简体中文. |
| `third_party/` | 上游可执行文件, 归档, 许可及来源记录. |
| `tools/` | 样式构建, 依赖校验与离线包构建工具. |
| `doc/` | 设计, 状态, 历史, 变更, 第三方声明及译文. |

控制台界面是基于最新 Web UI 起始模板的 Vue 单页(`web/`, 决策见 [LOG](LOG.md#决策)). `src/web/features/spa.py` 的 `SPA_PAGES` 列出全部页面路径: 控制台对它们返回 `web/dist/index.html`, `/assets/` 和根目录的 `appearance.js`, `favicon.svg` 来自 `web/dist/`; 页面通过同源 `/api/*` 读写, 写请求只接受 `application/json`(上传为 `application/octet-stream`)且检查 `Origin`. 接口按页面分在 `features/api_*.py`, 各自在 `API_ROUTES_*` 表里登记, 业务逻辑调用原有函数; 端口, 凭据, 命令等默认遮住的值统一经 `/api/private-value` 取. 登录沿用原有体系, 按模板的 `/api/session`, `login`, `login/ip`, `logout`, `security/verify` 约定提供, 另加 `login/cert`. 页面之外服务器只保留: 测速引擎(`/speedtest/*`), 终端 WebSocket(`/terminal/ws`), 迷你网盘下载(`/f/`), Clash 订阅(`/clash/sub/`), 备份下载, 公开页面跳转和两个旧地址跳转(`/anytls`, `/frp/client/edit`); 没有客户端证书的设备和未知路径得到一个独立的简单页面(`notice_page`). 随附的 LibreSpeed, xterm.js 和二维码库仍在 `src/web/static/third_party/`, 由页面按需加载. 功能被关闭时页面和接口都转到 `/closed`. 项目自己的界面组件在 `web/src/components/vps/`(只组合模板组件): 流量卡片, 默认遮住的值, 模块安装卡片, 管理员密码验证, 终端, 计划字段, 二维码. 界面文本在 `lang/ui/`(`console` 是沿用的原有译文, `vps` 是新增文本), 服务器生成的文本(任务描述, 模块任务状态等)仍用 `lang/web/`.

`web/src/styles/tokens.css` 是设计数值的唯一来源. 在 `web/` 运行 `npm ci && npm run check`: 设计检查, 类型检查, 生产构建, Playwright 测试(三个临时状态目录的 Python 控制台: 桌面, 手机和项目自己的功能测试 `e2e/vps-*.spec.ts`; HTTPS 自签名证书, Chromium 以 `--ignore-certificate-errors` 启动, 固定 UTC 时区; 截图里随运行变化的内容用 `e2e/support.ts` 的固定样例)和 Python 单元测试. 正式构建用 `APP_VERSION=<版本> npm run build`, 版本写进页面并与服务器报告的版本核对.

`.github/` 运行相同检查, `.claude/settings.json` 在编辑后运行模板设计检查. `tools/check-project/check_project.py` 另检查 Python/Bash/JavaScript, 翻译, 文档和固定构件. `tools/build-offline/build_offline.py` 生成两个安装包: 离线版(默认)内置全部第三方程序和 Debian 13 运行库(nft, iptables, `ip`, `ss`); `--variant online` 的在线版不含大型二进制, 安装时由 `src/web/online_assets.py` 按 `config/online-assets.json` 下载并逐个校验 SHA-256. 这些上游二进制不提交到 Git, 构建离线版时用同一模块下载到 `third_party/`(被 Git 忽略)再打包;nftables 运行库和对应源码由 `fetch_assets.py` 下载并核验. 两个包的安装和解压只依赖 python3, 不依赖 curl, tar, gzip 或 Git. 版本来自后端实际构建标识, 作为组件属性传入;正式变更日志继续取自三语言 CHANGELOG.

## 设计约束

- **必须**在认证与权限复验后提供敏感数据;初始 HTML **禁止**包含隐藏的真实凭据. 编辑已有对象**必须**载入原值, 不能用空白字段覆盖未修改值.
- 端口**必须**先锁定并登记归属再启用监听;失败时释放新增登记, **禁止**抢占其他项目的登记.
- FRP 修改**必须**先验证, 失败时保留或尽可能恢复原配置;高级非受管配置**禁止**被结构化编辑器丢弃.
- 节点可按目标限制访问范围(库存节点的可选字段 `access`):不设置即不限制;`internet` 拒绝私有, 回环, 链路本地和 100.64.0.0/10 地址;`custom` 只放行列出的 IP/网段/域名(可带端口), 其余拒绝. 规则由 `node_inventory.apply_access` 写入 sing-box `route.rules`(先 `resolve` 再匹配, 域名按解析出的地址判断), 与入站配置同一事务应用并随节点开关重新生成;**禁止**手写规则被覆盖(只替换仅匹配单个节点入站的规则).
- 首页顶部的总流量条(`src/web/total_meter.py`, 状态 `data/total-traffic.json`)把各计量条目的生命周期计数按各自倍数相加, 周期用量 = 周期开始后的增长. 周期按重置计划起算: 每周, 每月或每年的某个时间点(服务器本地时间, 与定时任务同一套规则, 规则在 `src/web/schedule_time.py`), 旧版本的"每月某日"设置仍按 UTC 0 点, 首次记录或旧状态重建时, 用各条目自己页面显示的\"当前周期\"计数器补上已用部分(没有周期计数器的从零开始), 这样总量和各页面对得上; 之后到期自动开始新周期, 删除的条目不会使用量变负. 每项显示原始流量 × 倍数 = 计费用量. 手动**校准**(填入服务商显示的已用量)把差值作为有符号的校准值单独保存, 在自己的一条进度条上显示并计入总量, 新周期开始时清零. 总上限目前只显示和提醒, **禁止**把它当作已强制的限制;控制台页面, 终端和 SSH 不计.
- 静态数据加密(`src/web/secure_store.py`, `src/web/crypto_box.py`): 数据密钥是 256 位随机数, 保存在 `/etc/vps-server/data.key`(0600, 由安装器创建, 不在状态目录). 控制台私有的状态文件写成 `VSE1` + 随机 nonce + ChaCha20-Poly1305 密文, 附加认证数据绑定文件名, 防止把一个文件换成另一个; 追加写的审计日志逐行加密. 读取同时接受旧版本的明文文件, 下一次写入或启动时的迁移把它转成加密; 没有密钥文件时一切照旧为明文. 加密但解不开的文件抛 `SecureStoreError`(`ValueError`), 绝不被空状态覆盖(控制台访问名单仍按"损坏的列表不能把所有人锁在外面"处理为关闭). TLS 私钥只在内存文件(`memfd`)里解密后交给 `ssl`; 客户端 CA 私钥只在签发证书的几毫秒里以 0600 的临时副本存在. 需要被 sing-box, frps, Caddy, tailscaled 直接读取的配置不加密. 原语(ChaCha20-Poly1305, X25519, HKDF)是 RFC 8439, 7748, 5869 的纯 Python 实现, 用 RFC 测试向量和参考库交叉验证.
- 备份加密: 配置备份封装到操作员的 X25519 公钥(每个备份一把临时密钥 + HKDF + ChaCha20-Poly1305, 文件头 `VSB1`), 服务器只有公钥, 写得了备份读不回; 私钥只在生成时显示一次, 恢复时随表单提交, 经 0600 临时文件交给后台恢复进程并立即删除. 加密备份包含数据密钥; 未设公钥时备份为明文且**必须不含**数据密钥, 否则密钥和密文就在同一个文件里. 恢复前先自动备份当前状态. 恢复分两步: 先预览(`config_backup.inspect`: 来源主机, 版本, 类型, 创建时间, 文件数; 加密备份要先输入私钥才能看), 再确认; 来自另一台主机或更新版本的备份属于风险项, 必须勾选确认, 服务器在执行前重新判断而不信任页面. 下载和上传都不需要私钥(服务器没有私钥, 也无法验证), 私钥只在恢复这一步给出. 加密备份的文件头(`VSB2`)记录目标公钥的 16 字节标识, 列表据此标出"密钥不同"; 旧格式(`VSB1`)仍可打开. 恢复进程把结果写入 `<状态目录>/restore-result.json`, 备份页顶部显示, 失败时说明未改动当前配置.
- 登录方式(`client_cert.py` 的 `login_mode`): `password`, `cert`, `either`, `both` 四种. 旧状态的 `required` 映射为 `cert`, 否则为 `either`; 保存时 `required` 同步写入以便旧版本行为合理. 需要证书的方式(`cert`, `both`)要求每个请求带有效客户端证书(逐请求判断, 以便吊销立即生效); 密码登录在 `password`, `either`, `both` 允许, 证书登录只在 `cert`, `either` 允许, `both` 中证书只是门槛, 不能单独登录. 切到需要证书的方式前, 当前连接必须出示有效证书且至少有一张有效证书.
- 升级签名(`src/web/release_trust.py`, `src/web/ed25519.py`, `src/web/upgrade.py`, `tools/sign-release/`): 发布的 `SHA256SUMS` 用维护者的 Ed25519 私钥签名, 私钥加密保存在另一台主机, 签名通过 SSH 取回, 构建机从不接触私钥. 主机把包里的公钥固定在 `<状态根>/release-key.pub`(0600), 之后只接受同一把密钥签名的包. 验证放在**已安装**的 `upgrade.py` 里先做(新包里的安装器不能为自己担保), 顺序是: 验签, 比对包的 SHA-256, 安全解包(拒绝绝对路径, `..`, 越界链接, 设备文件), 包内版本与标签一致, 最后才运行包里的安装器; 安装器自己也检查包带的密钥与固定的是否相同, 不同或没有密钥一律拒绝(旧命令装 fork 的包同样被拒). 验证只用标准库的纯 Python 实现(RFC 8032), 主机不需要装任何依赖. 换密钥必须由操作员给出新指纹. 首次固定是信任首次使用, 请核对指纹.
- 配置备份(`src/web/config_backup.py`)只保存配置和状态: 状态目录(不含 `data/files/` 迷你网盘内容和 `backups/` 本身, 含 Tailscale 登录状态), `/etc/vps-server*`, `/etc/frp`, Caddy 状态, 服务单元文件. 文件为 `<状态目录>/backups/config-<UTC 时间>-<类型>.tar.gz`, 权限 0600, 类型为 manual, scheduled, pre-upgrade, pre-restore. 创建只读文件, 由控制台自己完成; 恢复要写系统文件, 经 `systemd-run` 在沙箱外执行, 先校验每个条目只能落在配置路径内(拒绝符号链接, 绝对路径, `..`), 先自动备份当前状态, 再按顺序重启服务. 新文件用硬链接占位命名, 同一秒的两份备份不会互相覆盖. 安装器升级前自动执行 `config_backup.py create --kind pre-upgrade --keep 3`, 失败只警告不中止升级. 备份含私钥, **禁止**把它放进静态资源或日志.
- 定时任务(`src/web/scheduler.py`, 状态 `data/scheduled-tasks.json`, 记录 `data/scheduled-runs.json`)在控制台进程里每 10 秒检查一次, 用服务器本地时间触发. 执行方式有每隔一段时间(分钟, 小时, 天; 从上次启动起算, 停机很久后只补一次, 不连续补跑), 每天, 每周几天, 每月某日(1 到 31, 没有这一天的月份在月末那天), 每年某月某日和 cron 表达式, 前几种在存储里同时保存 `spec` 和等价的 cron; 命令经 `systemd-run` 以 root 在沙箱外执行并受超时限制, 上一次未结束时不重复启动(记录为已跳过), 每个任务只留最近 20 次记录, 失败可经 Bark 通知. 内置的配置备份用同一套计划模型和同一个表单. 计划分两类: 循环(每隔一段时间, 每天, 每周几天, 每月某日, cron)和只执行一次(日期 + 时间); 每天, 每周, 每月和单次的时间精确到秒, 控制台每秒检查一次. 每个计划保存一个\"标记\"(上次启动的时间或已处理的那一次的时间), 触发只看标记之后的时间点, 所以重启不会重复, 停机后只补一次而不是连发; 时间点型计划错过不超过 2 分钟仍会执行, 更久的不补. 单次计划不能选过去的时间, 执行后自动标为已完成并停用(任务保留在列表里, 备份则关闭定时), 错过的记录为已跳过; 已完成的单次任务要改成将来的时间才能重新启用. 重启期间错过的触发不补跑.
- 各计量条目的重置周期也用这套计划(`node_inventory` 的 `at:weekly|monthly|yearly:…@HH:MM:SS`, 服务器本地时间), 或只重置一次; 旧版本的"每隔 N 天/月/年"(`every:…`)继续有效, 直到在页面上改掉.
- 节点和 FRPS 的流量配额按 `(上传 + 下载) × 2` 计入;读取计量失败**禁止**被当作达到配额. 周期重置**必须**同步重建内核 quota.
- FRPS 与节点使用同一套计费和 nft 规则, 按 bindPort 计量(`src/web/frps_meter.py`, 独立表 `vps_server_frps`);FRPS 服务依赖计量服务, 计量失败时**必须**停止 FRPS.
- 其余走流量的功能也有同样的流量统计和限制(流量上限后限速到 1 Mbps 或断开, 上下行限速, 有效期, 重置周期), 在各自页面的"流量限制"里设置; 控制台页面, 终端和 SSH 不计. `src/web/traffic_meter.py`(服务 `vps-server-traffic-meter`, 独立表 `vps_server_traffic`)复用节点计量的 tick, 每个条目带自己的匹配规则和计数倍数: 域名转发计 Caddy 的 80/443, iperf3 计其端口, FRPC 计与服务器地址和端口的连接, 连接同一服务器的实例分不开, 合并为一个条目统计和限制(键 `frpcsrv:<服务器>:<端口>`, v6.3.0 的按实例条目升级时并入), 均计一次; 端口转发每条规则计 forward 链上去往和来自目标的包, 计两次; Tailscale 计 `tailscale0` 网卡, 经本机转发的包重复一次计数规则, 计两次. 删除的转发规则和不再有实例连接的 FRPC 服务器连同条目删除, 关闭或卸载的模块保留条目和限制. 这些功能并非围绕限额设计, 计量失败时只记录并重试, **禁止**因此停止它们. 迷你网盘和测速与控制台共用端口, 内核分不出它们的字节, 由控制台自己计数和限速(`src/web/app_meter.py`, 每个字节计一次); 经域名下载迷你网盘文件时, 这些字节同时计入迷你网盘和域名转发.
- 客户端证书**必须**用随附的 openssl 和项目自带的最小配置签发; 证书包**必须**用 SHA1/3DES 加密和 SHA1 MAC 导出(OpenSSL 3 默认的 AES/PBKDF2 在 macOS 上报密码错误);新的证书颁发机构**必须**先在主机 TLS 库上通过双向 TLS 自检.
- 新签发的 CA 和设备证书的 CN 带主机名(只保留 ASCII 字母数字, 点和横线);已有 CA 不改名, 改名会使已发证书失效. 设置文件由 `cert_setup.py` 生成, 带证书的版本只在签发页提供: Windows 是 .cmd 加内嵌 PowerShell, 只写当前用户的证书库和 HKCU 策略, 不需要管理员权限, 私钥导入为不可导出; macOS 是用户范围的描述文件(PKCS#12 载荷不含密码, 安装时由系统询问, 加 Chrome 和 Edge 的策略载荷); Linux 是 bash 脚本, 用 pk12util 导入到 `~/.pki/nssdb`, 并用 sudo 合并各浏览器策略目录下的 `vps-server.json`, 保留其他条目.
- 资源监控(`src/web/sysmon.py`)只读 `/proc`, `/sys` 和 statvfs, GPU 只在有 `nvidia-smi` 时读; 控制台进程里的采样线程每 5 秒更新 CPU 和网卡速率, 每分钟记一个历史点(保留 24 小时, `data/monitor-history.json`)并检查告警阈值(`data/monitor.json`), 告警经 Bark, 同一事件一天最多一次. 采样线程同时保留最近 1 分钟的 5 秒点(实时图). 页面画最近 15 分钟的每分钟平均值; 令牌接口另给 24 小时的 12 段和 24 段平均值.
- 系统页, 文件管理和多主机的所有接口要求安全设置权限(和终端一样, 最近验证过管理员密码). 控制台在 `ProtectSystem=strict` 下只能读, 要写系统文件的操作(主机名和 `/etc/hosts`, `apt-get update`, 文件的新建, 改名, 复制, 移动, 删除, 改权限和所有者, 压缩解压, 写入)经 `systemd-run` 交给 root 辅助程序 `src/web/sysadmin.py`, 它只接受白名单动作的 JSON 请求; 上传和编辑先写进 `data/fm-staging/`(0700), 再由辅助程序放到目标位置(覆盖时保留原权限和所有者). 系统目录本身(`/`, `/etc`, `/usr` 等)**禁止**删除, 移动或重命名; `/proc`, `/sys`, `/dev` **禁止**写入; 解压**必须**拒绝落到目标目录外的条目和设备文件. `apt-get upgrade` 作为单独的临时单元 `vps-server-apt-upgrade` 运行, 输出写到 `data/apt-upgrade.log`. 服务的启停和开机自启直接经 systemctl(D-Bus), 控制台自己的服务**禁止**停止或取消自启.
- 令牌接口(`/api/v1/*`, `src/web/api_tokens.py`, `features/api_v1.py`, 说明见 [API](API.md)): 令牌只存 SHA-256(`data/api-tokens.json`, 有数据密钥时加密), 分只读和读写; 请求在会话, 同源和客户端证书检查之前处理, 错误的令牌按登录失败计数. 多主机(`src/web/fleet.py`, `data/fleet.json`)保存其他控制台的地址, 令牌和证书校验方式: 添加时证书能按公共 CA 验证的用正常 HTTPS 校验(可以续期), 否则固定当时证书的 SHA-256 指纹; 发送令牌前先完成校验, 指纹变了就不再连接.
- iperf3 服务端**必须**限时运行, Web 停止时关闭临时进程与本项目转发规则. **禁止**重置整个主机的 `ip_forward` 或删除其他程序的防火墙规则.
- TLS 握手**必须**在各连接的工作线程中完成并设置超时;在接受连接的线程中握手会让空闲连接阻塞整个监听器.
- 重启 Web 期间**禁止**持有 `.ports.lock`;新 Web 进程启动时通过同一锁释放残留登记.
- 单模块安装**禁止**停止, 重装或禁用其他模块的服务.
- 公开监听器与控制台路由边界**必须**分离. 信任代理地址头时**禁止**依赖其地址进行 IP 免密认证.
- 信任代理地址头时, 客户端地址**必须**取代理追加的最后一个 `X-Forwarded-For` 项; 左侧各项可被客户端伪造, **禁止**用于封禁和访问限制.
- 控制台页面**禁止**使用内联脚本和内联事件属性; 响应默认带 `script-src 'self'` 的 Content-Security-Policy 和禁止嵌入的头. 内联样式保留允许, 因为 xterm.js 和 UI 在运行时设置样式.
- 控制台访问限制在 TLS 握手前按来源地址断开连接, 本机回环地址始终允许; 设置文件变化后立即生效, 文件损坏时按关闭处理, 以免把所有人挡在外面.
- 控制台**必须**只提供 HTTPS. 客户端证书由控制台自建 CA(`certs/client-ca.*`)签发, 服务器**禁止**保存设备私钥;TLS 层只请求不强制证书(`CERT_OPTIONAL`), "要求证书"在 HTTP 层逐请求检查并核对未撤销的序列号, 以便 Clash 订阅和迷你网盘下载链接照常访问, 撤销无需重建 TLS. 开启要求前当前连接**必须**已出示有效证书, 要求期间**禁止**撤销当前连接使用的证书.
- 同布局安装**必须**保留持久状态;旧布局或缺失定位文件**禁止**被当作空白安装自动覆盖.
- 第三方构件**必须**核验固定摘要并携带原始许可与对应源码获取方式. 文件身份校验不代表系统依赖完全锁定.

## 设计标记

`web/` 的设计标记原样取自最新 Web UI 起始模板(字号, 字重, 8 px 倍数行高, 间距, 圆角, 阴影, 容器, 八主题色, 动效), 本项目没有新增标记. 新增共享组件 `ModuleCard`(带开关的功能入口卡片)和 `LogOutput`(日志框), 样例在组件样例里; 改动的模板组件: `NumberField` 加 `grouping`(端口不加千位分隔符), `DataTable` 的滚动区域可键盘聚焦, `PaginationBar` 页码过多时换行, `LoginPanel` 加证书登录按钮, `CopyButton` 改用共用的 `lib/clipboard.ts`; 顶栏不显示项目标志(决策 2026-10-07). 外观记录沿用 v7 的 `vps-server-mode`/`vps-server-theme`, 语言同步到服务器的 `lang` Cookie. 检查命令: `cd web && npm run check`.

## 数据设计

| 位置 | 数据 |
| --- | --- |
| `/var/lib/vps-server` | 默认状态根, 布局 1;由 `/etc/vps-server/state-dir` 定位. |
| `admin_password.txt`, `console_port.txt`, `.env`, `paths.json`, `.layout-version` | 认证, 固定端口, 配置及路径/布局元数据. |
| `certs/` | TLS 证书与私钥;客户端证书 CA(`client-ca.pem`, `client-ca.key`)与签发记录 `client-auth.json`(要求开关, 序列号, 设备名, 撤销状态). |
| `data/` | SQLite 访客库, 会话与签名密钥, 功能状态, 节点清单和后台任务; 登录安全设置(`login-ban.json`, `console-access.json`, `alerts.json`), 安全记录(`security-audit.jsonl`)和登录过的地址(`known-logins.json`). |
| `data/files/` | 迷你网盘: `index.json`(容量上限, 文件, 下载链接令牌, 服务器下载任务)与 `blobs/<id>` 文件内容, 目录 `0700`, 文件 `0600`. |
| `/etc/vps-server-proxy/config.json` | Singbox 运行配置;节点身份与策略由受管清单协调. |
| `/etc/vps-server-frps/frps.toml` | FRPS 服务端配置. |
| `/etc/vps-server-frps/traffic.json`, `traffic-meter.json` | FRPS 流量条目(配额, 限速, 有效期, 用量)与计量账本. |
| `/etc/vps-server-traffic/traffic.json`, `meter.json` | 域名转发, iperf3, 端口转发, FRPC 和 Tailscale 的流量条目与计量账本. |
| `data/app-traffic.json` | 迷你网盘和测速的流量条目, 由控制台写入. |
| `data/monitor-history.json`, `monitor.json` | 资源监控 24 小时历史; 告警设置和已发送记录. |
| `data/api-tokens.json`, `fleet.json` | API 令牌(只存哈希); 多主机的地址, 令牌和证书指纹. |
| `data/fm-staging/`, `apt-upgrade.log`, `upgrade-api.log` | 文件管理的上传和编辑暂存; 系统更新和经接口升级的输出. |
| `/etc/frp/frpc-<name>.toml` | FRPC 实例配置;非 ASCII 名称映射到稳定的 unit 别名. |
| `/etc/vps-server-caddy` | 域名转发: 站点清单 `sites.json`, Cloudflare 令牌清单 `cloudflare-tokens.json`(每个令牌带名称和它能管理的主域名; 均为 `0600`; 旧版的单个 `cloudflare-token` 和 `zones.json` 在第一次改动令牌时转换并删除), DNS 同步结果 `dns.json`, 生成的 Caddy 配置 `caddy.json`. |
| `/var/lib/vps-server-caddy` | Caddy 的证书和 ACME 账号, 归 `vps-server-caddy` 用户. |
| `~/apps/PORTS.md`, `~/apps/.ports.lock` | 主机端口归属清单与互斥锁. |

状态文件按敏感等级限制权限, Web 不把备份或配置作为静态资源公开. FRPC 任务文件 `data/frp-jobs/*.json` 权限为 `0600`, 执行前移除请求凭据, 结果以任务状态保存. 转发规则保存为项目 JSON 并在启动时重放, 不保存整个主机规则集. 安装前备份和人工恢复流程见 README.

## 外部接口

- Web 页面与表单只面向本项目管理操作;受保护的显示/复制接口在认证后返回敏感值. `/frp/client/structured` 和 `/frp/client/rename` 是 POST 操作, 不是独立展示页.
- LibreSpeed 客户端使用 `/speedtest/garbage`, `/speedtest/empty`, `/speedtest/getip` 与原创 Python 后端交互;结果反映当前客户端到服务器的链路.
- 权限辅助程序通过白名单动作调用 systemd, FRP 验证器, nft/iptables 与安装器;不提供任意命令执行 API. root PTY 仅供经过密码复验的终端会话.
- FRPC 连接用户指定的服务器, 结构化编辑只支持简单 token 认证的 TCP/UDP/STCP 代理和 STCP 访问者. TCP/UDP 代理会在 FRPS 主机开放公网 remotePort;STCP 代理不开放端口,只有持相同 secretKey 的访问者(`[[visitors]]`, 固定监听 `127.0.0.1`, 端口登记到端口表)能连接. secretKey 不写入页面, 只经受保护的显示/复制接口返回.
- Tailscale CLI 与本机守护进程通信, 登录和路由审批由控制服务器/Tailnet 处理.
- Lucky 模块已移除, 由域名转发取代: 安装器升级时调用 `module_manager.remove_legacy_lucky()`, 先把 `/etc/vps-server-lucky` 归档到状态目录, 再停止服务, 删除 nft 表, 本项目放行的防火墙规则, 端口登记和程序文件.
- 域名转发(`caddy` 模块)由 `src/web/caddy_sites.py` 管理: 控制台经 `systemd-run` 以 root 调用它修改站点和令牌, 它生成 Caddy 原生 JSON 配置(每个域名一条到 `127.0.0.1:<端口>` 的反向代理, 其他域名和直接用 IP 访问一律断开连接), 再通过 Unix 套接字上的管理接口热加载. Caddy 以 `vps-server-caddy` 用户运行, 只有绑定低端口的能力, 证书由它自己的自动 HTTPS 用 HTTP-01/TLS-ALPN-01 申请, 因此需要 80 和 443, 也不支持泛域名. Caddy 服务启用时, `public_listener_enabled()` 一律读作关闭, 控制台不再监听 80/443, `PORTS.md` 中两行改登记给 Caddy; 公开可达性页面改由 Caddy 用 `static_response` 返回同样的一行文字(按 Accept-Language 选语言, 访客地址取 `{http.request.remote.host}`, 去掉 Server 头), 开关仍是控制台的 `web-http-enabled` 和 `web-https-enabled`(首页只有一个"公开页面"开关, 对应 `web_public` 任务, 同时写这两个文件; 不经 Caddy 时只重启一次控制台, 任一端口失败就两个都还原), 切换时只重新生成 Caddy 配置(`caddy_sites.probe_switches()`). 80 上关闭自动跳转, 域名站点的跳转由显式路由完成, 其余名字和 IP 显示该页; 443 上只对 IP 站点显示, 并关闭 `strict_sni_host`(浏览器访问 IP 不带 SNI, 否则返回 421; 只有控制台域名请求客户端证书, 是否必须由控制台逐请求判断, SNI 不一致得不到额外权限); 关闭或卸载模块时按原开关还给公开页面. DNS 记录用 Cloudflare API 维护(A, 有公网 IPv6 时加 AAAA, 仅 DNS). 可以保存多个令牌(最多 20 个, 例如域名分属不同账号): 每个域名先用已知能管理它主域名的令牌, 找不到时再依次试其余令牌(`caddy_sites.locate()`); 添加时 Cloudflare 拒绝的令牌不保存, 暂时连不上的照常保存. 页面和请求只用令牌 SHA-256 的前 12 位标识令牌, 不回显令牌本身. 添加站点时立即同步, `vps-server-caddy-dns.timer` 每 5 分钟比较本机地址, 地址变化, 上次失败或距上次检查超过一小时才请求 Cloudflare. 本机地址取自内核为外部路由选择的源地址, 只接受公网地址; 该 IPv4 是内网地址时(阿里云 ECS 等一对一 NAT 的云服务器), 改为通过 IPv4 请求 `https://www.cloudflare.com/cdn-cgi/trace`, 取它看到的来源地址, 结果缓存 10 分钟.
- 站点端口等于控制台端口时, 该域名指向控制台本身: Caddy 对这个域名请求客户端证书(`verify_if_given`, 用控制台客户端 CA 的副本 `/etc/vps-server-caddy/client-ca.pem` 校验), 经回环 TLS 连接控制台, 并覆盖写入三个请求头: 只有 root 和 Caddy 能读到的 `proxy-key` 密钥, 证书序列号, 访问者地址. 控制台只在连接来自回环地址且密钥匹配时采信这些头: 用序列号查自己的证书记录(吊销照常生效, 是否必须出示证书仍由控制台决定), 用访问者地址做登录封禁, 访问地址限制和安全记录; IP 白名单登录和只限内网的 Clash 订阅对这类请求不可用. 控制台的连接级访问限制因此放行回环地址, 改为逐个请求检查. 控制台端口或客户端 CA 变化时, DNS 定时任务会重新生成并热加载 Caddy 配置.
- 每个站点可以停用(从 Caddy 配置中移除, DNS 记录和证书保留)和编辑(目标端口或控制台, 后端是否 HTTPS, 发给后端的 Host). 后端为 HTTPS 时不校验其证书; Caddy 对 HTTPS 后端默认改写 Host, 所以两种 Host 选择都显式写入配置. Caddy 把所有站点的访问日志写到 `/var/lib/vps-server-caddy/logs/access.log`(JSON, 5 MB 轮转, 保留 2 份), 控制台的 `/domains/log` 按域名从文件末尾读取最近 200 条. 站点变更, DNS 记录增删改, 本机 IP 变化和同步失败追加到 `/etc/vps-server-caddy/dns-history.jsonl`(保留最近 200 条). IP 变化, DNS 同步失败和证书临近过期(域名少于 7 天, IP 少于 1 天)通过控制台已有的 Bark 设置推送, 同一事件一天最多一次(`alerts-sent.json`); 检测不到任何公网地址时不视为 IP 变化.
- 站点还可以有其他域名(最多 8 个, 与主域名同一目标, 各自有 DNS 记录和证书, 不能与其他站点重复), 允许访问的地址或网段(最多 32 条, 其他来源返回 403, 按连接地址判断), 以及基本认证(用户名和至少 8 位密码; 密码经 `caddy hash-password` 从标准输入生成 bcrypt 哈希, 只保存哈希, Caddy 缓存校验结果). 指向控制台的站点不设基本认证, 由控制台自己登录. 编辑时去掉的其他域名会删除其 DNS 记录.
- 首页的"IP 证书"(`ipcert`)与域名转发各有开关, 共用 `caddy` 模块: 域名转发的开关存于 `/etc/vps-server-caddy/domains-enabled`(没有该文件时沿用 Caddy 服务是否启用), 关闭时 Caddy 配置只保留 `ip` 站点, DNS 同步也只看它; 两者任一开启时 Caddy 服务运行, 都关闭时停止并把 80/443 还给公开可达性页面(`module_manager.sync_caddy`). IP 证书开关加入一个 `ip` 站点(本机公网 IPv4). Caddy 只为它申请和续期证书(`tls.certificates.automate`), 不建路由: 80/443 对裸 IP 不提供任何内容, 控制台仍只在随机端口. Let's Encrypt 只用 `shortlived` 配置签发 IP 证书(约 6 天, 由 Caddy 按续期信息自动续), 只能用 HTTP-01/TLS-ALPN-01 验证, 这两种验证由 Caddy 在 80/443 上处理, 不需要路由. 控制台以 root 运行, 直接读 Caddy 存储里的证书和私钥(`caddy_sites.ip_certificate()`), 每 30 秒查一次站点, 证书文件变化时重建 TLS 上下文, 读不到时退回自签名证书; 用 `VPSSRV_TLS_CERT` 指定的证书优先. IP 站点不建 DNS 记录, 本机地址变化时 DNS 定时任务改写站点.
- 地址来自本机网卡及已配置的 FRPC 服务器地址, 安装器不请求外部服务查询公网 IP.
