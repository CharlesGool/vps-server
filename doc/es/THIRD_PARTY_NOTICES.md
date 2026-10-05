---
name: project-third-party-notices-es
description: Atribuciones y avisos de cumplimiento de terceros
metadata:
  version: "2.0.0"
  lang: "es"
---

# Avisos de terceros

## Multilingüe

[简体中文](../THIRD_PARTY_NOTICES.md) | [English](../en/THIRD_PARTY_NOTICES.md) | **Español**

## Documentación

- Descripción general del proyecto: [README](README.md)

- Justificación del diseño: [DESIGN](DESIGN.md)

- Estado del proyecto: [LOG](LOG.md)
- Registros históricos: [HISTORY](HISTORY.md)
- Historial de cambios: [CHANGELOG](CHANGELOG.md)

- Avisos de terceros: [THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES.md)

## Avisos de terceros

Este inventario registra componentes y obligaciones, conserva textos originales y no considera fijos los paquetes del sistema. [Sumas fijas](../../config/dependencies.lock.json) cubren 15 artefactos.

### Componentes

| Componente | Versión o hash | Origen | Licencia | Uso | Titular de derechos | Obligaciones de distribución | Fecha de verificación |
| --- | --- | --- | --- | --- | --- | --- | --- |
| frps | 0.71.0 | [frps](https://github.com/fatedier/frp) | Apache-2.0 | Binario de servidor independiente. | fatedier/frp contributors | Conservar licencia; el archivo oficial no contiene NOTICE. | 2026-09-27 |
| frpc | 0.71.0 | [frpc](https://github.com/fatedier/frp) | Apache-2.0 | Binario de cliente por instancia. | fatedier/frp contributors | Conservar atribución y licencia íntegra. | 2026-10-04 |
| Lucky | 2.27.2 | [Lucky](https://github.com/gdy666/lucky) | MIT | Servicio de gestión independiente. | gdy (2022) | Conservar atribución y licencia íntegra. | 2026-09-27 |
| sing-box | 1.13.14 / `25a600db24f7680ad9806ce5427bd0ab8afe1114` | [sing-box](https://github.com/SagerNet/sing-box) | GPL-3.0-or-later | Núcleo proxy independiente. | nekohasekai (2022) | Conservar acceso al código y condiciones de nombre/asociación. | 2026-09-27 |
| LibreSpeed | 6.2.1 | [LibreSpeed](https://github.com/librespeed/speedtest) | LGPL-3.0 | Motor de pruebas del navegador. | LibreSpeed contributors | Conservar LGPL/GPL, ofrecer código correspondiente y archivos de cliente reemplazables. | 2026-09-27 |
| qrcode-generator | js2.0.4 / `83b7e8fe3fddd3b0368dbafd6ce56995bd25e3c8` | [qrcode-generator](https://github.com/kazuhikoarase/qrcode-generator) | MIT | Biblioteca QR del cliente. | Kazuhiko Arase (2009) | Conservar atribución y licencia íntegra. | 2026-09-27 |
| Inter | Fontsource 5.3.0 | [Inter](https://github.com/fontsource/font-files/tree/main/fonts/google/inter) | OFL-1.1 | Fuente incluida, 400/600/700. | The Inter Project Authors (2016) | Conservar OFL/atribución y condiciones de nombres reservados. | 2026-09-27 |
| Noto Sans SC | Fontsource 5.3.0 | [Noto Sans SC](https://github.com/fontsource/font-files/tree/main/fonts/google/noto-sans-sc) | OFL-1.1 | Fuente incluida, 400/700. | Google Inc. | Conservar OFL y atribución. | 2026-09-27 |
| Lucide | main, 2026-09-27 | [Lucide](https://github.com/lucide-icons/lucide) | ISC | Iconos SVG incluidos. | Lucide Icons and Contributors; Cole Bemis | Conservar atribución y licencia íntegra. | 2026-09-27 |
| xterm.js / Fit Addon | 6.0.0 / 0.11.0 | [xterm.js / Fit Addon](https://github.com/xtermjs/xterm.js) | MIT | Renderizado y tamaño del terminal. | The xterm.js authors; SourceLair; Christopher Jeffrey | Conservar ambos textos originales de licencia/atribución. | 2026-10-05 |
| iperf3 | 3.22 | [iperf3](https://github.com/esnet/iperf) | BSD-3-Clause | Compilación estática sin cambios para TCP/UDP. | The Regents of the University of California / Lawrence Berkeley National Laboratory | Conservar atribución y licencia íntegra. | 2026-10-04 |
| Tailscale | 1.102.4 | [Tailscale](https://pkgs.tailscale.com/stable/tailscale_1.102.4_amd64.tgz) | BSD-3-Clause | Archivo oficial de cliente/daemon estático. | Tailscale Inc & contributors (2020) | Conservar LICENSE, PATENTS y avisos/licencias originales de dependencias. | 2026-10-04 |
| nftables + 10 libraries | Debian 11 amd64, nftables 0.9.8-3.1+deb11u2 | [nftables + 10 libraries](https://deb.debian.org/debian/) | copyright de cada paquete: GPL/LGPL/BSD y otras. | Entorno privado, solo en paquetes completos. | Autores de cada paquete; consulte avisos del archivo. | Distribuir fuentes completas correspondientes, parches y avisos juntos. | 2026-10-04 |

Las fechas corresponden a verificaciones originales; el 2026-10-05 se repitieron sumas, no toda la procedencia. Los artefactos frp, Lucky, Singbox, LibreSpeed y QR no se modificaron. Inter/Noto indican versiones Fontsource, no internas. No se incluyen paquetes Python de terceros, conjuntos de imágenes ni pesos. Python, systemd, OpenSSL, iptables y similares dependen del sistema; sus licencias/actualizaciones corresponden a la distribución.

### Textos de licencia

- [frp](../../third_party/frp/LICENSE)
- [Lucky](../../third_party/lucky/LICENSE)
- [sing-box](../../third_party/sing-box/LICENSE)
- [GPL-3.0](../../LICENSE)
- [LibreSpeed LGPL-3.0](../../src/web/static/licenses/LGPL-3.0.txt)
- [qrcode-generator MIT](../../src/web/static/licenses/MIT.txt)
- [Inter OFL](../../src/web/static/licenses/OFL-Inter.txt)
- [Noto Sans SC OFL](../../src/web/static/licenses/OFL-Noto-Sans-SC.txt)
- [Lucide ISC](../../src/web/static/licenses/Lucide-ISC.txt)
- [xterm.js MIT](../../src/web/static/third_party/xterm/LICENSE-xterm)
- [Fit Addon MIT](../../src/web/static/third_party/xterm/LICENSE-addon-fit)
- [iperf3](../../third_party/iperf3/LICENSE)
- [Tailscale LICENSE](../../third_party/tailscale/LICENSE)
- [Tailscale PATENTS](../../third_party/tailscale/PATENTS)
- [Tailscale dependencies](../../third_party/tailscale/DEPENDENCY_NOTICES.md)
- [Tailscale license manifest](../../third_party/tailscale/license-manifest.json)

Las 80 licencias de dependencias Tailscale, licencia freetype y 3 NOTICE suman 84 originales en `third_party/tailscale/licenses/`, con procedencia y sumas en el manifiesto. freetype sigue como Unknown en la lista original; se añade el texto BSD original de una revisión fija sin modificarla. El archivo nftables conserva `usr/share/doc/<package>/copyright`; nombres y sumas están en [component.txt](../../third_party/nft/component.txt).

### Oferta de código fuente

- sing-box: [código v1.13.14](https://github.com/SagerNet/sing-box/tree/25a600db24f7680ad9806ce5427bd0ab8afe1114), [archivo fuente](https://github.com/SagerNet/sing-box/archive/refs/tags/v1.13.14.tar.gz).
- LibreSpeed: [código v6.2.1](https://github.com/librespeed/speedtest/tree/v6.2.1).
- iperf3: [3.22 archivo fuente](https://downloads.es.net/pub/iperf/iperf-3.22.tar.gz), SHA-256 `1c0d0fb02c52626111d6e132db80edfbf27bbaff8bd9245df2a371dcb0b35a92`.
- Tailscale: [código v1.102.4](https://github.com/tailscale/tailscale/tree/v1.102.4).

El Release completo incluye `third_party/nft/nft-runtime-bullseye.tar.gz` y `third_party/nft/nft-sources-bullseye.tar.gz`, con SHA-256 `42eeb9496a173777df2e46d67b32b631e5eb31bbc1a74d2a0fa335f32a46c9eb` y `fce6ca6c5050ff7715c5bd9fedb0160c942e3e5ede7d2702c02f01d920ac6e83`. Las fuentes incluyen 10 grupos, parches Debian y descriptores correspondientes a 11 paquetes binarios; los archivos están fijados en [source-manifest.json](../../third_party/nft/source-manifest.json). El constructor los descarga y verifica desde Debian; una copia del código no incluye ambos archivos nft. Los descriptores/parches reconstruyen el árbol Debian con archivos de compilación. El host usa el entorno privado sin sustituir nft del sistema.

iperf3 se compiló sin cambios en Ubuntu 22.04 x86-64 con `./configure --enable-static-bin --disable-shared --without-sctp && make -j2` y strip, sin SCTP/autenticación OpenSSL; falta aceptar resolución estática en sistemas antiguos.

### Revisión de cumplimiento

Revisión de publicación del 2026-10-05: se verificaron 15 artefactos y 84 avisos/licencias Tailscale, fuentes nft acompañaron el entorno y licencias originales no se reescribieron. La [decisión de licencia](LOG.md#decisiones) registra GPL-3.0-only. Análisis:

- sing-box se distribuye como ejecutable/proceso separado, no enlazado estáticamente a Python; separarlo no elimina obligaciones GPL. Se conservan condiciones de nombre sin asociación ni respaldo.
- JavaScript LibreSpeed es reemplazable con textos LGPL/GPL. `speedtest-ui.js` es integración propia; Python implementa el protocolo sin copiar PHP.
- nft reempaqueta artefactos Debian sin cambios con avisos y fuentes completas; rutas separadas no eliminan obligaciones.
- Tailscale conserva declaraciones, patente y textos complementarios; verificar licencias no prueba compatibilidad entre entornos.

Es una revisión de archivos/distribución sin interpretación jurídica independiente. El código del mismo autor `vps-webserver v0.4.1` se redistribuye desde Apache-2.0 bajo GPL-3.0-only; procedencia: [config/upstream-version](../../config/upstream-version). La elección inicial de Anytsl-Serve explica procedencia; los scripts AnyTLS separados se retiraron.
