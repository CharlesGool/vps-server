---
name: project-log-es
description: Errores, limitaciones, decisiones y traspaso del proyecto
metadata:
  version: "2.0.0"
  lang: "es"
---

# Registro

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

- [Historia](HISTORY.md)
- [Historial de cambios](CHANGELOG.md)

## Errores

- [x] Guardado FRPC correcto con respuesta vacía o renombrado con Invalid request: corregido en v5.2.2 mediante espera y consulta de resultados.
- [x] Valores de edición, privacidad, colores al pasar el ratón, fuentes y alineación inconsistentes: corregidos en v5.2.2 y confirmados por el operador.
- [x] Instalación interrumpida al desconectar FRPC: v5.2.2 usa una tarea systemd independiente.
- [x] Archivo Tailscale ausente al instalar desde Git: corregido en v5.2.1.
- [ ] Python 3.9, otras distribuciones, recuperación tras reinicio y dispositivos móviles reales requieren aceptación independiente.
- [ ] No se verificaron cierre de sesión autenticado de Tailscale ni políticas reales de rutas Tailnet.
- [ ] No se repitió la verificación completa de cuotas mensuales, tráfico sostenido y límites para v5.2.2; la confirmación anterior no equivale a una nueva prueba independiente.
- [ ] Las traducciones no tienen revisión independiente de hablantes nativos.
- [x] 2026-10-21 En un equipo vmshell con Debian 13 (KVM), el servicio de contabilidad de nodos se reiniciaba en bucle registrando solo `cannot list nftables tables`, y Singbox se detenía porque depende de él. Causa: la imagen no tenía nftables, así que la contabilidad usó el nft 0.9.8 incluido, que no puede leer las reglas iptables-nft de Debian 13; la comprobación solo ejecutaba `nft --version`, por lo que la verificación previa lo aceptó. Corregido en v5.4.0: las comprobaciones leen ahora el conjunto de reglas y el entorno incluido es nft/iptables de Debian 13 con su propia glibc.
- [ ] 2026-10-21 El terminal root de la consola se crea desde el proceso Web y hereda `ProtectSystem=strict` de su unidad, por lo que no puede instalar paquetes con apt ni modificar `/etc`. El cambio para ejecutarlo como unidad systemd-run independiente fue bloqueado por la comprobación de permisos de Claude Code y no se aplicó; queda pendiente de la decisión del operador.

Los puntos pendientes son carencias de aceptación, no fallos reproducidos.

## Limitaciones

- No se recupera estado borrado sin copia porque los datos originales ya no existen.
- Las interfaces locales no identifican de forma fiable una IP pública tras NAT; el proyecto no consulta servicios externos.
- El editor no reconstruye sin pérdidas cualquier configuración FRP compleja; los campos no soportados se conservan y administran de forma nativa.

## Decisiones

| Fecha | Decisión | Estado | Motivo |
| --- | --- | --- | --- |
| 2026-11-20 | Las tablas de listas largas (Procesos, Servicios, Puertos en escucha, Archivos y Gestión central) muestran 50 filas por página (propiedad `long` de `DataTable`, con `data-table-long`); las demás tablas siguen con 10. La comprobación de diseño `web/e2e/layout-checks.ts` admite hasta 50 filas en las tablas con esta marca. Exime la regla 22 de `Selección de controles` («una tabla muestra como máximo 10 filas a la vez») de las normas de comportamiento Web UI de all-in-one y la prohibición de modificar ese archivo de la regla 2 de `Comprobaciones de diseño` de las convenciones del usuario, limitado a estas tablas de este proyecto. | Aceptada | El usuario lo pidió: estas listas tienen muchas entradas, que quepan más por página y la página se desplace hacia abajo. |
| 2026-11-19 | El contenido que cambia entre ejecuciones o equipos en las comprobaciones de capturas y diseño (conexión de la terminal, visitantes recientes, mini disco, copias, tareas programadas, la página de seguridad en las capturas) y los módulos que el servidor de pruebas no tiene (Tailscale, reenvío de dominios, certificado IP, FRPS, FRPC, Singbox) usan muestras fijas de `web/e2e/support.ts`; las pruebas propias `web/e2e/vps-*.spec.ts` se ejecutan contra una consola real en un tercer proyecto de Playwright `vps`; el navegador de pruebas usa la zona horaria UTC. Exime la regla 2 de `Comprobaciones de diseño` de las convenciones Web UI de all-in-one que prohíbe cambiar los archivos de soporte e2e, limitado a estas muestras, el tercer proyecto y la zona horaria; las comprobaciones no cambian. | Aceptada | Ese contenido cambia en cada ejecución (hora, espacio en disco, número de sesiones) y las capturas no podían ser estables; los flujos reales tienen sus propias pruebas. |
| 2026-11-18 | Migrar toda la Web UI a la última plantilla Web UI (aplicación Vue de una página, todos los componentes, comprobación de diseño y pruebas visuales e2e) manteniendo el backend Python y el sistema de acceso existente (contraseña, certificados de cliente, cuatro modos de acceso, lista de IP, límites de acceso): Python sirve el frontend y APIs JSON según las convenciones `/api/session`, `login`, `login/ip`, `logout`, `security/*` de la plantilla; la lógica de negocio no cambia. Exime la regla 7 de `Usar la plantilla` de las convenciones Web UI de all-in-one, limitado a este proyecto. | Aceptada | El usuario pidió cambiar todas las interfaces a la última especificación y eligió la migración completa, cambiando solo el frontend. |
| 2026-11-18 | Para el backend Python se modifican `web/playwright.config.ts`, `web/scripts/check-server.mjs` y solo las aserciones de `web/e2e/` que de verdad difieren en el acceso de vps-server. Exime la prohibición de cambiar estos archivos de la regla 2 de `Comprobaciones de diseño`; las comprobaciones de diseño, cuadrícula, tamaño, accesibilidad y capturas no cambian. | Aceptada | El usuario lo aceptó; la configuración de pruebas de la plantilla solo admite el backend Go. |
| 2026-11-18 | Migrar por etapas en la rama `feat/webui-template`; durante la migración el frontend antiguo pasa a `web-legacy/` y las páginas no migradas siguen generadas por Python, y se elimina al terminar (eliminado el 2026-11-19). | Aceptada | Unas 25 páginas en varias sesiones; cada etapa de la rama sigue siendo usable. |
| 2026-10-23 | Cada versión publica un paquete sin conexión y uno en línea: el primero incluye todos los programas de terceros y herramientas del sistema (con iproute2); el segundo descarga y verifica los programas de terceros al instalar e instala con apt las herramientas que falten. | Aceptada | Las imágenes mínimas no tienen curl, tar ni gzip y pueden estar sin red, así que un paquete debe llevar todas las dependencias; los equipos con red solo necesitan un paquete de unos 4 MB. |
| 2026-10-21 | El paquete completo incluye nft e iptables-nft de Debian 13 con su propia glibc, iniciados mediante el cargador incluido; se prefiere un nft/iptables del equipo que pueda leer las reglas. Sustituye el entorno de Debian 11 decidido el 2026-10-04. | Aceptada | El antiguo nft 0.9.8 no puede leer las reglas escritas por iptables-nft de Debian 13 y los binarios nuevos no funcionan directamente con una glibc antigua. |
| 2026-10-13 | Las instalaciones nuevas sirven la consola por HTTPS con un certificado autofirmado; las actualizaciones conservan el ajuste anterior. Las cookies de sesión llevan `Secure` con HTTPS activo. | Aceptada | Un certificado autofirmado no prueba la identidad del servidor, pero evita que contraseñas y sesiones se lean en texto plano. |
| 2026-10-13 | Usar `git branch -D` en 10 ramas locales antiguas sin fusionar (`archive/*` ×3, `feat/two-stage-setup`, `fix/frpc-unicode-name`, `refactor/feature-modules`, `refactor/feature-modules-repo`, `release/v4.0.0`, `release/v4.1.0-test.1`, `test/host-validation-wip`). Exime la regla 2 de las normas Git de all-in-one `Ramas e historial` ("NO DEBE usarse `git branch -D`"), solo para estas ramas y una vez. | Aceptada | El usuario confirmó que estas ramas están abandonadas; sus SHA finales se guardan en notas privadas locales. |
| 2026-10-07 | La esquina superior izquierda de la cabecera muestra solo el nombre del proyecto, sin logotipo. Exime la regla 2 de las convenciones de Web UI de all-in-one `Marco de página y navegación` ("la esquina superior izquierda DEBE mostrar logotipo y nombre"), solo para la cabecera compartida; el icono de la pestaña no cambia. | Aceptada | El usuario lo pidió explícitamente en la conversación porque el logotipo no se veía bien. |
| 2026-10-05 | Reescribir 18 documentos según plantillas actuales y conservar licencias originales. | Aceptada | El usuario pidió una reescritura completa y las licencias conservan obligaciones de distribución. |
| 2026-10-05 | Usar tareas independientes para instalación y actualizaciones FRPC. | Aceptada | Un reinicio puede cortar la conexión del instalador o de la respuesta de guardado. |
| 2026-10-04 | Usar una raíz persistente separada de esquema 1. | Aceptada | Sustituir código no debe borrar credenciales ni ajustes. |
| 2026-10-04 | Migrar automáticamente esquemas v5.1.0 y anteriores. | Rechazada | Los directorios antiguos mezclan código y datos e impiden asumir rutas y pertenencia. |
| 2026-10-04 | Integrar AnyTLS en el servicio Singbox unificado. | Aceptada | Unifica nodos y políticas y elimina controles duplicados. |
| 2026-10-04 | Incluir entorno nft y fuentes correspondientes en paquetes completos. | Aceptada | Los binarios no cubren bibliotecas ausentes; se requiere un sistema básico. |
| 2026-10-03 | Eliminar el directorio de pruebas automáticas y usar comprobaciones y aceptación manual. | Aceptada | Sigue la petición expresa del operador. |
| 2026-09-19 | Usar DNAT del núcleo y reproducción de JSON propio. | Aceptada | Evita coste de retransmisión y control de todo el cortafuegos. |
| 2026-09-12 | Usar GPL-3.0-only y conservar avisos y [revisión de cumplimiento](THIRD_PARTY_NOTICES.md#revisión-de-cumplimiento). | Aceptada | La distribución incluye un núcleo GPL y el autor publica el proyecto bajo esa licencia. |
| 2026-09-21 | Terminar funciones de preguntas con `return 0` explícito. | Aceptada | Una prueba final vacía puede terminar silenciosamente con `set -e`. |
| 2026-09-12 | Separar escuchas y rutas públicas y de consola. | Aceptada | El manejador público no tiene rutas de gestión y la consola conserva puerto aleatorio. |
| 2026-09-12 | Usar ventanas iperf3 temporales sin servidor permanente. | Aceptada | Limita el consumo continuo de ancho de banda no previsto. |
| 2026-09-12 | Usar HTTPS público autofirmado sin ACME. | Aceptada | La página verifica accesibilidad IP/puerto sin dominio ni renovación. |
| 2026-09-12 | Incluir copias propias sin submódulos ni archivar originales. | Aceptada | Los tres proyectos siguen independientes y registran revisiones importadas. |

## Traspaso

El traspaso actual se mantiene en [LOG.md en chino simplificado](../LOG.md#交接).
