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
