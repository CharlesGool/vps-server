# Status

[English](../STATUS.md) | **简体中文**

> 译自 `STATUS.md`（v<release-version>）。如有冲突，以英文版为准。
> 本文件按规则只在打 tag 时重译，因此两次发版之间它滞后于英文版——**续接项目请读
> `STATUS.md`**，那里的 `In progress` 才是当前状态。

**Notion:** <项目私有页面 URL。仓库为 PUBLIC 时这里写 "private mirror (not published)"，真实 URL 放 ../.local-notes.md（在 repo/ 外面，不被 git 追踪）>
**Repo:** <GitHub URL>（private/public）
**Snapshots:** <私有快照路径；public 仓库写 "maintained privately (not published)">
**In progress:** <现在正在做的事>
**Next:** <下一步，具体到可以立刻开始>
**Known issues:** <已知问题>
**Blocked on:** <在等用户提供什么，或在等哪个外部条件>

<!--
这份译版刻意不带 YAML frontmatter。frontmatter 是机器读的那一半，只存在于
STATUS.md：scripts/pm-index.py 靠它生成跨项目总表，scripts/release-preflight.sh
拿它的 version 和正在打的 tag 比对。译版再放一份就是第二个版本号来源，两边一旦不
一致，显示哪个全看谁先被读到。

字段名（Notion / Repo / Snapshots / In progress / Next / Known issues /
Blocked on）逐字保留英文，只翻译它们后面的内容——这几个名字在 SKILL、preflight
和跨项目总表里都是按字面找的。

正文保持短：只记当前状态；历史在 CHANGELOG.md 和 git log 里。

public 仓库里绝不写 Notion URL、本地/NAS 绝对路径、内网主机名，以及任何只对维护者
有意义的标识。那些放在 <项目根>/<项目名>/.local-notes.md —— 在 repo/ 外面，
因此永远不会被提交，也不会进快照。

更新时机是事件触发，不是"会话结束前"（会话不会通知你它结束了）：
  - 打完一个 tag
  - 做了一个会影响后续的决策
  - 被 blocked
  - 用户说"先到这""下次再说"或类似收尾表达
  - 完成了 Next 里写的那一步
-->
