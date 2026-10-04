---
name: project-design-es
description: Arquitectura y restricciones de diseño del proyecto
metadata:
  version: "1.0.0"
  lang: "es"
---

# vps-server — Diseño

## Multilingüe

[简体中文](../DESIGN.md) | [English](../en/DESIGN.md) | **Español**

## Documentación

- Descripción general del proyecto: [README](README.md)

- Justificación del diseño: [DESIGN](DESIGN.md)

- Estado del proyecto: [LOG](LOG.md)
- Registros históricos: [HISTORY](HISTORY.md)
- Historial de cambios: [CHANGELOG](CHANGELOG.md)

- Avisos de terceros: [THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES.md)

## Objetivos de diseño

El instalador actual instala solo Web cuando se omite `VPSSRV_MODULES`.

<a id="vps-design-goals"></a>

**Objetivos implementados en la versión actual (consulta los [límites de aceptación][local-link-001]):**

La versión 2.0.0 también contiene rutas de instalación experimentales para frps y Lucky. Su funcionamiento no se ha aceptado en un servidor real; los objetivos siguientes describen los cuatro módulos documentados anteriormente.

- Instalar en un VPS Debian/Ubuntu nuevo la consola y los módulos de red que se necesiten (el módulo web incluye la página pública y la consola privada):
  1. **Página pública de accesibilidad**: una página deliberadamente mínima en TCP
     **80 y 443**, sin autenticación, para que cualquiera que reciba solo la IP pueda comprobar en un navegador si los puertos web de este servidor son accesibles desde donde esté.
  2. **Consola privada**: panel en un puerto alto aleatorio y persistente con pruebas de subida y bajada desde el navegador y registro de conexiones entrantes recientes. Admite la contraseña de administrador o una IP privada de LAN añadida expresamente.
  3. **Ventana iperf3 bajo demanda**: punto de prueba de ancho de banda y latencia
     **desactivado de forma predeterminada**; el operador abre desde la consola una ventana de duración limitada que se cierra automáticamente al vencer.
  4. **Proxy unificado**: un servicio sing-box ejecuta AnyTLS, VMess, VLESS, Trojan y Shadowsocks.
  5. **Tailscale**: estado, preferencias, lista de dispositivos y registros del cliente Linux local.
- El paquete sin conexión completo incluye los binarios de servicios y el entorno privado de nftables necesario para medir nodos; la instalación en destino no descarga código fuente ni paquetes del sistema.
- Convivir en el mismo servidor con `vps-webserver` y `Anytsl-Serve` sin conflictos de nombres de unidades systemd, prefijos de instalación, prefijos de variables de entorno ni puertos persistentes.

**Objetivos registrados y estado actual:**

- [ ] 2026-10-04 Aceptación de v6 en destino: la migración al proxy unificado debe conservar ID, puertos, credenciales, certificados y estado de medición de los nodos anteriores. El paquete sin conexión completo debe instalarse en Debian/Ubuntu admitidos sin Git ni acceso de red a repositorios. Para unirse al Tailnet sigue siendo necesario acceder al servidor de control.

- [x] 2026-09-19 Tráfico y límite de datos por nodo: los cinco protocolos proxy registran por separado subida y bajada. La limitación anterior a 1 Mbps al alcanzar el máximo y el reinicio mensual o en una fecha indicada se probaron en un servidor real el 2026-09-27. Esta rama añade límites independientes de subida y bajada, la elección entre limitar a 1 Mbps o bloquear al alcanzar el máximo, ciclos periódicos de días, meses o años y una validez opcional que bloquea el uso al expirar. Las nuevas reglas y la migración tienen pruebas automáticas; el host de prueba verificó la interfaz y la migración, pero no el tráfico real en todas las políticas.
- [x] 2026-09-19 La configuración inicial en el navegador estuvo disponible mediante `tools/setup_wizard/setup_wizard.py`; ese flujo se retiró. En v5.0.0 la primera instalación se completa en el terminal y solo instala Web de forma predeterminada.
- [x] 2026-09-22 Proporcionar FRPS / FRPC información de conexión en la consola autenticada. La página reporta el estado local de unidad FRPS, dirección bind, direcciones de interfaz, puerto y auth token; valores sensibles se capturan sólo en Mostrar o Copiar. Una plantilla de conexión FRPC utiliza los valores de servidor instalados y un marcador de lugar reemplazable de dirección servidor. El servidor no tiene visibilidad en FRPC funcionando en otro dispositivo.
- [x] 2026-09-29 Gestione la configuración de FRP local host-local. Un operador firmado puede cambiar el puerto de bind FRPS y señalizar, editar y verificar las instancias locales FRPC, y iniciar o detener esas instancias sin la verificación reciente del administrador-password. La página de instancia revela valores IP guardados y token sólo bajo petición. Un ayudante de raíz transitorio realiza operaciones fijas fuera de la caja de arena del sistema sólo lectura de la unidad Web. Se reserva el cambio de puertos locales de escucha en `~/apps/PORTS.md` antes de iniciarlos, libera asignaciones terminadas, restaura la configuración anterior sobre validación o fallo de servicio, y no modifica instancias FRPC en otros dispositivos. La página Módulos ahora instala una plantilla FRPC binaria y `frpc@.service` separadamente de FRPS; determina la instalación de esos archivos, en lugar de la presencia de una configuración de instancia. Desinstalar detiene las instancias y conserva sus configuraciones.
- El auxiliar de edición de FRPS mantiene el bloqueo del registro de puertos. Si una instalación antigua carece de la entrada del puerto FRPS actual, primero la registra según la configuración existente; rechaza el cambio si ese puerto pertenece a otro servicio. Reserva el puerto nuevo antes de cambiarlo, revierte la reserva si falla el guardado y libera el puerto anterior tras el éxito. Al cambiar solo el token, conserva la entrada del puerto actual.
- [x] 2026-09-29 Presente FRPS y los controles locales FRPC como tarjetas de operador. FRPS utiliza el patrón de edición en línea de la página del nodo y un interruptor de servicio. Cada instancia FRPC tiene un IP de destino enmascarado, indicador de conexión derivado de socket, y una acción de conexión de prueba independiente que hace un FRPC libre de proxy con credenciales guardadas. Su página muestra los campos del servidor y el tipo de cada proxy, IP local, puerto local y puerto remoto; La edición se abre sólo después de que el operador elija Editar, y ahorro de retornos a esa instancia. El editor de campo sólo acepta la configuración TCP/UDP simplificada con token-authenticated que puede representar y deja sin soporte TOML sin cambios. Una tarjeta de destino representa una instancia local de host, y el indicador de conexión inicial requiere un socket establecido propiedad del proceso principal sistema de esa instancia a su servidor y puerto configurados.

FRPC revisión de la tarjeta, 2026-09-29: las cuatro capturas de operador mostraron la vieja plantilla de conexión, hechos enmascarados sin una revelación directa, un panel TOML avanzado, y una tarjeta servidor sin una acción de prueba. Chromium en el `test-d09835d` implementado en 390 y 1440 CSS px comprobó la lista de instancias, enmascarado y revelado hechos del servidor, colapsó y abrió los controles Editar, hechos proxy, estados de conexión y un ahorro de retorno a la misma instancia. Los paneles redundantes están ausentes, ambos revelan carga bajo petición, los cuatro hechos proxy son visibles, y ninguno mirador tiene flujo horizontal. La interfaz conserva el estilo de tarjeta existente del proyecto; real hardware móvil y tráfico proxy estaban fuera de esta revisión del navegador.
- [x] 2026-09-29 Se retiró la configuración inicial en el navegador. Settings → Modules instala funciones ausentes desde el paquete de origen de la versión instalada y habilita o deshabilita las ya instaladas. Una tarea systemd separada ejecuta el instalador fuera del servicio Web; la selección explícita conserva las credenciales existentes. Los interruptores públicos HTTP y HTTPS afectan a sus respectivos escuchas y mantienen accesible la consola. Las pruebas del antiguo asistente se conservan en el historial.

El escucha retirado de configuración inicial reservaba su puerto aleatorio en `~/apps/PORTS.md` antes de atender peticiones y liberaba la reserva al cerrarse; la contraseña temporal admitía una sola sesión de navegador. La página Modules actual está en los ajustes ordinarios y usa la sesión iniciada. Solo envía nombres y acciones de módulo fijos a una tarea systemd privilegiada separada. La tarea registra el progreso fuera del servicio Web y permite reiniciar Web durante la instalación. Deshabilitar un módulo proxy conserva nodos y credenciales; los controles de nodos no arrancan unidades deshabilitadas. Los interruptores iperf3 y de las páginas públicas reinician Web para aplicar cambios de escucha; la consola permanece accesible.
- [ ] Delimitar la solicitud más amplia de funciones de `gdy666/lucky` registrada en la instantánea de estado del 2026-09-22. El árbol actual ya ofrece una ruta de instalación de Lucky; el operador aclaró el 2026-10-03 que los controles futuros solo deben reproducir las funciones necesarias, sin integrar toda la interfaz de Lucky. Falta concretar esas funciones y sus criterios de aceptación.
- [x] Validación de los controles de nodos en un servidor real completada: los números visibles quedan consecutivos tras borrar nodos y vuelven a empezar en 1 cuando no queda ninguno, mientras que los UUID ocultos conservan la identidad; se pueden editar nombre, puerto, credencial y SNI TLS; Shadowsocks muestra SNI como no aplicable; el restablecimiento aleatorio de puerto y credencial conserva el SNI. Cada nodo puede desactivarse sin borrar su configuración ni sus registros de tráfico y reactivarse en el mismo puerto. Los controles superaron las pruebas en un servidor real el 2026-09-27.
- [x] La interfaz Web comparte un sistema visual accesible para la consola y la página pública. Mantiene espacios y controles comunes, fuentes e iconos incluidos, foco visible y diseños adaptables. Los ajustes ordinarios ofrecen ocho colores de acento persistentes y modos claro y oscuro independientes; cambiar de modo conserva el color.

La página de acceso a la consola muestra el mismo nombre del proyecto y el enlace a Home que el resto de la interfaz. En el pie de su tarjeta, la versión en ejecución enlaza con el Registro de cambios y se puede elegir idioma antes de iniciar sesión. Los controles del tema permanecen en Ajustes ordinarios. Cada campo de contraseña editable comienza oculto y tiene su propio control accesible para mostrarla u ocultarla; cambiar la visibilidad conserva el valor y el foco y nunca envía el formulario.
La cabecera de las páginas autenticadas contiene Home, Changelog, Settings y Sign out; los enlaces a las funciones están en Dashboard. Las páginas secundarias incluyen un enlace para volver. Ajustes ordinarios y Ajustes de seguridad usan navegación lateral en escritorio y una fila desplazable en pantallas estrechas. Elegir el grupo Seguridad en Ajustes ordinarios lleva a su tarjeta de acceso; abrir la página protegida exige una acción separada y la verificación del administrador. Cada página tiene un icono de pestaña relacionado con su función, pero distinto.
Según lo solicitado el 2026-09-29, los cambios de página usan la navegación normal del navegador, sin animación de rutas ni ajuste de movimiento entre páginas. Al cambiar el tamaño de la ventana, los controles visibles se detienen brevemente y luego pasan a su nueva posición. Las páginas protegidas se ocultan antes de entrar en el historial y exigen una nueva solicitud al servidor al volver; tras cerrar sesión no se puede mostrar una página de consola almacenada en caché.
En las compilaciones de desarrollo, el Registro de cambios Web muestra las notas actuales de la compilación de prueba tomadas de `LOG.md` por encima del historial de versiones etiquetadas. La versión en ejecución procede del archivo `VERSION` desplegado; el historial de versiones traducido conserva su idioma y las notas de prueba se muestran en inglés si no hay traducción.

La preocupación por el bloqueo SQLite compartido es una [cuestión de medición conocida y sin resolver][local-link-002], no una orden de modificar la arquitectura. El trabajo histórico completado y las pruebas registradas están en [LOG][local-link-003].

**Fuera de alcance**

- **No sustituye a `vps-webserver` ni a `Anytsl-Serve`.** Ambos siguen manteniéndose y publicándose independientemente. vps-server incluye su código en vez de importarlo o reemplazarlos; consulta [Decisiones][local-link-004] para conocer el riesgo de divergencia aceptado y cómo se mitiga.
- **Ni ACME, ni Let's Encrypt, ni nombres de dominio.** TLS en 443 usa un certificado autofirmado. La página pública debe responder «¿se puede acceder a esta IP?», algo que ya demuestra una advertencia del navegador. La renovación del certificado y depender de un dominio no aportan nada para ese fin.
- **No mantener iperf3 siempre activo.** Un `iperf3 -s` público sin autenticación permite a cualquier desconocido saturar el enlace de salida durante el tiempo que desee.
- **La página pública no revela información sobre el servidor.** Ni nombre, ni versión del kernel, ni tiempo de actividad, ni inventario de servicios, ni lista de puertos, ni parámetros de anytls. Solo informa de que se ha podido acceder, la IP de origen detectada, la hora del servidor y el puerto/protocolo de entrada.
- **Ni proxy inverso, ni nginx, ni contenedores.** El proceso Python termina TLS por sí mismo, como ya hace `vps-webserver`.
- **Ni selector de servidores para medir la velocidad.** Un solo servidor: este.

## Arquitectura

Web, el proxy unificado y el servicio Tailscale opcional se ejecutan por separado; AnyTLS es un protocolo de entrada del proxy unificado. El servicio Web también inicia un proceso hijo iperf3 transitorio. La consola y la página pública usan escuchas distintas en un único proceso Python y comparten estado en memoria. Solo el tráfico de clientes configurados llega a esos servicios.

```
                       ┌──────────────────────── vps-server-web.service ───────┐
  anyone, no auth      │                                                       │
  :80  ──────────────► │  public listener (HTTP)  ──┐                          │
  :443 ──────────────► │  public listener (HTTPS) ──┤                          │
                       │                            ├─► ProbeHandler           │
                       │                            │   (reachability page)    │
                       │                            │                          │
  operator, password   │                            │                          │
  :<random> ─────────► │  console listener  ───────►│   ConsoleHandler         │
                       │                            │   ├─ LibreSpeed endpoints│
                       │                            │   ├─ visitor log         │
                       │                            │   └─ iperf3 window ctl ──┼──┐
                       │                            │                          │  │
                       │  connection poller ◄───────┴── /proc/net/tcp[6]       │  │
                       │  (all ports, not just HTTP)                           │  │
                       └───────────────────────────────────────────────────────┘  │
                                                                                   │
  tester with iperf3      :5201 ◄────────────── iperf3 -s  (child process, ────────┘
  client                                         killed when window expires)

                       ┌─── vps-server-proxy.service ────────┐
  proxy client ──────► │  one sing-box process, five protocols  │
  :<node port>        │  AnyTLS is an inbound protocol          │
                       └────────────────────────────────────────┘
```

El módulo proxy tiene una sola configuración y un solo servicio sing-box. La medición de nodos la gestiona el servicio compartido `vps-server-node-meter.service`. El servicio AnyTLS anterior se retira después de completar una migración con copia de seguridad.

### Módulos funcionales

`src/web/app.py` configura el proceso, los límites de autenticación, los escuchas y los nombres compatibles con llamadas anteriores. `ConsoleHandler` combina los mixins de `src/web/features/`; cada módulo contiene sus rutas, páginas y acciones. Las funciones de servicio reciben `context`; el punto de entrada pasa su propio módulo como contexto para conservar los puntos de sustitución de pruebas y las importaciones públicas de Python. Otro proyecto debe aportar los ajustes, funciones, objetos de la biblioteca estándar y auxiliares HTTP que use la función elegida. Los módulos funcionales no importan el punto de entrada de esta aplicación.

| Función | Módulo del servidor | Fuente de interfaz |
| --- | --- | --- |
| Acceso e inicio de sesión | `features/auth.py` | `src/web/static/password-fields.js`, `src/web/static/styles/login.css` |
| Ajustes | `features/settings.py` | `src/web/static/access-settings.js`, `src/web/static/settings-sections.js`, `src/web/static/styles/settings.css` |
| Inicio y gestión de módulos | `features/modules.py` | `src/web/static/module-controls.js`, `src/web/static/module-status.js`, `src/web/static/styles/dashboard.css`, `src/web/static/styles/modules.css` |
| Prueba de velocidad en navegador | `features/speedtest.py` | `src/web/static/speedtest-ui.js`, `src/web/static/styles/speedtest.css` |
| Ventana iperf3 y prueba remota | `features/iperf.py`, `features/iperf_client.py` | `src/web/static/iperf-countdown.js`, `src/web/static/styles/iperf.css` |
| FRPS y FRPC | `features/frp.py` | `src/web/static/frp-editor.js`, `src/web/static/styles/frp.css` |
| Nodos proxy y AnyTLS | `features/proxy.py`, `features/proxy_service.py` | `src/web/static/node-controls.js`, `src/web/static/private-values.js`, `src/web/static/styles/proxy.css`, `src/web/static/styles/nodes.css` |
| Reenvío de puertos | `features/portfwd.py` | `src/web/static/styles/forms.css` estilos de formulario compartidos en |
| Visitantes recientes | `features/visitors.py` | `src/web/static/visitors.js`, `src/web/static/styles/visitors.css` |
| Historial de cambios | `features/changelog.py` | `src/web/static/styles/changelog.css` |
| Estado de Lucky | `features/lucky.py` | estilos de tarjetas compartidos |
| Estado, ajustes y dispositivos Tailscale | `features/tailscale.py`, `tailscale_control.py` | `src/web/static/styles/modules.css`, controles compartidos de valores privados |
| Página pública de accesibilidad | `features/public.py` | `src/web/static/styles/public.css`,integrado en la respuesta |

`features/system.py` ofrece comandos del sistema y auxiliares de cortafuegos; `features/ui.py` ofrece renderización compartida. Los controladores de nodos y auxiliares FRP/de módulos siguen en `src/web/` y pueden reutilizarse fuera de los controladores HTTP. Cada JavaScript se vincula a los elementos de su función; los scripts compartidos gestionan tema, copia, contraseñas y selección. Las fuentes CSS ordenadas están en `src/web/static/styles/`; `python3 tools/build_styles/build_styles.py` genera `src/web/static/style.css` y conserva el orden. El instalador mantiene los módulos Python, `features/` y `static/` en `$PREFIX/src/web/`; `$PREFIX/app.py` en la raíz solo llama a `main()` de ese paquete. En el candidato v6 los datos persistentes están en una raíz de estado independiente; los archivos de código planos de versiones anteriores ya no son entradas de ejecución. La reutilización requiere adaptar el contexto y aportar estilos y scripts; estas rutas no tienen una política de autenticación independiente.

### Por qué la página pública y la consola usan escuchas distintas

Tienen requisitos de seguridad opuestos: combinarlos obligaría a renunciar a uno de ellos. La consola está autenticada y en un puerto difícil de adivinar para evitar su descubrimiento casual; la página pública **DEBE** ser fácil de encontrar y
**NO DEBE** pedir contraseña. Por ello se usan puertos, controladores de peticiones y tablas de rutas diferentes. Una petición recibida en 80/443 nunca puede alcanzar una ruta de la consola, porque `ProbeHandler` carece de esas rutas; no depende de que una comprobación la rechace. Ese es el objetivo: puede haber errores en una comprobación de autorización, pero no se puede acceder a una ruta inexistente.

La página pública acepta `GET` y `HEAD` exactamente en dos rutas (`/` y `/favicon.ico`) y responde con 404 a cualquier otra petición. No lee cadenas de consulta, no analiza el cuerpo de la petición y no establece cookies.

### Actualización sobre una instalación existente

El candidato `v6.0.0` establece la disposición `1` del estado persistente: los archivos de programa siguen en `$PREFIX` y la raíz de estado predeterminada está en `/var/lib/vps-server`. La contraseña, el puerto de la consola, los certificados, los datos de ejecución, el registro de instalación y `.env` se guardan en esa raíz; `/etc/vps-server/state-dir` registra su ubicación. Root administra la raíz de estado, cuyo directorio tiene permisos `0700`. Los instaladores posteriores **DEBEN** seguir leyendo la disposición `1` y conservar ese estado al sustituir los archivos de programa.

El instalador reconoce una instalación compatible mediante `.layout-version`, `install-state` y `paths.json` de la raíz de estado. Si faltan o no concuerdan, o faltan archivos esenciales de contraseña, secreto de sesión o puerto, rechaza la actualización antes de modificar los servicios. Las instalaciones con la disposición de v5.1.0 o anteriores no se migran automáticamente: el operador debe respaldar primero los datos antiguos y realizar expresamente una instalación nueva. Los datos antiguos ya borrados sin copia no se pueden recuperar. Una actualización normal ejecuta el instalador desde un directorio de código fuente independiente; **NO DEBES** borrar `$PREFIX` como método para conservar datos. Si solo se sustituye el directorio del código, la raíz de estado conservada sigue disponible para versiones posteriores con la misma disposición.

Los ajustes de la aplicación y la gestión de módulos usan la raíz de estado. Las entradas que leían directamente rutas antiguas como `$PREFIX/data` ahora usan rutas de estado unificadas. La configuración proxy y el inventario de nodos están en `/etc/vps-server-proxy/` y `/etc/vps-server-nodes/` respectivamente. El antiguo `/etc/vps-server-anytls/` solo sirve como entrada de migración. La identidad Tailscale se guarda en `tailscale/` dentro de la raíz de estado; FRP sigue configurado en `/etc/frp/`. `PORTS.md` permanece en el directorio superior al de instalación. Las rutas persistentes personalizadas se registran en `paths.json`; si cambian en una instalación posterior, el instalador rechaza el cambio silencioso y exige que el operador lo gestione manualmente.

### Desinstalación completa

`deploy/uninstall.sh` llama a `src/web/uninstall_cleanup.py` antes de borrar `$PREFIX`. Limpia FRPC cuando la unidad global coincide con la plantilla del proyecto, existe una marca de titularidad del binario o la desinstalación completa encuentra instancias nombradas que reconoce la consola. Primero detiene las instancias y luego retira la plantilla aplicable y el binario cuya suma SHA-256 coincide. Por defecto elimina `frpc-*.toml`, sus alias Unicode y las copias de recuperación `.deleted-frpc-*.toml`; `KEEP_DATA=1` conserva esos archivos. El desinstalador mantiene el bloqueo `.ports.lock` junto al directorio de instalación, reutiliza la validación de formato y la escritura atómica de `console_port.py` y libera las filas de `PORTS.md` identificadas como `vps-server`, conservando las de otros proyectos. Cuando encuentra instancias `frpc-*.toml` reconocibles, elimina también su plantilla antigua aunque difiera de la actual, el binario con la suma esperada y las configuraciones del proyecto. Sin instancias reconocibles ni prueba de titularidad, conserva los archivos FRPC y sus registros; una suma de binario incorrecta interrumpe la limpieza. `deploy/uninstall.sh` termina sin borrar más archivos ante ese error. `KEEP_DATA=1` conserva la configuración para reinstalar más tarde.

`KEEP_DATA=1` conserva `$PREFIX` y `$VPSSRV_STATE_DIR`. La desinstalación completa predeterminada solo borra la raíz de estado marcada con la disposición `1` después de limpiar los servicios y los puertos. No borra automáticamente las rutas personalizadas situadas fuera de esa raíz para evitar eliminar datos de otras aplicaciones.

### Módulo proxy unificado

<a id="vps-proxy-module"></a>

`/proxy` muestra los nodos AnyTLS, VMess, VLESS, Trojan y Shadowsocks; `/anytls` solo redirige los marcadores antiguos a la misma página. Los cinco protocolos comparten `/etc/vps-server-proxy/config.json`, `vps-server-proxy.service`, `/usr/local/bin/sing-box-vps-server` y las operaciones de instalación y desinstalación. Cada nodo administrado vincula su configuración, límite de tráfico y enlace Clash mediante un ID estable. Los nodos TLS nuevos reciben certificados autofirmados independientes; Shadowsocks no necesita certificado.

`proxy_migration.py` comprueba y combina el antiguo `/etc/vps-server-anytls/config.json`: primero archiva la configuración, el inventario, la medición y los archivos de servicio; luego conserva ID, puertos, credenciales y certificados de los nodos durante el cambio. Solo retira la antigua unidad cuando la nueva configuración pasa la validación sing-box y se restablece el estado del servicio. Al completar la instalación elimina el directorio de configuración anterior. Ante un fallo restaura los archivos y el servicio anteriores, y conserva el archivo de respaldo en `data/` dentro de la raíz de estado.

Crear, editar, activar, desactivar, eliminar y reiniciar nodos actualiza configuración, inventario, cortafuegos, medición y `PORTS.md` bajo el bloqueo de `node_control.py`. Antes de actuar se comprueban los puertos públicos contra escuchas y registros; ante un fallo se revierte el nuevo registro, y al desactivar o eliminar se liberan solo los registros del proyecto. El límite de tráfico cuenta (subida + bajada) × 2 y la cuota del kernel usa la mitad del umbral de medición bruta. Un hueco de medición no adelanta la limitación. Los períodos mensuales se reinician el día 1 a las 00:00 UTC; los períodos diarios y anuales conservan sus reglas anteriores.

La página de nodos oculta por defecto direcciones de interfaz, puertos y credenciales; una interfaz autenticada proporciona los valores para mostrarlos o copiarlos. Si falta el inventario administrado o no coincide con la configuración, la página pide migración o reparación y no usa el editor antiguo. El diseño de los módulos separados y los motivos de su retirada figuran en [HISTORY](HISTORY.md#retired-anytls-console).

### Módulo Tailscale

El paquete sin conexión incluye el archivo estático oficial para Linux amd64. El instalador comprueba su hash, crea `vps-server-tailscale.service` y un directorio privado de estado, y registra el puerto UDP fijo en `PORTS.md` antes de iniciar. La consola Tailscale lee estado, preferencias, conectividad, dispositivos y el journal de systemd mediante el socket local y parámetros CLI fijos. Las direcciones y cuentas privadas se ocultan por defecto. La clave de inicio de sesión se entrega al CLI en un archivo root temporal que se elimina al finalizar; no se guarda en el estado del proyecto. Los ajustes ordinarios usan `tailscale set` para Linux y no simulan las opciones de reenvío dnsmasq ni de cortafuegos del router OpenWrt. El binario se instala sin conexión, pero unirse al Tailnet requiere acceso al servidor de control elegido.

### Ciclo de vida de la ventana iperf3

1. El operador se autentica en la consola, selecciona una duración (10 minutos por defecto, limitada por `VPSSRV_IPERF_MAX_MINUTES`) y pulsa para abrir.
2. La consola inicia `iperf3 -s -p <port>` como proceso hijo, abre el puerto en el cortafuegos activo y guarda el plazo en memoria.
3. Mientras la ventana está abierta, la **página pública** muestra que iperf3 admite conexiones, en qué puerto y cuánto tiempo queda. El usuario remoto necesita esos datos y no son secretos: la ventana se abre deliberadamente.
4. Al llegar al plazo (o por petición del operador o al detenerse el servicio) termina el proceso hijo y se retira la regla del cortafuegos.

La ventana reside en memoria, no en disco: si el servicio termina, desaparece, lo que constituye el comportamiento seguro ante fallos. Reiniciar nunca restaura una ventana abierta.

La latencia se obtiene del `--json` de iperf3 (`mean_rtt` en el bloque de información TCP) del lado del cliente; no requiere código adicional en el servidor. El campo procede de `TCP_INFO` del kernel: aparece en un cliente Linux, pero no en uno que no pueda leerlo; iperf3 bajo Cygwin en Windows comunica la velocidad pero no `mean_rtt`. El modo UDP (`-u`) proporciona fluctuación y pérdida en todas las plataformas y es la alternativa portable cuando el cliente no usa Linux.

El puerto elegido se guarda por separado en el directorio de datos de la aplicación. Solo se puede cambiar desde la consola con la ventana cerrada; antes de guardarlo se comprueban los puertos de los servicios instalados, los reenvíos y los procesos que ya escuchan.

### Ciclo de vida del reenvío de puertos

Una regla redirige un puerto público TCP/UDP de este servidor a un dispositivo accesible por Tailscale o LAN; así, un equipo con IP pública puede actuar en nombre de otro que carece de ella. A diferencia de la ventana iperf3, esto es una configuración, no un préstamo temporal del enlace: debe persistir tras reiniciar el servicio o el servidor, por lo que su diseño es diferente.

1. El operador añade una regla desde la consola: protocolo (tcp/udp/ambos), puerto público y destino `host:port`. `PortForwardManager.add()` rechaza antes de tocar iptables cualquier puerto público ya utilizado por esta instalación (consola, página pública, iperf3, nodo anytls u otro reenvío).
2. Cada protocolo de la regla genera cuatro reglas `iptables`, marcadas con `-m comment --comment vps-server-portfwd-<id>` para distinguirlas de cualquier otra regla existente:
   - `nat`/`PREROUTING`: DNAT del puerto público a `target_host:target_port`.
   - `nat`/`POSTROUTING`: MASQUERADE del tráfico destinado al objetivo, para que las respuestas vuelvan por este servidor y no por la pasarela predeterminada del destino: el destino ve este servidor como cliente.
   - `filter`/`FORWARD`: una regla ACCEPT en cada dirección, pues la política predeterminada `DROP` de esa cadena (habitual, por ejemplo, en un servidor Docker) descartaría silenciosamente el tráfico reenviado.
3. `net.ipv4.ip_forward` se activa la primera vez que alguna regla lo necesita (`_ensure_ip_forward()`) y no se desactiva automáticamente; consulta el motivo en [Decisiones][local-link-007] (2026-09-19).
4. Las reglas residen en `PORTFWD_STATE_FILE` (JSON), no solo en memoria. Cada arranque del proceso ejecuta `PortForwardManager.load()`, que retira y vuelve a añadir incondicionalmente el estado iptables de cada regla habilitada. Las tablas del kernel no sobreviven a un reinicio del servidor, pero pueden conservar las reglas de la ejecución anterior si solo se reinició el servicio; esta única ruta debe funcionar en ambos casos.
5. Una parada limpia (`SIGTERM`, con el mismo controlador de señales de la ventana iperf3) ejecuta `PortForwardManager.shutdown()`: retira el estado iptables de todas las reglas habilitadas, pero deja intacto el valor `enabled` en JSON. Reiniciar el servicio o el servidor **DEBE** restaurarlas inmediatamente mediante `load()`.
   Es el mismo comportamiento seguro ante fallos que para la ventana iperf3: si el proceso gestor no funciona, su estado **NO DEBE** seguir activo inadvertidamente.

`target_host` **DEBE** ser una dirección IPv4 literal y no un nombre de host: `iptables --to-destination` requiere una dirección, y este proyecto no hace consultas DNS salientes
al recibir peticiones (consulta la decisión «Zero third-party runtime dependencies»).
La IP del dispositivo Tailscale es estable y puede consultarse con `tailscale status`
o `tailscale ip` en dicho dispositivo.

## Restricciones de diseño

- **Mantener** las rutas de la consola fuera de `ProbeHandler`: la autenticación no sustituye la tabla independiente de rutas públicas.
- Limitar iperf3 en el tiempo y retirar la regla del cortafuegos al cerrar o detener el servicio.
- Restaurar los reenvíos persistidos en JSON al arrancar el proceso; retirar las reglas activas al detenerlo limpiamente sin revertir el ajuste global `ip_forward` del servidor.
- Conservar credenciales de nodos y ajustes seleccionados al actualizar; utilizar los scripts propietarios para cambiarlas, fuera del aislamiento del sistema de archivos de la unidad web.
- Desde v6.0.0, las versiones posteriores **DEBEN** poder leer la disposición `1` del estado persistente y **NO DEBEN** devolver el estado persistente predeterminado a `$PREFIX`. El instalador **NO DEBE** migrar automáticamente instalaciones con la disposición de v5.1.0 o anteriores; si detecta un servicio antiguo o falta un estado esencial, **DEBE** rechazar la instalación antes de modificar los servicios. Si cambia una ruta de estado personalizada, el operador **DEBE** trasladar los datos manualmente; el instalador **NO DEBE** restablecerla en silencio.
- No separar el bloqueo compartido `_db_lock` sin pruebas de latencia perjudicial: la medición histórica con 60 emisores simultáneos no mostró ralentización. Consulta [Errores][local-link-008].

## Interfaces externas

- HTTP/HTTPS: las escuchas públicas en 80/443 solo exponen la página de accesibilidad; la consola del operador usa otro puerto persistente. iperf3 solo escucha durante una ventana autenticada de duración limitada.
- La consola lee `/proc/net/tcp[6]` para registrar conexiones TCP entrantes y no expone secretos de proxy en las rutas públicas.
- `install.sh` usa los binarios incluidos y el entorno privado de nftables; no consulta repositorios de paquetes ni la IP pública desde la máquina de destino. `setup-proxy.sh` administra la unidad y los certificados del proxy unificado sing-box. iptables, cuando está disponible, gestiona la apertura temporal del puerto iperf3 y los reenvíos habilitados; systemd supervisa servicios y ejecuta los auxiliares restringidos de nodos fuera del aislamiento Web.

## Tecnologías

| Capa | Elección | Versión | Motivo |
|---|---|---|---|
| Entorno | Python, solo biblioteca estándar | 3.9+ | Heredado de `vps-webserver`: no hay paquetes Python de terceros; el intérprete y bibliotecas de la distribución siguen necesitando actualizaciones de seguridad |
| Servidor HTTP | `http.server.ThreadingHTTPServer` | stdlib | Tres escuchas de unas pocas peticiones cada una; un framework añadiría peso innecesario |
| TLS | `ssl` de Python + certificado autofirmado generado por sing-box incluido | stdlib / sing-box | Ni dominio ni ACME (consulta lo excluido) |
| Almacenamiento | `sqlite3` | stdlib | El registro de visitantes **DEBE** sobrevivir a los reinicios |
| Motor de velocidad | LibreSpeed, incluido sin cambios | v6.2.1 | LGPL-3.0; ya estaba incluido y funcionaba en `vps-webserver` |
| Generación de QR | kazuhikoarase/qrcode-generator, incluido sin cambios | js2.0.4 | MIT; pequeño, sin compilación, usa una etiqueta `<script>` como LibreSpeed |
| Sonda de ancho de banda | `iperf3` incluido para Linux x86-64 | 3.22 | Herramienta de referencia que los usuarios ya tienen en el cliente |
| Núcleo proxy | sing-box, binario incluido (amd64) | v1.13.14 | GPL-3.0; incluir el binario permite instalar sin acceder al origen |
| Inicio | systemd | — | Predeterminado del SO de destino |
| Instalador | Bash | — | Heredado de ambos proyectos de origen |

Las alternativas descartadas y el razonamiento de cada elección están en [Decisiones][local-link-009]; no se repiten aquí.

## Requisitos de reproducción

<a id="vps-reproduction-requirements"></a>

### Entorno

- SO: Debian 11+ / Ubuntu 20.04+, systemd; ejecutar como root.
- Entorno: Python 3.9+ (basta el python3 de la distribución).
- Arquitectura: todo el proyecto requiere Linux x86-64; los ejecutables incluidos de FRPC, FRPS, iperf3, sing-box, Lucky, Tailscale y nftables se distribuyen para esa plataforma.
- Hardware: sin GPU; al menos 1 GiB de espacio libre recomendado para el paquete sin conexión completo, el directorio extraído y el programa instalado; la cantidad de RAM habitual de un VPS.
- Comprobación de integridad de los archivos incluidos: desde la raíz del repositorio, ejecutar `python3 tools/verify_dependencies/verify_dependencies.py`. Compara mediante SHA-256 los nueve archivos de distribución de terceros registrados con [dependencies.lock.json][local-link-010] sin ejecutarlos. Los campos de versión y revisión de origen proceden de registros anteriores del proyecto, no de una comprobación independiente de su identidad original. No se registra la revisión original exacta de LibreSpeed.
- No existe un bloqueo de paquetes de Python de terceros porque `app.py` usa la biblioteca estándar. Este archivo de bloqueo de artefactos no es un comando para restaurar dependencias ni un bloqueo completo de paquetes del sistema; consulta [THIRD_PARTY_NOTICES.md][local-link-011].

### Dependencias externas

| Elemento | Origen | Ubicación |
|---|---|---|
| `iperf3` | artefacto estático incluido en el repositorio | `$PREFIX/vendor/iperf3/iperf3` |
| `frpc`,`frps` | incluidos en el repositorio | `third_party/frp/`, copiados por cada módulo tras instalar |
| nftables y sus bibliotecas de ejecución | paquetes oficiales Debian 11 incluidos al construir el paquete sin conexión | `$PREFIX/vendor/nft/`, sin escribir en la base de datos de paquetes del sistema |
| Cliente Tailscale | archivo estático oficial para Linux incluido al construir el paquete sin conexión | `/usr/local/bin/tailscale-vps-server` y `tailscaled-vps-server` |
| Bash, systemd, Python, tar y coreutils | entorno básico del sistema admitido | ruta del sistema |
| binario sing-box | incluido en este repositorio | `/usr/local/bin/sing-box-vps-server` |
| motor LibreSpeed y biblioteca qrcode-generator | incluidos en este repositorio | `$PREFIX/src/web/static/` |
| certificados TLS | generados durante la primera ejecución por el instalador | `$VPSSRV_CERT_DIR` |

El instalador usa los artefactos FRPC, FRPS e iperf3 incluidos. Los demás paquetes del sistema que falten pueden proceder de los repositorios Debian/Ubuntu de destino, sin seleccionar versiones exactas ni instantáneas. Python, OpenSSL, las herramientas del sistema y shell y systemd también los proporciona el SO de destino. El operador depende de los canales de paquetes de la distribución elegida, mantenidos con actualizaciones de seguridad. Esto evita incluir sus binarios, pero versiones, hashes y resolución transitiva pueden variar entre servidores y fechas; **no se consigue una
restauración de dependencias estrictamente reproducible**. Conseguirla exigiría un cambio de instalador aprobado por separado y seleccionar una instantánea de distribución/repositorio. El campo `exclusions` del bloqueo, legible por máquina, registra este límite, no una fijación ficticia.

Sin claves de API. Ni el servicio web ni el instalador consultan la IP pública en Internet.

### Rutas y montajes

<a id="vps-paths-mounts"></a>

| Ruta | Proporcionada por | Propósito |
|---|---|---|
| `$PREFIX` | instalador; por defecto `~/apps/vps-server` | Código de programa reemplazable, recursos estáticos y artefactos incluidos |
| `$VPSSRV_STATE_DIR` | instalador; por defecto `/var/lib/vps-server` | Marca de disposición, registro de instalación, inventario de rutas, contraseña, puerto, certificados y datos de ejecución |
| `$VPSSRV_DATA_DIR` | instalador; por defecto `$VPSSRV_STATE_DIR/data` | `visitors.db`, `session_secret.txt`, `portfwd.json`, `login-access.json` |
| `$VPSSRV_CERT_DIR` | instalador; por defecto `$VPSSRV_STATE_DIR/certs` | Certificado autofirmado y clave Web |
| `/etc/vps-server/state-dir` | instalador | Ubicación de la raíz de estado para los auxiliares independientes |
| `/etc/vps-server-proxy/` | instalador | `config.json` de sing-box (varias entradas) y su certificado autofirmado inicial; los certificados de nuevos nodos están en `/etc/vps-server-nodes/certs/` |
| `$VPSSRV_STATE_DIR/tailscale/` | demonio Tailscale | identidad del dispositivo y estado de conexión local |

### Referencia de configuración

<a id="vps-configuration-reference"></a>

Todas las variables usan el prefijo `VPSSRV_`. No es una cuestión estética: `vps-webserver` utiliza `VPSWS_` y `Anytsl-Serve` utiliza `ANYTLS_`, y los tres pueden estar instalados en el mismo servidor; un prefijo compartido permitiría que el `.env` de un proyecto reconfigurase silenciosamente otro.

| Variable | Significado | Predeterminado | Obligatoria |
|---|---|---|---|
| `PREFIX` | Raíz de instalación del programa, establecida en el comando de instalación o desinstalación, no mediante `.env` | directorio personal de root, `apps/vps-server` | no |
| `VPSSRV_STATE_DIR` | Raíz de estado persistente definida en el entorno antes de la primera instalación; `.env` no cambia su ubicación | `/var/lib/vps-server` | no |
| `VPSSRV_DATA_DIR` | SQLite, secreto de sesión y estado de funciones | `$VPSSRV_STATE_DIR/data` | no |
| `VPSSRV_HOST` | Dirección de escucha de todas las conexiones | `0.0.0.0` | no |
| `VPSSRV_PUBLIC_HTTP_PORT` | Página pública de accesibilidad sin cifrar | `80` | no |
| `VPSSRV_PUBLIC_HTTPS_PORT` | Página pública de accesibilidad, TLS | `443` | no |
| `VPSSRV_PUBLIC_ENABLE` | Habilitar la página pública | `0` | no |
| `VPSSRV_CONSOLE_PORT` | Puerto de consola; `0` = generar uno y conservarlo | `0` | no |
| `VPSSRV_CONSOLE_PORT_FILE` | Archivo donde se conserva el puerto generado de la consola | `$VPSSRV_STATE_DIR/console_port.txt` | no |
| `VPSSRV_CONSOLE_TLS` | Servir la consola mediante HTTPS | `0` | no |
| `VPSSRV_AUTH` | Exigir inicio de sesión en la consola | `1` | no |
| `VPSSRV_PASSWORD_FILE` | Contraseña en texto claro de la consola; Ajustes verifica la contraseña actual antes de cambiarla | `$VPSSRV_STATE_DIR/admin_password.txt` | no |
| `VPSSRV_IP_ALLOWLIST_FILE` | Ruta opcional de la lista de IP privadas | `$VPSSRV_DATA_DIR/login-access.json` | no |
| `VPSSRV_CERT_DIR` | Ubicación del certificado autofirmado | `$VPSSRV_STATE_DIR/certs` | no |
| `VPSSRV_TLS_CERT` / `VPSSRV_TLS_KEY` | Usar un certificado facilitado por el operador | — | no |
| `VPSSRV_IPERF_PORT` | Puerto de escucha de la ventana iperf3 | `5201` | no |
| `VPSSRV_IPERF_DEFAULT_MINUTES` | Duración propuesta de la ventana | `10` | no |
| `VPSSRV_IPERF_MAX_MINUTES` | Límite máximo de la consola | `60` | no |
| `VPSSRV_IPERF_ENABLE` | Permitir abrir ventanas | `1` | no |
| `VPSSRV_PORTFWD_ENABLE` | Mostrar la página de reenvíos y permitir nuevas reglas | `1` | no |
| `VPSSRV_PORTFWD_MAX_RULES` | Número máximo de reenvíos configurados | `20` | no |
| `VPSSRV_TRUST_PROXY` | Respetar `X-Forwarded-For` al registrar visitantes | `0` | no |
| `VPSSRV_TRACK_CONNECTIONS` | Consultar `/proc/net/tcp[6]` para registrar conexiones a todos los puertos | `1` | no |
| `VPSSRV_CONN_POLL_SECONDS` | Intervalo de consulta | `5` | no |
| `VPSSRV_MAX_TEST_MB` | Límite de una transferencia de prueba de velocidad, en MB | `200` | no |
| `VPSSRV_TEST_SECONDS` | Tiempo de medición por dirección | `10` | no |
| `VPSSRV_WARMUP_SECONDS` | Tiempo de calentamiento descartado al principio de cada dirección | `2` | no |
| `VPSSRV_DOWNLOAD_STREAMS` / `VPSSRV_UPLOAD_STREAMS` | Flujos paralelos por dirección | `6` / `3` | no |
| `VPSSRV_PING_SAMPLES` | Viajes de ida y vuelta usados para calcular la latencia | `20` | no |
| `VPSSRV_DEFAULT_LANG` | `en` / `zh_cn` / `es` | `en` | no |
| `PROXY_PROTOCOLS`, `PROXY_SNI` | conjunto inicial de protocolos y nombre TLS del proxy unificado; incluye AnyTLS | consulta `.env.example` | no |
| `VPSSRV_PROXY_CONFIG` | Ruta donde la consola lee el conjunto de nodos instalados | `/etc/vps-server-proxy/config.json` | no |
| `VPSSRV_PROXY_SERVICE` | Unidad cuya actividad del nodo consulta la consola | `vps-server-proxy.service` | no |

Los antiguos `ANYTLS_*` y `VPSSRV_ANYTLS_*` solo se leen durante la migración; la configuración nueva no crea un servicio AnyTLS independiente.

## Instalación desde cero

1. Ejecuta `git clone <repo>` y entra con `cd`: comprueba que `ls -lh third_party/sing-box/sing-box` muestre un archivo de unos 57 MB.
2. Ejecuta `bash deploy/install.sh`: la primera ejecución instala Web directamente e imprime la dirección y la contraseña; elige otros módulos de servidor con `VPSSRV_MODULES` o instálalos después desde Settings → Modules.
3. Ejecuta `systemctl status vps-server-web`: comprueba que indique `active (running)`.
4. Desde otra máquina, abre `http://<ip>/`: comprueba que aparece la página de accesibilidad y muestra tu propia IP de origen.
5. Desde otra máquina, abre `https://<ip>/` y acepta la advertencia del certificado: comprueba que aparece la misma página y la línea del protocolo dice HTTPS.
6. Abre `http://<ip>:<console port>/` e inicia sesión: comprueba que se carga el panel y el control de iperf3 indica que la ventana está cerrada.
7. Abre desde la consola una ventana iperf3 de 5 minutos y ejecuta desde otra máquina `iperf3 -c <ip> -p 5201 --json`: comprueba que comunica la velocidad e incluye `mean_rtt`.
8. Si se instaló el módulo proxy, ejecuta `systemctl status vps-server-proxy` para comprobar el servicio unificado; después de crear un nodo AnyTLS en la consola, comprueba su puerto y configuración.

## Diseño de datos

La página Ajustes muestra los módulos de ejecución instalados. Un auxiliar root serializa la instalación y desinstalación de los módulos opcionales; `data/module-job.json` guarda el estado de la tarea, `data/module-job.log` la salida actual y `data/module-history.log` agrega el historial. Módulos solo muestra temporalmente el progreso en la página de la operación actual: se oculta 30 segundos después de la última salida y el aviso de finalización no reaparece al actualizar o volver a entrar. La página independiente `/settings/logs` lee el historial de módulos y los journal de Web, medición de nodos, Singbox, FRPS, FRPC, Lucky y Tailscale; el alcance de los registros de servicios depende de la retención del journal de la máquina.

Los interruptores de funciones de Home son independientes del estado de instalación de los módulos. Los puertos ocupados por escuchas Web públicas, nodos proxy, Tailscale, FRPS, FRPC, reenvíos y ventanas temporales de iperf3 se registran en `PORTS.md` junto al directorio de instalación. Los interruptores en ejecución y las operaciones de nodos comparten `.ports.lock` y escrituras atómicas; ante un fallo revierten el nuevo registro, y al detener o eliminar liberan solo las filas propias del proyecto. El sandbox Web mantiene el directorio superior al de instalación en modo de solo lectura; una tarea auxiliar systemd con argumentos fijos actualiza `PORTS.md` en tiempo de ejecución. iperf3 solo registra su puerto mientras la ventana está abierta; lo libera al cerrarse o al reiniciar Web. El interruptor del grupo FRPC registra las instancias activas antes de detenerlas y restaura únicamente esas instancias al activarlo de nuevo. El grupo Nodos proxy controla solo el servicio sing-box unificado. Home abre FRPS en `/frps`, la lista FRPC en `/frpc` y Tailscale en `/tailscale`; el antiguo marcador `/frp` redirige a la lista FRPC.

La base de datos de visitantes, `portfwd.json` y `login-access.json` permanecen en `$VPSSRV_DATA_DIR`. La página Visitantes recientes permite vaciar la base de datos mediante una sesión iniciada y una comprobación CSRF; la propia solicitud de borrado no vuelve a registrarse, pero las visitas posteriores y los dispositivos que sigan conectados sí. La contraseña de la consola, el puerto elegido, los certificados Web y `install-state` residen en `$VPSSRV_STATE_DIR`; el directorio del programa puede reemplazarse por separado. La configuración y los certificados sing-box residen en `/etc/vps-server-proxy/`. Consulta [Rutas y montajes][local-link-012]. El plazo de iperf3 permanece en memoria y no sobrevive a un reinicio.

### Modelo de datos y disposición de archivos

```
<project root>/
├── snapshots/                 # private snapshots; not part of the Git repository
└── repo/                      # Git working tree; paths below are relative to it
    ├── README.md              # entry point for users and documentation navigation
    ├── config/VERSION         # release version used in checkout
    ├── src/web/app.py         # web service implementation
    ├── deploy/
    │   ├── install.sh         # module-selecting installer
    │   ├── uninstall.sh       # module removal
    │   ├── systemd/vps-server-web.service
    │   ├── proxy/setup-proxy.sh
    │   ├── frps/setup-frps.sh
    │   ├── lucky/setup-lucky.sh
    │   └── tailscale/setup-tailscale.sh
    ├── src/web/static/        # first-party UI assets and vendored browser libraries
    │   └── third_party/
    │       ├── librespeed/    # speedtest.js, speedtest_worker.js
    │       └── qrcode/        # qrcode.js, qrcode-utf8.js
    ├── lang/                  # interface catalogs for web, installers, and tools
    ├── third_party/sing-box/
    │   ├── sing-box           # vendored amd64 binary
    │   ├── sing-box.version   # binary version metadata
    │   └── LICENSE            # original upstream notice
    ├── third_party/tailscale/  # pinned static-client metadata and license
    ├── third_party/nft/        # pinned Debian runtime metadata
    ├── tools/build_offline/    # checked offline asset and archive builder
    ├── tools/verify_dependencies/verify_dependencies.py # checks config/dependencies.lock.json from repo root
    ├── config/dependencies.lock.json
    ├── config/upstream-version # records: vps-webserver v0.4.1
    ├── LICENSE                # GPL-3.0
    └── doc/
        ├── DESIGN.md          # architecture, constraints, and tracked goals
        ├── LOG.md             # current status, bugs, decisions, and handoff
        ├── HISTORY.md         # historical work and prior handoffs
        ├── CHANGELOG.md       # formal version changes
        ├── THIRD_PARTY_NOTICES.md
        ├── en/               # English translation
        └── es/               # Spanish translation
```

Estas rutas corresponden al repositorio: el código Web instalado se conserva en `$PREFIX/src/web/` y el ejecutable proxy en `$PREFIX/sing-box`. La entrada compatible sigue siendo el `ExecStart` de systemd, pero solo llama a `src.web.app.main()`. Las URL HTTP de los recursos no cambian. En el repositorio, el instalador y el desinstalador son `deploy/install.sh` y `deploy/uninstall.sh`; el punto de entrada web instalado sigue siendo `$PREFIX/app.py`. La raíz de estado persistente del candidato v6 está separada del directorio de instalación; los datos guardados dentro del directorio por versiones anteriores no se migran automáticamente.

Solo `repo/` está bajo control de Git; `snapshots/` está separado y es privado. Empieza por [README][local-link-013], consulta [LOG][local-link-014] para verificaciones históricas e historial de versiones, y los [avisos de terceros][local-link-015] para conocer los archivos de origen. La documentación no convierte una instantánea ni un servidor instalado en un árbol de código reproducible.

El esquema SQLite se hereda sin cambios de `vps-webserver`: una tabla `visits` limitada a las 1000 filas más recientes. `portfwd.json` es una lista JSON plana de objetos de reglas (`id`, `label`, `protocol`, `public_port`, `target_host`, `target_port`, `enabled`, `created`); consulta `PortForwardManager` en `src/web/app.py`.

## Límites conocidos y precauciones

- **Para usar los puertos 80 y 443 se requiere root y que estén libres.** Si nginx, Apache, Caddy u otra instancia de `vps-webserver` ocupa cualquiera de ellos, el instalador se niega a disputar el puerto. Compruébalo con `ss -lntp '( sport = :80 or sport = :443 )'` antes de instalar.
- **La página pública es realmente pública.** Cualquiera que adivine o explore la IP puede verla; cada acceso queda en el registro de visitantes. Es la finalidad de la función, pero también significa que un registro asociado a una IP explorada se llena de tráfico de fondo de Internet en pocas horas.
- **Los nombres de servicios están separados de los proyectos originales.** El proxy unificado usa `vps-server-proxy.service` y Tailscale usa `vps-server-tailscale.service`; no sustituyen la unidad Tailscale estándar que ya pudiera existir en el sistema.
- **El iperf3 incluido es la versión 3.22.** Se compiló como binario estático x86-64 sin SCTP ni autenticación OpenSSL. Quedan por comprobar la resolución de nombres y el tráfico TCP/UDP real en Debian 11 y Ubuntu 20.04.
- **Todo el proyecto requiere Linux x86-64.** El instalador rechaza otras arquitecturas antes de escribir el estado del sistema.
- **El TLS autofirmado provoca una advertencia del navegador en 443, siempre.** Es esperado y no conviene «solucionarlo» mediante excepciones ni una cabecera HSTS.
- **Reiniciar cierra cualquier ventana iperf3 abierta.** Es intencionado; consulta su ciclo de vida.
- **Detener el servicio retira todos los
reenvíos de puertos, incluso los habilitados.** Es intencionado y simétrico con la ventana iperf3; consulta el ciclo de vida del reenvío. `systemctl restart` o reiniciar el servidor los restaura inmediatamente; dejarlo detenido con `systemctl stop`, no.
- **`net.ipv4.ip_forward` se activa automáticamente y nunca se desactiva.** Es un ajuste de todo el servidor del que puede depender otro programa (Docker, por ejemplo); por ello, quitar el último reenvío no lo modifica. Desactívalo manualmente si ya no lo necesita ningún otro programa.
- **Un reenvío solo cubre el tráfico visible para `iptables` sin intermediarios.** Si `ufw` o `firewalld` está activo con su propia política `FORWARD` de denegación predeterminada, sus cadenas se evalúan antes de la regla que añade esta función y quizá también exijan una regla que permita ese puerto para que pase el tráfico.
- **El binario sing-box supera el tamaño recomendado por GitHub.** Con unos 55 MB excede el límite flexible de 50 MB, por lo que cada push muestra una advertencia «Large files detected» que recomienda Git LFS. Los envíos todavía funcionan; el límite estricto es 100 MB. Una actualización futura de sing-box podría superarlo y entonces habrá que tomar una decisión deliberada (LFS o dejar de incluir el binario), no descubrirlo por sorpresa al publicar.
- **Ejecuta los scripts con `bash <script>`, no con `./<script>`.** Git registra el bit de ejecución, por lo que una clonación nueva lo conserva; pero una copia de trabajo en un volumen CIFS/SMB no, y allí `./install.sh` falla con «Permission denied».
- **Volver a incorporar un ejecutable de un proyecto de origen pierde su bit de ejecución.** La copia de trabajo del mantenedor está en CIFS: un archivo extraído ahí y luego añadido con `git add` queda registrado como `100644` aunque el original fuese `100755`. Ya ocurrió una vez con el binario `sing-box` y dejó inservible todo el módulo anytls. Tras una nueva incorporación, comprueba con `git ls-files -s` y restaura el bit con `git update-index --chmod=+x <path>`; `chmod +x` por sí solo no tiene efecto en ese volumen.
- **La página de nodos muestra las direcciones de las interfaces y de Tailscale.** Se eliminó el antiguo bloque de dirección pública detectada durante la instalación: duplicaba la dirección de la interfaz en un VPS y podía inducir a error tras NAT. Los scripts de configuración eliminan el `public-ip.txt` que haya dejado una instalación anterior; la consola no lo lee.
- **El `body` pasado a `render_page()`** **DEBE** contener exactamente un elemento de nivel superior. `<main>` usa `display: flex` sin cambiar `flex-direction`; con varios elementos hermanos superiores (por ejemplo, un `<div class="card wide">` por protocolo), se colocan en paralelo en vez de apilados. Fue un fallo real publicado en una versión anterior de `/proxy`, descrito por un operador como «layout is messed up». Todas las páginas envuelven su contenido en una sola tarjeta exterior y anidan las secciones repetidas como elementos `.node-addr` dentro de ella.
- **Para desinstalar se necesitan los mismos `PREFIX` y `SERVICE_NAME` usados al instalar.** `uninstall.sh` sin variables toma los valores predeterminados, no encuentra nada en esas rutas y comunica éxito sin quitar nada. La última línea del instalador imprime el comando exacto con los valores correspondientes: úsalo en lugar de escribirlo de memoria.

## Ampliación

### Cómo ampliar

- **Un módulo nuevo** (otro componente opcional del instalador): añade `deploy/<name>/setup-<name>.sh`, su unidad systemd (incluida en `deploy/systemd/` o generada por el script), una opción en el menú de módulos de `deploy/install.sh` y una rama de desinstalación en `deploy/uninstall.sh`. Los módulos no se invocan entre sí.
- **Una página nueva de consola**: añade una ruta a `ConsoleHandler`. No añadas rutas a `ProbeHandler`: su tabla casi vacía de rutas es una propiedad de seguridad, no un descuido.
- **Un idioma nuevo**: añade catálogos correspondientes en todos los directorios `lang/<component>/`, registra el código en el selector de idiomas web y el mapeo del historial de cambios, en el instalador, el asistente de configuración y los cargadores de los scripts de módulos; después añade el árbol correspondiente `doc/<BCP47>/`.
- **Un color nuevo**: añade un token a `:root` en `src/web/static/style.css` *y* un valor de modo claro en el bloque `prefers-color-scheme: light`, y después utiliza el token. Nunca escribas un color hexadecimal literal en una regla de componente: un literal no sigue el tema y será correcto en el modo para el que se eligió visualmente e incorrecto en el otro, sin que nada lo detecte. Todo fondo de color necesita un valor de primer plano `--on-*`: un color adecuado para el texto rara vez sirve también de fondo para texto blanco. Comprueba ambos modos frente a WCAG AA (4.5:1) antes de hacer commit; Los antiguos tests verificaban la estructura, pero no podían juzgar la relación de contraste. Las comprobaciones actuales requieren revisión visual.
- **Actualizar un componente incluido de otro proyecto**: vuelve a copiar desde la etiqueta original, actualiza el archivo `.upstream-version` correspondiente en el mismo commit y anota la nueva versión en [LOG.md][local-link-016]. No modifiques el código incluido directamente sin registrar la desviación: un cambio local no reflejado en el origen causaría una regresión silenciosa en la siguiente actualización.

[local-link-001]: ../LOG.md#交接
[local-link-002]: LOG.md#errores
[local-link-003]: HISTORY.md
[local-link-004]: LOG.md#decisiones
[local-link-005]: #vps-proxy-module
[local-link-006]: LOG.md#decisiones
[local-link-007]: LOG.md#decisiones
[local-link-008]: LOG.md#errores
[local-link-009]: LOG.md#decisiones
[local-link-010]: ../../config/dependencies.lock.json
[local-link-011]: THIRD_PARTY_NOTICES.md
[local-link-012]: #vps-paths-mounts
[local-link-013]: README.md
[local-link-014]: LOG.md
[local-link-015]: THIRD_PARTY_NOTICES.md
[local-link-016]: CHANGELOG.md
