---
name: project-log-es
description: Decisiones, limitaciones, errores y cambios del proyecto
metadata:
  version: "1.0.0"
  lang: "es"
---

# vps-server — Registro

Este registro reúne errores conocidos, decisiones, trabajos anteriores, límites actuales de aceptación y cambios publicados. Las menciones a pruebas anteriores no significan que se hayan vuelto a ejecutar para esta migración documental.

## Multilingüe

[简体中文](../LOG.md) | [English](../en/LOG.md) | **Español**

## Documentación

- Descripción general del proyecto: [README](README.md)

- Justificación del diseño: [DESIGN](DESIGN.md)

- Estado del proyecto: [LOG](LOG.md)
- Registros históricos: [HISTORY](HISTORY.md)
- Historial de cambios: [CHANGELOG](CHANGELOG.md)

- Avisos de terceros: [THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES.md)

## Registros

- [Registros históricos](HISTORY.md)
- [Historial de cambios](CHANGELOG.md)

## Errores

- [x] 2026-10-04 [P1] La edición de FRPS siempre devolvía "Falló la actualización de FRP": el `PORTS.md` de la máquina de prueba solo tenía una entrada Web, sin entrada para el puerto FRPS actual. El auxiliar anterior exigía esa entrada antes de ejecutar el instalador, por lo que rechazaba tanto cambios de token como de puerto. El código registra el puerto FRPS actual bajo el bloqueo del registro, sigue rechazando entradas de otros servicios y revierte la nueva reserva si falla. Pasaron las comprobaciones aisladas y el operador comunicó después que las pruebas manuales pasaron; esta sesión no lo comprobó de forma independiente por SSH. La versión de corrección prevista es `v5.1.1`; aún no está publicada.

- [ ] 2026-10-04 [P1] Al borrar el antiguo directorio de instalación no se conservaron el puerto ni parte del estado: el operador confirmó que borró el viejo `$PREFIX` antes de copiar el código fuente y que no tenía copia de seguridad. El puerto anterior de la consola ya no responde; la contraseña anterior aún no se ha probado. La disposición antigua guardaba la contraseña administrativa, el puerto aleatorio, los certificados y `data/` en `$PREFIX`. El instalador podía detectar la unidad systemd restante como instalación existente y generar de nuevo el estado ausente. El código fuente no puede recuperar datos borrados sin copia. Se prevé que v5.1.1 use una raíz de estado independiente y rechace la instalación si falta estado esencial; aún no se han aceptado en la máquina de prueba ni una instalación nueva ni una reinstalación posterior.

- [x] 2026-10-04 La desinstalación completa omitía datos de instancias FRPC y entradas en `PORTS.md`. Tras la primera corrección `3335a7f`, el operador reprodujo que la plantilla antigua sin marca de titularidad se clasificaba como `unowned` y conservaba configuraciones y entradas; la consola volvía a mostrar clientes antiguos después de instalar solo Web. El código `01b76ba` limpia la plantilla antigua si encuentra instancias reconocibles; pasó una comprobación local aislada. El operador confirmó el resultado en el servidor de prueba; la versión de corrección es `v5.1.0`. Esta sesión no comprobó el servidor de manera independiente.
- [x] 2026-10-04 [P1] Una contraseña de administrador no ASCII podía guardarse pero impedía iniciar sesión. `src/web/features/auth.py` aceptaba caracteres chinos en `change_admin_password`, mientras que la verificación anterior llamaba a `hmac.compare_digest` con cadenas y lanzaba TypeError. El código compara bytes UTF-8 y conserva la validación y la invalidación de sesiones. El operador confirmó el inicio de sesión; corregido en `v5.1.0`.
- [x] 2026-10-04 [P1] El reinicio periódico del tráfico no reconstruía la cuota del kernel: en la versión anterior de `src/web/node_meter.py`, la huella de política no incluía el período. Una comprobación aislada reprodujo que una cuota de 1000 bytes, tras consumir 600 y reiniciarse, mantenía la misma huella. El código reconstruye la cuota al cambiar de período; el operador confirmó los nodos y su tráfico. Corregido en `v5.1.0`.
- [ ] 2026-10-04 [P1] La compatibilidad con Python 3.9 aún no se ha probado en ese intérprete. El antiguo `src/web/node_inventory.py` usaba `int | None` sin posponer la evaluación, en contra del requisito 3.9+ de README. El código ya pospone las anotaciones; aquí solo se confirmaron la sintaxis y la importación en una versión más nueva. Falta comprobar la instalación y el inicio Web en un entorno Python 3.9.
- [x] 2026-10-04 [P2] Un fallo al aplicar un reenvío podía comunicarse como éxito: el antiguo add/set_enabled/load ignoraba el False devuelto por `portfwd_rule_apply` y una prueba aislada dejó enabled=true. El código ahora revierte o informa del fallo; el operador confirmó el reenvío de puertos. Corregido en `v5.1.0`.
- [x] 2026-10-04 [P2] Antes, `_dispatch` devolvía un 500 genérico sin registrar la excepción y se perdía el error del auxiliar de nodos. El código registra etapas y tipos de error sin credenciales y conserva el mensaje genérico para el cliente; pasó una comprobación local aislada. Corregido en `v5.1.0`. No se han probado fallos reales de este tipo.
- [ ] 2026-09-12 Decidir si es necesario separar el bloqueo compartido `_db_lock`: cada visita pública escribe en SQLite mientras lo mantiene y la consola comparte ese bloqueo. **No se reprodujo un retraso perjudicial**: con 60 solicitudes simultáneas la latencia de la consola siguió entre 0.4 y 0.6 ms, igual que en reposo. Conservar la observación evita rediseñar sin pruebas de perjuicio.

Quedan por verificar la instalación y reinstalación de la nueva disposición de estado en la máquina de destino, la instalación y el inicio Web en Python 3.9 y la posible incidencia de rendimiento aún no demostrada del bloqueo `_db_lock`. El estado de las ramas históricas figura en [HISTORY](HISTORY.md).

## Limitaciones

- Las comprobaciones automáticas verifican las claves de los catálogos, los marcadores de posición y la estructura documental; las traducciones nuevas no tienen todavía una revisión independiente por hablantes nativos.
- Los originales chinos y las traducciones anteriores de cuatro documentos principales ocupaban rutas distintas antes de la migración. No se pudo reconstruir una base íntegra de sincronización; en esta versión se sincronizan de nuevo inglés y español con el texto chino vigente; el siguiente cambio retomará la traducción incremental desde este commit. Las antiguas traducciones de otros idiomas y los registros exclusivos del inglés se conservan en Git; su límite histórico consta en [HISTORY](HISTORY.md).
- En la estandarización del 2026-10-03, los datos ignorados por Git y cachés antiguos se trasladaron sin modificar a `private/local-runtime-prestandardization-20261003/`. En montajes CIFS que fuerzan 0644 para archivos y 0755 para directorios, `chmod` no cambia los permisos visibles de secretos locales: comprueba por separado el control de acceso del montaje.
- El iperf3 3.22 incluido se compiló desde el código original y se verificó como ELF estático con `--version` en Ubuntu 22.04 x86-64. Quedan sin aceptar la resolución de nombres y el tráfico TCP/UDP real en Debian 11 y Ubuntu 20.04. La compilación excluye SCTP y autenticación OpenSSL.
- FRPC, FRPS e iperf3 se pueden instalar sin conexión desde el código fuente completo. Si faltan paquetes básicos como Python, OpenSSL o nftables, los demás módulos aún pueden necesitar los repositorios de la distribución.
- `third_party/frp/frpc` mide 16,593,080 bytes y su blob es `e2a8dc5b1bd2d995ec49896d20e1b2a4a8252ada`. Antes de esta tarea ya era accesible en el `origin/main` público, revisión `f306f6e`. No se modificó en esta tarea; se conserva para la instalación sin conexión ya aceptada. Los archivos grandes nuevos o modificados deberán seguir el flujo de recursos de GitHub Release.
- Los límites de aceptación en un servidor real de la rama actual figuran en el traspaso enlazado abajo.

## Decisiones

<a id="vps-decisions"></a>

Las decisiones fechadas conservan tanto las alternativas descartadas como sus costes. Una decisión histórica no constituye una nueva aprobación legal ni de publicación.

| Decisiones | Motivos, alternativas descartadas y costes |
| --- | --- |
| 2026-10-04 — v5.1.1 establece la disposición `1` del estado persistente | Las nuevas instalaciones guardan contraseña, puerto, certificados, datos de ejecución, registro de instalación y `.env` en `/var/lib/vps-server`; las versiones posteriores seguirán leyendo esta disposición. El instalador rechazará una disposición antigua o la ausencia de estado esencial antes de modificar servicios, sin generar valores de sustitución. **Descartado:** migrar automáticamente los directorios de v5.1.0 y versiones anteriores; el operador pidió compatibilidad a partir del estándar nuevo, sin compatibilidad anterior a él. **Coste:** las instalaciones antiguas requieren copia de seguridad y una nueva instalación expresa; los datos borrados sin copia no pueden recuperarse. |
| 2026-10-03 — Se retiró `tests/` y el operador acepta las funciones manualmente | El operador pidió retirar la suite automática y revisar y simplificar el código; se borró `tests/` tanto del código fuente como de la instalación de prueba. Los cambios ya no se protegen con las antiguas pruebas unitarias; hay que seguir ejecutando las comprobaciones de estructura, sintaxis y construcción y aceptar manualmente cada módulo habilitado. Las pruebas antiguas pueden recuperarse desde Git. |
| 2026-09-22 — `proxy` es un único proceso sing-box con hasta cuatro entradas, no cuatro clones de anytls | - **Resuelto, no descartado:** se confirmó que el binario sing-box incluido cubre vmess/vless/trojan/shadowsocks ejecutando realmente los cuatro a la vez en un proceso, no solo con `sing-box check`; no hace falta otro backend. Se probaron y descartaron hysteria2/tuic (requisitos distintos de campos y TLS). - **Descartado:** una unidad systemd y una configuración por protocolo, reproduciendo exactamente la estructura de anytls: supondría vigilar cuatro unidades, tres certificados autofirmados redundantes y dificultaría una futura función de contabilización de tráfico por nodo (un proceso cuya lista `inbounds` ya es la lista de nodos). - **Coste:** dos módulos independientes usan ahora el binario incluido compartido; el `uninstall()` de cada uno **DEBE** comprobar si existe la configuración del otro antes de borrarlo (el script incluido de anytls incorporó este cambio local documentado; véase `anytls/.upstream-version`). |
| 2026-09-21 — `prompt_new_settings()` termina con un `return 0` explícito, no simplemente al salir del bucle | - **Descartado:** dejar que el código de salida de la función proceda de su último bucle `for`, como ocurre con la mayoría de las demás funciones de `install.sh`: su última instrucción era `[ -n "$value" ] && export ...`, por lo que dejar el *último* ajuste solicitado con su valor predeterminado hacía que esa comprobación devolviera falso y ese se convirtiera en el estado de salida de la función. Invocada directamente (`prompt_new_settings` dentro del cuerpo de un `if`, sin estar ella misma exenta de `set -e`), interrumpía silenciosamente todo el instalador justo después de la última pregunta: sin error, copia de archivos, sello `VERSION` ni reinicio del servicio. Se reprodujo en un sistema real al pasar de v1.0.4 a v1.1.1 y se corrigió encerrando la exportación en `if`/`fi` y añadiendo al final un `return 0` explícito; así, el resultado de la función deja de depender del último ajuste preguntado. - **No eliminar el `return 0` final por parecer código innecesario.** Es la corrección, no código de plantilla. |
| 2026-09-19 — Los reenvíos de puertos usan DNAT de iptables y se reaplican desde JSON en cada arranque; nada se escribe fuera del proceso | - **Descartado:** un repetidor `socat` en espacio de usuario por regla, más seguro (sin modificar la tabla NAT ni `ip_forward`), porque el usuario eligió expresamente DNAT+MASQUERADE en el núcleo para este proyecto. - **Descartado:** `iptables-persistent` para mantener las reglas en el núcleo tras reiniciar; convertiría la consola y un paquete del sistema en dos fuentes de verdad para las mismas reglas. En cambio, `app.py` las reaplica desde su propio JSON en cada arranque (DESIGN.md, «Port forwarding lifecycle»), dejando una sola fuente. - **Descartado:** restablecer automáticamente `net.ipv4.ip_forward` a `0` tras eliminar el último reenvío; afecta a todo el servidor y puede que otros programas (el propio servidor de pruebas de este proyecto ejecuta Docker) necesiten mantenerlo activado. - **Coste:** detener `vps-server-web` (no reiniciarlo) retira del núcleo todos los reenvíos, incluso los habilitados, en la misma dirección de seguridad que la ventana iperf3. No trasladar las reglas a una unidad independiente siempre activa para «arreglar» esto; ya se consideró y descartó. |
| 2026-09-12 — La página pública y la consola tienen escuchas y clases de manejadores separadas | - **Descartado:** una única escucha para ambas, con rutas de consola detrás de un prefijo y una comprobación de autenticación; una comprobación puede contener errores que permitan pasar, pero una ruta inexistente no. - **Descartado:** colocar la consola en 80/443 protegida por contraseña y eliminar el puerto aleatorio; perdería la capa de ocultación elegida expresamente por `vps-webserver`. - **Coste:** tres escuchas en un proceso y dos clases de manejadores en las que conectar por separado el registro de visitantes. - **No volver a proponer esto como mejora.** |
| 2026-09-12 — iperf3 solo funciona durante una ventana temporal abierta por el operador | - **Descartado:** un `iperf3 -s` público siempre activo; cualquier desconocido podría saturar indefinidamente el enlace de salida sin que nada lo señale. - **Descartado:** mantenerlo activo con autenticación RSA `--authorized-users-path`; las credenciales tendrían que entregarse por otro canal antes de probar, contrario a «darle a alguien la IP y dejar que mida». - **Coste:** quien pruebe desde fuera no puede hacerlo sin atención; alguien tiene que abrir antes la ventana. La página pública anuncia la ventana abierta para indicar cuándo conectarse. |
| 2026-09-12 — El puerto 443 usa un certificado autofirmado; sin ACME ni dominio | - **Descartado:** certbot / acme.sh con un dominio real: la página responde «¿puedes acceder a esta IP?» y una advertencia del navegador ya demuestra que es accesible. Depender de un dominio y programar renovaciones no aporta nada a esa pregunta. - **Descartado:** servir solo en el puerto 80; no permitiría distinguir «no se puede acceder al servidor» de «el 443 está bloqueado concretamente», el caso habitual que interesa detectar. - **Coste:** todas las visitas HTTPS presentan una advertencia de certificado. Es lo esperado; no «corregirlo» con HSTS ni una excepción fijada. |
| 2026-09-12 — El binario sing-box se distribuye en el repositorio, por lo que todo el proyecto es GPL-3.0 | - **Descartado:** descargar sing-box durante la instalación para reducir el tamaño del repositorio y mantener la licencia Apache-2.0: `Anytsl-Serve` ya había descartado exactamente eso para permitir instalar sin acceso a GitHub; replantearlo aquí anularía silenciosamente ese objetivo. - **Descartado:** quitar el módulo anytls para conservar Apache-2.0 de `vps-webserver`; el encargo consistía en combinar ambos proyectos, no elegir uno. - **Coste:** unos 57 MB en git, que aumentan con cada actualización de sing-box; y el código Apache-2.0 de `vps-webserver` se redistribuye aquí bajo GPL-3.0. |
| 2026-09-12 — Los proyectos originales se incluyen como código de terceros, sin sustituirlos ni usarlos como submódulos | - **Descartado:** sustituir `vps-webserver` y `Anytsl-Serve` por vps-server y archivar ambos; los tres deben mantenerse y publicarse de forma independiente. - **Descartado:** submódulos git apuntando a los dos repositorios originales; un submódulo no permite los cambios de nombre que necesita este proyecto (unidades, nombre del binario, `VPSWS_` → `VPSSRV_`) y una clonación requeriría acceso de red a otros dos repositorios. - **Coste:** el mismo código vive en tres repositorios y divergirá. Mitigación: los archivos `.upstream-version` indican la etiqueta exacta de origen de cada árbol incluido y **DEBEN** actualizarse en el mismo commit que cualquier renovación. |

<a id="development-updates"></a>

## Actualizaciones de desarrollo

- La edición de FRPS registra el puerto actual del proyecto si falta su entrada en `PORTS.md`, sigue rechazando puertos asignados a otros servicios y elimina la nueva reserva si falla un cambio de puerto. El operador comunicó que pasó la prueba manual de esta corrección.
- La contraseña, el puerto de la consola, los certificados, los datos de ejecución y el registro de instalación de una nueva instalación pasan a `/var/lib/vps-server`. Las versiones posteriores conservan la disposición `1`; no se migran automáticamente las disposiciones antiguas y el instalador se detiene antes de modificar servicios cuando falta estado esencial.
- La nueva disposición de estado solo ha pasado comprobaciones locales aisladas; siguen pendientes de aceptación en la máquina de destino la instalación nueva, la reinstalación tras reemplazar el directorio del programa y la desinstalación, el entorno de ejecución Python 3.9, la recuperación tras reiniciar el servidor y los dispositivos móviles reales.

## Traspaso

La rama de publicación actual, el trabajo terminado, las comprobaciones, los pasos de publicación pendientes y la siguiente acción se mantienen en el [traspaso actual del LOG.md en chino simplificado](../LOG.md#交接).
