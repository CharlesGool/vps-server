---
name: project-readme-es
description: Descripción general y uso del proyecto
metadata:
  version: "1.0.0"
  lang: "es"
---

# vps-server

## Multilingüe

[简体中文](../../README.md) | [English](../en/README.md) | **Español**

## Documentación

- Descripción general del proyecto: [README](README.md)

- Justificación del diseño: [DESIGN](DESIGN.md)

- Estado del proyecto: [LOG](LOG.md)
- Registros históricos: [HISTORY](HISTORY.md)
- Historial de cambios: [CHANGELOG](CHANGELOG.md)

- Avisos de terceros: [THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES.md)

## Introducción

Un paquete de módulos seleccionables para un VPS Debian/Ubuntu: página pública para comprobar la accesibilidad de los puertos web, consola para medir velocidad y registrar conexiones, ventana iperf3 bajo demanda y nodos proxy sing-box. v5.1.0 incluye nodos administrados, políticas de tráfico, acceso sin contraseña desde IP privadas, interruptores HTTP/HTTPS separados, gestión de FRPS y FRPC local, instalación de Lucky e instalador directo en terminal. Consulta el alcance de la versión y las comprobaciones en el [historial de cambios][local-link-001].

## Qué hace

- **Permite a cualquiera comprobar la accesibilidad.** Una página deliberadamente mínima en los puertos **80** y
  **443**, sin inicio de sesión. Dale a alguien la IP: si se muestra la página, tus puertos web son accesibles desde su ubicación. Muestra su IP de origen, la hora del servidor y el puerto y protocolo por los que entró, y nada más sobre el servidor.
- **Mide la velocidad desde un navegador.** La consola, en un puerto alto aleatorio y persistente, realiza pruebas de subida y bajada con LibreSpeed. Admite la contraseña de administrador o una IP privada de LAN añadida expresamente. El botón de acceso por IP siempre aparece; quien no esté autorizado recibe indicaciones para entrar con contraseña y añadir una IP privada en los ajustes. Los ajustes de seguridad exigen una verificación reciente de la contraseña de administrador antes de mostrar la lista de IP o aceptar cambios. La lista admite direcciones IPv4 privadas o IPv6 locales únicas, una por entrada, y se puede desactivar el acceso por IP sin borrar las entradas. Cambiar la contraseña invalida las sesiones existentes. La página general de ajustes permite elegir apariencia e idioma directamente; cuando vence la verificación de la contraseña de administrador para seguridad, debe repetirse.
- **Mide velocidad y latencia con iperf3, bajo demanda.** La consola abre una ventana de duración limitada; `iperf3 -s` solo funciona durante ese periodo y se cierra automáticamente al terminar. El cliente obtiene el ancho de banda con iperf3 y, en Linux, también el tiempo de ida y vuelta de `mean_rtt` en su salida `--json`: este campo procede de `TCP_INFO` del kernel y falta en clientes que no pueden leerlo, especialmente iperf3 bajo Cygwin en Windows. El modo UDP (`-u`) añade fluctuación y pérdida en cualquier plataforma. La consola muestra por separado el estado y el puerto; el puerto se puede cambiar con la ventana cerrada y el ajuste persiste tras reiniciar el servicio.
- **Registra quién se conecta.** Cada conexión TCP entrante, en cualquier puerto y no solo HTTP, se lee de `/proc/net/tcp[6]` y se guarda en SQLite; se conservan las 1000 más recientes.
- **Ofrece un proxy anytls.** sing-box usa un certificado autofirmado y BBR. La página autenticada `/proxy` muestra el estado, el tráfico y los ajustes de conexión editables; si hay una dirección LAN privada, también ofrece un enlace de importación directa en Clash Meta for Android y un código QR. La URL de suscripción también se puede copiar.
- **Ofrece proxies vmess/vless/trojan/shadowsocks en cualquier combinación.** Otro proceso sing-box comparte el binario incluido con anytls. Cada protocolo instalado empieza con un nodo numerado; la consola permite crear más nodos del mismo protocolo y eliminarlos individualmente. Cada nodo tiene un límite de tráfico en GiB, editores separados para la conexión y los límites, controles de restablecimiento aleatorio y la misma opción de importación en Clash Meta solo por LAN. La URL de importación contiene un token opaco y se invalida cuando cambian el nombre o los ajustes de conexión del nodo. Los puertos públicos no ofrecen configuraciones proxy. Al crear un nodo se puede introducir la contraseña o la clave/UUID del protocolo o dejar el campo vacío para generarla al azar; el SNI predeterminado para TLS es `www.bing.com`. La página muestra las direcciones de las interfaces y de Tailscale. Cada nodo admite límites independientes de velocidad de subida y bajada en Mbps. Al alcanzar el límite de tráfico en GiB, se puede limitar ambas direcciones a 1 Mbps o bloquear el uso. El tráfico del período se reinicia cada número elegido de días, meses o años. Una duración de validez opcional bloquea el uso al terminar. También se puede copiar el enlace de suscripción de la LAN.

La primera instalación instala solo Web. `VPSSRV_MODULES` permite elegir otros módulos de servidor entre web, iperf3, anytls, proxy, frps y lucky; los módulos opcionales también se pueden instalar desde la consola. FRPC es una función de cliente local separada.
La página FRPS autenticada muestra el estado del servicio local, las direcciones de las interfaces y los datos de conexión; el token y el puerto permanecen ocultos hasta que se solicitan. En ella se pueden modificar el puerto y el token de FRPS y activar o desactivar el servicio. La página FRPC independiente presenta las instancias locales del cliente como tarjetas con la IP oculta y un indicador de conexión basado en el socket TCP establecido. Su botón Probar conexión realiza un inicio de sesión FRPC separado con el servidor, el puerto y el token guardados. La página de cada instancia revela la IP o el token cuando se solicita y, antes de editar, muestra el tipo, la IP local, el puerto local y el puerto remoto de cada proxy TCP/UDP. Al guardar, el operador permanece en la página de la instancia; se verifica el archivo y, si falla la operación, se restaura la configuración anterior. Estas acciones de FRP utilizan la sesión iniciada; la verificación reciente de la contraseña del administrador se reserva para acciones de Ajustes de seguridad, como cambiar la contraseña o las IP de acceso sin contraseña. El editor de campos solo admite configuraciones TCP/UDP sencillas con autenticación por token y no modifica TOML de FRPC que no puede representar. La consola no muestra el estado en tiempo real de instancias FRPC de otros dispositivos. La página Módulos comprueba por separado el ejecutable local de FRPC y la plantilla `frpc@.service`, sin depender de las configuraciones de instancia del servidor. Ofrece Instalar si falta cualquiera de los dos. La instalación utiliza el binario FRPC v0.71.0 incluido y verificado; no crea conexiones ni abre puertos de escucha por sí sola. El registro del módulo muestra la instalación y la verificación. Los binarios FRPC y FRPS v0.71.0 se incluyen en el repositorio. La instalación de FRPC consulta primero `vendor/frp/frpc` y también puede usar la copia del paquete de origen conservada por el instalador, sin acceso a GitHub. Su procedencia y SHA-256 figuran en los [avisos de terceros](THIRD_PARTY_NOTICES.md). Desinstalar detiene las instancias locales de FRPC, guarda una copia de sus configuraciones en `data/` y conserva los archivos de configuración para instalarlos de nuevo más adelante.

**Fuera de alcance:** ni ACME ni nombres de dominio (el certificado de 443 es autofirmado deliberadamente); iperf3 no permanece activo; ni proxy inverso ni contenedores; la página pública nunca revela el nombre del equipo, el kernel, el tiempo de actividad, la lista de servicios ni parámetros de proxy. Este proyecto no sustituye a `vps-webserver` ni a `Anytsl-Serve`: ambos siguen manteniéndose por separado y su código se incluye aquí sin absorberlos.

## Requisitos

- SO: Debian 11+ o Ubuntu 20.04+, systemd; ejecutar como root.
- Entorno: Python 3.9+ (basta el `python3` de la distribución; no hay dependencias de Python que instalar).
- Arquitectura: todo el proyecto requiere Linux x86-64; el instalador rechaza otras plataformas antes de modificar el sistema.
- Para el módulo web en sus puertos públicos predeterminados, 80 y 443 **DEBEN** estar libres: el instalador rechaza la instalación en vez de competir con nginx, Apache, Caddy o `vps-webserver`.
- Servicios externos: ninguno en tiempo de ejecución. FRPS, FRPC e iperf3 se instalan desde los artefactos incluidos; otros paquetes del sistema que falten pueden requerir un repositorio de la distribución. Los resúmenes de nodos usan direcciones de interfaces y de Tailscale si están disponibles, sin consultar la IP pública en Internet.
- Mínimo: el SO, entorno, arquitectura y puertos libres anteriores. No se registra ningún requisito de hardware recomendado adicional; un VPS con unos 180 MB de disco admite el binario incluido.

## Instalación

### Instalación rápida

Ejecuta como root; de forma predeterminada solo se instala la consola Web y el terminal muestra un puerto administrativo y una contraseña aleatorios. Estos comandos corresponden al código fuente de la versión formal `v5.1.0`; consulta el historial de cambios para conocer el alcance de las comprobaciones y los comportamientos aún sin verificar.

```bash
git clone --branch v5.1.0 --depth 1 https://github.com/CharlesGool/vps-server.git vps-server && cd vps-server && bash deploy/install.sh
```

### Instalación estándar

```bash
git clone --branch v5.1.0 --depth 1 https://github.com/CharlesGool/vps-server.git vps-server
cd vps-server
cp .env.example .env  # opcional: ajusta los valores siguiendo los comentarios
bash deploy/install.sh
```

`PREFIX` vale `/root/apps/vps-server` de forma predeterminada. La primera instalación se hace en el terminal, sin asistente en el navegador. Usa `VPSSRV_MODULES=web,iperf3,anytls,proxy,frps,lucky` para elegir módulos de servidor; si se omite, solo se instala Web. Instala o retira funciones opcionales desde Settings → Modules. Activa los sitios públicos HTTP y HTTPS por separado desde Home; la consola administrativa usa otro puerto. Instala FRPC por separado cuando necesites un cliente local; la instalación usa directamente el binario incluido.

## Orientaciones

### Quick start

La implementación Web está en `src/web/`, los recursos estáticos en `src/web/static/` y el instalador en `deploy/`. Los binarios y licencias incluidos están en `third_party/`; los metadatos de versión están en `config/`. El código Web instalado permanece en `$PREFIX/src/web/`, con la entrada compatible `$PREFIX/app.py` en la raíz. Los datos, certificados y el estado de instalación conservan sus rutas anteriores durante la actualización. El código fuente de v5.1.0 incluye FRPC, FRPS e iperf3; la etiqueta anterior `v5.0.0` conserva el comportamiento descrito en su documentación.

```bash
bash deploy/install.sh                       # primera instalación de la consola Web en el terminal
sudo VPSSRV_MODULES=web,iperf3 bash deploy/install.sh   # selecciona Web e iperf3
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

Después de `bash deploy/install.sh`, comprueba la dirección administrativa, la contraseña y el resumen de módulos que aparecen en el terminal. Los puertos públicos están desactivados por defecto; actívalos desde la consola antes de comprobarlos desde otra máquina:

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
| `VPSSRV_PUBLIC_ENABLE` | Mostrar la página pública al instalar; después, HTTP y HTTPS se controlan por separado desde Home | `0` | no |
| `VPSSRV_CONSOLE_PORT` | Puerto de la consola; `0` genera uno y lo recuerda | `0` | no |
| `VPSSRV_AUTH` | Exigir contraseña en la consola | `1` | no |
| `VPSSRV_IPERF_PORT` | Puerto donde escucha la ventana iperf3 abierta | `5201` | no |
| `VPSSRV_IPERF_MAX_MINUTES` | Límite que la consola no puede superar | `60` | no |
| `VPSSRV_DEFAULT_LANG` | `en` / `zh_cn` / `es`; los valores antiguos vuelven a `en` | `en` | no |

Referencia completa: [Referencia de configuración][local-link-002].

## Actualización

Para actualizar, usa el código fuente de la versión actual y vuelve a ejecutar el instalador con el mismo directorio de instalación y la misma selección de módulos. El instalador importa las configuraciones proxy antiguas al inventario de nodos administrados. Una instalación que tenía seleccionados zh-TW, zh-HK, hi, ar o fr pasa a inglés; después se puede elegir chino simplificado o español en Settings. Si la importación falla, examina la configuración y el registro del servicio: la consola no vuelve al editor anterior. Conserva una copia de los datos persistentes hasta verificar los servicios y la consola actualizados.

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

Ambas modalidades eliminan los servicios anytls/proxy y sus configuraciones separadas, si están instalados. También detienen las instancias FRPC de este proyecto, retiran su plantilla de servicio y el binario coincidente, y liberan de forma atómica sus entradas en `PORTS.md` sin tocar las de otros proyectos. `KEEP_DATA=1` conserva `$PREFIX`, las configuraciones `/etc/frp/frpc-*.toml` y sus copias de recuperación, pero no las configuraciones anytls/proxy. Sin `KEEP_DATA=1`, la desinstalación completa elimina también las configuraciones FRPC, los alias y las copias reconocidas como propias. Si encuentra instancias `frpc-*.toml` reconocibles por la consola, las detiene y elimina los archivos FRPC globales incluso cuando la plantilla antigua difiere de la actual: confirma antes la titularidad de esas instancias en servidores que compartan FRPC. Si no reconoce instancias y no puede determinar la titularidad, conserva los archivos FRPC globales e informa de ello. Un binario cuya suma de verificación no coincide detiene la limpieza.

## Agradecimientos

La prueba del navegador usa [LibreSpeed](https://github.com/librespeed/speedtest); para generar códigos QR se usa
[qrcode-generator](https://github.com/kazuhikoarase/qrcode-generator); el núcleo proxy incluido es
[sing-box](https://github.com/SagerNet/sing-box). Los módulos experimentales incluyen
[frp](https://github.com/fatedier/frp) y
[Lucky](https://github.com/gdy666/lucky). Consulta los [avisos de terceros][local-link-003] para ver el inventario y las rutas de las licencias originales.

## Licencia

Licencia del proyecto: GPL-3.0 (SPDX: `GPL-3.0-only`); lee la [LICENSE][local-link-004] completa. Los fundamentos históricos de la combinación están en [Decisiones][local-link-005]. Los componentes incluidos, sus licencias originales, las fuentes verificadas de los artefactos y los límites pendientes de revisión jurídica están en [THIRD_PARTY_NOTICES.md][local-link-006].

Este proyecto no está afiliado a sing-box/SagerNet ni a LibreSpeed y no cuenta con su respaldo.

[local-link-001]: CHANGELOG.md
[local-link-002]: DESIGN.md#referencia-de-configuración
[local-link-003]: THIRD_PARTY_NOTICES.md
[local-link-004]: ../../LICENSE
[local-link-005]: LOG.md#decisiones
[local-link-006]: THIRD_PARTY_NOTICES.md
