---
name: project-third-party-notices-es
description: Atribuciones y avisos de cumplimiento de terceros
metadata:
  version: "1.0.0"
  lang: "es"
---

# Avisos de terceros

Este documento registra componentes de terceros incluidos y suministrados por el sistema operativo, declaraciones sobre el código fuente y límites de revisión para publicaciones.

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

La tabla inventaría los componentes incluidos y los proporcionados por el sistema operativo. Los nueve artefactos originales del repositorio tienen valores SHA-256 en [dependencies.lock.json][local-link-001]; ejecuta `python3 tools/verify_dependencies/verify_dependencies.py` desde la raíz para comparar sus bytes sin conexión. Los archivos Tailscale y nftables solo entran en el paquete sin conexión generado: el constructor comprueba hashes fijos, y sus fuentes y licencias constan en sus respectivos `component.txt`. Se conserva el registro de los siete artefactos originales comprobados el 2026-09-27; las fuentes de FRPC e iperf3 añadidos se indican abajo. Estas comprobaciones identifican los artefactos, pero no prueban la compatibilidad entre distribuciones ni cierran todas las dependencias del sistema.

| Componente / recurso | Versión / hash | Fuente | Licencia registrada | Uso | Atribución / ruta de licencia original | Obligaciones a revisar antes de publicar | Verificado el |
| --- | --- | --- | --- | --- | --- | --- | --- |
| frps | `v0.71.0`; binary SHA-256 `b95dee2bf29a021c562565cdf2116376b9fa7590361bd36ef57041a04d0e6654` | [fatedier/frp](https://github.com/fatedier/frp) | Apache-2.0, según la licencia original | Ejecutable frps incluido | [included license](../../third_party/frp/LICENSE); [artifact record](../../third_party/frp/component.txt) | Conservar la licencia Apache-2.0 incluida; el archivo binario oficial no contenía un archivo NOTICE | 2026-09-27: coinciden el archivo de publicación, el binario y la licencia |
| frpc | `v0.71.0`; binary SHA-256 `f79fff8de3089ec711ff8bdd4b73e00dfe491a1c3d754983c8b0f8d58c21b068` | [fatedier/frp](https://github.com/fatedier/frp) | Apache-2.0, según la licencia original | Ejecutable frpc incluido en el repositorio y verificado antes de instalarlo | [included license](../../third_party/frp/LICENSE); [artifact record](../../third_party/frp/component.txt) | Distribuir la misma licencia original con el código fuente y conservar la suma de verificación del recurso | 2026-10-04: el ejecutable cliente incluido coincidió con un miembro del archivo original |
| Lucky | `v2.27.2`; binary SHA-256 `7d3193cf969e8ed041761544b41786bcc368d46b9cf4d4d679a5bc215bd3357a` | [gdy666/lucky](https://github.com/gdy666/lucky) | MIT, según la licencia original | Ejecutable Lucky incluido | [included license](../../third_party/lucky/LICENSE); [artifact record](../../third_party/lucky/component.txt) | Conservar los avisos de copyright y la licencia MIT incluidos | 2026-09-27: coinciden el archivo de publicación, el binario y la licencia |
| sing-box | `v1.13.14`; revisión `25a600db24f7680ad9806ce5427bd0ab8afe1114`; SHA-256 del binario `68aeab83cc4ab2659a5b92232261a20746ccdafc3b3d1e19b2d63247eec3bbf7` | [SagerNet/sing-box](https://github.com/SagerNet/sing-box) | GPL versión 3 o posterior, más la condición de denominación original (según el aviso) | Ejecutable incluido, compartido por anytls y proxy | [aviso original][local-link-002]; [texto íntegro de GPL][local-link-003] | Conservar los enlaces al código fuente correspondiente y la condición original de nombre y asociación | 2026-09-27: coinciden el archivo de publicación, el binario, la licencia y la revisión de la etiqueta |
| LibreSpeed | `v6.2.1` | [LibreSpeed](https://github.com/librespeed/speedtest) | LGPL-3.0, según la licencia original | Motor de navegador incluido | [texto LGPL original][local-link-006] y [texto GPL][local-link-007] | Conservar el texto de la licencia y facilitar el código fuente original | 2026-09-27: coinciden los dos archivos de la etiqueta y la licencia |
| qrcode-generator | `js2.0.4`; revisión `83b7e8fe3fddd3b0368dbafd6ce56995bd25e3c8` | [kazuhikoarase/qrcode-generator](https://github.com/kazuhikoarase/qrcode-generator) | MIT, según la licencia original | Biblioteca QR del cliente incluida | [texto MIT original][local-link-008] | Conservar los avisos de atribución y licencia exigidos | 2026-09-27: coinciden los dos archivos de la etiqueta y la licencia |
| Inter | `5.3.0` | [Fontsource Inter](https://github.com/fontsource/font-files/blob/main/fonts/google/inter/README.md) | SIL OFL 1.1 | Fuente latina incluida, pesos 400/600/700 | [license](../../src/web/static/licenses/OFL-Inter.txt) | Conservar la licencia y el aviso de derechos incluidos | 2026-09-27 |
| Noto Sans SC | `5.3.0` | [Fontsource Noto Sans SC](https://github.com/fontsource/font-files/blob/main/fonts/google/noto-sans-sc/README.md) | SIL OFL 1.1 | Fuente CJK incluida, pesos 400/700 | [license](../../src/web/static/licenses/OFL-Noto-Sans-SC.txt) | Conservar la licencia y el aviso de derechos incluidos | 2026-09-27 |
| Lucide icons | `main` 2026-09-27 | [lucide-icons/lucide](https://github.com/lucide-icons/lucide) | ISC | Iconos SVG incluidos para la interfaz | [license](../../src/web/static/licenses/Lucide-ISC.txt) | Conservar la licencia y el aviso de derechos incluidos | 2026-09-27 |
| iperf3 | `3.22`; SHA-256 del binario incluido `f1924a042ef4074b5974b8985a235ad2fcb45d52d02cec46b0dfb45e269b9bf2` | [ESnet/iperf](https://github.com/esnet/iperf) | BSD-3-Clause | Ejecutable estático para Linux x86-64 compilado localmente desde el código oficial | [licencia original](../../third_party/iperf3/LICENSE); [registro de compilación](../../third_party/iperf3/component.txt) | Conservar el aviso de copyright y la licencia íntegra; falta comprobar la compatibilidad en las distribuciones de destino | 2026-10-04: suma del código fuente oficial, compilación local y ejecución en el equipo actual |
| Tailscale | `1.102.4`; SHA-256 del archivo estático amd64 oficial `50748df1045e60b5b695f19f4c56b0da36c019948b440fb456b6584a50f0d8b9` | [paquetes oficiales Linux](https://pkgs.tailscale.com/stable/) | BSD-3-Clause, según LICENSE original | Archivo incorporado al construir el paquete v6 sin conexión; el destino instala cliente y demonio | [licencia original](../../third_party/tailscale/LICENSE); [registro del artefacto](../../third_party/tailscale/component.txt) | Conservar licencia y aviso de copyright originales en el paquete; revisar las declaraciones de dependencias transitivas antes de la publicación formal | 2026-10-04: hash del archivo oficial y versión ejecutada localmente coinciden |
| nftables y diez bibliotecas de ejecución | Debian 11 amd64 `nftables 0.9.8-3.1+deb11u2`; SHA-256 del archivo conjunto `42eeb9496a173777df2e46d67b32b631e5eb31bbc1a74d2a0fa335f32a46c9eb` | [repositorio oficial Debian](https://deb.debian.org/debian/) | Licencias de cada paquete en `usr/share/doc/<package>/copyright` dentro del archivo | Entorno privado nft para medir nodos en el paquete v6 sin conexión; no se instala en la base de datos de paquetes del sistema | [paquetes y hashes](../../third_party/nft/component.txt) | Conservar los archivos de copyright originales de cada paquete; falta aceptar la compatibilidad entre distribuciones en destino | 2026-10-04: los `.deb` coinciden con los hashes del índice Debian; se analizó localmente la sintaxis de cuotas |

El registro existente identifica GPL-3.0 como licencia de este proyecto ([LICENSE][local-link-009]) y señala como motivo la redistribución de un ejecutable sing-box bajo GPL; [Decisiones][local-link-010] conserva el razonamiento y las alternativas descartadas. El registro anterior describe `vps-webserver` como Apache-2.0 en origen y redistribuido aquí bajo GPL-3.0. Este inventario registra los archivos y condiciones comprobados para v2.0.0; no constituye una opinión jurídica independiente.

No hay paquetes de Python de terceros. `src/web/app.py` usa la biblioteca estándar, por lo que no hay un archivo de bloqueo de paquetes Python. El bloqueo de los artefactos incluidos no fija Python ni otros paquetes del sistema proporcionados por el SO: sus versiones y actualizaciones de seguridad dependen de los canales de paquetes de la distribución Debian/Ubuntu de destino. El instalador no selecciona versiones exactas ni una instantánea del repositorio; la resolución completamente reproducible de dependencias del sistema sigue pendiente (consulta [Requisitos de reproducción][local-link-011]).

---

## sing-box

Este repositorio redistribuye un ejecutable sing-box como `third_party/sing-box/sing-box` en el repositorio. El 2026-09-27, sus bytes y la licencia original incluida coincidían con el archivo oficial de publicación v1.13.14. Se instala como `/usr/local/bin/sing-box-vps-server`.

- Componente: `sing-box`
- Proyecto original: https://github.com/SagerNet/sing-box
- Copyright (C) 2022 by nekohasekai <contact-sagernet@sekai.icu>
- Versión: `v1.13.14`
- Revisión del código fuente: `25a600db24f7680ad9806ce5427bd0ab8afe1114`
- Artefacto distribuido: `sing-box-1.13.14-linux-amd64.tar.gz`
- SHA-256 del binario del repositorio: `68aeab83cc4ab2659a5b92232261a20746ccdafc3b3d1e19b2d63247eec3bbf7`
- Licencia: GNU GPL versión 3 o cualquier versión posterior, además de la condición original sobre nombre/asociación; consulta [`third_party/sing-box/LICENSE`][local-link-012]

El SHA-256 del archivo de publicación descargado fue `f48703461a15476951ac4967cdad339d986f4b8096b4eb3ff0829a500502d697`. El binario y la licencia del repositorio coincidían byte a byte con los miembros extraídos de ese archivo.

### Código fuente correspondiente

El 2026-09-27, la etiqueta v1.13.14 apuntaba a la revisión de código fuente `25a600db24f7680ad9806ce5427bd0ab8afe1114`. Los siguientes enlaces al código fuente original acompañan al ejecutable incluido:

- Árbol de código etiquetado: https://github.com/SagerNet/sing-box/tree/v1.13.14
- Revisión exacta del código: https://github.com/SagerNet/sing-box/tree/25a600db24f7680ad9806ce5427bd0ab8afe1114
- Archivo del código fuente: https://github.com/SagerNet/sing-box/archive/refs/tags/v1.13.14.tar.gz

El archivo de publicación original citado en el registro anterior es:

- https://github.com/SagerNet/sing-box/releases/download/v1.13.14/sing-box-1.13.14-linux-amd64.tar.gz

Este proyecto es independiente y no está afiliado a los autores de sing-box o SagerNet ni cuenta con su respaldo.

---

## LibreSpeed

La prueba de velocidad del navegador usa un motor cliente LibreSpeed incluido en el repositorio. El 2026-09-27, sus dos archivos JavaScript incluidos y su licencia coincidían byte a byte con los archivos de la etiqueta original v6.2.1.

- Componente: motor cliente LibreSpeed — `src/web/static/third_party/librespeed/speedtest.js`, `src/web/static/third_party/librespeed/speedtest_worker.js`
- Proyecto original: https://github.com/librespeed/speedtest
- Versión: `v6.2.1`
- Licencia: GNU LGPL versión 3; texto íntegro en [`src/web/static/licenses/LGPL-3.0.txt`][local-link-013]
- Verificación: ambos archivos y la licencia original coincidían con la etiqueta v6.2.1; este inventario no registra el commit exacto de la etiqueta.

`src/web/static/speedtest-ui.js` es código de integración propio de este proyecto y no forma parte de LibreSpeed. Los endpoints del servidor en `src/web/app.py` (`/speedtest/garbage`, `/speedtest/empty`, `/speedtest/getip`) vuelven a implementar el contrato cliente/servidor documentado de LibreSpeed; son código original y no derivan del backend PHP original.

El texto LGPL-3.0 está incluido y se enlaza al código fuente original; este inventario no constituye una opinión jurídica independiente sobre la combinación.

---

## qrcode-generator

La página `/proxy` de la consola muestra los enlaces para compartir como códigos QR escaneables mediante esta biblioteca cliente incluida. El 2026-09-27, sus dos archivos JavaScript incluidos y la licencia original coincidían byte a byte con los archivos de la etiqueta original js2.0.4.

- Componente: `src/web/static/third_party/qrcode/qrcode.js`, `src/web/static/third_party/qrcode/qrcode-utf8.js`
- Proyecto original: https://github.com/kazuhikoarase/qrcode-generator
- Copyright (c) 2009 Kazuhiko Arase
- Versión: `js2.0.4`
- Revisión del código fuente: `83b7e8fe3fddd3b0368dbafd6ce56995bd25e3c8`
- Licencia: MIT; texto íntegro en [`src/web/static/licenses/MIT.txt`][local-link-014]
- Verificación: ambos archivos coincidían con los originales `js/dist/qrcode.js` y `js/dist/qrcode_UTF8.js`; también coincidía la licencia MIT original.

`src/web/static/qrcode-render.js` es código de integración propio de este proyecto (busca elementos `[data-qr-text]` y los rellena con el SVG generado), no forma parte de la biblioteca incluida.

El aviso de copyright y la licencia MIT están incluidos con la biblioteca cliente.

---

## iperf3

- Componente: `iperf3`
- Proyecto original: https://github.com/esnet/iperf
- Licencia: BSD-3-Clause
- Procedencia: [archivo fuente oficial 3.22](https://downloads.es.net/pub/iperf/iperf-3.22.tar.gz), SHA-256 `1c0d0fb02c52626111d6e132db80edfbf27bbaff8bd9245df2a371dcb0b35a92`.
- Compilación: en Ubuntu 22.04 x86-64 se ejecutó `./configure --enable-static-bin --disable-shared --without-sctp && make -j2` y luego `strip` sobre `src/iperf3`. No se modificó el código fuente; la suma del binario figura en la tabla.
- Distribución: el ejecutable se incluye en `third_party/iperf3/iperf3` junto con el aviso de copyright y la [licencia íntegra `third_party/iperf3/LICENSE`](../../third_party/iperf3/LICENSE). Tras instalarse usa `$PREFIX/vendor/iperf3/iperf3`.
- Límite: la compilación no incluye SCTP ni autenticación OpenSSL. La resolución de nombres con glibc enlazada estáticamente aún requiere validación en las distribuciones antiguas de destino. Las pruebas TCP/UDP de duración limitada de este proyecto no utilizan esas funciones opcionales.

---

## Código incorporado de otros proyectos del autor

No son componentes de terceros, pero se registran aquí porque el código no se originó en este repositorio y su procedencia es importante para las actualizaciones:

- `src/web/app.py`, `src/web/static/speedtest-ui.js`, `src/web/static/style.css`, `src/web/static/visitors.js`,
  `tests/`, `deploy/install.sh`, `deploy/uninstall.sh`, `deploy/systemd/` — proceden de `vps-webserver`
  v0.4.1 (Apache-2.0 original, relicenciado aquí bajo GPL-3.0). Consulta `config/upstream-version`.
- `third_party/sing-box/sing-box` y `third_party/sing-box/sing-box.version` utilizaron inicialmente la selección de `Anytsl-Serve`; el script de instalación independiente de AnyTLS se retiró del candidato v6. El origen del binario y su licencia figuran en la tabla anterior.

---

Las fuentes y los iconos de terceros incluidos se enumeran en la tabla anterior. No se incluyen conjuntos de imágenes ni pesos de modelos de terceros. Al construir el paquete sin conexión, la máquina de construcción con red descarga y comprueba los recursos Tailscale y nftables. La instalación en destino no descarga FRPC ni otros ejecutables ni consulta la IP pública.

[local-link-001]: ../../config/dependencies.lock.json
[local-link-002]: ../../third_party/sing-box/LICENSE
[local-link-003]: ../../LICENSE
[local-link-004]: #código-fuente-correspondiente
[local-link-005]: LOG.md#decisiones
[local-link-006]: ../../src/web/static/licenses/LGPL-3.0.txt
[local-link-007]: ../../LICENSE
[local-link-008]: ../../src/web/static/licenses/MIT.txt
[local-link-009]: ../../LICENSE
[local-link-010]: LOG.md#decisiones
[local-link-011]: DESIGN.md#requisitos-de-reproducción
[local-link-012]: ../../third_party/sing-box/LICENSE
[local-link-013]: ../../src/web/static/licenses/LGPL-3.0.txt
[local-link-014]: ../../src/web/static/licenses/MIT.txt
