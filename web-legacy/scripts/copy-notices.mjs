import { readdirSync, readFileSync, existsSync, mkdirSync, copyFileSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'
const root = fileURLToPath(new URL('..', import.meta.url))
const directory = join(root, 'node_modules')
const output = join(root, 'dist', 'licenses')
mkdirSync(output, {recursive: true})
const notices = []
function inspect(path) {
  if (!existsSync(join(path, 'package.json'))) return
  const info = JSON.parse(readFileSync(join(path, 'package.json'), 'utf8'))
  const licenses = readdirSync(path).filter(name => /^(LICENSE|COPYING|NOTICE)/i.test(name))
  const destination = info.name.replaceAll('/', '--')
  mkdirSync(join(output, destination), {recursive: true})
  for (const file of licenses) copyFileSync(join(path, file), join(output, destination, file))
  notices.push({name: info.name, version: info.version, license: info.license, source: `https://registry.npmjs.org/${info.name}/-/${info.name.split('/').at(-1)}-${info.version}.tgz`, texts: licenses.map(file => `${destination}/${file}`)})
}
for (const name of readdirSync(directory)) {
  if (name.startsWith('@')) for (const item of readdirSync(join(directory, name))) inspect(join(directory, name, item))
  else if (!name.startsWith('.')) inspect(join(directory, name))
}
writeFileSync(join(output, 'manifest.json'), JSON.stringify(notices, null, 2) + '\n')
console.log(`Preserved notices for ${notices.length} frontend and build packages`)
