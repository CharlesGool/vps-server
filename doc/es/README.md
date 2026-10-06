# vps-server

[简体中文](../../README.md) | [English](../en/README.md) | **Español**

Administre pruebas de velocidad, proxies, FRP y Tailscale desde una consola Web.

[![License](https://img.shields.io/badge/license-GPL--3.0--only-blue)](../../LICENSE) [![Release](https://img.shields.io/badge/release-v5.2.3-blue)](https://github.com/CharlesGool/vps-server/releases/tag/v5.2.3)

## Documentación

- Descripción general del proyecto: [README](README.md)

- Justificación del diseño: [DESIGN](DESIGN.md)

- Estado del proyecto: [LOG](LOG.md)
- Registros históricos: [HISTORY](HISTORY.md)
- Historial de cambios: [CHANGELOG](CHANGELOG.md)

- Avisos de terceros: [THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES.md)

## Introducción

- Pruebas de subida/bajada en el navegador, registros de visitantes y pruebas iperf3 de cliente y servidor con duración limitada.
- Nodos Singbox para AnyTLS, VMess, VLESS, Trojan y Shadowsocks, con enlaces, cuotas, límites de velocidad y caducidad.
- Servidor FRPS, instancias FRPC y proxies TCP/UDP, acceso a Lucky y estado y dispositivos de Tailscale.
- Módulos opcionales, reenvío de puertos, registros detallados, terminal root con contraseña, tres idiomas y temas.
- Las instalaciones nuevas incluyen solo Web; las páginas públicas están desactivadas. Consulte [LOG](LOG.md#errores) para problemas y límites de verificación.

### Capturas de pantalla

Capturas de la compilación de prueba test-d2335e8 en el entorno de prueba con la interfaz en chino simplificado. Muestran módulos instalados, formularios de creación y Tailscale sin iniciar sesión; la instalación predeterminada sigue incluyendo solo Web. Las direcciones y credenciales permanecen ocultas, y las capturas de registros muestran solo categorías y filtros.

![Inicio y accesos a funciones](../resources/screenshots/zh-cn/home.jpg)

<details>
<summary>Inicio de sesión y pruebas</summary>

**Inicio de sesión**

![Inicio de sesión](../resources/screenshots/zh-cn/login.jpg)

**Servidor y cliente iperf3**

![Servidor y cliente iperf3](../resources/screenshots/zh-cn/iperf3.jpg)

</details>

<details>
<summary>Singbox y FRP</summary>

**Vista de nodos Singbox**

![Vista de nodos Singbox](../resources/screenshots/zh-cn/singbox.jpg)

**Crear un nodo Singbox**

![Crear un nodo Singbox](../resources/screenshots/zh-cn/singbox-create.jpg)

**Gestión de acceso de Singbox**

![Gestión de acceso de Singbox](../resources/screenshots/zh-cn/singbox-access.jpg)

**Servidor FRPS**

![Servidor FRPS](../resources/screenshots/zh-cn/frps.jpg)

**Crear una instancia FRPC**

![Crear una instancia FRPC](../resources/screenshots/zh-cn/frpc-create.jpg)

</details>

<details>
<summary>Tailscale</summary>

**Vista y formulario de conexión de Tailscale**

![Vista y formulario de conexión de Tailscale](../resources/screenshots/zh-cn/tailscale-overview.jpg)

**Configuración general de Tailscale**

![Configuración general de Tailscale](../resources/screenshots/zh-cn/tailscale-settings.jpg)

**Filtros de registros de Tailscale**

![Filtros de registros de Tailscale](../resources/screenshots/zh-cn/tailscale-log-filters.jpg)

</details>

<details>
<summary>Configuración y registros</summary>

**Configuración de tema e idioma**

![Configuración de tema e idioma](../resources/screenshots/zh-cn/settings-appearance.jpg)

**Gestión de módulos**

![Gestión de módulos](../resources/screenshots/zh-cn/settings-modules.jpg)

**Verificación de contraseña de administrador**

![Verificación de contraseña de administrador](../resources/screenshots/zh-cn/password-verification.jpg)

**Categorías y filtros de registros detallados**

![Categorías y filtros de registros detallados](../resources/screenshots/zh-cn/detailed-log-filters.jpg)

**Historial de cambios**

![Historial de cambios](../resources/screenshots/zh-cn/changelog.jpg)

</details>

## Requisitos

Mínimo: Linux x86-64, systemd, acceso root, Python 3.9+, Bash y directorios de instalación/estado escribibles. El instalador está dirigido a Debian 11+ y Ubuntu 20.04+; otras arquitecturas no están soportadas.

Se recomienda una versión mantenida de Debian/Ubuntu, espacio para copias de seguridad y puertos abiertos para las funciones activadas. Debian 13 x86-64 se verificó en una máquina; Python 3.9 y otras distribuciones no tienen aceptación independiente. El paquete Release incluye artefactos sin conexión, pero los paquetes básicos ausentes requieren un repositorio del sistema. Crear el paquete completo desde el código fuente requiere red.

## Instalación

Ejecute como root.

### Instalación rápida

Instale solo la consola Web con un comando. Añada otros módulos según necesite desde Configuración/Módulos.

```bash
curl -fL https://github.com/CharlesGool/vps-server/releases/download/v5.2.3/vps-server-v5.2.3-linux-amd64.tar.gz | tar -xz -C /root && VPSSRV_MODULES=web bash /root/vps-server/deploy/install.sh
```

### Instalación normal

La instalación desde código incluye el archivo Tailscale; el entorno privado nftables solo se incluye en el paquete completo. Copiar `.env` es opcional; edítelo antes de instalar si necesita personalización.

```bash
git clone --depth 1 --branch v5.2.3 https://github.com/CharlesGool/vps-server.git /root/vps-server-source
cd /root/vps-server-source
cp .env.example .env
bash deploy/install.sh
```

#### Instalación sin conexión

Descargue el [paquete completo](https://github.com/CharlesGool/vps-server/releases/download/v5.2.3/vps-server-v5.2.3-linux-amd64.tar.gz) y [SHA256SUMS](https://github.com/CharlesGool/vps-server/releases/download/v5.2.3/SHA256SUMS) en una máquina con red y transfiéralos a `/root/vps-server-download/` del destino. Ejecute lo siguiente; el destino debe disponer de las dependencias básicas del sistema indicadas arriba.

```bash
cd /root/vps-server-download
sha256sum -c SHA256SUMS
mkdir -p /root/vps-server-v5.2.3
tar -xzf vps-server-v5.2.3-linux-amd64.tar.gz -C /root/vps-server-v5.2.3 --strip-components=1
cd /root/vps-server-v5.2.3
VPSSRV_MODULES=web bash deploy/install.sh
```

Después de elegir el idioma, systemd ejecuta la instalación en segundo plano. **DEBE** conservar el directorio fuente hasta que finalice. Para la ruta predeterminada, consulte:

```bash
tail -f /root/apps/vps-server/.local/install-job/install.log
cat /root/apps/vps-server/.local/install-job/exit-code
```

La ausencia de `exit-code` indica que la tarea no terminó; `0` indica éxito y otros valores, fallo. Ajuste la ruta para un `PREFIX` personalizado. El registro final incluye las direcciones de la consola, la contraseña inicial y los resultados de módulos. Una desconexión del terminal no significa que falló.

## Uso

Inicie sesión con la dirección y contraseña del registro. Instale componentes en Configuración/Módulos y gestione nodos, instancias FRPC o pruebas temporales. Direcciones y credenciales se ocultan por defecto; los editores cargan los valores actuales. El terminal root y la seguridad requieren verificar la contraseña. Conecte y autentique Tailscale; las rutas anunciadas requieren aprobación en Tailnet.

Plantilla de configuración: [.env.example](../../.env.example). Todas las variables tienen valores predeterminados; no es obligatorio indicar credenciales. Use rutas absolutas, interruptores `0/1`, puertos `1-65535` (salvo el `0` de consola) y cantidades/duraciones enteras. Salvo `PREFIX` y el `VPSSRV_STATE_DIR` inicial, se guardan en `.env` de la raíz del estado; reinicie Web tras cambiarlos. Los valores iniciales de módulos se aplican al instalarlos.

| Parámetro | Predeterminado | Significado |
| --- | --- | --- |
| `PREFIX` | `/root/apps/vps-server` | Directorio de código, parámetro de entorno del instalador/desinstalador; no tiene efecto en `.env`. |
| `VPSSRV_STATE_DIR` | `/var/lib/vps-server` | Raíz del estado para la primera instalación; editar `.env` no migra datos. |
| `VPSSRV_DATA_DIR` | vacío | Directorio de datos; vacío usa `data/` bajo la raíz del estado. |
| `VPSSRV_CERT_DIR` | vacío | Directorio de certificados; vacío usa `certs/` bajo la raíz del estado. |
| `VPSSRV_PUBLIC_ENABLE` | `0` | Páginas públicas de accesibilidad; 1 las activa. |
| `VPSSRV_PUBLIC_HTTP_PORT` | `80` | Puerto HTTP público. |
| `VPSSRV_PUBLIC_HTTPS_PORT` | `443` | Puerto HTTPS público. |
| `VPSSRV_HOST` | `0.0.0.0` | Dirección de escucha Web. |
| `VPSSRV_CONSOLE_PORT` | `0` | Puerto de consola; 0 elige y guarda uno entre 20000-59999. |
| `VPSSRV_CONSOLE_PORT_FILE` | vacío | Archivo del puerto; vacío usa `console_port.txt` bajo la raíz del estado. |
| `VPSSRV_CONSOLE_TLS` | `0` | Activación de TLS para la consola. |
| `VPSSRV_AUTH` | `1` | Autenticación de consola; 0 permite administrar sin autenticación. |
| `VPSSRV_PASSWORD_FILE` | vacío | Archivo de contraseña; vacío usa `admin_password.txt` bajo la raíz del estado. |
| `VPSSRV_IP_ALLOWLIST_FILE` | vacío | Archivo de IP permitidas sin contraseña; vacío usa la lista predeterminada. |
| `VPSSRV_LOGIN_MAX_ATTEMPTS` | `5` | Máximo de intentos fallidos por ventana. |
| `VPSSRV_LOGIN_WINDOW_SECONDS` | `60` | Ventana de intentos fallidos en segundos. |
| `VPSSRV_LOGIN_LOCKOUT_SECONDS` | `30` | Bloqueo tras superar el límite, en segundos. |
| `VPSSRV_TLS_CERT` | vacío | Ruta del certificado TLS propio; indique también la clave. |
| `VPSSRV_TLS_KEY` | vacío | Ruta de clave TLS propia; sin el par se genera un certificado autofirmado. |
| `VPSSRV_IPERF_ENABLE` | `1` | Activación de iperf3. |
| `VPSSRV_IPERF_PORT` | `5201` | Puerto del servidor temporal. |
| `VPSSRV_IPERF_DEFAULT_MINUTES` | `10` | Duración predeterminada en minutos. |
| `VPSSRV_IPERF_MAX_MINUTES` | `60` | Duración máxima en minutos. |
| `VPSSRV_PORTFWD_ENABLE` | `1` | Activación de reenvío de puertos. |
| `VPSSRV_PORTFWD_MAX_RULES` | `20` | Máximo de reglas de reenvío guardadas. |
| `VPSSRV_TRACK_CONNECTIONS` | `1` | Recopilar conexiones TCP del núcleo. |
| `VPSSRV_CONN_POLL_SECONDS` | `5` | Intervalo de muestreo de conexiones en segundos. |
| `VPSSRV_TRUST_PROXY` | `0` | Confiar en cabeceras del proxy; solo con un proxy controlado, desactiva el acceso por IP sin contraseña. |
| `VPSSRV_MAX_TEST_MB` | `200` | Límite de transferencia por prueba Web, en MB. |
| `VPSSRV_TEST_SECONDS` | `10` | Duración de medición, en segundos. |
| `VPSSRV_WARMUP_SECONDS` | `2` | Segundos de calentamiento excluidos del resultado. |
| `VPSSRV_DOWNLOAD_STREAMS` | `6` | Flujos de descarga paralelos. |
| `VPSSRV_UPLOAD_STREAMS` | `3` | Flujos de subida paralelos. |
| `VPSSRV_PING_SAMPLES` | `20` | Número de muestras de latencia. |
| `VPSSRV_DEFAULT_LANG` | `en` | Idioma predeterminado: `en`, `zh_cn`, `es`. |
| `VPSSRV_PROXY_CONFIG` | `/etc/vps-server-proxy/config.json` | Ruta de configuración del proxy unificado. |
| `VPSSRV_PROXY_SERVICE` | `vps-server-proxy.service` | Nombre del servicio proxy unificado. |
| `PROXY_PROTOCOLS` | vacío | Subconjunto separado por comas; vacío instala los cinco protocolos. |
| `PROXY_SNI` | `www.bing.com` | SNI TLS inicial para VMess, VLESS y Trojan. |
| `PROXY_ANYTLS_PORT` | vacío | Puerto inicial del protocolo; vacío lo selecciona automáticamente. |
| `PROXY_ANYTLS_PASSWORD` | vacío | Credencial inicial del protocolo; vacío la genera. |
| `PROXY_VMESS_PORT` | vacío | Puerto inicial del protocolo; vacío lo selecciona automáticamente. |
| `PROXY_VMESS_UUID` | vacío | Credencial inicial del protocolo; vacío la genera. |
| `PROXY_VLESS_PORT` | vacío | Puerto inicial del protocolo; vacío lo selecciona automáticamente. |
| `PROXY_VLESS_UUID` | vacío | Credencial inicial del protocolo; vacío la genera. |
| `PROXY_TROJAN_PORT` | vacío | Puerto inicial del protocolo; vacío lo selecciona automáticamente. |
| `PROXY_TROJAN_PASSWORD` | vacío | Credencial inicial del protocolo; vacío la genera. |
| `PROXY_SS_PORT` | vacío | Puerto inicial del protocolo; vacío lo selecciona automáticamente. |
| `PROXY_SS_PASSWORD` | vacío | Credencial inicial del protocolo; vacío la genera. |

El instalador también acepta `VPSSRV_MODULES` (lista `web,iperf3,proxy,frps,lucky,tailscale`; valor inicial `web`, conserva módulos al reinstalar) y `SERVICE_NAME` (predeterminado `vps-server-web`). El argumento `KEEP_DATA=1` conserva los datos al desinstalar. No son parámetros de Web.

Para mantener el código, ejecute `python3 tools/check-project/check_project.py`. Requiere Git, Bash, Python 3.9+ y Node.js 24; Node.js compila el frontend y comprueba JavaScript y no es necesario para ejecutar el servidor. Use `--node /ruta/absoluta/node` si no está en PATH. Los directorios `tools/build_styles`, `tools/build_offline`, `tools/verify_dependencies` pasan a llamarse `build-styles`, `build-offline`, `verify-dependencies`, respectivamente; sustituya las rutas en los comandos antiguos de mantenimiento. Los comandos de instalación no cambian. La comprobación no inicia servicios ni sustituye la aceptación del despliegue.

Antes de instalar el código de desarrollo, ejecute `npm ci && npm run check` en `web/` (la compilación requiere Node.js 24). El paquete completo ya incluye el frontend; el servidor no necesita Node.js. La comprobación unificada incluye diseño, tipos y compilación frontend.

## Actualización

Las versiones de esquema 1, v5.1.1 de prueba, v5.2.0 y v5.2.1, se actualizan con los pasos anteriores. Copie la raíz del estado, `/etc/vps-server-proxy`, `/etc/vps-server-frps`, configuraciones FRPC y Lucky. Extraiga fuera del directorio instalado y use el mismo `PREFIX` y raíz del estado. Se conservan contraseñas, puertos, certificados, sesiones y módulos; el directorio fuente ya no almacena datos persistentes.

v5.1.0 y anteriores usan el esquema antiguo, sin migración automática. **DEBE** respaldar el directorio antiguo y las configuraciones, instalar de nuevo y restaurar manualmente los ajustes necesarios. Si falta el localizador de estado o se detecta el esquema antiguo, se rechaza la actualización directa; no elimine antes el directorio antiguo.

Compruebe el código de salida `0`, que `systemctl is-active vps-server-web` indique `active`, la versión v5.2.3, la contraseña original, las configuraciones de nodos/FRPC y los módulos y puertos. Ajuste el nombre del servicio si lo personalizó. Conserve registros y copias ante un fallo; una ejecución parcial no es éxito.

## Desinstalación

El primer bloque desinstala servicios conservando programa, configuración y datos; el segundo elimina todo. Indique el mismo `PREFIX` personalizado o ejecute desde un directorio fuente conservado.

```bash
cd /root/apps/vps-server/installer-source
KEEP_DATA=1 bash deploy/uninstall.sh
```

```bash
cd /root/apps/vps-server/installer-source
bash deploy/uninstall.sh
```

Ambos detienen servicios y liberan puertos del proyecto. La eliminación completa borra además el estado predeterminado, configuraciones FRPS/proxy/FRPC, ajustes y tareas Lucky e identidad Tailscale. No elimina automáticamente datos externos a la raíz del estado. Revise la pertenencia de instancias FRPC compartidas. Un fallo al limpiar el cortafuegos detiene la eliminación completa y conserva los registros de pertenencia.

## Agradecimientos

Este proyecto utiliza o toma como referencia: [LibreSpeed](https://github.com/librespeed/speedtest), [sing-box](https://github.com/SagerNet/sing-box), [frp](https://github.com/fatedier/frp), [Lucky](https://github.com/gdy666/lucky), [Tailscale](https://github.com/tailscale/tailscale), [iperf3](https://github.com/esnet/iperf), [qrcode-generator](https://github.com/kazuhikoarase/qrcode-generator), [xterm.js](https://github.com/xtermjs/xterm.js), [Fontsource](https://github.com/fontsource/font-files), [Lucide](https://github.com/lucide-icons/lucide).

Consulte [Avisos de terceros](THIRD_PARTY_NOTICES.md) para atribución y condiciones originales.

## Licencia

GNU General Public License v3.0, SPDX: `GPL-3.0-only`. Texto íntegro: [LICENSE](../../LICENSE). Los componentes de terceros conservan sus licencias originales. Este proyecto no está asociado ni respaldado por sing-box/SagerNet o LibreSpeed.
