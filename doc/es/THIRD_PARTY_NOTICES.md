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

[English](../THIRD_PARTY_NOTICES.md) | [简体中文](../zh-CN/THIRD_PARTY_NOTICES.md) | [繁體中文(台灣)](../zh-TW/THIRD_PARTY_NOTICES.md) | [繁體中文(香港)](../zh-HK/THIRD_PARTY_NOTICES.md) | [हिन्दी](../hi/THIRD_PARTY_NOTICES.md) | **Español** | [العربية](../ar/THIRD_PARTY_NOTICES.md) | [Français](../fr/THIRD_PARTY_NOTICES.md)

## Documentación

- Descripción general del proyecto: [README](README.md)

- Justificación del diseño: [DESIGN](DESIGN.md)

- Historial de versiones: [LOG](LOG.md)

- Avisos de terceros: [THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES.md)

## Avisos de terceros

La tabla inventaría los componentes y declaraciones sobre su origen que ya constaban aquí. Los siete archivos de terceros incluidos tienen valores SHA-256 calculados localmente en [dependencies.lock.json][local-link-001]; ejecuta `python3 tools/verify_dependencies/verify_dependencies.py` desde la raíz del repositorio para comparar sin conexión los bytes del árbol de trabajo. Esa comprobación no acredita la identidad de origen, las condiciones de las licencias originales ni el cumplimiento de los requisitos de distribución. No se afirma ninguna fecha de una nueva revisión de licencias originales o distribución. Antes de distribuir, comprueba las versiones registradas de los artefactos, textos originales de licencias, avisos de copyright, obligaciones aplicables de facilitar el código fuente y cualquier análisis de separación frente a los artefactos que se distribuirán. Esta tabla no supone una aprobación de publicación.

| Componente / recurso | Versión / hash | Fuente | Licencia registrada | Uso | Atribución / ruta de licencia original | Obligaciones a revisar antes de publicar | Verificado el |
| --- | --- | --- | --- | --- | --- | --- | --- |
| frps | `v0.71.0`; binary SHA-256 `b95dee2bf29a021c562565cdf2116376b9fa7590361bd36ef57041a04d0e6654` | [fatedier/frp](https://github.com/fatedier/frp) | Apache-2.0, per bundled license | Ejecutable frps incluido | [included license](../../third_party/frp/LICENSE); [artifact record](../../third_party/frp/component.txt) | Conservar la licencia Apache-2.0 incluida y revisar las obligaciones NOTICE antes de distribuir | Repository artifact hash verified; upstream identity pending |
| Lucky | `v2.27.2`; binary SHA-256 `7d3193cf969e8ed041761544b41786bcc368d46b9cf4d4d679a5bc215bd3357a` | [gdy666/lucky](https://github.com/gdy666/lucky) | MIT, per bundled license | Ejecutable Lucky incluido | [included license](../../third_party/lucky/LICENSE); [artifact record](../../third_party/lucky/component.txt) | Conservar los avisos de copyright y la licencia MIT incluidos | Repository artifact hash verified; upstream identity pending |
| sing-box | `v1.13.14`; revisión `25a600db24f7680ad9806ce5427bd0ab8afe1114`; SHA-256 del binario `68aeab83cc4ab2659a5b92232261a20746ccdafc3b3d1e19b2d63247eec3bbf7` | [SagerNet/sing-box](https://github.com/SagerNet/sing-box) | GPL versión 3 o posterior, más la condición de denominación original (según el aviso) | Ejecutable incluido, compartido por anytls y proxy | [aviso original][local-link-002]; [texto íntegro de GPL][local-link-003] | Código fuente correspondiente y condición de denominación; revisar los [enlaces registrados al código fuente][local-link-004] y [Decisiones][local-link-005] | No consta; volver a comprobar antes de distribuir |
| LibreSpeed | `v6.2.1`, según registros anteriores | [LibreSpeed](https://github.com/librespeed/speedtest) | LGPL-3.0, según registros anteriores | Motor de navegador incluido | no registrado aquí; [texto LGPL original][local-link-006] y [texto GPL][local-link-007] | Revisar la combinación de bibliotecas y disponibilidad del código fuente | No consta; volver a comprobar antes de distribuir |
| qrcode-generator | `js2.0.4`; revisión `83b7e8fe3fddd3b0368dbafd6ce56995bd25e3c8` | [kazuhikoarase/qrcode-generator](https://github.com/kazuhikoarase/qrcode-generator) | MIT, según registros anteriores | Biblioteca QR del cliente incluida | [texto MIT original][local-link-008] | Conservar los avisos de atribución y licencia exigidos | No consta; volver a comprobar antes de distribuir |
| iperf3 | Paquete de la distribución; versión sin fijar | [ESnet/iperf](https://github.com/esnet/iperf) | BSD-3-Clause, según registros anteriores | Invocado como programa independiente instalado desde el SO; no se redistribuye aquí | No registrado; el paquete del SO aporta la licencia original | Volver a evaluar si se incluye o redistribuye más adelante | No consta; volver a comprobar antes de distribuir |

El registro existente identifica GPL-3.0 como licencia de este proyecto ([LICENSE][local-link-009]) y señala como motivo la redistribución de un ejecutable sing-box bajo GPL; [Decisiones][local-link-010] conserva el razonamiento y las alternativas descartadas. El registro anterior describe `vps-webserver` como Apache-2.0 en origen y redistribuido aquí bajo GPL-3.0. Son afirmaciones históricas del proyecto, no una nueva conclusión jurídica; revisa obligaciones y compatibilidad antes de publicar.

No hay paquetes de Python de terceros. `src/web/app.py` usa la biblioteca estándar, por lo que no hay un archivo de bloqueo de paquetes Python. El bloqueo de artefactos incluidos anterior no fija Python, iperf3 ni otros paquetes del sistema proporcionados por el SO: sus versiones y actualizaciones de seguridad dependen de los canales de paquetes de la distribución Debian/Ubuntu de destino. El instalador no selecciona versiones exactas ni una instantánea del repositorio; la resolución completamente reproducible de dependencias del sistema sigue pendiente (consulta [Requisitos de reproducción][local-link-011]).

---

## sing-box

Este repositorio redistribuye un ejecutable sing-box como `third_party/sing-box/sing-box` en el repositorio. Su identidad como versión de origen se declaró en registros anteriores, pero no se volvió a comprobar independientemente en esta auditoría local de hashes. Se instala como `/usr/local/bin/sing-box-vps-server`.

- Componente: `sing-box`
- Proyecto original: https://github.com/SagerNet/sing-box
- Copyright (C) 2022 by nekohasekai <contact-sagernet@sekai.icu>
- Versión: `v1.13.14`
- Revisión del código fuente: `25a600db24f7680ad9806ce5427bd0ab8afe1114`
- Artefacto distribuido: `sing-box-1.13.14-linux-amd64.tar.gz`
- SHA-256 del binario del repositorio: `68aeab83cc4ab2659a5b92232261a20746ccdafc3b3d1e19b2d63247eec3bbf7`
- Licencia: GNU GPL versión 3 o cualquier versión posterior, además de la condición original sobre nombre/asociación; consulta [`third_party/sing-box/LICENSE`][local-link-012]

El registro anterior comunica una comparación byte a byte con el archivo de publicación original. Esta auditoría solo comprobó el SHA-256 del binario del repositorio; la equivalencia con la publicación aún requiere una comparación independiente con el origen.

### Código fuente correspondiente

El registro anterior identifica los siguientes enlaces al código fuente correspondiente de la versión declarada; esta auditoría no comprobó su contenido frente al binario del repositorio. Confirma la correspondencia y las obligaciones de facilitar el código fuente antes de redistribuir:

- Árbol de código etiquetado: https://github.com/SagerNet/sing-box/tree/v1.13.14
- Revisión exacta del código: https://github.com/SagerNet/sing-box/tree/25a600db24f7680ad9806ce5427bd0ab8afe1114
- Archivo del código fuente: https://github.com/SagerNet/sing-box/archive/refs/tags/v1.13.14.tar.gz

El archivo de publicación original citado en el registro anterior es:

- https://github.com/SagerNet/sing-box/releases/download/v1.13.14/sing-box-1.13.14-linux-amd64.tar.gz

Este proyecto es independiente y no está afiliado a los autores de sing-box o SagerNet ni cuenta con su respaldo.

---

## LibreSpeed

La prueba de velocidad del navegador usa un motor cliente LibreSpeed incluido en el repositorio. La versión registrada y su equivalencia con el origen no se comprobaron independientemente en esta auditoría.

- Componente: motor cliente LibreSpeed — `static/third_party/librespeed/speedtest.js`, `static/third_party/librespeed/speedtest_worker.js`
- Proyecto original: https://github.com/librespeed/speedtest
- Versión: `v6.2.1`
- Licencia: GNU LGPL versión 3; texto íntegro en [`static/licenses/LGPL-3.0.txt`][local-link-013]
- Registro anterior: se describía que ambos archivos eran idénticos byte a byte a la publicación original; esta auditoría solo comprobó hashes del árbol local. No se registra la revisión exacta del código fuente original.

`static/speedtest-ui.js` es código de integración propio de este proyecto y no forma parte de LibreSpeed. Los endpoints del servidor en `src/web/app.py` (`/speedtest/garbage`, `/speedtest/empty`, `/speedtest/getip`) vuelven a implementar el contrato cliente/servidor documentado de LibreSpeed; son código original y no derivan del backend PHP original.

El registro anterior evaluó la combinación LGPL-3.0 con este trabajo GPL-3.0; confirma las obligaciones antes de distribuir.

---

## qrcode-generator

La página `/proxy` de la consola muestra como código QR escaneable el enlace de cada dirección anytls mediante esta biblioteca cliente incluida. La versión registrada y su equivalencia con el origen no se comprobaron independientemente en esta auditoría.

- Componente: `static/third_party/qrcode/qrcode.js`, `static/third_party/qrcode/qrcode-utf8.js`
- Proyecto original: https://github.com/kazuhikoarase/qrcode-generator
- Copyright (c) 2009 Kazuhiko Arase
- Versión: `js2.0.4`
- Revisión del código fuente: `83b7e8fe3fddd3b0368dbafd6ce56995bd25e3c8`
- Licencia: MIT; texto íntegro en [`static/licenses/MIT.txt`][local-link-014]
- Registro anterior: se describía que ambos archivos eran idénticos byte a byte a los originales `js/dist/qrcode.js` y `js/dist/qrcode_UTF8.js`; esta auditoría solo comprobó hashes del árbol local.

`static/qrcode-render.js` es código de integración propio de este proyecto (busca elementos `[data-qr-text]` y los rellena con el SVG generado), no forma parte de la biblioteca incluida.

El registro anterior evaluó la combinación MIT con este trabajo GPL-3.0; confirma las obligaciones relativas a avisos antes de distribuir.

---

## iperf3

- Componente: `iperf3`
- Proyecto original: https://github.com/esnet/iperf
- Licencia: BSD 3-Clause
- Modificado: no
- **No redistribuido.** `iperf3` se instala desde el repositorio de paquetes del sistema operativo mediante `install.sh` y se invoca como programa independiente, mediante un proceso separado. Este repositorio no incluye código ni binarios de iperf3, por lo que, según el registro anterior, no se activa aquí la obligación de atribución BSD vinculada a la redistribución; vuelve a evaluarlo si cambia la distribución. Se incluye en esta lista porque el proyecto depende de él durante la ejecución.

---

## Código incorporado de otros proyectos del autor

No son componentes de terceros, pero se registran aquí porque el código no se originó en este repositorio y su procedencia es importante para las actualizaciones:

- `src/web/app.py`, `static/speedtest-ui.js`, `static/style.css`, `static/visitors.js`,
  `tests/`, `deploy/install.sh`, `deploy/uninstall.sh`, `deploy/systemd/` — proceden de `vps-webserver`
  v0.4.1 (Apache-2.0 original, relicenciado aquí bajo GPL-3.0). Consulta `config/upstream-version`.
- `deploy/anytls/setup-anytls.sh`, `third_party/sing-box/sing-box`, `third_party/sing-box/sing-box.version` — proceden de
  `Anytsl-Serve` v1.2.0 (GPL-3.0 original). Consulta `deploy/anytls/.upstream-version`.

---

No se incluyen fuentes tipográficas, iconos, imágenes, conjuntos de datos ni pesos de modelos de terceros. Durante la ejecución el servicio no hace solicitudes salientes; la única llamada saliente opcional es una consulta de IP pública durante la instalación, cuyo fallo solo produce una advertencia.

[local-link-001]: ../../config/dependencies.lock.json
[local-link-002]: ../../third_party/sing-box/LICENSE
[local-link-003]: ../../LICENSE
[local-link-004]: #código-fuente-correspondiente
[local-link-005]: LOG.md#decisiones
[local-link-006]: ../../static/licenses/LGPL-3.0.txt
[local-link-007]: ../../LICENSE
[local-link-008]: ../../static/licenses/MIT.txt
[local-link-009]: ../../LICENSE
[local-link-010]: LOG.md#decisiones
[local-link-011]: DESIGN.md#reproduction-requirements
[local-link-012]: ../../third_party/sing-box/LICENSE
[local-link-013]: ../../static/licenses/LGPL-3.0.txt
[local-link-014]: ../../static/licenses/MIT.txt
