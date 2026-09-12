# Status

[English](../STATUS.md) | **繁體中文**

> 譯自 `STATUS.md`（v<release-version>）。如有衝突，以英文版為準。
> 本文件按規則只在打 tag 時重譯，因此兩次發版之間它滯後於英文版——**接續專案請讀
> `STATUS.md`**，那裡的 `In progress` 才是目前狀態。

**Notion:** <專案私有頁面 URL。儲存庫為 PUBLIC 時這裡寫 "private mirror (not published)"，真實 URL 放 ../.local-notes.md（在 repo/ 外面，不被 git 追蹤）>
**Repo:** <GitHub URL>（private/public）
**Snapshots:** <私有快照路徑；public 儲存庫寫 "maintained privately (not published)">
**In progress:** <現在正在做的事>
**Next:** <下一步，具體到可以立刻開始>
**Known issues:** <已知問題>
**Blocked on:** <在等使用者提供什麼，或在等哪個外部條件>

<!--
這份譯版刻意不帶 YAML front matter。front matter 是機器讀的那一半，只存在於
STATUS.md：scripts/pm-index.py 靠它生成跨專案總表，scripts/release-preflight.sh
拿它的 version 和正在打的 tag 比對。譯版再放一份就是第二個版本號來源，兩邊一旦不
一致，顯示哪個全看誰先被讀到。

欄位名（Notion / Repo / Snapshots / In progress / Next / Known issues /
Blocked on）逐字保留英文，只翻譯它們後面的內容——這幾個名字在 SKILL、preflight
和跨專案總表裡都是按字面找的。

正文保持短：只記目前狀態；歷史在 CHANGELOG.md 和 git log 裡。

public 儲存庫裡絕不寫 Notion URL、本地/NAS 絕對路徑、內網主機名稱，以及任何只對
維護者有意義的識別碼。那些放在 <專案根>/<專案名>/.local-notes.md —— 在 repo/
外面，因此永遠不會被提交，也不會進快照。

更新時機是事件觸發，不是「會話結束前」（會話不會通知你它結束了）：
  - 打完一個 tag
  - 做了一個會影響後續的決策
  - 被 blocked
  - 使用者說「先到這」「下次再說」或類似收尾表達
  - 完成了 Next 裡寫的那一步
-->
