---
name: project-changelog-es
description: Historial de cambios
metadata:
  version: "2.0.0"
  lang: "es"
---

# Historial de cambios

## Multilingüe

[简体中文](../CHANGELOG.md) | [English](../en/CHANGELOG.md) | **Español**

## Documentación

- Descripción general del proyecto: [README](README.md)

- Justificación del diseño: [DESIGN](DESIGN.md)

- Estado del proyecto: [LOG](LOG.md)
- Registros históricos: [HISTORY](HISTORY.md)
- Historial de cambios: [CHANGELOG](CHANGELOG.md)

- Avisos de terceros: [THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES.md)

## Historial de cambios

### v6.0.0 — 2026-11-11

Añade un módulo de reenvío de dominios (con Caddy incluido) que sustituye al módulo Lucky, eliminado: HTTPS por subdominio hacia un puerto local o la consola, con certificados automáticos y registros DNS mantenidos en Cloudflare. La consola también puede obtener un certificado de confianza para la IP del servidor. El comando de actualización no cambia y se conservan la configuración y los datos; el módulo Lucky se elimina durante la actualización.

#### Añadido

- **Reenvío de dominios (módulo `caddy`).** En la página Dominios se añade un subdominio (eligiendo entre los dominios principales que gestiona el token de Cloudflare) y se reenvía a un puerto local (por ejemplo, un puerto de frps) o a la propia consola. El Caddy 2.11.9 incluido obtiene y renueva certificados de Let's Encrypt, por lo que ocupa los puertos 80/443 y la página pública de alcance se desactiva mientras funciona. Los registros A/AAAA (solo DNS) se crean y eliminan con la API de Cloudflare; la IP pública se comprueba cada 5 minutos y los registros la siguen.
- **Gestión de sitios.** Cada sitio se puede desactivar y editar; el backend puede usar HTTPS (sin comprobar su certificado, para NAS o routers autofirmados) y puede recibir como Host el nombre original o su propia dirección. Hasta 8 nombres adicionales por sitio, límites por dirección o red de origen y una contraseña de acceso (solo se guarda el hash). Cada sitio tiene un registro de acceso (últimas 200 peticiones).
- **Historial y avisos.** Se registran los cambios de sitios, activaciones, registros DNS y cambios de IP pública. Un cambio de IP, un fallo de DNS o un certificado a punto de caducar sin renovar se notifica con la configuración de Bark de la consola, como mucho una vez al día por evento.
- **Consola en un dominio.** Un sitio puede apuntar a "esta consola": Caddy entrega el certificado de cliente a la consola y "exigir certificado de cliente" sigue aplicándose.
- **Certificado HTTPS para el acceso por IP.** Al activarlo en la página Dominios se obtiene un certificado de Let's Encrypt para la IPv4 pública (unos 6 días, Caddy lo renueva) y la dirección actual de la consola, `https://IP:puerto`, pasa a usarlo, de modo que el navegador deja de avisar. Los puertos 80/443 no sirven la consola para la IP sola.

#### Eliminado

- **Módulo Lucky (incompatible).** Las funciones de DDNS, proxy inverso y certificados que se usaban las cubre el reenvío de dominios. La actualización detiene y elimina Lucky tras archivar su configuración en `data/module-backup-lucky-*.tar.gz` del directorio de estado; `lucky` en `VPSSRV_MODULES` se ignora.

#### Corregido

- La comprobación del instalador en línea daba por ausentes los certificados de CA guardados en directorios con hash.

#### Verificación

Instalado y actualizado desde una versión anterior en contenedores de sistema Ubuntu 24.04 desechables, probando activación, edición, backends HTTPS, la elección de Host, límites de dirección, contraseñas, nombres adicionales, registros de acceso y la deduplicación de avisos. En un servidor de pruebas público con una zona real de Cloudflare y Let's Encrypt: certificados para subdominios y nombres adicionales, contraseñas, límites de dirección, activación, limpieza de DNS al eliminar, la consola en un dominio y la emisión del certificado de IP y su adopción por la consola (una reemisión forzada se adoptó sola). Sin verificar: la renovación natural del certificado de IP de 6 días, el envío real por Bark (solo simulado), los registros IPv6 y la apertura de 80/443 en ufw/firewalld. No se admiten certificados comodín ni la exportación de certificados; el DNS es solo Cloudflare.

### v5.8.0 — 2026-11-08

FRPS obtiene la misma contabilidad y límites de tráfico que los nodos Singbox; los certificados de cliente se firman ahora con un OpenSSL incluido, lo que corrige autoridades de certificación inválidas en equipos con un openssl antiguo. El comando de actualización no cambia y se conservan la configuración y los datos.

#### Añadido

- **Contabilidad y límites de tráfico de FRPS.** Igual que un nodo Singbox: uso de subida/bajada, cuota de tráfico (limitar a 1 Mbps o bloquear al superarla), límites de velocidad de subida y bajada, vigencia y ciclo de reinicio; la cuota cuenta `(subida + bajada) × 2`. FRPS se mide en su bindPort, por el que pasan todos los túneles frpc. El uso aparece en la página de FRPS y se edita en el diálogo "Límites". Un servicio nuevo, `vps-server-frps-meter`, hace la medición y detiene FRPS si la contabilidad falla. Por ello el módulo FRPS necesita nftables: el paquete sin conexión lo incluye y, para el paquete en línea, el instalador lo instala con apt si falta.
- **Versiones mínimas de dependencias.** Antes de cambiar cualquier servicio, el instalador comprueba Bash 4.1, systemd 240, SQLite 3.24 y la biblioteca OpenSSL 1.1.1 que usa Python, `/usr/bin/python3` 3.9+ y comandos básicos (flock, sha256sum, base64, getent, install, mktemp, systemd-run); el paquete en línea también comprueba los certificados CA. Si algo no se cumple, la instalación se detiene e indica qué falta.
- `python3 /root/apps/vps-server/src/web/client_cert.py check` muestra el openssl usado para firmar certificados y el resultado de la autoprueba de la autoridad de certificación.

#### Mejorado

- Los certificados de cliente los firma el OpenSSL 3.5.9 LTS estático incluido en el paquete, con una configuración mínima propia, así que la versión de openssl y el openssl.cnf del equipo ya no influyen; el instalador ya no instala openssl con apt.
- Un `ip`/`ss` del equipo sin rutas JSON o sin `-H` cede ante la copia incluida; un iperf3 del equipo solo se usa si no hay copia incluida y debe ser 3.1+.

#### Corregido

- En equipos con OpenSSL 1.1.1k u otras versiones antiguas, la autoridad de certificados de cliente se creaba con Basic Constraints duplicado y fallaba incluso su propia verificación, por lo que el inicio de sesión con certificado no funcionaba. Ahora una autoridad nueva debe pasar una autoprueba de TLS mutuo con la biblioteca TLS del equipo; una autoridad inválida existente se reemplaza la próxima vez que se emite un certificado, sus certificados se marcan como revocados y se desactiva "Exigir certificado de cliente".
- El estado de conexión de FRPC siempre aparecía como desconectado en equipos que solo tienen el `ss` incluido.
- El `sha256sum -c SHA256SUMS` de la instalación sin conexión del README fallaba si solo se descargaba el paquete sin conexión; ahora usa `--ignore-missing`.

#### Verificación

OpenSSL 1.1.1k reprodujo el problema original en local y se confirmó la corrección; las comprobaciones de dependencias y la emisión de certificados pasaron en un contenedor Debian 11 (Python 3.9, libssl 1.1.1w). En un contenedor de sistema Debian 13, el paquete sin conexión instaló web, proxy y frps: todos los servicios funcionaron, la consola se usó por HTTPS, los límites de FRPS se aplicaron en las reglas del kernel, los límites de nodos siguieron funcionando y la desinstalación completa no dejó restos. El operador actualizó un VPS en el sitio con `v5.8.0-test.1` y confirmó la emisión e inicio de sesión con certificado y la contabilidad y cuota de FRPS. No se verificó en un equipo real cuya biblioteca TLS sea OpenSSL 1.1.1k, ni se midió en un equipo real la velocidad del límite de 1 Mbps. Tras cambiar el bindPort de FRPS, el nuevo puerto queda sin medir hasta unos 2 segundos.

### v5.7.0 — 2026-11-08

Más seguridad en el inicio de sesión de la consola. El comando de actualización no cambia y se conservan la configuración y los datos; el instalador menciona 4 variables opcionales nuevas, y si no se definen se usan los valores predeterminados. La nueva configuración está en Configuración > Seguridad.

#### Añadido

- **Interruptor del bloqueo por fallos.** Activado por defecto. Desactivado no bloquea, pero sigue contando los fallos de cada IP y marca la que alcanza el umbral como "umbral alcanzado, sin bloqueo", para comprobar que la detección funciona. Los registros se pueden borrar.
- **Bloqueos crecientes.** Cada nuevo bloqueo de la misma IP en un día dura diez veces más: 30 segundos, 5 minutos, 50 minutos, unas 8 horas, como máximo 24 horas (`VPSSRV_LOGIN_LOCKOUT_MAX_SECONDS`). Un inicio de sesión correcto lo reinicia.
- **Agrupación IPv6 por /64 y límite global.** Las direcciones del mismo /64 cuentan juntas. Si todas las fuentes suman 20 fallos en 60 segundos, las direcciones que nunca iniciaron sesión no pueden usar la contraseña durante 5 minutos (`VPSSRV_LOGIN_GLOBAL_MAX_ATTEMPTS`, `VPSSRV_LOGIN_GLOBAL_LOCKOUT_SECONDS`); las direcciones conocidas, el acceso con certificado y el acceso por IP no se ven afectados.
- **Límite de acceso a la consola.** Desactivado por defecto. Activado, solo las IP o redes de la lista pueden conectarse a la consola; las demás se cortan antes del saludo TLS. No se puede activar ni quitar una entrada de forma que deje fuera la conexión actual. Si queda fuera, ejecute como root `python3 /root/apps/vps-server/src/web/console_access.py disable`; no hace falta reiniciar.
- **Dispositivos conectados.** Muestra los dispositivos con sesión (navegador, sistema, IP, inicio y última actividad) y permite cerrar la sesión de uno o de todos los demás. La sesión termina tras 2 horas sin actividad (`VPSSRV_SESSION_IDLE_SECONDS`); escribir en el terminal cuenta como actividad.
- **Registro de seguridad y avisos de Bark.** Registra inicios de sesión, bloqueos, aperturas del terminal root y cambios de seguridad, y muestra los 50 más recientes. Con una clave de Bark, los inicios de sesión desde una dirección nueva y los bloqueos se envían al móvil; la clave nunca se muestra en la página.

#### Mejorado

- Las respuestas de la consola llevan una Content-Security-Policy que solo permite los scripts propios y prohíben que otros sitios la incrusten. El antiguo script en línea pasó a un archivo propio.

#### Corregido

- Detrás de un proxy inverso (`VPSSRV_TRUST_PROXY=1`), la dirección del cliente es ahora la última entrada de `X-Forwarded-For` añadida por el proxy, así que un encabezado falsificado ya no afecta al límite de intentos, los registros ni el límite de acceso.
- La página de inicio de sesión deja espacio entre el botón de acceso con certificado y la etiqueta de la contraseña.
- Los comandos de extracción del README y la extracción interna del instalador indican el filtro `tar` de forma explícita, lo que elimina el `DeprecationWarning` de Python 3.12 y 3.13.

#### Verificación

Las pruebas locales cubren bloqueos, el interruptor, la agrupación IPv6, la pausa global, el límite de acceso, los dispositivos, el registro de seguridad y los avisos de Bark con un servidor simulado; 15 páginas no muestran bloqueos de CSP en un navegador sin interfaz. El operador instaló por red `v5.7.0-test.1` y `v5.7.0-test.2` en un equipo de prueba de la LAN y confirmó el recuento de fallos, el marcado con el bloqueo desactivado, el bloqueo activado y el nuevo diseño. Aún no se ha probado con una cuenta real de Bark ni detrás de un proxy inverso real.

### v5.6.3 — 2026-11-06

**Se recomienda actualizar a todos, sobre todo en equipos instalados con el paquete offline.** El comando de actualización no cambia y se conservan la configuración y los datos. Ejecute la actualización por SSH, no en el terminal integrado de la consola.

#### Corregido

- pcre2 del entorno de sistema incluido en el paquete offline (nft, iptables, `ip`, `ss`) se actualiza a la versión de seguridad de Debian 10.46-1~deb13u3, que corrige una reserva excesiva de pila JIT (GHSA-r9hj-j2rw-4q3m). Antes los paquetes se tomaban solo del archivo principal de Debian y faltaba el de seguridad; los otros 31 paquetes se revisaron uno a uno y coinciden con Debian 13 actual. Las actualizaciones sustituyen el entorno instalado.
- Al actualizar desde el terminal integrado de la consola solo aparecía `Terminated`, sin indicar si la instalación seguía en marcha. Ahora avisa de antemano de que el terminal se desconecta cuando la consola se reinicia mientras la instalación continúa en segundo plano, e indica el comando para ver el resultado; si la vista del progreso se interrumpe, también lo explica.
- Los reinicios de la consola ya no se bloquean 90 segundos: los terminales abiertos se cuelgan correctamente al apagar.

#### Mejorado

- Tras generar un certificado de cliente, la página muestra cuatro pasos: descargar, importar en el almacén de certificados del sistema (con Windows, macOS, Android e iOS explicados por separado, y el almacén propio de Firefox), cerrar y reabrir el navegador por completo, y confirmar que el certificado está en uso antes de activar Exigir certificado de cliente. Los ajustes de seguridad explican las causas habituales cuando hay certificados pero la conexión actual no presentó ninguno.

#### Mantenimiento interno

- Los binarios de terceros como sing-box, frp, Lucky y Tailscale ya no se guardan en el repositorio; la compilación offline los descarga desde direcciones fijadas y verifica cada SHA-256. El contenido de los paquetes no cambia. La instalación desde código descarga estos programas al instalar, como el paquete en línea.

#### Verificación

Verificado en un contenedor Debian 13 desechable: actualizaciones desde v5.6.2 dentro del grupo de control del terminal de la consola y desde un shell normal; nft, iptables, `ip` y `ss` del nuevo entorno funcionan; un paquete offline compilado desde un clon nuevo contiene programas idénticos byte a byte e instaló y ejecutó el módulo de proxy. Los pasos de importación del certificado solo se revisaron como contenido de la página y aún no se probaron en macOS, Android ni iOS.

### v5.6.2 — 2026-11-06

**Se recomienda encarecidamente actualizar, sobre todo en equipos con el módulo Tailscale.** El comando de actualización no cambia y se conservan la configuración y los datos.

#### Cambiado

- Componentes incluidos actualizados: Tailscale 1.102.4 → 1.104.5, sing-box 1.13.14 → 1.13.21, frp (FRPS, FRPC) 0.71.0 → 0.72.0. Los tres coinciden con las sumas publicadas por los proyectos originales.
  - Tailscale 1.104.4 corrige los boletines de seguridad TS-2026-014 a 017 (Tailscale SSH y serve). Este proyecto no activa ninguna de las dos funciones, así que el uso predeterminado no se ve afectado; los equipos donde se activó Tailscale SSH manualmente deben actualizar cuanto antes.
  - frp 0.72.0 corrige la pérdida de configuración de frpc al reconectar, un bucle de CPU tras cerrar la sesión y una condición de carrera que podía bloquear el proceso.
- Las actualizaciones sustituyen ahora el cliente FRPC anterior instalado por este proyecto (`/usr/local/bin/frpc`) y reinician las instancias en ejecución; un frpc colocado o modificado por el usuario no se toca. La desinstalación sigue reconociendo el cliente anterior.

### v5.6.1 — 2026-11-06

**Se recomienda encarecidamente actualizar.** Esta versión solo actualiza una dependencia relacionada con la seguridad; los pasos de actualización no cambian y la configuración y los datos no se ven afectados.

#### Corregido

- vue-i18n del frontend de la consola pasa de 11.4.13 a 11.4.18 y corrige dos avisos de cross-site scripting (XSS) (GHSA-8rc2-428q-7ww3, GHSA-83rm-6c8r-g728). El análisis del código actual no encontró una vía explotable, porque la consola no activa `escapeParameter` ni muestra traducciones como HTML; la actualización evita dejar en los sistemas instalados una dependencia con avisos abiertos.

### v5.6.0 — 2026-11-06

#### Añadido

- Inicio de sesión con certificado de cliente. Configuración > Seguridad > Certificados de cliente emite un certificado `.p12` por dispositivo (la contraseña de importación se muestra una sola vez); una vez importado en el sistema, el navegador inicia sesión con él en lugar de la contraseña. Los certificados se revocan uno a uno y el servidor nunca guarda la clave privada de un dispositivo. Con "Exigir certificado de cliente" activado, un dispositivo sin certificado válido solo ve una página de bloqueo (el acceso por IP sin contraseña también necesita certificado), la contraseña solo sirve para volver a verificar el terminal root y la configuración de seguridad, y las suscripciones de Clash siguen funcionando. No se puede activar si la conexión actual no presenta un certificado, y mientras se exige no se puede revocar el certificado en uso; si se pierde un certificado, root ejecuta `python3 /root/apps/vps-server/src/web/client_cert.py disable` para recuperar el acceso con contraseña. Se verificaron en Chrome para Windows la emisión, la importación, el inicio de sesión con certificado y la activación del requisito.

- Si el equipo no tiene un nftables funcional, instalar Singbox desde el instalador o desde una tarea de módulo de la consola lo instala primero con apt, sin pedir un comando manual; solo se detiene con un motivo si no hay apt o la instalación falla. Las tarjetas de módulos no instalados de la consola indican que se instalará automáticamente.

#### Cambiado

- La consola solo se sirve por HTTPS. `VPSSRV_CONSOLE_TLS=0` ya no tiene efecto y una instalación que funcionaba por HTTP pasa a HTTPS al actualizar, con el mismo puerto. El instalador instala `openssl` con apt si falta, para emitir certificados.

### v5.5.1 — 2026-10-23

#### Corregido

- El paquete sin conexión ya no anuncia una descarga durante la instalación: si los componentes ya están en el paquete no se descarga ni se avisa, y el aviso aparece solo cuando de verdad hay que descargar.

### v5.5.0 — 2026-10-23

#### Añadido

- Cada versión publica dos paquetes. El paquete sin conexión incluye todos los programas de terceros y herramientas del sistema; el destino no necesita red, curl, Git, tar ni gzip, solo Python 3.9+. El paquete en línea pesa unos 4 MB: el instalador descarga Singbox, Lucky, FRP y Tailscale para los módulos elegidos, verifica cada uno con SHA-256 e instala con apt los iptables, iproute2 y nftables que falten. Al añadir más tarde el módulo FRPC o Tailscale desde la consola, se descargan igual.

- El entorno incluido en el paquete sin conexión ahora trae iproute2 (`ss`, `ip`) y sus bibliotecas. Si el equipo no tiene esos comandos se usan los incluidos y ya no aparece la advertencia de `ss` o `ip` ausentes.

- La pregunta de idioma al inicio de la instalación continúa con el valor predeterminado tras 5 segundos sin respuesta, así que las instalaciones desatendidas terminan solas. `VPSSRV_PROMPT_TIMEOUT` cambia los segundos; `0` espera indefinidamente.

#### Cambiado

- La instalación ya no depende de curl, tar ni gzip: el comando de instalación en una línea, la extracción de los entornos de Tailscale y nftables y las comprobaciones del equipo usan tarfile y urllib de Python. Las imágenes mínimas no necesitan instalar esos comandos antes.

- El paquete sin conexión pasó de unos 98 MB a unos 167 MB porque incluye iproute2 y su código fuente.

- El separador del título de la pestaña del navegador cambió del guion largo `—` al guion corto `-`.

- El script de compilación reintenta cuando falla la descarga de paquetes Debian.

### v5.4.0 — 2026-10-21

#### Añadido

- El paquete completo incluye nftables 1.1.3 e iptables 1.8.11 de Debian 13 junto con glibc, iniciados por el cargador incluido. En equipos Debian 11+ y Ubuntu 20.04+ sin nftables ni iptables, o sin conexión, la contabilidad de tráfico de nodos, los límites de velocidad y el reenvío de puertos siguen funcionando. Se sigue prefiriendo una versión del equipo que pueda leer las reglas; las instalaciones solo de Web también reciben este entorno.

- Se comprueban los requisitos del equipo antes de instalar un módulo: Singbox necesita nftables funcional y Tailscale necesita `/dev/net/tun` y que no haya otro tailscaled en ejecución. El instalador, las tareas de instalación de la consola y las tarjetas y páginas de instalación de módulos no instalados comparten estas comprobaciones; si falta alguna, la instalación se detiene antes de cambiar nada y muestra el motivo y la solución en lugar de un simple "error".

- En la primera instalación, el comando queda en primer plano siguiendo la tarea en segundo plano y muestra solo los pasos clave y, al final, la dirección de la consola y la contraseña inicial; si falla, muestra el motivo y algunas líneas relacionadas del registro. Ctrl-C o una desconexión SSH solo detienen la vista; la instalación continúa.

- Las páginas de funciones de un módulo ausente permiten instalarlo directamente y muestran el progreso en la misma página.

- Un guardado de ajustes fallido muestra un toast durante 8 segundos y la página ya no repite el mismo error.

#### Cambiado

- Las instalaciones nuevas sirven la consola por HTTPS con un certificado autofirmado y las cookies de sesión llevan `Secure`; las actualizaciones conservan el ajuste anterior.

- Instalar Singbox, Lucky o Tailscale desde la consola instala solo ese módulo; Web y los demás módulos siguen funcionando.

- Antes de detener cualquier servicio, el instalador comprueba la versión de Python (se detiene por debajo de 3.9) e iptables, `ss` e `ip` (avisa si faltan e indica las funciones afectadas).

- Los errores de la contabilidad de nodos incluyen ahora el mensaje de error propio de nft.

#### Corregido

- En equipos Debian 13 sin nftables del sistema, la contabilidad de nodos se reiniciaba en bucle y detenía Singbox: el antiguo nft 0.9.8 incluido no puede leer reglas escritas por iptables-nft reciente, y la verificación previa solo ejecutaba `nft --version`, por lo que no lo detectó. La verificación previa y las comprobaciones en ejecución leen ahora realmente el conjunto de reglas.

- Los formularios de reenvío de puertos e iperf3 no tenían tokens CSRF, por lo que una página en otro puerto del mismo equipo podía enviarlos.

- Las conexiones inactivas que abren los navegadores por adelantado podían hacer que la consola HTTPS y la página pública dejaran de responder: los handshakes TLS se ejecutan ahora en el hilo de trabajo de cada conexión con un límite de 10 segundos.

- Cambiar el puerto de la consola reiniciaba Web manteniendo un bloqueo, por lo que el nuevo proceso agotaba el tiempo al liberar un registro de puerto iperf3 pendiente y fallaba; un fallo al liberar registros pendientes ya no impide que Web se inicie.

- Instalar Lucky desde la consola detenía Singbox; tras desinstalar Lucky su página ya no ofrecía el botón de instalación.

- Una primera instalación fallida de Tailscale dejaba su archivo de unidad y sus binarios, y la reversión podía no liberar registros de puertos.

- El estado de la página pública en el resumen de instalación no coincidía con los interruptores de la consola; las instalaciones de FRPS/Lucky fallaban y se revertían ante una regla de cortafuegos que ya no existía; el archivo de configuración del proxy pasa a 0600 y BBR usa su propio archivo sysctl, que la desinstalación completa elimina.

- La página del terminal y las páginas de FRPS y FRPC no instalados usaban el icono de pestaña de inicio.

### v5.3.1 — 2026-10-07

#### Corregido

- Instalar con un `VPSSRV_MODULES` más corto (como la instalación rápida del README) eliminaba módulos instalados del registro y detenía sing-box por la dependencia del medidor de nodos: una lista explícita ahora solo añade módulos y los módulos que siguen en disco se vuelven a contar.

- Un proceso ajeno en un puerto de la página pública abortaba todas las instalaciones y tareas de módulos de una instalación existente; ahora es una advertencia. Si falta el paquete del frontend, la instalación se detiene antes de escribir nada, en lugar de dejar un directorio de estado parcial que bloqueaba instalaciones posteriores.

- Desinstalar Singbox eliminaba todos los nodos: ahora conserva la configuración de sing-box y el inventario de nodos y solo libera el servicio, las reglas del cortafuegos y los registros de puertos. Al reinstalar se registran de nuevo los puertos de los nodos conservados (falla limpiamente si alguno está en uso) y se reabren sus reglas. La confirmación de desinstalación ahora indica que la configuración se conserva.

- Reinstalar Lucky fallaba con "Address already in use" porque las conexiones recién cerradas por la consola estaban en TIME_WAIT: los scripts de instalación de Lucky y FRPS y las comprobaciones de puertos de nodos, FRP e iperf3 ahora sondean con `SO_REUSEADDR` como los servidores.

- Desinstalar FRPC detenía todas las instancias y reinstalar no las recuperaba: la desinstalación ahora recuerda qué instancias estaban activas y la reinstalación las activa de nuevo, salvo que todo el grupo FRPC esté desactivado.

### v5.3.0 — 2026-10-07

#### Añadido

- Componentes de interfaz compartidos: la cabecera y el nuevo pie de página (perfil de GitHub, repositorio del proyecto) se desplazan elemento por elemento al cambiar el tamaño de la ventana; la navegación de secciones de ajustes sigue el desplazamiento con suavidad y pasa a una barra superior en pantallas estrechas; el icono de la pestaña sigue el color del tema y el modo claro/oscuro; Apariencia incorpora "Seguir el sistema"; la insignia de la etiqueta del servidor enlaza con el panel.

- El código QR de Clash se abre desde un botón en un diálogo; las confirmaciones al desinstalar, vaciar el historial de registros, eliminar un proxy y borrar visitantes usan el diálogo propio de la consola en lugar del aviso del navegador.

#### Cambiado

- El frontend Web usa ahora la plantilla compartida (Vue 3, Vite, TypeScript, Tailwind CSS): tokens de diseño unificados, ocho colores de tema y diseño adaptable, con el contenido de la página tan ancho como la cabecera. El frontend se compila en `web/` y el paquete completo incluye el resultado; la instalación desde código debe ejecutar antes `npm ci && npm run check` en `web/` (Node.js 24).

- La esquina superior izquierda de la cabecera muestra solo el nombre del proyecto, sin el logotipo (excepción del proyecto registrada en `doc/LOG.md`).

- La página pública (80/443) devuelve una sola línea de texto plano, "El servidor ve tu dirección IP".

- Al recargar, el diseño de reserva generado por el servidor permanece oculto hasta que la cabecera compartida y los menús desplegables con estilo están listos, por lo que ya no parpadean el diseño antiguo ni los menús nativos.

- Se reorganizaron las páginas de iPerf 3, Singbox, FRPS, FRPC, Lucky, Tailscale y Terminal: título de iPerf 3 con tarjetas Servidor y Cliente, contadores de Singbox alineados a la izquierda, título de instancias de FRPC y botón de nueva instancia en la misma fila, y un terminal más grande con fuente más pequeña. La página de administración de Lucky y las tarjetas HTTP y HTTPS del inicio se abren en una pestaña nueva. El botón de conexión de Tailscale pasa a la misma fila, la versión muestra solo el número de publicación y las listas de rutas y nodos de salida ya no tienen la entrada "Borrar".

- Los directorios de herramientas usan nombres con guiones (por ejemplo `tools/build-offline`), se añadió la comprobación estática compartida `tools/check-project` y la CI fija sus Actions; los comandos de instalación no cambian.

#### Corregido

- Al instalar o conmutar iperf3, el reinicio de Web coincidía con la carga de la página de estado y esta se quedaba en el estado anterior.

- El instalador abortaba durante una actualización porque los sockets TIME_WAIT de conexiones recién cerradas se tomaban por puertos 80/443 en uso.

- Fallaban los clics repetidos en "Conectar" de Tailscale: solo se ejecuta una conexión a la vez, se espera la dirección de inicio de sesión y el botón se desactiva tras el clic (Tailscale funciona en el equipo real, confirmado por el operador).

- Franja negra al pie del terminal, tarjeta vacía en las páginas de módulos cerrados, destino erróneo del control de retroceso en el registro detallado e iconos de página duplicados.

### v5.2.3 — 2026-10-05

#### Cambios

- Se reescribió la documentación conforme a las normas actuales, en chino simplificado, inglés y español.

- Se simplificó la instalación rápida a un comando que instala solo Web por defecto, y se añadieron pasos sin conexión bajo la instalación normal.

- Se añadieron 16 capturas reales al README, agrupadas en secciones desplegables con direcciones y credenciales ocultas.

### v5.2.2 — 2026-10-05

#### Cambiado

- La instalación continúa en una tarea systemd independiente tras elegir el idioma, con registro y código de salida, incluso al desconectar.

#### Corregido

- Unifica fuentes y controles de Configuración, iperf3, Singbox, FRPC y Tailscale; corrige desplegables, pantallas estrechas y filtros. Añade acceso a registros detallados junto al historial de inicio.

- Los editores cargan valores actuales; editar/eliminar comparten fila y los botones de eliminar tienen fondo rojo y respuesta visible. FRPC muestra IP del servidor y destino con visibilidad sincronizada; FRPS oculta direcciones por defecto.

- Guardar/renombrar FRPC devuelve una espera y reintenta el resultado tras reiniciar el túnel, evitando respuestas vacías pese al éxito. Configuraciones inválidas conservan/restauran valores y se eliminan credenciales antes de ejecutar.

- Tailscale confirma la salida con diálogo y usa selección única para rutas/salida; corrige textos largos, formulario sin sesión y controles de clave.

### v5.2.1 — 2026-10-05

#### Corregido

- Incluye y verifica Tailscale 1.102.4 en código, conserva recursos al instalar solo Web e informa si falta el archivo.

- La eliminación completa limpia ajustes/tareas Lucky y restos FRPS/proxy; conserva el modo de retención. Si falla el cortafuegos, detiene el borrado y guarda pertenencia.

### v5.2.0 — 2026-10-05

#### Añadido

- Añade terminal root con verificación, módulo Tailscale sin conexión, registros detallados y limpieza de visitantes; incluye entorno nftables y fuentes Debian correspondientes.

#### Cambiado

- Mueve el estado a `/var/lib/vps-server` y lo conserva en reinstalaciones del mismo esquema; no migra automáticamente v5.1.0 o anteriores. Unifica AnyTLS en Singbox, mueve módulos a Configuración y cuenta `(subida + bajada) × 2`.

#### Corregido

- Corrige edición FRPS sin registro de puerto, nodos, sincronización Lucky, tamaño/desplazamiento del terminal y retorno tras verificar. Prefiere nft operativo y registra puertos mediante auxiliares.

### v5.1.0 — 2026-10-04

#### Añadido

- Incluye artefactos FRPC, FRPS e iperf3 x86-64 Linux con sumas fijas.

#### Cambiado

- Limita idiomas a chino simplificado, inglés y español, elimina COMMITS.md, usa x86-64 Linux y solo edita nodos gestionados. La eliminación limpia instancias/plantillas/puertos FRPC; el modo de retención conserva configuraciones.

#### Corregido

- Soporta contraseñas no ASCII, reconstruye cuotas al reiniciar ciclos, revierte reenvíos parciales, unifica puertos/versión y corrige estado FRPC e identificación de versiones de prueba.

### v5.0.0 — 2026-10-03

#### Añadido

- Añade pruebas iperf3 TCP/UDP temporales, controles públicos independientes y nombre persistente del servidor.

#### Cambiado

- Completa la instalación inicial en terminal con solo Web; separa código/estilos por función y conserva sesiones vigentes al reiniciar.

#### Corregido

- Soporta nombres Unicode FRPC, conserva nodos/estado y corrige mensajes y código de salida al eliminar.

### v4.0.0 — 2026-09-29

#### Añadido

- Añade asistente HTTPS temporal, tareas de módulos y gestión/prueba/edición simple FRPC; separa FRPS/FRPC en inicio.

#### Cambiado

- Añade interruptores independientes, mueve módulos a Configuración, ajusta formularios/temas, elimina animaciones de navegación y cambia reenvío sin reiniciar Web.

#### Corregido

- No exige índice al crear proxies FRPC, detiene recopilación desactivada y conserva campos de nodos al reabrir.

### v3.0.0 — 2026-09-28

#### Añadido

- Añade nodos de cinco protocolos, enlaces/QR, cuotas/límites/reinicios/caducidad y lista de IP privadas sin contraseña.

#### Cambiado

- Unifica diseño, temas/colores y ocultación; separa estado iperf3 de edición y conserva entrada/módulos al actualizar.

### v2.0.0 — 2026-09-27

#### Añadido

- Añade proxy de cuatro protocolos, asistente inicial y módulos experimentales FRPS/Lucky con licencias y sumas.

#### Cambiado

- Mueve instalación a `deploy/`, Web a `src/web/`, dependencias a `third_party/` y metadatos a `config/`; organiza documentos/traducciones en directorios estándar.

### v1.1.2 — 2026-09-21

#### Corregido

- Corrige actualizaciones que terminaban silenciosamente tras una pregunta nueva, antes de copiar o actualizar servicios.

### v1.1.1 — 2026-09-20

#### Corregido

- Corrige comandos README que descargaban v1.0.4 en vez de v1.1.0.

### v1.1.0 — 2026-09-19

#### Añadido

- Añade reenvío TCP/UDP, DNAT/MASQUERADE, reproducción al iniciar y comprobación de conflictos.

### v1.0.4 — 2026-09-12

#### Cambiado

- Muestra direcciones de salida/interfaces y mantiene un marcador sin abortar si falla la detección.

### v1.0.3 — 2026-09-12

#### Corregido

- Reintenta actualización/instalación ante índices obsoletos y sustituye marcadores de repositorio/versión.

### v1.0.2 — 2026-09-12

#### Corregido

- Intenta instalar iperf3 aunque falle actualizar repositorios, reintenta y conserva errores.

### v1.0.1 — 2026-09-12

#### Corregido

- Deja de mostrar comentarios HTML de mantenimiento en el historial.

### v1.0.0 — 2026-09-12

#### Añadido

- Primera versión: pruebas Web con contraseña, visitantes, AnyTLS, accesibilidad pública 80/443, iperf3 temporal, configuración con prefijo y desinstalación con retención.
