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

vps-server ofrece una página para comprobar la accesibilidad de los puertos Web de un VPS Debian/Ubuntu y una consola para medir velocidad y registrar conexiones. También permite instalar módulos proxy, FRP, Lucky y Tailscale. La rama actual prepara un candidato de prueba de v6.0.0; la última versión formal sigue siendo v5.1.0. Consulta el [estado del proyecto](LOG.md).

## Qué hace

- **Página pública de accesibilidad:** Una vez habilitada, muestra en los puertos 80 y 443 la IP del visitante, la hora del servidor y el puerto y protocolo de conexión. El puerto 443 usa un certificado autofirmado. La página no exige inicio de sesión ni muestra la configuración del servidor.
- **Consola privada:** En un puerto independiente y persistente ofrece pruebas de subida y bajada con LibreSpeed y conserva las últimas 1000 conexiones TCP entrantes. Se puede entrar con la contraseña de administrador o una IP privada autorizada.
- **iperf3:** La consola abre una ventana de duración limitada que se cierra al vencer. La salida `--json` de un cliente Linux puede contener `mean_rtt`; un cliente que no pueda leer `TCP_INFO` no mostrará ese campo. Las pruebas UDP permiten ver fluctuación y pérdida.
- **Nodos proxy:** Un solo servicio sing-box ejecuta AnyTLS, VMess, VLESS, Trojan y Shadowsocks. La consola gestiona conexiones, límites de tráfico y velocidad, reinicios periódicos y vencimiento de los nodos. En la red local se puede importar la configuración a Clash Meta.
- **FRP:** La consola gestiona el puerto, el token y el estado del servicio FRPS local, además de las instancias FRPC locales y los proxies TCP/UDP sencillos con autenticación por token. Verifica la configuración al editarla y la restaura si falla; no supervisa clientes de otros dispositivos. FRPC se instala con un recurso incluido en el repositorio.
- **Lucky:** Se puede instalar o retirar junto con los demás módulos. La consola enlaza a la página de administración propia de Lucky; este proyecto no reproduce sus funciones DDNS y de proxy inverso.
- **Tailscale:** Se puede instalar o retirar el cliente Linux incluido en el paquete sin conexión. La consola muestra estado, conectividad, dispositivos y registros, y ofrece ajustes Linux de DNS, rutas de subred, nodo de salida, modo de protección y SSH. Para unirse al Tailnet sigue siendo necesario acceder al servidor de control elegido.

La primera instalación habilita solo la consola Web; los demás módulos se instalan según sea necesario. Consulta los límites funcionales, las reglas de acceso y las restricciones del editor FRP en el [documento de diseño](DESIGN.md).

## Requisitos

- Sistema operativo: Debian 11+ o Ubuntu 20.04+, systemd; ejecutar como root.
- Entorno: Python 3.9+ (basta el `python3` de la distribución, sin dependencias Python adicionales).
- Arquitectura: todo el proyecto requiere Linux x86-64; el instalador rechaza otras plataformas antes de modificar el sistema.
- Si el módulo Web usa los puertos públicos predeterminados, 80 y 443 **DEBEN** estar libres; el instalador rechaza los que ocupen nginx, Apache, Caddy o `vps-webserver`.
- Otras dependencias: la máquina de destino necesita Bash, systemd, Python y las herramientas básicas habituales del sistema. El paquete sin conexión completo incluye FRP, Lucky, Tailscale, sing-box, iperf3 y un entorno privado de nftables; la máquina de destino no necesita Git ni acceso a repositorios de paquetes. La autenticación con el servidor de control, las actualizaciones de servicios y la conexión entre dispositivos sí requieren red.
- Requisitos mínimos: el sistema, entorno y arquitectura indicados. Si se habilita la página pública, sus puertos deben estar libres. Se recomienda reservar al menos 1 GiB para el paquete sin conexión completo, el directorio de extracción y el programa instalado.

## Instalación

### Instalación rápida

Ejecuta como root en la máquina de destino. De forma predeterminada solo se instala la consola Web. La primera instalación interactiva muestra las opciones de idioma 1/2/3 y luego imprime un puerto administrativo y una contraseña aleatorios. Para una instalación sin intervención, usa `VPSSRV_DEFAULT_LANG=en|zh_cn|es`. v6.0.0 formal todavía no se ha publicado; el siguiente comando de código fuente solo sirve para esta rama de prueba. Para disponer de todos los módulos sin conexión, sigue el procedimiento del archivo comprimido indicado abajo.

```bash
git clone --branch release/v6.0.0-test.1 --depth 1 https://github.com/CharlesGool/vps-server.git vps-server && cd vps-server && bash deploy/install.sh
```

### Instalación estándar

```bash
git clone --branch release/v6.0.0-test.1 --depth 1 https://github.com/CharlesGool/vps-server.git vps-server
cd vps-server
cp .env.example .env  # opcional: ajusta los valores siguiendo los comentarios
bash deploy/install.sh
```

`PREFIX` vale `/root/apps/vps-server` de forma predeterminada y solo contiene archivos de programa reemplazables. La contraseña, el puerto de la consola, los certificados, los datos de ejecución, el registro de instalación y `.env` se guardan de forma predeterminada en `/var/lib/vps-server`; en la primera instalación se puede establecer `VPSSRV_STATE_DIR` en el entorno del comando para usar otro directorio externo. `VPSSRV_MODULES=web,iperf3,proxy,frps,lucky,tailscale` permite elegir módulos de servidor; si se omite, solo se instala Web. AnyTLS es un protocolo de `proxy`, sin módulo ni servicio independientes. Después se pueden instalar o retirar módulos opcionales desde Settings → Modules. Las páginas públicas HTTP y HTTPS se habilitan por separado en Home; la consola administrativa usa otro puerto. FRPC se instala por separado cuando se necesita un cliente local.

### Paquete de instalación sin conexión

El paquete de prueba v6.0.0 incluirá el código fuente completo y los recursos Tailscale, nftables y otros necesarios, comprobados previamente. Generar el paquete e instalarlo en destino no exige Git en la máquina de destino. Tras publicar el paquete de prueba, comprueba su SHA-256 y extráelo en un directorio independiente; no sobrescribas directamente el `$PREFIX` instalado. El paquete todavía no se ha publicado: sustituye `<测试包>` por su nombre real en los siguientes comandos.

```bash
mkdir -p /root/vps-server-v6-test
tar -xzf /root/<测试包>.tar.gz -C /root/vps-server-v6-test --strip-components=1
cd /root/vps-server-v6-test
bash deploy/install.sh
```

## Orientaciones

El resumen del instalador muestra la dirección de la consola, la contraseña administrativa y los módulos instalados. Las páginas públicas están desactivadas por defecto; después de habilitarlas en Home, comprueba desde otra máquina la accesibilidad de los puertos 80 y 443 en `http://<ip>/` y `https://<ip>/`. HTTPS usa un certificado autofirmado. Comprueba el servicio con `systemctl status vps-server-web` y entra en la consola para administrar módulos, nodos proxy y FRP.

Para usar iperf3, abre primero una ventana de duración limitada en la consola y luego ejecuta `iperf3 -c <ip> -p 5201 --json` desde otra máquina. Al terminar la ventana, el puerto deja de escuchar. El código fuente no incluye una suite de pruebas automáticas; acepta manualmente los módulos que hayas habilitado. Consulta rutas de servicio, límites y archivos de estado en el [documento de diseño](DESIGN.md).

El límite de tráfico de los nodos proxy cuenta (subida + bajada) × 2. La interfaz muestra la cantidad contabilizada; la falta de datos de medición por sí sola no adelanta la limitación de velocidad. El reinicio mensual se ejecuta el día 1 de cada mes a las 00:00 UTC; los períodos diarios y anuales conservan su cálculo anterior. Las direcciones de interfaz de red de los nodos se ocultan por defecto y se pueden mostrar o copiar. En «Visitantes recientes» se puede borrar el historial tras confirmar; las visitas posteriores y los dispositivos que sigan conectados se registrarán de nuevo. El progreso de instalación y desinstalación de la página Módulos se oculta 30 segundos después de la última salida; el aviso de finalización solo aparece brevemente en la página de la operación actual y no reaparece al actualizar o volver a entrar. «Registros detallados», a la derecha de «Registro de cambios» en la cabecera, muestra el historial de operaciones de módulos y los registros de servicios; la retención de estos últimos depende del journal de systemd de la máquina. Lucky usa su propia página de administración; si la red actual no permite acceder directamente, se puede reenviar el puerto de administración mediante SSH.

### Configuración

Cada variable tiene un valor predeterminado. La primera instalación puede importar `.env` desde el directorio del código fuente; después se conserva en el archivo `.env` de la raíz de estado. Variables principales:

| Variable | Significado | Predeterminado | Obligatoria |
|---|---|---|---|
| `VPSSRV_STATE_DIR` | Raíz de estado persistente definida en el entorno antes de la primera instalación; `.env` no cambia su ubicación | `/var/lib/vps-server` | no |
| `VPSSRV_PUBLIC_HTTP_PORT` | Puerto sin cifrar de la página pública | `80` | no |
| `VPSSRV_PUBLIC_HTTPS_PORT` | Puerto TLS de la página pública | `443` | no |
| `VPSSRV_PUBLIC_ENABLE` | Mostrar la página pública al instalar; después se controlan HTTP y HTTPS por separado desde Home | `0` | no |
| `VPSSRV_CONSOLE_PORT` | Puerto de la consola; `0` genera uno y lo recuerda | `0` | no |
| `VPSSRV_AUTH` | Exigir contraseña en la consola | `1` | no |
| `VPSSRV_IPERF_PORT` | Puerto donde escucha la ventana iperf3 abierta | `5201` | no |
| `VPSSRV_IPERF_MAX_MINUTES` | Duración máxima permitida por la consola | `60` | no |
| `VPSSRV_DEFAULT_LANG` | `en` / `zh_cn` / `es` | `en` | no |

Referencia completa: [Referencia de configuración][local-link-002].

## Actualización

El candidato v6.0.0 establece la disposición `1` del estado persistente. Las versiones v5.1.0 y anteriores **no admiten migración automática**. Si aún quedan datos antiguos, cópialos fuera del directorio de instalación antes de realizar una instalación nueva; los datos ya borrados sin copia no se pueden recuperar. Si el instalador encuentra un servicio anterior pero falta el estado, se detiene antes de modificar los servicios.

Para actualizar posteriormente desde la disposición `1`, obtén el código nuevo en un directorio independiente y ejecuta el instalador con los mismos `PREFIX` y `VPSSRV_STATE_DIR`. Conserva la raíz de estado y las configuraciones de módulos bajo `/etc`; el instalador reutiliza la contraseña, el puerto, los certificados, los datos de ejecución y los módulos registrados sin volver a mostrar la contraseña anterior. Conserva copias del código y los datos antes de actualizar; después comprueba el estado de los servicios, el puerto administrativo, el inicio de sesión y los módulos utilizados. Usa la misma ruta de estado personalizada en las instalaciones posteriores; si quieres cambiarla, traslada y comprueba los datos manualmente.

## Desinstalación

Ejecuta como root desde el directorio del código fuente de instalación y usa los mismos `PREFIX` y `SERVICE_NAME` que al instalar; el resumen muestra el comando exacto:

```bash
KEEP_DATA=1 bash deploy/uninstall.sh  # detener servicios y conservar programa y estado persistente
bash deploy/uninstall.sh              # desinstalación completa y borrado de la raíz de estado predeterminada
```

Ambos modos detienen los servicios gestionados por el proyecto y liberan sus registros de puertos. El modo que conserva datos mantiene el programa, la raíz de estado, la configuración del proxy unificado, la de FRPS y de las instancias FRPC y la identidad de Tailscale. La desinstalación completa elimina estas configuraciones propias del proyecto y sus copias de recuperación. En un servidor que comparta FRPC, comprueba primero a quién pertenecen las instancias. No se borran automáticamente las rutas de datos personalizadas situadas fuera de la raíz de estado. Consulta el alcance detallado de la limpieza en el [documento de diseño](DESIGN.md#desinstalación-completa).

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
