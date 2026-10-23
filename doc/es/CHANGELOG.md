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
