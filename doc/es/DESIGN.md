---
name: project-design-es
description: Arquitectura y restricciones de diseño del proyecto
metadata:
  version: "1.0.0"
  lang: "es"
---

# vps-server — Diseño

## Multilingüe

[English](../DESIGN.md) | [简体中文](../zh-CN/DESIGN.md) | [繁體中文(台灣)](../zh-TW/DESIGN.md) | [繁體中文(香港)](../zh-HK/DESIGN.md) | [हिन्दी](../hi/DESIGN.md) | **Español** | [العربية](../ar/DESIGN.md) | [Français](../fr/DESIGN.md)

## Documentación

- Descripción general del proyecto: [README](README.md)

- Justificación del diseño: [DESIGN](DESIGN.md)

- Historial de versiones: [LOG](LOG.md)

- Avisos de terceros: [THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES.md)

## Objetivos de diseño

**Objetivos implementados en v2.0.0 (consulta los [límites de aceptación][local-link-001]):**

La versión 2.0.0 también contiene rutas de instalación experimentales para frps y Lucky. Su funcionamiento no se ha aceptado en un servidor real; los objetivos siguientes describen los cuatro módulos documentados anteriormente.

- Instalar en un VPS Debian/Ubuntu nuevo un único paquete con cuatro módulos seleccionables que proporcionan cinco capacidades (el módulo web incluye la página pública y la consola privada):
  1. **Página pública de accesibilidad**: una página deliberadamente mínima en TCP
     **80 y 443**, sin autenticación, para que cualquiera que reciba solo la IP pueda comprobar en un navegador si los puertos web de este servidor son accesibles desde donde esté.
  2. **Consola privada**: un panel protegido con contraseña en un puerto alto aleatorio y persistente que permite medir la velocidad de subida y bajada desde el navegador y consultar un registro de conexiones entrantes observadas recientemente.
  3. **Ventana iperf3 bajo demanda**: punto de prueba de ancho de banda y latencia
     **desactivado de forma predeterminada**; el operador abre desde la consola una ventana de duración limitada que se cierra automáticamente al vencer.
  4. **Proxy anytls**: una entrada `anytls` de sing-box con certificado autofirmado y BBR.
  5. **proxy**: cualquier combinación de entradas `vmess`/`vless`/`trojan`/`shadowsocks` de sing-box, que comparten una unidad systemd, una configuración y el mismo binario sing-box incluido que usa el módulo anytls. Consulta «El módulo proxy» más abajo.
- Poder instalarse sin acceso a la red exterior salvo al repositorio de paquetes de la distribución. El binario sing-box se incluye en el repositorio.
- Convivir en el mismo servidor con `vps-webserver` y `Anytsl-Serve` sin conflictos de nombres de unidades systemd, prefijos de instalación, prefijos de variables de entorno ni puertos persistentes.

**Objetivos registrados y estado actual:**

- [ ] 2026-09-19 Contabilización del tráfico por nodo, límite de datos y caducidad: registrar subida y bajada por nodo; desactivar el nodo cuando se alcance su límite o fecha de caducidad; mostrar los totales en la consola. Requiere diseño y revisión del operador.
- [x] 2026-09-19 Configuración inicial desde el navegador: este árbol usa un asistente de configuración de corta duración en `tools/setup_wizard/setup_wizard.py` cuando el instalador interactivo no recibe `VPSSRV_MODULES`. Recoge las opciones de idioma, módulos, puertos y autenticación; el instalador de shell ejecuta las acciones seleccionadas solo después de validar el resultado. Este árbol aún no se ha aceptado en un servidor real.
- [ ] 2026-09-22 Completar el soporte de frps en la consola para tokens e información de conexión. El instalador actual ya ofrece frps, pero el requisito de la consola sigue sin delimitarse: decidir si la información del token significa un token de autenticación, un fragmento de configuración del cliente o una lista de proxies conectados.
- [ ] Delimitar la solicitud más amplia de funciones de `gdy666/lucky` registrada en la instantánea de estado del 2026-09-22. El árbol actual ya ofrece una ruta de instalación de Lucky, pero no se registraron una lista más amplia de funciones ni criterios de aceptación.
- [ ] Delimitar la petición de nodos muy personalizables registrada en el mismo estado; allí no se registraron criterios de implementación.

La preocupación por el bloqueo SQLite compartido es una [cuestión de medición conocida y sin resolver][local-link-002], no una orden de modificar la arquitectura. El trabajo histórico completado y las pruebas registradas están en [LOG][local-link-003].

**Fuera de alcance**

- **No sustituye a `vps-webserver` ni a `Anytsl-Serve`.** Ambos siguen manteniéndose y publicándose independientemente. vps-server incluye su código en vez de importarlo o reemplazarlos; consulta [Decisiones][local-link-004] para conocer el riesgo de divergencia aceptado y cómo se mitiga.
- **Ni ACME, ni Let's Encrypt, ni nombres de dominio.** TLS en 443 usa un certificado autofirmado. La página pública debe responder «¿se puede acceder a esta IP?», algo que ya demuestra una advertencia del navegador. La renovación del certificado y depender de un dominio no aportan nada para ese fin.
- **No mantener iperf3 siempre activo.** Un `iperf3 -s` público sin autenticación permite a cualquier desconocido saturar el enlace de salida durante el tiempo que desee.
- **La página pública no revela información sobre el servidor.** Ni nombre, ni versión del kernel, ni tiempo de actividad, ni inventario de servicios, ni lista de puertos, ni parámetros de anytls. Solo informa de que se ha podido acceder, la IP de origen detectada, la hora del servidor y el puerto/protocolo de entrada.
- **Ni proxy inverso, ni nginx, ni contenedores.** El proceso Python termina TLS por sí mismo, como ya hace `vps-webserver`.
- **Ni selector de servidores para medir la velocidad.** Un solo servidor: este.

## Arquitectura

El servicio web, el servicio anytls y el servicio proxy opcional funcionan como procesos separados; el servicio web también inicia un proceso hijo iperf3 transitorio. La consola y la página pública usan escuchas distintas en un único proceso Python y comparten estado en memoria. Solo el tráfico de clientes configurados llega a esos servicios.

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

                       ┌─── vps-server-anytls.service ───┐
  proxy client ──────► │  sing-box, anytls inbound, TLS  │
  :<random>            │  self-signed cert               │
                       └─────────────────────────────────┘
```

El diagrama muestra las unidades web y anytls; el servicio opcional `vps-server-proxy.service` ejecuta hasta cuatro entradas independientes en un tercer proceso y comparte el binario sing-box incluido, pero no el estado de las otras unidades. Cada módulo puede seleccionarse por separado; consulta [El módulo proxy][local-link-005].

### Why the public page and the console are separate listeners

Tienen requisitos de seguridad opuestos: combinarlos obligaría a renunciar a uno de ellos. La consola está autenticada y en un puerto difícil de adivinar para evitar su descubrimiento casual; la página pública **DEBE** ser fácil de encontrar y
**NO DEBE** pedir contraseña. Por ello se usan puertos, controladores de peticiones y tablas de rutas diferentes. Una petición recibida en 80/443 nunca puede alcanzar una ruta de la consola, porque `ProbeHandler` carece de esas rutas; no depende de que una comprobación la rechace. Ese es el objetivo: puede haber errores en una comprobación de autorización, pero no se puede acceder a una ruta inexistente.

La página pública acepta `GET` y `HEAD` exactamente en dos rutas (`/` y `/favicon.ico`) y responde con 404 a cualquier otra petición. No lee cadenas de consulta, no analiza el cuerpo de la petición y no establece cookies.

### Upgrading over an existing install

`install.sh` detecta una instalación anterior y ofrece conservar su configuración. Responder que sí restaura los ajustes registrados en la instalación previa; responder que no vuelve a preguntar todo. En ambos casos sobreviven la contraseña de la consola, el puerto persistente, los certificados y el registro de visitantes: el instalador nunca modifica esos archivos.

Se mantienen dos registros porque responden a preguntas diferentes:

- **Las líneas `Environment=` de la unidad systemd** indican qué valores se *establecieron*. Recuperarlos impide que una opción elegida una vez —un puerto público personalizado o TLS para la consola— vuelva silenciosamente a su valor predeterminado en la siguiente actualización.
- **`$PREFIX/.install-state`** indica qué opciones *conocía* la versión instalada: su versión, lista de módulos y los nombres de todos los ajustes que admitía. La unidad no puede responder a esto porque solo registra los ajustes a los que se dio un valor, no cuáles existían.

El segundo archivo permite calcular «qué hay de nuevo en esta versión»: los ajustes conocidos por la versión actual menos los enumerados en el registro. Cada uno se ofrece con el valor predeterminado de `.env.example`, que se acepta pulsando Intro.

Una instalación anterior a ese registro no contiene tal lista. En vez de presentar una conjetura como si fuera una diferencia, el instalador advierte que no puede determinarla, conserva lo registrado en la unidad e indica la opción de volver a preguntar. La detección de módulos también se degrada: sin registro, infiere la lista a partir de lo que hay en disco —las unidades web y anytls y la presencia de `iperf3`.

El nodo anytls se conserva durante la actualización leyendo su puerto y contraseña de `config.json` y pasándolos al script. De lo contrario, `setup-anytls.sh` generaría nuevos valores aleatorios y todos los clientes configurados dejarían de funcionar por una actualización ordinaria; consulta el aviso más abajo, que sigue aplicándose a una reinstalación *deliberada*.

### The console's anytls section

**Ahora está en `/proxy`, no en una página independiente** (2026-09-22): consulta «El módulo proxy» más abajo para saber por qué anytls y los protocolos proxy se unieron en una sola página. `/anytls` sigue existiendo como redirección a `/proxy` y `POST /anytls/reset` no ha cambiado; solo desaparecieron la página independiente `GET /anytls` y su enlace de navegación/tarjeta del panel. Lo siguiente sigue describiendo el comportamiento de la sección anytls de la página conjunta.

La consola lee el nodo instalado de `VPSSRV_ANYTLS_CONFIG` y muestra su estado, una entrada Clash lista para pegar y un enlace `anytls://`.

Solo escribe una cosa: el botón «restablecer puerto y contraseña», que además delega la operación. La consola no modifica directamente `config.json`: ejecuta `setup-anytls.sh reset`, ya que es fácil equivocarse con el orden crítico; la regla del cortafuegos del puerto anterior debe retirarse *antes* de abrir el nuevo, o cada restablecimiento deja una regla `ACCEPT` para un puerto en el que nadie escucha. Esa lógica pertenece al script propietario del nodo, no a dos sitios distintos. El restablecimiento exige marcar una casilla de confirmación validada por el servidor: `required` en el HTML evita un clic accidental, pero no detiene a un cliente que no sea un navegador. Cambiar las credenciales deja inoperativos todos los clientes configurados hasta que reciban las nuevas.

Además se ejecuta **fuera del aislamiento de este servicio**, como unidad transitoria mediante `systemd-run --pipe --wait --collect`. La unidad web tiene `ProtectSystem=strict` y solo `ReadWritePaths=$PREFIX`, por lo que no puede escribir en `/etc`; restablecer requiere modificar `/etc/vps-server-anytls` y un archivo de unidad. El primer intento real falló a mitad de proceso precisamente por eso, después de haber retirado la regla del puerto anterior. La alternativa de añadir `/etc/systemd/system` a `ReadWritePaths` ampliaría permanentemente los permisos de escritura del servicio para hacer funcionar un solo botón; mantener el aislamiento es más importante. Si no hay `systemd-run`, se hace la llamada directamente: los entornos que carecen de él son también aquellos en los que `install.sh` no aplica ese endurecimiento.

`setup-anytls.sh reset` también comprueba que puede escribir antes de tocar el cortafuegos. Si falla después de retirar la regla anterior, quedaría un nodo en ejecución pero inaccesible, peor que uno que no llegó a arrancar.

Dos detalles son esenciales. **La contraseña del nodo aparece en texto claro en esa sección de la consola**, lo que solo es aceptable porque la página reside en `ConsoleHandler`, detrás del inicio de sesión; `ProbeHandler` no tiene esa ruta, y una prueba verifica que la escucha pública responde 404 a `/anytls` y nunca incluye la contraseña. Y
**la dirección del servidor procede de
la cabecera `Host` de la petición**, no de una consulta: la dirección que alcanzó la consola puede alcanzar el nodo; consultar la IP externa al mostrar la página contradice la prohibición de solicitudes salientes, y quien necesite otra dirección puede editar la línea una vez copiada.

El SNI ni siquiera se almacena en la configuración de sing-box: `setup-anytls.sh` solo lo incorpora al CN del certificado autofirmado. La consola lo vuelve a leer del certificado, en lugar de conservar una segunda copia susceptible de divergir.

### The proxy module

El antiguo registro de tareas preguntaba si el binario sing-box ya incluido admite protocolos adicionales a anytls o requiere otro backend. Sí los admite: `vmess`, `vless`, `trojan` y `shadowsocks` (2022-blake3-aes-128-gcm) pasan `sing-box check` y, como confirmó su ejecución real en vez de solo validar la configuración, los cuatro abren sus puertos y aceptan conexiones simultáneamente en un único proceso `sing-box run`. No se añadió otro backend.

A diferencia de anytls, se trata de **una unidad systemd (`vps-server-proxy.service`) con hasta
cuatro entradas simultáneas en un único `config.json`**, no cuatro copias del esquema de anytls. Motivos: supervisar una sola unidad en lugar de cuatro, un certificado autofirmado compartido en vez de tres (shadowsocks no lo necesita), y la misma estructura que convendría para una futura función de contabilización de tráfico por nodo: un proceso cuya matriz `inbounds` ya representa la lista de nodos. `deploy/proxy/setup-proxy.sh` es código propio de vps-server, no procedente de otro proyecto, ya que ninguno de esos cuatro protocolos procede de Anytsl-Serve.

**Comparte el binario sing-box incluido con el módulo anytls** (`/usr/local/bin/sing-box-vps-server`) en vez de incorporar otra copia de unos 57 MB. La función `uninstall()` de ambos módulos comprueba si sigue existiendo la configuración del *otro* antes de eliminar el binario. El `setup-anytls.sh` incluido de otro proyecto recibió esa comprobación como desviación local documentada (consulta `deploy/anytls/.upstream-version`), porque el binario ya no pertenece solo a anytls.

`PROXY_PROTOCOLS` (separados por comas; los cuatro por defecto) se valida en una matriz global y no se devuelve por sustitución de comandos `$(...)`: una versión inicial lo validaba dentro de una función invocada como `read -ra x <<< "$(fn)"`, y `exit 1` dentro del subproceso de esa sustitución solo terminaba el subproceso. El script padre continuaba silenciosamente con una lista de protocolos vacía e iniciaba un servicio sin entradas. Es el mismo tipo de fallo que `prompt_new_settings()` en [Decisiones][local-link-006]. El puerto de cada protocolo procede de un intervalo distinto de 5000 números por debajo de 60000 (no de un intervalo de 10000 a partir de 60000, que desbordaba el `uint16 listen_port` de sing-box por encima de 65535 cuando se generaba un puerto alto; se detectó con cinco instalaciones nuevas consecutivas y no en la primera). Para conservar las credenciales al actualizar se sigue el mismo procedimiento que en `preserve_anytls()`: `preserve_proxy()` lee de `config.json` el puerto y la credencial de cada protocolo instalado, además del *conjunto* de protocolos, para que ejecutar de nuevo `VPSSRV_MODULES=proxy` no elimine ni añada protocolos sin avisar.

La página `/proxy` de la consola muestra una sección por protocolo instalado: puerto, UUID o contraseña según corresponda, SNI compartido (leído del CN del certificado como en anytls), entrada Clash y enlace para compartir (`vmess://`, `vless://`, `trojan://`, `ss://`) para cada dirección detectada. **Cada protocolo dispone de su propio botón de restablecimiento**, no uno único que «restablece todo»: un operador señaló que el botón conjunto obliga a cambiar protocolos que nadie pidió tocar; por ejemplo, filtrar un UUID vmess no debería implicar reconfigurar también todos los clientes trojan/vless/shadowsocks. `setup-proxy.sh reset <protocol>` cambia solo el puerto y la credencial de ese protocolo; `load_installed_vars()` lee primero del disco los valores actuales de los *otros*, que quedan intactos. `reset` sin argumentos sigue cambiando todos los protocolos instalados, opción reservada a la terminal y scripts, no a la interfaz de consola. Ambas modalidades siguen el patrón `systemd-run` fuera del aislamiento utilizado por `anytls_reset()`, por el mismo motivo de `ProtectSystem=strict`. Una consecuencia real de compartir servicio systemd: restablecer un protocolo reinicia todo el servicio y corta brevemente las *conexiones* de los demás, aunque sus credenciales permanezcan iguales.

`PortForwardManager.reserved_ports()` reserva el puerto de cada protocolo proxy instalado igual que ya reserva el del nodo anytls y el de la consola, para impedir que una regla de reenvío apunte a un puerto ocupado por un protocolo proxy.

**La página `/proxy` de la consola también muestra el nodo anytls** si está instalado. Un operador consideró artificial mantener anytls en otra página, pues ambos son «nodos proxy» desde su punto de vista, aunque los sirvan dos módulos independientes. `/anytls` redirige aquí; `POST /anytls/reset` no cambia y después vuelve a `/proxy`. Los módulos mantienen estados completamente independientes (los `public-ip.txt`/`SERVER_IP` de anytls no son los del módulo proxy; pueden configurarse de manera diferente) y botones de restablecimiento distintos; solo comparten página. Por ello, toda la página utiliza una sola función auxiliar `address_entries()` en lugar de dos copias casi idénticas de la lógica de eliminación de direcciones duplicadas de anytls y page_proxy: dos lugares de uso y una función.

### iperf3 window lifecycle

1. El operador se autentica en la consola, selecciona una duración (10 minutos por defecto, limitada por `VPSSRV_IPERF_MAX_MINUTES`) y pulsa para abrir.
2. La consola inicia `iperf3 -s -p <port>` como proceso hijo, abre el puerto en el cortafuegos activo y guarda el plazo en memoria.
3. Mientras la ventana está abierta, la **página pública** muestra que iperf3 admite conexiones, en qué puerto y cuánto tiempo queda. El usuario remoto necesita esos datos y no son secretos: la ventana se abre deliberadamente.
4. Al llegar al plazo (o por petición del operador o al detenerse el servicio) termina el proceso hijo y se retira la regla del cortafuegos.

La ventana reside en memoria, no en disco: si el servicio termina, desaparece, lo que constituye el comportamiento seguro ante fallos. Reiniciar nunca restaura una ventana abierta.

La latencia se obtiene del `--json` de iperf3 (`mean_rtt` en el bloque de información TCP) del lado del cliente; no requiere código adicional en el servidor. El campo procede de `TCP_INFO` del kernel: aparece en un cliente Linux, pero no en uno que no pueda leerlo; iperf3 bajo Cygwin en Windows comunica la velocidad pero no `mean_rtt`. El modo UDP (`-u`) proporciona fluctuación y pérdida en todas las plataformas y es la alternativa portable cuando el cliente no usa Linux.

### Port forwarding lifecycle

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

- Mantener las rutas de la consola fuera de `ProbeHandler`: la autenticación no sustituye la tabla independiente de rutas públicas.
- Limitar iperf3 en el tiempo y retirar la regla del cortafuegos al cerrar o detener el servicio.
- Restaurar los reenvíos persistidos en JSON al arrancar el proceso; retirar las reglas activas al detenerlo limpiamente sin revertir el ajuste global `ip_forward` del servidor.
- Conservar credenciales de nodos y ajustes seleccionados al actualizar; utilizar los scripts propietarios para cambiarlas, fuera del aislamiento del sistema de archivos de la unidad web.
- No separar el bloqueo compartido `_db_lock` sin pruebas de latencia perjudicial: la medición histórica con 60 emisores simultáneos no mostró ralentización. Consulta [Errores][local-link-008].

## External Interfaces

- HTTP/HTTPS: las escuchas públicas en 80/443 solo exponen la página de accesibilidad; la consola del operador usa otro puerto persistente. iperf3 solo escucha durante una ventana autenticada de duración limitada.
- La consola lee `/proc/net/tcp[6]` para registrar conexiones TCP entrantes y no expone secretos de proxy en las rutas públicas.
- `install.sh` usa el gestor de paquetes de la distribución y, opcionalmente, consulta la IP pública durante la instalación; el servicio no hace solicitudes salientes mientras funciona. `setup-anytls.sh` y `setup-proxy.sh` administran unidades y certificados sing-box. iptables gestiona la apertura temporal de iperf3 y los reenvíos habilitados; systemd supervisa servicios y ejecuta los cambios de credenciales fuera del aislamiento web.

## Tech stack

| Capa | Elección | Versión | Motivo |
|---|---|---|---|
| Entorno | Python, solo biblioteca estándar | 3.9+ | Heredado de `vps-webserver`: no hay paquetes Python de terceros; el intérprete y bibliotecas de la distribución siguen necesitando actualizaciones de seguridad |
| Servidor HTTP | `http.server.ThreadingHTTPServer` | stdlib | Tres escuchas de unas pocas peticiones cada una; un framework añadiría peso innecesario |
| TLS | `ssl` + certificado autofirmado generado por `openssl` | stdlib / distro | Ni dominio ni ACME (consulta lo excluido) |
| Almacenamiento | `sqlite3` | stdlib | El registro de visitantes **DEBE** sobrevivir a los reinicios |
| Motor de velocidad | LibreSpeed, incluido sin cambios | v6.2.1 | LGPL-3.0; ya estaba incluido y funcionaba en `vps-webserver` |
| Generación de QR | kazuhikoarase/qrcode-generator, incluido sin cambios | js2.0.4 | MIT; pequeño, sin compilación, usa una etiqueta `<script>` como LibreSpeed |
| Sonda de ancho de banda | `iperf3` de la distribución | este proyecto no fija la versión | Herramienta de referencia que los usuarios ya tienen en el cliente |
| Núcleo proxy | sing-box, binario incluido (amd64) | v1.13.14 | GPL-3.0; incluir el binario permite instalar sin acceder al origen |
| Inicio | systemd | — | Predeterminado del SO de destino |
| Instalador | Bash | — | Heredado de ambos proyectos de origen |

Las alternativas descartadas y el razonamiento de cada elección están en [Decisiones][local-link-009]; no se repiten aquí.

## Reproduction requirements

### Environment

- SO: Debian 11+ / Ubuntu 20.04+, systemd; ejecutar como root.
- Entorno: Python 3.9+ (basta el python3 de la distribución).
- Arquitectura: **solo x86-64** para los módulos anytls y proxy; ambos utilizan el mismo binario sing-box amd64 incluido. Los módulos web e iperf3 no dependen de la arquitectura.
- Hardware: sin GPU; unos 150 MB de disco (de los cuales unos 57 MB corresponden al binario sing-box); la cantidad de RAM habitual de un VPS.
- Comprobación de integridad de los archivos incluidos: desde la raíz del repositorio, ejecutar `python3 tools/verify_dependencies/verify_dependencies.py`. Compara mediante SHA-256 los cinco archivos de distribución de terceros registrados con [dependencies.lock.json][local-link-010] sin ejecutarlos. Los campos de versión y revisión de origen proceden de registros anteriores del proyecto, no de una comprobación independiente de su identidad original. No se registra la revisión original exacta de LibreSpeed.
- No existe un bloqueo de paquetes de Python de terceros porque `app.py` usa la biblioteca estándar. Este archivo de bloqueo de artefactos no es un comando para restaurar dependencias ni un bloqueo completo de paquetes del sistema; consulta [THIRD_PARTY_NOTICES.md][local-link-011].

### External dependencies

| Elemento | Origen | Ubicación |
|---|---|---|
| `iperf3` | gestor de paquetes de la distribución (`apt-get install iperf3`) | ruta del sistema |
| `openssl`, `curl`, `jq`, `iproute2`, `procps`, `iptables`, `ca-certificates` | gestor de paquetes de la distribución o instalación existente en el servidor | ruta del sistema |
| binario sing-box | incluido en este repositorio | `/usr/local/bin/sing-box-vps-server` |
| motor LibreSpeed y biblioteca qrcode-generator | incluidos en este repositorio | `$PREFIX/static/` |
| certificados TLS | generados durante la primera ejecución por el instalador | `$VPSSRV_CERT_DIR` |

El instalador incorpora los paquetes del sistema que falten (incluido `iperf3` opcional) desde los repositorios Debian/Ubuntu de destino, sin seleccionar versiones exactas ni instantáneas de repositorios. Python, OpenSSL, las herramientas del sistema y shell y systemd también los proporciona el SO de destino. El operador depende de los canales de paquetes de la distribución elegida, mantenidos con actualizaciones de seguridad. Esto evita incluir sus binarios, pero versiones, hashes y resolución transitiva pueden variar entre servidores y fechas; **no se consigue una
restauración de dependencias estrictamente reproducible**. Conseguirla exigiría un cambio de instalador aprobado por separado y seleccionar una instantánea de distribución/repositorio. El campo `exclusions` del bloqueo, legible por máquina, registra este límite, no una fijación ficticia.

Sin claves de API. El servicio web no consulta la IP pública fuera de la máquina durante la ejecución. El instalador puede hacer una consulta saliente opcional; su fallo solo advierte.

### Paths & mounts

| Ruta | Proporcionada por | Propósito |
|---|---|---|
| `$PREFIX` | instalador; por defecto `/opt/vps-server` | Código, recursos estáticos y archivos de puertos persistentes |
| `$VPSSRV_DATA_DIR` | instalador; por defecto `$PREFIX/data` | `visitors.db`, `session_secret.txt`, `portfwd.json` |
| `$VPSSRV_CERT_DIR` | instalador; por defecto `$PREFIX/certs` | Certificado autofirmado y clave para 443 |
| `/etc/vps-server-anytls/` | instalador | `config.json` de sing-box y su certificado autofirmado |
| `/etc/vps-server-proxy/` | instalador | `config.json` de sing-box (hasta 4 entradas) y su certificado autofirmado |

### Configuration reference

Todas las variables usan el prefijo `VPSSRV_`. No es una cuestión estética: `vps-webserver` utiliza `VPSWS_` y `Anytsl-Serve` utiliza `ANYTLS_`, y los tres pueden estar instalados en el mismo servidor; un prefijo compartido permitiría que el `.env` de un proyecto reconfigurase silenciosamente otro.

| Variable | Significado | Predeterminado | Obligatoria |
|---|---|---|---|
| `PREFIX` | Raíz de instalación. Se pasa a `install.sh`/`uninstall.sh`, **no** se lee de `.env`: la ruta se necesita antes de disponer de una instalación de la que leer `.env` | `/opt/vps-server` | no |
| `VPSSRV_DATA_DIR` | SQLite y secreto de sesión | `$PREFIX/data` | no |
| `VPSSRV_HOST` | Dirección de escucha de todas las conexiones | `0.0.0.0` | no |
| `VPSSRV_PUBLIC_HTTP_PORT` | Página pública de accesibilidad sin cifrar | `80` | no |
| `VPSSRV_PUBLIC_HTTPS_PORT` | Página pública de accesibilidad, TLS | `443` | no |
| `VPSSRV_PUBLIC_ENABLE` | Habilitar la página pública | `1` | no |
| `VPSSRV_CONSOLE_PORT` | Puerto de consola; `0` = generar uno y conservarlo | `0` | no |
| `VPSSRV_CONSOLE_PORT_FILE` | Archivo donde se conserva el puerto generado de la consola | `$PREFIX/console_port.txt` | no |
| `VPSSRV_CONSOLE_TLS` | Servir la consola mediante HTTPS | `0` | no |
| `VPSSRV_AUTH` | Exigir inicio de sesión en la consola | `1` | no |
| `VPSSRV_PASSWORD_FILE` | Contraseña en texto claro de la consola, editable por el operador | `$PREFIX/admin_password.txt` | no |
| `VPSSRV_CERT_DIR` | Ubicación del certificado autofirmado | `$PREFIX/certs` | no |
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
| `VPSSRV_DEFAULT_LANG` | `en` / `zh_cn` / `zh_tw` / `zh_hk` / `hi` / `es` / `ar` / `fr` | `en` | no |
| `ANYTLS_PORT`, `ANYTLS_PASSWORD`, `SNI`, `SERVER_IP` | El módulo anytls conserva los nombres originales | consulta `.env.example` | no |
| `VPSSRV_ANYTLS_CONFIG` | Ruta donde la consola lee el nodo instalado | `/etc/vps-server-anytls/config.json` | no |
| `VPSSRV_ANYTLS_SERVICE` | Unidad cuya actividad del nodo consulta la consola | `vps-server-anytls.service` | no |
| `VPSSRV_ANYTLS_SETUP` | Script que ejecuta la consola para cambiar las credenciales del nodo | `$PREFIX/anytls/setup-anytls.sh` | no |
| `PROXY_PROTOCOLS`, `PROXY_SNI`, `SERVER_IP` | Ajustes del script del módulo proxy: código propio, sin obligación de compatibilidad con código incluido de terceros, pero sin prefijo para mantener la distinción entre script y consola de anytls | consulta `.env.example` | no |
| `VPSSRV_PROXY_CONFIG` | Ruta donde la consola lee el conjunto de nodos instalados | `/etc/vps-server-proxy/config.json` | no |
| `VPSSRV_PROXY_SERVICE` | Unidad cuya actividad del nodo consulta la consola | `vps-server-proxy.service` | no |
| `VPSSRV_PROXY_SETUP` | Script que ejecuta la consola para cambiar las credenciales del protocolo elegido | `$PREFIX/proxy/setup-proxy.sh` | no |

El módulo anytls conserva deliberadamente los nombres de variables de `Anytsl-Serve` en lugar de cambiarlos a `VPSSRV_ANYTLS_*`: los lee el generador de configuración incluido, y renombrarlos supondría modificar código de terceros incluido, precisamente lo que la política de inclusión intenta evitar.

## Setup from scratch

1. Ejecuta `git clone <repo>` y entra con `cd`: comprueba que `ls -lh third_party/sing-box/sing-box` muestre un archivo de unos 57 MB.
2. Ejecuta `bash deploy/install.sh`: en modo interactivo se inicia un asistente temporal en el navegador para elegir módulos, idioma de la interfaz, autenticación de la consola y puertos. Abre la URL mostrada e introduce el token de un solo uso; después de aplicar la selección validada, comprueba que el resumen de la terminal indique cada módulo y su puerto.
3. Ejecuta `systemctl status vps-server-web`: comprueba que indique `active (running)`.
4. Desde otra máquina, abre `http://<ip>/`: comprueba que aparece la página de accesibilidad y muestra tu propia IP de origen.
5. Desde otra máquina, abre `https://<ip>/` y acepta la advertencia del certificado: comprueba que aparece la misma página y la línea del protocolo dice HTTPS.
6. Abre `http://<ip>:<console port>/` e inicia sesión: comprueba que se carga el panel y el control de iperf3 indica que la ventana está cerrada.
7. Abre desde la consola una ventana iperf3 de 5 minutos y ejecuta desde otra máquina `iperf3 -c <ip> -p 5201 --json`: comprueba que comunica la velocidad e incluye `mean_rtt`.
8. Si se instaló el módulo anytls: ejecuta `systemctl status vps-server-anytls` y comprueba que indique `active (running)`; el resumen del instalador debe haber mostrado una línea de configuración del cliente.

## Data Design

La base de datos de visitantes y `portfwd.json` (reglas de reenvío habilitadas) permanecen en `$VPSSRV_DATA_DIR`. La contraseña de la consola, el puerto elegido, los certificados web y `.install-state` residen en `$PREFIX`; las configuraciones de los módulos sing-box y sus certificados residen en `/etc/vps-server-anytls/` y `/etc/vps-server-proxy/`. Consulta [Rutas y montajes][local-link-012]. El plazo de iperf3 permanece en memoria y no sobrevive a un reinicio.

### Data model / file layout

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
    │   ├── anytls/setup-anytls.sh
    │   ├── proxy/setup-proxy.sh
    │   ├── frps/setup-frps.sh
    │   └── lucky/setup-lucky.sh
    ├── static/                # first-party UI assets and vendored browser libraries
    │   └── third_party/
    │       ├── librespeed/    # speedtest.js, speedtest_worker.js
    │       └── qrcode/        # qrcode.js, qrcode-utf8.js
    ├── lang/                  # interface catalogs for web, installers, and tools
    ├── third_party/sing-box/
    │   ├── sing-box           # vendored amd64 binary
    │   ├── sing-box.version   # binary version metadata
    │   └── LICENSE            # original upstream notice
    ├── tools/verify_dependencies/verify_dependencies.py # checks config/dependencies.lock.json from repo root
    ├── config/dependencies.lock.json
    ├── config/upstream-version # records: vps-webserver v0.4.1
    ├── deploy/anytls/.upstream-version # records: Anytsl-Serve v1.2.0
    ├── tests/
    ├── LICENSE                # GPL-3.0
    └── doc/
        ├── DESIGN.md          # architecture, constraints, and tracked goals
        ├── LOG.md             # bugs, dated decisions, verification, release history
        ├── THIRD_PARTY_NOTICES.md
        └── <lang>/            # translated docs (seven language directories)
```

Estas rutas corresponden solo al repositorio: la instalación sigue usando `$PREFIX/app.py`, `$PREFIX/sing-box` y `$PREFIX/static/`. Las URL HTTP de los recursos no cambian. `app.py`, `install.sh` y `uninstall.sh` siguen siendo puntos de entrada en la raíz.

Solo `repo/` está bajo control de Git; `snapshots/` está separado y es privado. Empieza por [README][local-link-013], consulta [LOG][local-link-014] para verificaciones históricas e historial de versiones, y los [avisos de terceros][local-link-015] para conocer los archivos de origen. La documentación no convierte una instantánea ni un servidor instalado en un árbol de código reproducible.

El esquema SQLite se hereda sin cambios de `vps-webserver`: una tabla `visits` limitada a las 1000 filas más recientes. `portfwd.json` es una lista JSON plana de objetos de reglas (`id`, `label`, `protocol`, `public_port`, `target_host`, `target_port`, `enabled`, `created`); consulta `PortForwardManager` en `src/web/app.py`.

## Known limitations & gotchas

- **Para usar los puertos 80 y 443 se requiere root y que estén libres.** Si nginx, Apache, Caddy u otra instancia de `vps-webserver` ocupa cualquiera de ellos, el instalador se niega a disputar el puerto. Compruébalo con `ss -lntp '( sport = :80 or sport = :443 )'` antes de instalar.
- **La página pública es realmente pública.** Cualquiera que adivine o explore la IP puede verla; cada acceso queda en el registro de visitantes. Es la finalidad de la función, pero también significa que un registro asociado a una IP explorada se llena de tráfico de fondo de Internet en pocas horas.
- **Los nombres de las unidades difieren del proyecto original deliberadamente.** `Anytsl-Serve` instala `sing-box-anytls.service`; este proyecto instala `vps-server-anytls.service` y un binario con otro nombre, de modo que ambos puedan coexistir. El instalador aun así se niega a continuar si la unidad original funciona: dos entradas anytls en el mismo servidor casi siempre indican un error, no una decisión intencionada.
- **La versión de `iperf3` no está fijada.** Procede de la distribución y varía según su versión. El protocolo de red se ha mantenido estable en la serie 3.x, pero un cliente mucho más antiguo que el servidor puede fallar en la negociación de versiones.
- **Solo amd64 para anytls y proxy.** El binario incluido no sirve para varias arquitecturas; en arm64 el instalador omite el módulo con una explicación en vez de instalar un binario que no podría ejecutarse.
- **El TLS autofirmado provoca una advertencia del navegador en 443, siempre.** Es esperado y no conviene «solucionarlo» mediante excepciones ni una cabecera HSTS.
- **Reiniciar cierra cualquier ventana iperf3 abierta.** Es intencionado; consulta su ciclo de vida.
- **Detener el servicio retira todos los
reenvíos de puertos, incluso los habilitados.** Es intencionado y simétrico con la ventana iperf3; consulta el ciclo de vida del reenvío. `systemctl restart` o reiniciar el servidor los restaura inmediatamente; dejarlo detenido con `systemctl stop`, no.
- **`net.ipv4.ip_forward` se activa automáticamente y nunca se desactiva.** Es un ajuste de todo el servidor del que puede depender otro programa (Docker, por ejemplo); por ello, quitar el último reenvío no lo modifica. Desactívalo manualmente si ya no lo necesita ningún otro programa.
- **Un reenvío solo cubre el tráfico visible para `iptables` sin intermediarios.** Si `ufw` o `firewalld` está activo con su propia política `FORWARD` de denegación predeterminada, sus cadenas se evalúan antes de la regla que añade esta función y quizá también exijan una regla que permita ese puerto para que pase el tráfico.
- **El binario sing-box supera el tamaño recomendado por GitHub.** Con unos 55 MB excede el límite flexible de 50 MB, por lo que cada push muestra una advertencia «Large files detected» que recomienda Git LFS. Los envíos todavía funcionan; el límite estricto es 100 MB. Una actualización futura de sing-box podría superarlo y entonces habrá que tomar una decisión deliberada (LFS o dejar de incluir el binario), no descubrirlo por sorpresa al publicar.
- **Ejecuta los scripts con `bash <script>`, no con `./<script>`.** Git registra el bit de ejecución, por lo que una clonación nueva lo conserva; pero una copia de trabajo en un volumen CIFS/SMB no, y allí `./install.sh` falla con «Permission denied».
- **Volver a incorporar un ejecutable de un proyecto de origen pierde su bit de ejecución.** La copia de trabajo del mantenedor está en CIFS: un archivo extraído ahí y luego añadido con `git add` queda registrado como `100644` aunque el original fuese `100755`. Ya ocurrió una vez con el binario `sing-box` y dejó inservible todo el módulo anytls. Tras una nueva incorporación, comprueba con `git ls-files -s` y restaura el bit con `git update-index --chmod=+x <path>`; `chmod +x` por sí solo no tiene efecto en ese volumen.
- **Ejecutar `setup-anytls.sh` directamente cambia su puerto y contraseña.** Sus valores predeterminados para `ANYTLS_PORT` y `ANYTLS_PASSWORD` son nuevos valores aleatorios y reescribe `config.json` en cada ejecución; una ejecución manual invalida todos los clientes configurados con los valores previos. `install.sh` ya no lo hace: durante la actualización lee ambos valores de `config.json` y los pasa al script. Pero una ejecución directa sigue haciéndolo. Para conservar el nodo, facilita sus valores actuales, visibles en la sección anytls de `/proxy` en la consola: `ANYTLS_PORT=<current> ANYTLS_PASSWORD='<current>' bash deploy/anytls/setup-anytls.sh`. Es comportamiento original conservado deliberadamente. `setup-anytls.sh reset` cambia esos valores de forma intencionada y el botón de restablecimiento de la consola es la forma admitida de pedirlo.
- **El bloque de dirección pública de la
consola solo aparece si `SERVER_IP` se estableció explícitamente.** `get_ip()` utilizaba una consulta curl saliente como respaldo (`api.ip.sb` y luego `ifconfig.me`); se eliminó por completo (2026-09-22) porque, en el caso habitual de un VPS sin NAT, devolvía exactamente la misma dirección que ya indica `get_lan_ips()`, duplicando la IP en la página del nodo. En un equipo realmente detrás de NAT sin valor explícito, era peor: mostraba una dirección desde la que no se puede llegar a ese nodo sin un reenvío que el proyecto no puede confirmar. `public-ip.txt` (todavía escrito por `setup-anytls.sh`/`setup-proxy.sh`, todavía la única forma de evitar una consulta saliente al mostrar la página) solo existe ahora si el operador pasó `SERVER_IP`/el `PROXY_PROTOCOLS` asociado a `SERVER_IP`: un caso deliberado y conocido como correcto (por ejemplo, NAT con reenvío configurado realmente).
- **El `body` pasado a `render_page()`** **DEBE** contener exactamente un elemento de nivel superior. `<main>` usa `display: flex` sin cambiar `flex-direction`; con varios elementos hermanos superiores (por ejemplo, un `<div class="card wide">` por protocolo), se colocan en paralelo en vez de apilados. Fue un fallo real publicado en una versión anterior de `/proxy`, descrito por un operador como «layout is messed up». Todas las páginas envuelven su contenido en una sola tarjeta exterior y anidan las secciones repetidas como elementos `.node-addr` dentro de ella.
- **Para desinstalar se necesitan los mismos `PREFIX` y `SERVICE_NAME` usados al instalar.** `uninstall.sh` sin variables toma los valores predeterminados, no encuentra nada en esas rutas y comunica éxito sin quitar nada. La última línea del instalador imprime el comando exacto con los valores correspondientes: úsalo en lugar de escribirlo de memoria.

## Extension

### How to extend

- **Un módulo nuevo** (otro componente opcional del instalador): añade `deploy/<name>/setup-<name>.sh`, su unidad systemd (incluida en `deploy/systemd/` o generada por el script), una opción en el menú de módulos de `deploy/install.sh` y una rama de desinstalación en `deploy/uninstall.sh`. Los módulos no se invocan entre sí.
- **Una página nueva de consola**: añade una ruta a `ConsoleHandler`. No añadas rutas a `ProbeHandler`: su tabla casi vacía de rutas es una propiedad de seguridad, no un descuido.
- **Un idioma nuevo**: añade catálogos correspondientes en todos los directorios `lang/<component>/`, registra el código en el selector de idiomas web y el mapeo del historial de cambios, en el instalador, el asistente de configuración y los cargadores de los scripts de módulos; después añade el árbol correspondiente `doc/<BCP47>/`.
- **Un color nuevo**: añade un token a `:root` en `static/style.css` *y* un valor de modo claro en el bloque `prefers-color-scheme: light`, y después utiliza el token. Nunca escribas un color hexadecimal literal en una regla de componente: un literal no sigue el tema y será correcto en el modo para el que se eligió visualmente e incorrecto en el otro, sin que nada lo detecte. Todo fondo de color necesita un valor de primer plano `--on-*`: un color adecuado para el texto rara vez sirve también de fondo para texto blanco. Comprueba ambos modos frente a WCAG AA (4.5:1) antes de hacer commit; `tests/test_app.py::StylesheetTest` verifica la estructura, pero no puede juzgar la relación de contraste.
- **Actualizar un componente incluido de otro proyecto**: vuelve a copiar desde la etiqueta original, actualiza el archivo `.upstream-version` correspondiente en el mismo commit y anota la nueva versión en [LOG.md][local-link-016]. No modifiques el código incluido directamente sin registrar la desviación: un cambio local no reflejado en el origen causaría una regresión silenciosa en la siguiente actualización.

[local-link-001]: LOG.md#limitaciones-y-estado-actual-de-aceptación
[local-link-002]: LOG.md#errores
[local-link-003]: LOG.md#historial-del-trabajo-completado
[local-link-004]: LOG.md#decisiones
[local-link-005]: #the-proxy-module
[local-link-006]: LOG.md#decisiones
[local-link-007]: LOG.md#decisiones
[local-link-008]: LOG.md#errores
[local-link-009]: LOG.md#decisiones
[local-link-010]: ../../config/dependencies.lock.json
[local-link-011]: THIRD_PARTY_NOTICES.md
[local-link-012]: #paths-mounts
[local-link-013]: README.md
[local-link-014]: LOG.md
[local-link-015]: THIRD_PARTY_NOTICES.md
[local-link-016]: LOG.md#historial-de-cambios
