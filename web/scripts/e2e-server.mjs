#!/usr/bin/env node
// 视觉测试用的 Python 控制台: 临时状态目录, 固定测试密码, openssl 生成的自签名证书, 无数据密钥.
// 用法: node scripts/e2e-server.mjs <端口>; 由 playwright.config.ts 启动, 结束时随进程退出.
import { spawn, execFileSync } from 'node:child_process'
import { mkdirSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { E2E_PASSWORD } from '../e2e/password.ts'

const port = Number(process.argv[2])
if (!port) throw new Error('需要端口')
const root = join(dirname(fileURLToPath(import.meta.url)), '..', '..')
const state = join(tmpdir(), `vps-server-e2e-${port}`)
rmSync(state, { recursive: true, force: true })
mkdirSync(join(state, 'certs'), { recursive: true })
writeFileSync(join(state, 'admin_password.txt'), `${E2E_PASSWORD}\n`, { mode: 0o600 })
execFileSync('openssl', [
  'req', '-x509', '-newkey', 'ec', '-pkeyopt', 'ec_paramgen_curve:P-256', '-nodes', '-subj', '/CN=localhost',
  '-days', '30', '-keyout', join(state, 'certs', 'key.pem'), '-out', join(state, 'certs', 'cert.pem'),
], { stdio: 'ignore' })

const child = spawn('python3', ['app.py'], {
  cwd: join(root, 'src', 'web'),
  stdio: 'inherit',
  env: {
    ...process.env,
    VPSSRV_VERSION: process.env.APP_VERSION || 'e2e',
    VPSSRV_STATE_DIR: state,
    VPSSRV_DATA_KEY_FILE: join(state, 'no-data-key'),
    VPSSRV_CONSOLE_PORT: String(port),
    VPSSRV_HOST: '127.0.0.1',
    VPSSRV_PUBLIC_ENABLE: '0',
    VPSSRV_IPERF_ENABLE: '0',
    VPSSRV_TRACK_CONNECTIONS: '0',
    VPSSRV_DEFAULT_LANG: 'zh_cn',
    // 测试从同一地址发出, 不让失败次数限制挡住后面的测试
    VPSSRV_LOGIN_MAX_ATTEMPTS: '1000',
    VPSSRV_LOGIN_GLOBAL_MAX_ATTEMPTS: '100000',
  },
})
for (const signal of ['SIGINT', 'SIGTERM']) process.on(signal, () => child.kill(signal))
child.on('exit', (code) => process.exit(code ?? 1))
