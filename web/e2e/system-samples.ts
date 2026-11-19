// vps-server: 资源监控, 系统, 文件管理和多主机页面显示本机实时数据(CPU, 磁盘, 进程, 服务, 端口, 文件), 每次运行都不同;
// 截图和布局检查用这里的固定样例(由 support.ts 的 stableServer 接管对应的接口).
const NOW = Date.UTC(2026, 10, 19, 12, 0, 0) / 1000
const hours = (count: number, step: number) => Array.from({ length: count }, (_, index) => NOW - (count - index) * step)

const chart = hours(12, 7200).map((time, index) => [time, 8 + ((index * 7) % 23), 41 + ((index * 3) % 9), 120_000 + index * 9_000, 30_000 + index * 2_500])
const live = Array.from({ length: 12 }, (_, index) => [NOW - (12 - index) * 5, 10 + ((index * 7) % 9), 44 + (index % 3), 150_000 + ((index * 13_000) % 60_000), 35_000 + ((index * 4_000) % 12_000)])
const recent = Array.from({ length: 15 }, (_, index) => [NOW - (15 - index) * 60, 9 + ((index * 5) % 13), 43 + (index % 4), 140_000 + ((index * 11_000) % 50_000), 33_000 + ((index * 3_000) % 9_000)])
const trend = hours(24, 3600).map((time, index) => [time, 6 + ((index * 5) % 19), 40 + ((index * 2) % 11), 100_000, 25_000])

const DISKS = [
  { mount: '/', device: '/dev/vda1', type: 'ext4', total: 42_949_672_960, used: 15_032_385_536, free: 25_769_803_776, percent: 36.8 },
  { mount: '/data', device: '/dev/vdb1', type: 'xfs', total: 214_748_364_800, used: 182_536_110_080, free: 32_212_254_720, percent: 85 },
]

export const MONITOR_SAMPLE = {
  cpu: { percent: 12.4, cores: 4, model: 'AMD EPYC 7763 64-Core Processor' },
  memory: { total: 8_589_934_592, used: 3_865_470_566, available: 4_724_464_026, swapTotal: 2_147_483_648, swapUsed: 104_857_600 },
  disks: DISKS,
  disk: DISKS[0],
  load: [0.42, 0.38, 0.35],
  uptime: 1_234_567,
  network: { rx: 182_400, tx: 41_200, interfaces: [{ name: 'eth0', rx: 182_400, tx: 41_200 }, { name: 'tailscale0', rx: 0, tx: 0 }] },
  temperatures: [{ name: 'k10temp Tctl', celsius: 48.5 }],
  gpus: [],
  chart,
  trend,
  live,
  recent,
  hourAgo: { cpu: 10.1, memory: 44.2 },
  time: NOW,
}

export const RESOURCES_SAMPLE = {
  cpu: MONITOR_SAMPLE.cpu,
  memory: MONITOR_SAMPLE.memory,
  disk: MONITOR_SAMPLE.disk,
  load: MONITOR_SAMPLE.load,
  trend,
  hourAgo: MONITOR_SAMPLE.hourAgo,
}

export const MONITOR_ALERTS_SAMPLE = { alerts: { enabled: true, disk: 90, memory: 95, cpu: 95, cpu_minutes: 10, services: true }, barkReady: true }

export const SYSTEM_SAMPLE = { hostname: 'vps-demo', os: 'Debian GNU/Linux 13 (trixie)', kernel: '6.12.48+deb13-amd64', arch: 'x86_64' }

export const UPDATES_SAMPLE = {
  supported: true,
  packages: [
    { package: 'openssl', version: '3.5.4-1~deb13u1', current: '3.5.1-1' },
    { package: 'libssl3t64', version: '3.5.4-1~deb13u1', current: '3.5.1-1' },
    { package: 'tzdata', version: '2025c-0+deb13u1', current: '2025b-4' },
  ],
  listsAge: 5400,
  running: false,
  log: '',
  lastExit: null,
}

export const SSH_SAMPLE = {
  accepted: [
    { time: '2026-11-19T11:42:08+0000', method: 'publickey', user: 'root', ip: '198.51.100.24' },
    { time: '2026-11-18T22:05:51+0000', method: 'publickey', user: 'root', ip: '198.51.100.24' },
  ],
  failed: [
    { time: '2026-11-19T11:58:31+0000', user: 'admin', ip: '203.0.113.77' },
    { time: '2026-11-19T11:58:29+0000', user: 'root', ip: '203.0.113.77' },
    { time: '2026-11-19T09:13:02+0000', user: 'oracle', ip: '192.0.2.150' },
  ],
  failedTotal: 3,
  topFailed: [
    { ip: '203.0.113.77', count: 2 },
    { ip: '192.0.2.150', count: 1 },
  ],
}

const PROCESS_NAMES = ['systemd', 'sshd', 'python3', 'sing-box', 'frps', 'caddy', 'tailscaled', 'cron', 'journald', 'bash', 'iperf3', 'nginx']
export const PROCESSES_SAMPLE = {
  rows: PROCESS_NAMES.map((name, index) => ({
    pid: index === 0 ? 1 : 300 + index * 41,
    ppid: index === 0 ? 0 : 1,
    name,
    state: 'S',
    user: index % 4 === 3 ? 'vps-server-caddy' : 'root',
    cpu: Math.round(((index * 37) % 50) * 10) / 100,
    memory: (index + 3) * 7_340_032,
    command: index === 2 ? '/usr/bin/python3 /root/apps/vps-server/src/web/app.py' : `/usr/bin/${name}`,
  })),
  self: 382,
}

const SERVICE_ROWS = [
  ['caddy.service', 'inactive', 'dead', 'disabled', 'Caddy'],
  ['cron.service', 'active', 'running', 'enabled', 'Regular background program processing daemon'],
  ['frpc-home.service', 'failed', 'failed', 'enabled', 'FRP client home'],
  ['ssh.service', 'active', 'running', 'enabled', 'OpenBSD Secure Shell server'],
  ['systemd-journald.service', 'active', 'running', 'static', 'Journal Service'],
  ['tailscaled.service', 'active', 'running', 'enabled', 'Tailscale node agent'],
  ['vps-server-frps.service', 'active', 'running', 'enabled', 'vps-server FRPS'],
  ['vps-server-proxy.service', 'active', 'running', 'enabled', 'vps-server Singbox nodes'],
  ['vps-server-traffic-meter.service', 'active', 'running', 'enabled', 'vps-server traffic meter'],
  ['vps-server-web.service', 'active', 'running', 'enabled', 'vps-server console'],
  ['unattended-upgrades.service', 'inactive', 'dead', 'disabled', 'Unattended Upgrades Shutdown'],
]
export const SERVICES_SAMPLE = {
  rows: SERVICE_ROWS.map(([unit, active, sub, enabled, description]) => ({ unit, load: 'loaded', active, sub, enabled, description })),
  protected: ['vps-server-web.service', 'vps-server.service'],
}

export const PORTS_SAMPLE = {
  rows: [
    { protocol: 'tcp', address: '0.0.0.0', port: 22, process: 'sshd', pid: 512, owner: '' },
    { protocol: 'tcp', address: '0.0.0.0', port: 7000, process: 'frps', pid: 1204, owner: 'vps-server-frps' },
    { protocol: 'tcp', address: '*', port: 20425, process: 'python3', pid: 382, owner: 'vps-server' },
    { protocol: 'udp', address: '0.0.0.0', port: 41641, process: 'tailscaled', pid: 901, owner: '' },
    { protocol: 'tcp', address: '0.0.0.0', port: 443, process: 'sing-box', pid: 1311, owner: 'vps-server-proxy' },
  ],
}

const entry = (name: string, type: string, size: number | null, extra: Record<string, unknown> = {}) => ({
  name,
  type,
  size,
  modified: NOW - 86_400,
  mode: type === 'dir' ? 'drwxr-xr-x' : type === 'link' ? 'lrwxrwxrwx' : '-rw-r--r--',
  octal: type === 'dir' ? '0755' : '0644',
  owner: 'root',
  group: 'root',
  ...extra,
})
export const FM_SAMPLE = {
  path: '/root',
  rows: [
    entry('.ssh', 'dir', null),
    entry('apps', 'dir', null),
    entry('backups', 'dir', null),
    entry('current', 'link', null, { target: '/root/apps/vps-server', targetDir: true }),
    entry('.bashrc', 'file', 3_771),
    entry('notes.txt', 'file', 1_204),
    entry('release.tar.gz', 'file', 34_012_455),
  ],
  truncated: false,
  free: 25_769_803_776,
  users: ['root'],
  groups: ['root'],
}

const host = (id: string, name: string, version: string, cpu: number, memory: number, disk: number, ok = true, failed: string[] = []) => ({
  id,
  name,
  url: `https://${name}.example.net:20425`,
  mode: 'pin',
  fingerprint: '91:E1:45:56:6C:AF:92:3B:A6:48:B9:2A:8C:55:00:BF:48:83:79:04:AC:93:67:88:D1:B1:15:61:EE:D1:83:3F',
  added: NOW - 86_400 * 3,
  ok,
  ...(ok
    ? {
        status: {
          hostname: name,
          version,
          serverLabel: '',
          kernel: '6.12.48+deb13-amd64',
          resources: { cpu: { percent: cpu, cores: 2, model: '' }, memory: { total: 100, used: memory, available: 100 - memory, swapTotal: 0, swapUsed: 0 }, disk: { ...DISKS[0], percent: disk }, load: [0.1, 0.1, 0.1], uptime: 86_400 },
          traffic: { used: 128_849_018_880, cap: null },
          services: [],
          failed,
        },
      }
    : { error: 'unreachable' }),
})
export const FLEET_SAMPLE = {
  hosts: [
    host('a1', 'tokyo-1', 'v7.2.0', 7.5, 38, 41),
    host('a2', 'macau-2', 'v7.2.0', 22.1, 61, 72, true, ['frpc-home.service']),
    host('a3', 'sydney-1', 'v7.1.2', 3.2, 25, 18),
    host('a4', 'lab-vm', '', 0, 0, 0, false),
  ],
}

// 资源监控的样例只替换主页接口里的 resources, 模块卡片仍来自真实服务器(开关测试要用)
export const SYSTEM_ROUTES: [RegExp, unknown][] = [
  [/\/api\/monitor$/, MONITOR_SAMPLE],
  [/\/api\/monitor\/alerts$/, MONITOR_ALERTS_SAMPLE],
  [/\/api\/monitor\/summary$/, RESOURCES_SAMPLE],
  [/\/api\/system$/, SYSTEM_SAMPLE],
  [/\/api\/system\/updates$/, UPDATES_SAMPLE],
  [/\/api\/system\/ssh$/, SSH_SAMPLE],
  [/\/api\/system\/processes$/, PROCESSES_SAMPLE],
  [/\/api\/system\/services$/, SERVICES_SAMPLE],
  [/\/api\/system\/ports$/, PORTS_SAMPLE],
  [/\/api\/fm\/list(\?.*)?$/, FM_SAMPLE],
  [/\/api\/fleet$/, FLEET_SAMPLE],
]
