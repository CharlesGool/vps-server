---
name: project-readme-es
description: Descripción general y uso del proyecto
metadata:
  version: "1.0.0"
  lang: "es"
---

# vps-server

## Multilingüe

[English](../../README.md) | [简体中文](../zh-CN/README.md) | [繁體中文(台灣)](../zh-TW/README.md) | [繁體中文(香港)](../zh-HK/README.md) | [हिन्दी](../hi/README.md) | **Español** | [العربية](../ar/README.md) | [Français](../fr/README.md)

## Documentación

- Descripción general del proyecto: [README](README.md)

- Justificación del diseño: [DESIGN](DESIGN.md)

- Historial de versiones: [LOG](LOG.md)

- Avisos de terceros: [THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES.md)

## Introducción

Un paquete de módulos seleccionables para un VPS Debian/Ubuntu: una página pública para comprobar la accesibilidad de los puertos web, una consola para realizar pruebas de velocidad y registrar conexiones, una ventana iperf3 bajo demanda y nodos proxy sing-box. La versión 2.0.0 también incluye el módulo `proxy` de cuatro protocolos y los instaladores experimentales de frps y Lucky. Consulta el [estado actual y los límites de aceptación][local-link-001].

## Qué hace

- **Permite a cualquiera comprobar la accesibilidad.** Una página deliberadamente mínima en los puertos **80** y
  **443**, sin inicio de sesión. Dale a alguien la IP: si se muestra la página, tus puertos web son accesibles desde su ubicación. Muestra su IP de origen, la hora del servidor y el puerto y protocolo por los que entró, y nada más sobre el servidor.
- **Mide la velocidad desde un navegador.** Una consola protegida con contraseña en un puerto alto aleatorio y persistente realiza pruebas de subida y bajada con el motor de LibreSpeed.
- **Mide velocidad y latencia con iperf3, bajo demanda.** La consola abre una ventana de duración limitada; `iperf3 -s` solo funciona durante ese periodo y se cierra automáticamente al terminar. El cliente obtiene el ancho de banda con iperf3 y, en Linux, también el tiempo de ida y vuelta de `mean_rtt` en su salida `--json`: este campo procede de `TCP_INFO` del kernel y falta en clientes que no pueden leerlo, especialmente iperf3 bajo Cygwin en Windows. El modo UDP (`-u`) añade fluctuación y pérdida en cualquier plataforma.
- **Registra quién se conecta.** Cada conexión TCP entrante, en cualquier puerto y no solo HTTP, se lee de `/proc/net/tcp[6]` y se guarda en SQLite; se conservan las 1000 más recientes.
- **Proporciona un proxy anytls.** sing-box con certificado autofirmado y BBR. Si se instala el módulo, la página `/proxy` de la consola indica si el nodo funciona y ofrece su entrada Clash y enlace `anytls://` con botón de copia, para compartir el nodo sin volver a la terminal.
- **Proporciona un proxy vmess/vless/trojan/shadowsocks, en cualquier combinación.** Otro proceso sing-box comparte el mismo binario incluido que anytls. Si se instala, la página compartida `/proxy` añade una sección por protocolo con puerto, UUID o contraseña, entrada Clash, enlace para compartir y código QR. Cada protocolo tiene su propio botón de restablecimiento, sin cambiar las credenciales de los demás.

Los módulos seleccionables son web, iperf3, anytls, proxy, frps y Lucky. frps y Lucky siguen siendo experimentales; su funcionamiento no se ha aceptado en un servidor real para esta versión.

**Fuera de alcance:** ni ACME ni nombres de dominio (el certificado de 443 es autofirmado deliberadamente); iperf3 no permanece activo; ni proxy inverso ni contenedores; la página pública nunca revela el nombre del equipo, el kernel, el tiempo de actividad, la lista de servicios ni parámetros de proxy. Este proyecto no sustituye a `vps-webserver` ni a `Anytsl-Serve`: ambos siguen manteniéndose por separado y su código se incluye aquí sin absorberlos.

## Requisitos

- SO: Debian 11+ o Ubuntu 20.04+, systemd; ejecutar como root.
- Entorno: Python 3.9+ (basta el `python3` de la distribución; no hay dependencias de Python que instalar).
- Arquitectura: cualquiera para web e iperf3; **solo x86-64** para anytls, proxy, frps y Lucky, porque los ejecutables incluidos son para amd64.
- Para el módulo web en sus puertos públicos predeterminados, 80 y 443 **DEBEN** estar libres: el instalador rechaza la instalación en vez de competir con nginx, Apache, Caddy o `vps-webserver`.
- Servicios externos: ninguno durante la ejecución. La instalación requiere el repositorio de paquetes de tu distribución; la consulta opcional de la IP pública puede contactar con un servicio externo.
- Mínimo: el SO, entorno, arquitectura y puertos libres anteriores. No se registra ningún requisito de hardware recomendado adicional; un VPS con unos 150 MB de disco admite el binario incluido.

## Instalación

Instalación rápida en una línea (última etiqueta de versión, sin variables de configuración):

```bash
git clone --branch v2.0.0 --depth 1 https://github.com/CharlesGool/vps-server.git vps-server && cd vps-server && bash deploy/install.sh
```

Paso a paso, con configuración:

```bash
# Always clone a tag, not the default branch — the branch tip may be mid-work.
# Latest release tag: git ls-remote --tags https://github.com/CharlesGool/vps-server.git
git clone --branch v2.0.0 --depth 1 https://github.com/CharlesGool/vps-server.git vps-server
cd vps-server
cp .env.example .env   # optional — every variable has a working default
bash deploy/install.sh
```

`deploy/install.sh` pregunta qué módulos instalar, el idioma de la interfaz, si se debe proteger la consola con contraseña y qué puertos usar. La etiqueta v2.0.0 incluye los seis módulos seleccionables; frps y Lucky son experimentales.

**Volver a ejecutarlo actualiza la instalación existente.** Detecta una instalación previa, ofrece conservar su configuración y solo pregunta por los ajustes inexistentes en la versión instalada, cada uno con su valor predeterminado, por lo que pulsar Intro es válido. Se conservan la contraseña de la consola, el puerto persistente, los certificados, el registro de visitantes, las credenciales del nodo anytls y el puerto y las credenciales de cada protocolo proxy instalado. Responde `n` a la pregunta de actualización para volver a configurar los ajustes.

## Orientaciones

### Quick start

La versión 2.0.0 sitúa la implementación web en `src/web/app.py` y ejecuta los instaladores desde `deploy/`. Los ejecutables incluidos y sus avisos de licencia están en `third_party/`; los metadatos de versión están en `config/`. Los archivos instalados conservan una estructura plana bajo `$PREFIX`; el cambio de organización del repositorio no migra los datos de ejecución. Las rutas nuevas han superado las pruebas locales, pero esta versión no se ha aceptado en un servidor real.

```bash
bash deploy/install.sh                       # interactive: temporary browser setup wizard
sudo VPSSRV_MODULES=web,iperf3 bash deploy/install.sh   # unattended, no prompts
systemctl status vps-server-web              # is it up
bash deploy/anytls/setup-anytls.sh status           # anytls node details, if that module is installed
bash deploy/proxy/setup-proxy.sh status             # proxy node details, if that module is installed
```

Después, desde otra máquina:

```bash
curl -sS  http://<ip>/                     # reachability over plain HTTP
curl -sSk https://<ip>/                    # ... and over TLS (self-signed)
iperf3 -c <ip> -p 5201 --json              # only while a window is open
```

### Verify it works

Después de `bash deploy/install.sh` debes ver un resumen con cada módulo instalado y su puerto. A continuación:

- `systemctl status vps-server-web` muestra `active (running)`.
- Abrir `http://<ip>/` desde **otra máquina** muestra una página titulada «Reachable» con tu propia IP pública. Abrir `https://<ip>/` muestra la misma página después de aceptar la advertencia del certificado; la línea del protocolo indica HTTPS.
- Iniciar sesión en `http://<ip>:<console port>/` muestra el panel con el control de iperf3 y la ventana cerrada.
- Tras abrir una ventana de 5 minutos, `iperf3 -c <ip> -p 5201 --json` desde otra máquina muestra la velocidad y contiene `mean_rtt`. Cinco minutos después, el mismo comando no puede conectarse: significa que la ventana se cerró automáticamente, no que haya un fallo.
- Si instalaste anytls: `systemctl status vps-server-anytls` muestra `active (running)`.
- Si instalaste proxy: `systemctl status vps-server-proxy` muestra `active (running)`.

### Configuration

Cada variable tiene un valor predeterminado funcional; `.env` es opcional. Las más importantes:

| Variable | Significado | Predeterminado | Obligatoria |
|---|---|---|---|
| `VPSSRV_PUBLIC_HTTP_PORT` | Página pública de accesibilidad, sin cifrar | `80` | no |
| `VPSSRV_PUBLIC_HTTPS_PORT` | Página pública de accesibilidad, TLS | `443` | no |
| `VPSSRV_PUBLIC_ENABLE` | Habilitar la página pública | `1` | no |
| `VPSSRV_CONSOLE_PORT` | Puerto de la consola; `0` genera uno y lo recuerda | `0` | no |
| `VPSSRV_AUTH` | Exigir contraseña en la consola | `1` | no |
| `VPSSRV_IPERF_PORT` | Puerto donde escucha la ventana iperf3 abierta | `5201` | no |
| `VPSSRV_IPERF_MAX_MINUTES` | Límite que la consola no puede superar | `60` | no |
| `VPSSRV_DEFAULT_LANG` | `en` / `zh_cn` / `zh_tw` / `zh_hk` / `hi` / `es` / `ar` / `fr` | `en` | no |

Referencia completa: [Referencia de configuración][local-link-002].

## Desinstalación

Ejecuta como root desde el directorio del instalador, con los mismos valores `PREFIX` y `SERVICE_NAME` usados al instalar (el resumen del instalador muestra el comando exacto de desinstalación). Para eliminar los módulos y unidades instalados **conservando
los datos** en `$PREFIX` para una reinstalación posterior:

```bash
KEEP_DATA=1 bash deploy/uninstall.sh
```

Para eliminar los módulos instalados y **también borrar los datos** (incluidos el registro de visitantes, la contraseña de la consola, el puerto guardado y los certificados en `$PREFIX`):

```bash
bash deploy/uninstall.sh
```

Ambas modalidades desactivan los servicios anytls/proxy y sus configuraciones separadas, si están instalados. `KEEP_DATA=1` conserva `$PREFIX`, no esas configuraciones de módulos.

## Agradecimientos

La prueba del navegador usa [LibreSpeed](https://github.com/librespeed/speedtest); para generar códigos QR se usa
[qrcode-generator](https://github.com/kazuhikoarase/qrcode-generator); el núcleo proxy incluido es
[sing-box](https://github.com/SagerNet/sing-box). Los módulos experimentales incluyen
[frp](https://github.com/fatedier/frp) y
[Lucky](https://github.com/gdy666/lucky). Consulta los [avisos de terceros][local-link-003] para ver el inventario y las rutas de las licencias originales.

## Licencia

Licencia del proyecto: GPL-3.0 (SPDX: `GPL-3.0-only`); lee la [LICENSE][local-link-004] completa. Los fundamentos históricos de la combinación están en [Decisiones][local-link-005]. Los componentes de terceros registrados, rutas de licencias originales, enlaces al código fuente y asuntos pendientes para revisar antes de una versión están en [THIRD_PARTY_NOTICES.md][local-link-006]. Esta migración de documentación no constituye una nueva revisión jurídica.

Este proyecto no está afiliado a sing-box/SagerNet ni a LibreSpeed y no cuenta con su respaldo.

[local-link-001]: LOG.md#limitaciones-y-estado-actual-de-aceptación
[local-link-002]: DESIGN.md#configuration-reference
[local-link-003]: THIRD_PARTY_NOTICES.md
[local-link-004]: ../../LICENSE
[local-link-005]: LOG.md#decisiones
[local-link-006]: THIRD_PARTY_NOTICES.md
