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

Los puntos pendientes son carencias de aceptación, no fallos reproducidos.

## Limitaciones

- No se recupera estado borrado sin copia porque los datos originales ya no existen.
- Las interfaces locales no identifican de forma fiable una IP pública tras NAT; el proyecto no consulta servicios externos.
- El editor no reconstruye sin pérdidas cualquier configuración FRP compleja; los campos no soportados se conservan y administran de forma nativa.

## Decisiones

| Fecha | Decisión | Estado | Motivo |
| --- | --- | --- | --- |
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
