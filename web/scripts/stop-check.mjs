#!/usr/bin/env node
// Claude Code Stop hook: 结束回复前, Web UI 或 Go 后端有未提交的改动时运行 npm run check.
// 失败时退出码 2, Claude Code 把输出交回 Agent 继续修改. 通过的改动记录在 .local/check-stamp.json, 内容不变时不重复运行.
// 同一份改动被拦下 3 次后放行, 并提示用户检查未通过.
import { spawnSync } from 'node:child_process'
import { createHash } from 'node:crypto'
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const web = join(dirname(fileURLToPath(import.meta.url)), '..')
const root = join(web, '..')
const PATHS = ['web', 'lang', 'cmd', 'internal', 'go.mod', 'go.sum']
const MAX_BLOCKS = 3
const stampPath = join(root, '.local', 'check-stamp.json')

function git(args) {
  return spawnSync('git', args, { cwd: root, encoding: 'utf8' })
}

// 与 HEAD 相比有改动的相关文件; 不是 Git 仓库时跳过
const status = git(['status', '--porcelain', '-z', '--no-renames', '--untracked-files=all', '--', ...PATHS])
if (status.status !== 0) process.exit(0)
const changed = status.stdout
  .split('\0')
  .filter((entry) => entry.length > 3)
  .map((entry) => entry.slice(3))
  .sort()
if (!changed.length) process.exit(0)

const hash = createHash('sha256')
for (const path of changed) {
  hash.update(`${path}\0`)
  const file = join(root, path)
  hash.update(existsSync(file) ? readFileSync(file) : 'deleted')
  hash.update('\0')
}
const digest = hash.digest('hex')

let stamp = { passed: '', blocked: '', count: 0 }
try {
  stamp = { ...stamp, ...JSON.parse(readFileSync(stampPath, 'utf8')) }
} catch {
  // 首次运行
}
function save() {
  mkdirSync(dirname(stampPath), { recursive: true })
  writeFileSync(stampPath, `${JSON.stringify(stamp, null, 2)}\n`)
}
if (stamp.passed === digest) process.exit(0)

const check = spawnSync('npm', ['run', 'check'], {
  cwd: web,
  encoding: 'utf8',
  shell: process.platform === 'win32',
  maxBuffer: 64 * 1024 * 1024,
})
if (check.status === 0) {
  stamp = { passed: digest, blocked: '', count: 0 }
  save()
  process.exit(0)
}

stamp.count = stamp.blocked === digest ? stamp.count + 1 : 1
stamp.blocked = digest
save()

const output = `${check.stdout ?? ''}${check.stderr ?? ''}${check.error ? `\n${check.error.message}` : ''}`
// 去掉 Playwright 进度行, 保留错误详情和末尾汇总
const lines = output
  .trim()
  .split('\n')
  .filter((line) => !/^\s+[✓✘-]\s+\d+ \[/.test(line))
const tail =
  lines.length > 140
    ? [...lines.slice(0, 120), `... 省略 ${lines.length - 140} 行, 在 web/ 运行 npm run check 查看全部 ...`, ...lines.slice(-20)].join('\n')
    : lines.join('\n')

if (stamp.count > MAX_BLOCKS) {
  // 防止无限循环: 放行, 提示用户
  console.log(
    JSON.stringify({
      systemMessage: `npm run check 未通过, 同一份改动已拦下 ${MAX_BLOCKS} 次后放行. 这些改动不能提交, 需要列为未验证.`,
    }),
  )
  process.exit(0)
}

console.error(
  [
    `Web UI 有未提交的改动, npm run check 未通过 (第 ${stamp.count} 次). 修改代码直到通过; 禁止修改检查脚本和测试.`,
    '有意改变外观时按 Web UI 用户约定 `设计检查` 规则 3 更新截图基准. Chromium 或 Go 无法运行时在回复中列为未验证.',
    '',
    tail,
  ].join('\n'),
)
process.exit(2)
