---
name: project-history-es
description: Registros históricos
metadata:
  version: "2.0.0"
  lang: "es"
---

# Registros históricos

## Multilingüe

[简体中文](../HISTORY.md) | [English](../en/HISTORY.md) | **Español**

## Documentación

- Descripción general del proyecto: [README](README.md)

- Justificación del diseño: [DESIGN](DESIGN.md)

- Estado del proyecto: [LOG](LOG.md)
- Registros históricos: [HISTORY](HISTORY.md)
- Historial de cambios: [CHANGELOG](CHANGELOG.md)

- Avisos de terceros: [THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES.md)

## Registros históricos

Estos resúmenes conservan el estado de su fecha, no la aceptación automática de la versión actual. Las diferencias exactas están en [historia Git](https://github.com/CharlesGool/vps-server/commits/main/); los cambios formales están en CHANGELOG.

| Fecha | Estado histórico y decisiones |
| --- | --- |
| 2026-09-12 | Se publicó v1.0.0. Se aceptaron escuchas separadas, iperf3 temporal, TLS autofirmado, copias de código y GPL-3.0-only; se rechazaron ACME e iperf3 permanente. Los tres proyectos originales siguieron independientes. |
| 2026-09-12—2026-09-22 | Los registros ingleses iniciales indicaban instalación/eliminación escrita pero nunca ejecutada; después hubo observaciones reales de puertos públicos, acceso/pruebas, iperf3 LAN 2.8 Gbit/s y rechazo al caducar, gestión AnyTLS y conservación al actualizar. El reenvío v1.1.0 se comprobó en host tras tres contenedores y 119 pruebas. No equivalen a aceptación completa actual. |
| 2026-09-19—2026-09-21 | v1.1.0 añadió reenvío del núcleo; v1.1.1 corrigió etiquetas y v1.1.2 retornos falsos de preguntas bajo `set -e`. La eliminación no restablece el reenvío global para no afectar a Docker y otros. |
| 2026-09-22 | La rama de cuatro protocolos avanzó con 147/150/153/156 comprobaciones aisladas y un sustituto de systemctl, no aceptación real. La aprobación de la rama v2 seguía pendiente. |
| 2026-09-22 | Cuatro protocolos funcionaron en un proceso; se excluyeron hysteria2/tuic por campos/TLS y se rechazaron servicios separados. AnyTLS era independiente entonces, sustituido por la decisión de cinco protocolos del 2026-10-04. Los arreglos de direcciones requerían conciliar ramas; se corrigieron protocolos desconocidos/puertos y reinicios individuales conservaron credenciales. Se implementó contraseña manual usando biblioteca estándar Python. |
| 2026-09-27 | v2.0.0 adoptó directorios estándar. Pasaron 271 pruebas y se omitieron 8; hubo cuatro advertencias de navegación inglesa. Siete artefactos coincidieron; host/systemd y revisión nativa seguían pendientes, FRPS/Lucky eran experimentales. |
| 2026-09-28—2026-09-29 | v3.0.0 añadió políticas/enlaces con 311 pruebas aprobadas y 8 omitidas. v4.0.0 añadió asistente Web/FRPC con 341/8. El operador informó funcionamiento; no se observaron independientemente reinicios y todas las políticas; las etiquetas no actualizaron máquinas automáticamente. |
| 2026-10-03 | v5.0.0 trasladó instalación a terminal y dividió código. Se ejecutaron 377 pruebas, 369 aprobadas/8 omitidas; faltó reinstalación real tras reorganizar. Después se eliminaron `tests/` y el asistente por petición; los conteos antiguos no aceptan versiones actuales. |
| 2026-10-04 | Se corrigieron cuota cíclica, contraseñas Unicode, reversión y restos. No se reprodujo la hipótesis de contención `_db_lock`: 60 solicitudes midieron unos 0.4–0.6 ms, sin rediseño. Lecturas ausentes ya no limitan prematuramente; faltaba cubrir cuotas reales sostenidas. |
| 2026-10-04 | Se publicó v5.1.0. El operador confirmó eliminación, acceso, iperf3, tráfico, reenvío y actualizaciones; SSH no era accesible y no se revisó independientemente. v5.1.1-test.1 introdujo esquema 1 con pruebas aisladas aprobadas, pero reinstalar/eliminar en host seguía pendiente. |
| 2026-10-04—2026-10-05 | El candidato v6.0.0 añadió terminal, Tailscale, recursos y AnyTLS unificado. `test-6b26f02`, `test-68e7c5f`, `test-f14ab01` y `test-a9e3cdb` corrigieron registros, estado y terminal. Se pidió v5.2.0 como versión menor; se conservó historia al fusionar en main y no se publicó v6. |
| 2026-10-05 | v5.2.0 usó `53a24c6`, suma `44727d247a39b62cb558fc734d1a8601a1e5c1eef7a9700277d0571d46551e4f`. La confirmación general no fue prueba independiente de cada punto; no se desplegó. v5.2.1 `79bb076` corrigió Tailscale/eliminación, suma `4ff4cae467e0b176b50459245fdf639a0e44e89e1230207dfdf28e98dc823a53`; tampoco instaló/eliminó en el VPS del operador. |
| 2026-10-05 | El operador confirmó guardar ajustes en `test-cd085d6`; `test-cd8b114` aún devolvía respuesta vacía tras guardar, colores extraños y acciones desalineadas. Se confirmaron las correcciones posteriores. Se publicó e instaló v5.2.2 desde el paquete completo en Debian 13, verificando reinicio FRPC real, conservación ante error, servicios y arranque Web. |
| 2026-10-05 | Publicar no cerró automáticamente carencias de Python 3.9, otras distribuciones, móviles reales, reinicios y todas las políticas. Un host sin sesión no verifica salir de Tailscale autenticado. LOG concentra el estado actual; guías antiguas solo registran diseños pasados. |
| 2026-10-07—2026-10-13 | Traspaso antes de su sustitución (tras v5.3.1): se publicó v5.3.1 y la prepublicación de prueba `v5.3.1-test.1` no mostró problemas evidentes en las pruebas del operador; `v5.3.0-test.1` se actualizó en el mismo lugar desde v5.2.x en un equipo de prueba Debian 13 y en una máquina real, donde Tailscale funcionó (confirmado por el operador). Sin verificar entonces: arranque automático tras reiniciar, Python 3.9 y otras distribuciones, dispositivos móviles reales, cierre de sesión autenticado de Tailscale y rutas Tailnet; la serialización de la conexión Tailscale solo se comprobó en el código y con clics únicos. Pendiente entonces: renombrar los tokens `compat-*` y la revisión de hablantes nativos. Estos puntos pasaron al traspaso del 2026-10-13. |
| 2026-10-13—2026-10-21 | Traspaso antes de su sustitución (tras v5.3.1, antes de v5.4.0): las correcciones posteriores a v5.3.1 se verificaron en el equipo de prueba antiguo con instalación de todos los módulos, desinstalación conservando datos y reinstalación, desinstalación completa sin restos, actualizaciones que conservan HTTP, HTTPS por defecto en instalaciones nuevas, HTTPS accesible con 10 conexiones inactivas e identificadores de proceso de otros módulos sin cambios al instalar un solo módulo; la última compilación de prueba era `test-ec0f2be`. Sin verificar entonces: arranque automático tras reiniciar, Python 3.9 y otras distribuciones, dispositivos móviles reales, cierre de sesión autenticado de Tailscale y rutas Tailnet, reinstalación de Tailscale como módulo único, detención de la verificación previa con nft inutilizable o un tailscaled existente, y registros del cortafuegos con ufw/firewalld. Pendiente entonces: escribir el registro de cambios y sincronizar traducciones, renombrar `compat-*`, revisión de hablantes nativos y decisiones pendientes como la propiedad de reglas al cerrar puertos de Singbox. Esto se publicó en v5.4.0 o pasó al nuevo traspaso. |
| 2026-10-21—2026-10-23 | Traspaso antes de sustituirlo (tras v5.4.0, antes de v5.5.0): v5.4.0 se publicó y se verificó en contenedores de ubt-sev con una instalación nueva de Debian 13 sin red ni nft, comprobaciones de módulos, sustitución del entorno incluido con actualización en el sitio, y lectura y escritura de reglas con nft/iptables incluidos en contenedores Debian 11/12/13 y Ubuntu 20.04/22.04/24.04. Sin verificar entonces: instalación y actualización en un VPS real, arranque automático tras reiniciar, dispositivos móviles reales, cierre de sesión autenticado de Tailscale y rutas Tailnet, y registros del cortafuegos con ufw/firewalld. Pendiente entonces: decidir si el terminal root sale del sandbox Web, renombrar `compat-*` y la revisión de hablantes nativos. Esto pasó al nuevo traspaso en la publicación de v5.5.0. |
