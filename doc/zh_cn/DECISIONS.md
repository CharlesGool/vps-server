# 决策记录

[English](../DECISIONS.md) | **简体中文** | [繁體中文](../zh_tw/DECISIONS.md) | [繁體中文（香港）](../zh_hk/DECISIONS.md) | [हिन्दी](../hi/DECISIONS.md) | [Español](../es/DECISIONS.md) | [العربية](../ar/DECISIONS.md) | [Français](../fr/DECISIONS.md)

## 文档说明

- 项目概览：[README](README.md)
- 设计理念：[DESIGN](DESIGN.md)
- 发布历史：[CHANGELOG](CHANGELOG.md)
- 当前状态：[STATUS](STATUS.md)
- 需求列表：[BACKLOG](BACKLOG.md)
- 第三方声明：[THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES.md)

> 译自 `DECISIONS.md`（v1.1.0）。如有冲突，以英文版为准。

这不是一份决策日志，而是一道防止重新提议的关卡。判断某件事该不该收进这里，只看一个问题：

> 六个月后，我或另一个 agent 会不会把这当作一个新点子再提一遍？

会 → 记一条。不会 → 不收，这不算遗漏。"我们用 PostgreSQL" 该写进 DESIGN.md；"MongoDB 评估过，因为 X 被否决了" 才该写在这里。

**每条决策最多五行要点，正文控制在约 1000 字节以内。** 两条限制都要满足，而不是二选一：只卡行数不够用，因为实测过的最大文件里，大部分正是每条五行、但每一行都是一段没换行的长段落。超出这个上限说明它属于 DESIGN.md 的材料——挪过去。

这道上限正是让这份文件保持可用的关键。一条决策写到 2 KB，就没人会在提议前先打开它看一眼，而没人读的关卡等于没有关卡。

新的写在最前面。只追加，不改写。要推翻一条决策，就新增一条说明推翻的理由——绝不修改或删除旧的那条。

---

## 2026-09-19 — 端口转发通过 iptables DNAT 实现，每次启动时都从 JSON 重新应用；不会在进程之外写入任何东西

- **Rejected:** 用 `socat` 做用户态转发——更安全（不改 NAT 表和 `ip_forward`），但用户为本项目明确选择了内核级的 DNAT+MASQUERADE。
- **Rejected:** 用 `iptables-persistent` 让规则在内核层面挺过重启——这会让控制台和一个系统包成为同一套规则的两个事实来源。`app.py` 改为每次启动都从自己的 JSON 重新应用（见 DESIGN.md 的"Port forwarding lifecycle"一节），事实来源始终只有一个。
- **Rejected:** 最后一条转发被删除后自动把 `net.ipv4.ip_forward` 改回 `0`——这是整机层面的开关，主机上其它软件（本项目自己的测试主机就跑着 Docker）可能依赖它保持开启。
- **Cost:** 停止（而非重启）`vps-server-web` 会撤掉每一条转发的内核状态，包括启用中的——这和 iperf3 窗口的"故障时收紧"方向一致。不要为"修复"这一点把规则挪进单独常驻的 unit；这个方案上面已经考虑过并被否决了。

---

## 2026-09-12 — 公共页面和控制台是两个独立的监听器，各用各的处理类

- **Rejected:** 用一个监听器同时服务两者，控制台路由靠路径前缀加鉴权来把关——鉴权检查可能被搞出漏洞而放行；一个根本不存在的路由则不会。
- **Rejected:** 把控制台本身也挂到 80/443 端口、靠密码保护，去掉那个随机端口——这样会丢掉 `vps-webserver` 当初刻意选用的隐蔽层。
- **Cost:** 一个进程里跑三个监听器，两个处理类各自都要单独接入访客日志钩子。
- **Do not re-add this as an improvement.**

---

## 2026-09-12 — iperf3 只在操作员手动打开的限时窗口内运行

- **Rejected:** 常驻开放的公共 `iperf3 -s` ——任何陌生人都能无限期跑满上行带宽，且没有任何提示能显示这件事正在发生。
- **Rejected:** 常驻开放但用 `--authorized-users-path` 做 RSA 鉴权——凭证必须先通过带外方式交给对方，这就违背了"把 IP 给别人、让他直接测"的初衷。
- **Cost:** 远程测试者不能无人值守地测试，必须先有人打开窗口。公共页面会公示当前开放的窗口，让测试者知道什么时候可以连。

---

## 2026-09-12 — 443 端口使用自签名证书；不接 ACME，不用域名

- **Rejected:** 针对真实域名跑 certbot / acme.sh ——这个页面存在的目的就是回答"你能不能连到这个 IP"，浏览器弹出的证书警告页本身就已经证明了可达性。为了这个问题而引入域名依赖和续期定时任务，没有任何收益。
- **Rejected:** 只提供 80 端口——那样无法区分"整个主机不可达"和"443 端口specifically被封锁"，而后者恰恰是最值得检测的常见情形。
- **Cost:** 每次访问 HTTPS 都会显示证书警告。这是预期行为，不要用 HSTS 或固定例外去"修复"它。

---

## 2026-09-12 — sing-box 二进制文件随仓库一起发布，因此整个项目采用 GPL-3.0

- **Rejected:** 在安装时下载 sing-box，以保持仓库体积小、许可证维持 Apache-2.0——`Anytsl-Serve` 此前已经明确否决过完全一样的方案，为的是让安装过程不依赖 GitHub 访问；在这里重新决定一遍，等于悄悄推翻那个目标。
- **Rejected:** 去掉 anytls 模块以保留 `vps-webserver` 的 Apache-2.0——最初的诉求是把两个项目合并起来，而不是二选一。
- **Cost:** git 仓库里约增加 57 MB，且每次升级 sing-box 都会继续增长；`vps-webserver` 原本的 Apache-2.0 代码在这里以 GPL-3.0 的形式被重新分发。

---

## 2026-09-12 — 上游项目采用 vendor 方式引入，不取代、不用子模块

- **Rejected:** 让 vps-server 取代 `vps-webserver` 和 `Anytsl-Serve` 并将两者归档——这三个项目要各自独立维护、独立发布。
- **Rejected:** 用 git submodule 指向那两个上游仓库——submodule 无法承载本项目需要的重命名（unit 名称、二进制名称、`VPSWS_` → `VPSSRV_`），而且这样一来 clone 时还得额外访问两个远程仓库。
- **Cost:** 同一份代码存在于三个仓库中，会逐渐产生分歧。缓解办法：`.upstream-version` 文件记录每一份被 vendor 进来的代码树对应的确切上游 tag，且必须在每次刷新时与代码改动同一次提交更新。
