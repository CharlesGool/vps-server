---
project: vps-server
version: unreleased
status: active
branch: main
updated: 2026-09-12
---

# Status

**English** | [简体中文](translated_zh_cn/STATUS_zh_cn.md) | [繁體中文](translated_zh_tw/STATUS_zh_tw.md)

**Notion:** private mirror (not published)
**Repo:** private
**Snapshots:** maintained privately (not published)
**In progress:** Feature-complete on paper and all three modules are in the
tree. The two new capabilities are verified for real: the public page answers
on its own listeners and 404s all thirteen console routes, and the iperf3
window opens, advertises itself, self-closes on time, and leaves no child
behind — driven against a real `iperf3` client, not just asserted. 67 tests
pass. The installers are the untested part.
**Next:** Run `install.sh` and `uninstall.sh` end to end on a real host. Both
are syntax- and shellcheck-clean but have never been executed even once; see
the `BACKLOG.md` entry for the exact isolated-prefix command to use.
**Known issues:** `install.sh`, `uninstall.sh` and `anytls/setup-anytls.sh`
have never been run. The first two are new to this project and the third is
vendored-and-renamed, so its three changed constants are unexercised. Until
somebody runs them, treat the install path as unproven — the service code
itself is not.
**Blocked on:** Two things need a human, because this environment's safety
classifier blocks both for the agent: creating the GitHub remote
(`gh repo create vps-server --private --source=. --remote=origin` followed by
`git push -u origin HEAD`), and executing the installer. Until the first is
done, every commit exists only on this machine with no off-site copy.
