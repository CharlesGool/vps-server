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
- **Mide la velocidad desde un navegador.** Una consola en un puerto alto aleatorio y persistente realiza pruebas de subida y bajada con LibreSpeed. Admite la contraseña de administrador o una IP privada de LAN añadida expresamente. Solo un administrador autenticado con contraseña puede cambiar la contraseña o la lista de IP; no se admiten IP públicas.
- **Mide velocidad y latencia con iperf3, bajo demanda.** La consola abre una ventana de duración limitada; `iperf3 -s` solo funciona durante ese periodo y se cierra automáticamente al terminar. El cliente obtiene el ancho de banda con iperf3 y, en Linux, también el tiempo de ida y vuelta de `mean_rtt` en su salida `--json`: este campo procede de `TCP_INFO` del kernel y falta en clientes que no pueden leerlo, especialmente iperf3 bajo Cygwin en Windows. El modo UDP (`-u`) añade fluctuación y pérdida en cualquier plataforma. La consola muestra por separado el estado y el puerto; el puerto se puede cambiar con la ventana cerrada y el ajuste persiste tras reiniciar el servicio.
- **Registra quién se conecta.** Cada conexión TCP entrante, en cualquier puerto y no solo HTTP, se lee de `/proc/net/tcp[6]` y se guarda en SQLite; se conservan las 1000 más recientes.
- **Ofrece un proxy anytls.** sing-box usa un certificado autofirmado y BBR. La página autenticada `/proxy` muestra el estado, el tráfico y los ajustes de conexión editables; si hay una dirección LAN privada, también ofrece un enlace de importación directa en Clash Meta for Android y un código QR.
- **Ofrece proxies vmess/vless/trojan/shadowsocks en cualquier combinación.** Otro proceso sing-box comparte el binario incluido con anytls. Cada protocolo instalado empieza con un nodo numerado; la consola permite crear más nodos del mismo protocolo y eliminarlos individualmente. Cada nodo tiene un límite de tráfico en GiB, editores separados para la conexión y los límites, controles de restablecimiento aleatorio y la misma opción de importación en Clash Meta solo por LAN. La URL de importación contiene un token opaco y se invalida cuando cambian el nombre o los ajustes de conexión del nodo. Los puertos públicos no ofrecen configuraciones proxy. Al crear un nodo se puede introducir la credencial o dejar el campo vacío para generarla al azar; el SNI predeterminado para TLS es `www.bing.com`. La página muestra las direcciones de las interfaces y de Tailscale.

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
# Clona una etiqueta de versión; la rama predeterminada puede contener cambios aún no publicados.
# Lista las etiquetas de versión: `git ls-remote --tags https://github.com/CharlesGool/vps-server.git`
git clone --branch v2.0.0 --depth 1 https://github.com/CharlesGool/vps-server.git vps-server
cd vps-server
cp .env.example .env   # opcional: todas las variables tienen un valor predeterminado funcional
bash deploy/install.sh
```

`deploy/install.sh` pregunta qué módulos instalar, el idioma de la interfaz, si se debe proteger la consola con contraseña y qué puertos usar. La etiqueta v2.0.0 incluye los seis módulos seleccionables; frps y Lucky son experimentales.

**Volver a ejecutarlo actualiza la instalación existente.** Detecta una instalación previa, ofrece conservar su configuración y solo pregunta por los ajustes inexistentes en la versión instalada, cada uno con su valor predeterminado, por lo que pulsar Intro es válido. Se conservan la contraseña de la consola, el puerto persistente, los certificados, el registro de visitantes, las credenciales del nodo anytls y el puerto y las credenciales de cada protocolo proxy instalado. Responde `n` a la pregunta de actualización para volver a configurar los ajustes.

## Orientaciones

### Quick start

La versión 2.0.0 sitúa la implementación web en `src/web/app.py` y ejecuta los instaladores desde `deploy/`. Los ejecutables incluidos y sus avisos de licencia están en `third_party/`; los metadatos de versión están en `config/`. Los archivos instalados conservan una estructura plana bajo `$PREFIX`; el cambio de organización del repositorio no migra los datos de ejecución. Las rutas nuevas han superado las pruebas locales, pero esta versión no se ha aceptado en un servidor real.

```bash
bash deploy/install.sh                       # configuración interactiva mediante un asistente temporal en el navegador
sudo VPSSRV_MODULES=web,iperf3 bash deploy/install.sh   # instalación desatendida, sin preguntas
systemctl status vps-server-web              # comprueba si está activo
bash deploy/anytls/setup-anytls.sh status           # detalles del nodo anytls, si está instalado ese módulo
bash deploy/proxy/setup-proxy.sh status             # detalles del nodo proxy, si está instalado ese módulo
```

Después, desde otra máquina:

```bash
curl -sS  http://<ip>/                     # comprueba la accesibilidad mediante HTTP sin cifrar
curl -sSk https://<ip>/                    # ... y mediante TLS (certificado autofirmado)
iperf3 -c <ip> -p 5201 --json              # solo mientras haya una ventana abierta
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

## Actualización

Para actualizar, use un árbol de trabajo actual y vuelva a ejecutar el instalador con el mismo directorio de instalación y los mismos módulos. Conserve una copia de los datos persistentes hasta comprobar los servicios y la consola actualizados.

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

Licencia del proyecto: GPL-3.0 (SPDX: `GPL-3.0-only`); lee la [LICENSE][local-link-004] completa. Los fundamentos históricos de la combinación están en [Decisiones][local-link-005]. Los componentes incluidos, sus licencias originales, las fuentes verificadas de los artefactos y los límites pendientes de revisión jurídica están en [THIRD_PARTY_NOTICES.md][local-link-006].

Este proyecto no está afiliado a sing-box/SagerNet ni a LibreSpeed y no cuenta con su respaldo.

[local-link-001]: LOG.md#limitaciones-y-estado-actual-de-aceptación
[local-link-002]: DESIGN.md#configuration-reference
[local-link-003]: THIRD_PARTY_NOTICES.md
[local-link-004]: ../../LICENSE
[local-link-005]: LOG.md#decisiones
[local-link-006]: THIRD_PARTY_NOTICES.md
