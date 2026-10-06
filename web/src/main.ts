import { createApp, defineComponent, h, onMounted, ref } from 'vue'
import AppHeader from '@/components/app/AppHeader.vue'
import PageHeader from '@/components/app/PageHeader.vue'
import CardGrid from '@/components/app/CardGrid.vue'
import SectionNav from '@/components/app/SectionNav.vue'
import ThemeSelect from '@/components/app/ThemeSelect.vue'
import SegmentedControl from '@/components/app/SegmentedControl.vue'
import { initAppearance, mode } from '@/lib/appearance'
import { initResizeReflow } from '@/lib/resize-reflow'
import { i18n } from '@/lib/i18n'
import '@/styles/main.css'

type Config = {version: string; title: string; serverLabel?: string; label: string; login: boolean; back?: {to: string; label: string}; items: {href: string; label: string; key: string; current?: 'page' | 'location'}[]}
const data = document.getElementById('ui-context')
if (!data) throw new Error('Missing UI context')
const config = JSON.parse(data.textContent || '{}') as Config
function mount(component: Parameters<typeof createApp>[0], props: Record<string, unknown>, element: Element) {
  createApp(component, props).use(i18n).mount(element)
}
initAppearance()
const header = document.getElementById('ui-header')
if (header) mount(AppHeader, config, header)
const main = document.querySelector('main')!
if (!config.login) {
  const heading = main.querySelector('h1')
  const title = heading?.textContent || config.title
  heading?.remove()
  main.querySelector('.page-back')?.remove()
  const holder = document.createElement('div')
  holder.className = 'ui-page-heading'
  main.prepend(holder)
  mount(PageHeader, {title, back: config.back}, holder)
}
for (const nav of document.querySelectorAll('.section-nav')) {
  const sections = [...nav.querySelectorAll<HTMLAnchorElement>('a')].map(a => ({id: a.hash.slice(1), label: a.textContent || ''}))
  const label = nav.getAttribute('aria-label') || config.title
  const holder = document.createElement('div')
  nav.replaceWith(holder)
  mount(SectionNav, {sections, label}, holder)
}
const themes = document.querySelector('[data-theme-choice]')?.parentElement
if (themes) { themes.className = 'ui-theme-control'; mount(ThemeSelect, {label: themes.getAttribute('aria-label') || config.title}, themes) }
const modes = document.querySelector('[data-mode-choice]')?.parentElement
if (modes) {
  modes.className = 'ui-mode-control'
  const options = [...modes.querySelectorAll<HTMLElement>('[data-mode-choice]')].map(el => ({value: el.dataset.modeChoice!, label: el.textContent || ''}))
  mount(defineComponent({setup: () => () => h(SegmentedControl, {options, label: modes.getAttribute('aria-label') || config.title, modelValue: mode.value, 'onUpdate:modelValue': (value: string) => {mode.value = value as typeof mode.value}})}), {}, modes)
}
for (const language of document.querySelectorAll('#settings-language .preferences-choices, .login-language-field')) {
  const links = [...language.querySelectorAll<HTMLAnchorElement>('a[href]')]
  const options = links.map(link => ({value: link.href, label: link.textContent || ''}))
  const selected = ref(links.find(link => link.getAttribute('aria-current') || link.classList.contains('active'))?.href || links[0]?.href || '')
  mount(defineComponent({setup: () => () => h(SegmentedControl, {options, label: language.getAttribute('aria-label') || config.title, modelValue: selected.value, 'onUpdate:modelValue': (value: string) => {selected.value = value; location.assign(value)}})}), {}, language)
}
// Move original DOM nodes into the shared grid: native forms and their values survive.
const tiles = document.querySelector('.tiles')
if (tiles) {
  const nodes = [...tiles.children]
  const NativeCard = (node: Element) => defineComponent({setup() {
    onMounted(() => {document.getElementById(node.id + '-host')?.append(node)})
    return () => h('div', {id: node.id + '-host', class: 'native-card'})
  }})
  nodes.forEach((node, index) => {node.id = `ui-card-${index}`})
  tiles.classList.remove('tiles')
  mount(defineComponent({setup: () => () => h(CardGrid, {}, {default: () => nodes.map(node => h(NativeCard(node)))})}), {}, tiles)
}
for (const el of main.children) if (!el.querySelector('[data-reflow]')) el.setAttribute('data-reflow', '')
initResizeReflow()
