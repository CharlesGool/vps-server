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

[简体中文](../LOG.md) | [English](../en/LOG.md) | [繁體中文(台灣)](../zh-TW/LOG.md) | [繁體中文(香港)](../zh-HK/LOG.md) | [हिन्दी](../hi/LOG.md) | **Español** | [العربية](../ar/LOG.md) | [Français](../fr/LOG.md)

## Documentación

- Descripción general del proyecto: [README](README.md)

- Justificación del diseño: [DESIGN](DESIGN.md)

- Estado del proyecto: [LOG](LOG.md)
- Registros históricos: [HISTORY](HISTORY.md)
- Historial de cambios: [CHANGELOG](CHANGELOG.md)
- Historial de commits: [COMMITS](COMMITS.md)

- Avisos de terceros: [THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES.md)

## Registros

- [Registros históricos](HISTORY.md)
- [Historial de cambios](CHANGELOG.md)
- [Historial de commits](COMMITS.md)

## Errores

- [ ] 2026-09-12 Decidir si es necesario desacoplar el `_db_lock` compartido: cada acceso a la página pública toma un bloqueo global del proceso y realiza una escritura síncrona en SQLite; la consola comparte ese bloqueo, por lo que, en principio, una avalancha de solicitudes anónimas podría ralentizar una página autenticada. **Se midió y no se reprodujo**: 60 clientes simultáneos enviando solicitudes dejaron la latencia de la consola en 0.4–0.6 ms, igual que en reposo. Se registra para no redescubrir el mecanismo como novedad; no rediseñar sin una medición que demuestre perjuicio.

La anterior instantánea de estado no registraba otros problemas que impidieran el funcionamiento; los casos límite de señales durante el arranque y el apagado, la combinación del instalador con solo iperf3 y la limitación de intentos de inicio de sesión se corrigieron en `feat/hardening-batch`, aún pendiente de integración y revisión. Esto no afirma que la rama actual se haya vuelto a validar en un servidor real.

## Limitaciones

- Las comprobaciones automatizadas verifican las claves de los catálogos, los marcadores de posición y la estructura de los documentos, pero las nuevas traducciones todavía no han recibido una revisión independiente por hablantes nativos.
- Durante la estandarización del 2026-10-03, los datos de ejecución y cachés antiguos ignorados por Git se trasladaron sin cambios desde la raíz del código a `private/local-runtime-prestandardization-20261003/`; el árbol de trabajo actual supera la comprobación de estructura. Si un montaje CIFS presenta los archivos siempre con modo 0644 y los directorios con 0755, `chmod` no cambia el modo visible de los archivos secretos locales; evalúe por separado el control de acceso del montaje.
- Los límites actuales de aceptación de esta rama en un servidor real se documentan más abajo.

## Decisiones

<a id="vps-decisions"></a>

Las decisiones fechadas conservan tanto las alternativas descartadas como sus costes. Una decisión histórica no constituye una nueva aprobación legal ni de publicación.

| Decisiones | Motivos, alternativas descartadas y costes |
| --- | --- |
| 2026-09-22 — `proxy` es un único proceso sing-box con hasta cuatro entradas, no cuatro clones de anytls | - **Resuelto, no descartado:** se confirmó que el binario sing-box incluido cubre vmess/vless/trojan/shadowsocks ejecutando realmente los cuatro a la vez en un proceso, no solo con `sing-box check`; no hace falta otro backend. Se probaron y descartaron hysteria2/tuic (requisitos distintos de campos y TLS). - **Descartado:** una unidad systemd y una configuración por protocolo, reproduciendo exactamente la estructura de anytls: supondría vigilar cuatro unidades, tres certificados autofirmados redundantes y dificultaría una futura función de contabilización de tráfico por nodo (un proceso cuya lista `inbounds` ya es la lista de nodos). - **Coste:** dos módulos independientes usan ahora el binario incluido compartido; el `uninstall()` de cada uno **DEBE** comprobar si existe la configuración del otro antes de borrarlo (el script incluido de anytls incorporó este cambio local documentado; véase `anytls/.upstream-version`). |
| 2026-09-21 — `prompt_new_settings()` termina con un `return 0` explícito, no simplemente al salir del bucle | - **Descartado:** dejar que el código de salida de la función proceda de su último bucle `for`, como ocurre con la mayoría de las demás funciones de `install.sh`: su última instrucción era `[ -n "$value" ] && export ...`, por lo que dejar el *último* ajuste solicitado con su valor predeterminado hacía que esa comprobación devolviera falso y ese se convirtiera en el estado de salida de la función. Invocada directamente (`prompt_new_settings` dentro del cuerpo de un `if`, sin estar ella misma exenta de `set -e`), interrumpía silenciosamente todo el instalador justo después de la última pregunta: sin error, copia de archivos, sello `VERSION` ni reinicio del servicio. Se reprodujo en un sistema real al pasar de v1.0.4 a v1.1.1 y se corrigió encerrando la exportación en `if`/`fi` y añadiendo al final un `return 0` explícito; así, el resultado de la función deja de depender del último ajuste preguntado. - **No eliminar el `return 0` final por parecer código innecesario.** Es la corrección, no código de plantilla. |
| 2026-09-19 — Los reenvíos de puertos usan DNAT de iptables y se reaplican desde JSON en cada arranque; nada se escribe fuera del proceso | - **Descartado:** un repetidor `socat` en espacio de usuario por regla, más seguro (sin modificar la tabla NAT ni `ip_forward`), porque el usuario eligió expresamente DNAT+MASQUERADE en el núcleo para este proyecto. - **Descartado:** `iptables-persistent` para mantener las reglas en el núcleo tras reiniciar; convertiría la consola y un paquete del sistema en dos fuentes de verdad para las mismas reglas. En cambio, `app.py` las reaplica desde su propio JSON en cada arranque (DESIGN.md, «Port forwarding lifecycle»), dejando una sola fuente. - **Descartado:** restablecer automáticamente `net.ipv4.ip_forward` a `0` tras eliminar el último reenvío; afecta a todo el servidor y puede que otros programas (el propio servidor de pruebas de este proyecto ejecuta Docker) necesiten mantenerlo activado. - **Coste:** detener `vps-server-web` (no reiniciarlo) retira del núcleo todos los reenvíos, incluso los habilitados, en la misma dirección de seguridad que la ventana iperf3. No trasladar las reglas a una unidad independiente siempre activa para «arreglar» esto; ya se consideró y descartó. |
| 2026-09-12 — La página pública y la consola tienen escuchas y clases de manejadores separadas | - **Descartado:** una única escucha para ambas, con rutas de consola detrás de un prefijo y una comprobación de autenticación; una comprobación puede contener errores que permitan pasar, pero una ruta inexistente no. - **Descartado:** colocar la consola en 80/443 protegida por contraseña y eliminar el puerto aleatorio; perdería la capa de ocultación elegida expresamente por `vps-webserver`. - **Coste:** tres escuchas en un proceso y dos clases de manejadores en las que conectar por separado el registro de visitantes. - **No volver a proponer esto como mejora.** |
| 2026-09-12 — iperf3 solo funciona durante una ventana temporal abierta por el operador | - **Descartado:** un `iperf3 -s` público siempre activo; cualquier desconocido podría saturar indefinidamente el enlace de salida sin que nada lo señale. - **Descartado:** mantenerlo activo con autenticación RSA `--authorized-users-path`; las credenciales tendrían que entregarse por otro canal antes de probar, contrario a «darle a alguien la IP y dejar que mida». - **Coste:** quien pruebe desde fuera no puede hacerlo sin atención; alguien tiene que abrir antes la ventana. La página pública anuncia la ventana abierta para indicar cuándo conectarse. |
| 2026-09-12 — El puerto 443 usa un certificado autofirmado; sin ACME ni dominio | - **Descartado:** certbot / acme.sh con un dominio real: la página responde «¿puedes acceder a esta IP?» y una advertencia del navegador ya demuestra que es accesible. Depender de un dominio y programar renovaciones no aporta nada a esa pregunta. - **Descartado:** servir solo en el puerto 80; no permitiría distinguir «no se puede acceder al servidor» de «el 443 está bloqueado concretamente», el caso habitual que interesa detectar. - **Coste:** todas las visitas HTTPS presentan una advertencia de certificado. Es lo esperado; no «corregirlo» con HSTS ni una excepción fijada. |
| 2026-09-12 — El binario sing-box se distribuye en el repositorio, por lo que todo el proyecto es GPL-3.0 | - **Descartado:** descargar sing-box durante la instalación para reducir el tamaño del repositorio y mantener la licencia Apache-2.0: `Anytsl-Serve` ya había descartado exactamente eso para permitir instalar sin acceso a GitHub; replantearlo aquí anularía silenciosamente ese objetivo. - **Descartado:** quitar el módulo anytls para conservar Apache-2.0 de `vps-webserver`; el encargo consistía en combinar ambos proyectos, no elegir uno. - **Coste:** unos 57 MB en git, que aumentan con cada actualización de sing-box; y el código Apache-2.0 de `vps-webserver` se redistribuye aquí bajo GPL-3.0. |
| 2026-09-12 — Los proyectos originales se incluyen como código de terceros, sin sustituirlos ni usarlos como submódulos | - **Descartado:** sustituir `vps-webserver` y `Anytsl-Serve` por vps-server y archivar ambos; los tres deben mantenerse y publicarse de forma independiente. - **Descartado:** submódulos git apuntando a los dos repositorios originales; un submódulo no permite los cambios de nombre que necesita este proyecto (unidades, nombre del binario, `VPSWS_` → `VPSSRV_`) y una clonación requeriría acceso de red a otros dos repositorios. - **Coste:** el mismo código vive en tres repositorios y divergirá. Mitigación: los archivos `.upstream-version` indican la etiqueta exacta de origen de cada árbol incluido y **DEBEN** actualizarse en el mismo commit que cualquier renovación. |

## Traspaso

La rama de publicación actual, el trabajo terminado, las comprobaciones, los pasos de publicación pendientes y la siguiente acción se mantienen en el [traspaso actual del LOG.md en chino simplificado](../LOG.md#交接).
