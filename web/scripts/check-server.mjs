#!/usr/bin/env node
// 后端检查: 运行 Python 控制台的单元测试(项目决策 2026-11-18, 见 doc/LOG.md; 后端是 Python, 不是模板的 Go).
import { execFileSync } from 'node:child_process'
import { tmpdir } from 'node:os'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = join(dirname(fileURLToPath(import.meta.url)), '..', '..')
// 不读本机真实的数据密钥(/etc/vps-server/data.key 只有 root 能读)
const env = { ...process.env, VPSSRV_DATA_KEY_FILE: join(tmpdir(), 'vps-server-check-no-data-key') }
execFileSync('python3', ['-m', 'unittest', 'discover', '-s', 'tests', '-q'], { cwd: root, stdio: 'inherit', env })
console.log('后端检查通过')
