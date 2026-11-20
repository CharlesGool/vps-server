import { ApiError } from './api'
import { i18n } from './i18n'

// 请求失败时给用户看的文字. 服务器拒绝某一项输入时, 错误响应除了 error(错误码)还带 field(请求体里的键, 嵌套用点号,
// 如 resetSpec.time)和可选的 reason(required, type, format, range, too_long, too_short, exists, not_found, past, port_in_use).
// codes: 页面按错误码的具体文案, 没有时返回 undefined. labels: field → 该表单上这一项的标签.
export interface ErrorTextOptions {
  codes?: (code: string) => string | undefined
  labels?: Record<string, string>
}

// 只说明"请求无效"的错误码: 有 field 时, 指出哪一项比页面的通用说明更有用
const GENERIC = new Set(['invalid_request', 'invalid', 'invalid_limits', 'request_failed', 'failed'])

// 服务器指出的输入项(field), 没有时 undefined
export function errorField(error: unknown): string | undefined {
  return error instanceof ApiError && typeof error.data.field === 'string' ? error.data.field : undefined
}

function reasonText(error: ApiError): string | undefined {
  const key = `vps.error.reason.${String(error.data.reason)}`
  return typeof error.data.reason === 'string' && i18n.global.te(key) ? i18n.global.t(key) : undefined
}

// 字段的标签: 先找完整的键, 再依次去掉最后一段(resetSpec.time → resetSpec); 都没有时用键本身
function labelOf(field: string, labels: Record<string, string> = {}): string {
  for (let name = field; name; name = name.includes('.') ? name.slice(0, name.lastIndexOf('.')) : '') {
    if (labels[name]) return labels[name]
  }
  return field
}

// 优先级: 页面按错误码的具体文案 > "<字段标签>: <原因>" > 页面对这个通用码的说明 > 通用的"操作失败"; 有 detail 时附在后面
export function errorText(error: unknown, options: ErrorTextOptions = {}): string {
  const { t } = i18n.global
  if (!(error instanceof ApiError)) return t('vps.common.failed')
  const specific = options.codes?.(error.code)
  const field = errorField(error)
  let text = GENERIC.has(error.code) ? undefined : specific
  if (!text && field) {
    const reason = reasonText(error) ?? specific
    if (reason) text = t('vps.error.field', { field: labelOf(field, options.labels), reason })
  }
  text ??= specific ?? t('vps.common.failed')
  const detail = typeof error.data.detail === 'string' ? error.data.detail.trim() : ''
  return detail ? t('vps.error.detail', { text, detail }) : text
}

// 页面的提示条是否可以不显示: 被拒绝的那一项在表单上已经标出原因(labels 里有它的标签), 也没有附带服务器输出
export function shownInline(error: unknown, labels: Record<string, string> = {}): boolean {
  const field = errorField(error)
  if (!field || !(error instanceof ApiError) || (typeof error.data.detail === 'string' && error.data.detail.trim())) return false
  for (let name = field; name; name = name.includes('.') ? name.slice(0, name.lastIndexOf('.')) : '') {
    if (labels[name]) return true
  }
  return false
}

// 绑定到 FormField 的 error: 被拒绝的正是这一项(或它下面的一项, 如 resetSpec 之于 resetSpec.time)时给出原因, 否则 undefined
export function fieldError(error: unknown, field: string, options: Pick<ErrorTextOptions, 'codes'> = {}): string | undefined {
  const name = errorField(error)
  if (!(error instanceof ApiError) || !name || (name !== field && !name.startsWith(`${field}.`))) return undefined
  return reasonText(error) ?? options.codes?.(error.code) ?? i18n.global.t('vps.common.failed')
}

// ScheduleFields 各项的标签, 键是计划在请求体里的键(prefix, 如 spec 或 resetSpec)加计划的键
export function scheduleLabels(prefix: string): Record<string, string> {
  const { t } = i18n.global
  const keys = {
    mode: 'console.task_mode', n: 'console.task_every', unit: 'console.task_unit', time: 'console.task_time',
    date: 'console.task_date', days: 'console.task_weekdays', day: 'console.task_month_day', month: 'console.task_month',
    expr: 'console.task_schedule',
  }
  return Object.fromEntries([[prefix, t('console.task_mode')], ...Object.entries(keys).map(([key, label]) => [`${prefix}.${key}`, t(label)])])
}
