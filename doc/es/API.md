---
name: api-es
description: API de tokens de la consola: autenticación, permisos y solicitud y respuesta de cada interfaz
metadata:
  version: "1.0.0"
  lang: "es"
---

# API de tokens

Este documento describe `/api/v1/*`, pensada para scripts y para otras consolas (la página Gestión central). Las API de sesión `/api/*` que usan las páginas del navegador quedan fuera de su alcance y no se garantiza su estabilidad.

## Autenticación

1. Genere un token en la tarjeta Tokens de API de la página Gestión central. Los tokens tienen la forma `vpss_...`, se muestran una sola vez al generarlos y el servidor solo guarda su SHA-256.
2. Si el interruptor de Gestión central del inicio está desactivado, todas las interfaces de tokens devuelven 403 `feature_closed`.
3. Cada solicitud lleva la cabecera `Authorization: Bearer <token>`. No hace falta cookie de sesión y tampoco se aplican «Exigir certificado de cliente» ni la comprobación de mismo origen; el límite de acceso a la consola sigue vigente.
4. Un token erróneo cuenta como fallo de inicio de sesión; al alcanzar el número configurado, la dirección de origen queda bloqueada (se devuelve 429 y `retryAfter` son los segundos restantes).
5. Hay dos permisos: `read` solo puede llamar a las interfaces de lectura de la tabla siguiente; `write` además puede llamar a las de escritura. Un token de solo lectura que llama a una interfaz de escritura recibe 403 `read_only_token`.

Se admiten hasta 20 tokens. El registro de seguridad anota la generación y eliminación de cada token y las operaciones de escritura que dispara; la lista de tokens muestra la hora y la dirección de origen del último uso.

## Interfaces

Las solicitudes y respuestas son JSON. Un éxito devuelve 200; un fallo devuelve 4xx/5xx y `{"error": "<código>"}`.

| Método y ruta | Permiso | Función |
| --- | --- | --- |
| `GET /api/v1/status` | read | Nombre del equipo, versión, identificador del servidor, kernel, recursos (como `monitor`, sin gráficas), tráfico total del ciclo actual, estado de los servicios de este proyecto, servicios fallidos |
| `GET /api/v1/monitor` | read | Todos los datos de la página Recursos, incluidas las gráficas de 24 horas (promedios de 12 y 24 tramos) |
| `GET /api/v1/services` | read | Todos los servicios de systemd: `unit`, `load`, `active`, `sub`, `description`, `enabled` |
| `GET /api/v1/upgrade` | read | Si hay una actualización lanzada por la API en curso (`running`), la versión actual y las últimas 40 líneas de la salida de la actualización |
| `POST /api/v1/services/restart` | write | Reinicia un servicio; cuerpo `{"unit": "<nombre>.service"}`; si se reinicia la propia consola, responde de inmediato |
| `POST /api/v1/upgrade` | write | Actualiza en segundo plano a la última versión estable, o a la indicada con `{"version": "v7.2.0"}`; `variant` puede ser `online` (por defecto) u `offline`. Si ya hay una actualización en curso, devuelve 409 `busy` |
| `POST /api/v1/backup` | write | Crea una copia de seguridad manual de la configuración y devuelve `{"name": "<nombre del archivo>"}` |

La actualización es igual que el comando de actualización del panel: primero verifica la firma de la versión, luego ejecuta el instalador del paquete y la consola se reinicia una vez. La actualización se descarga de GitHub; los equipos que no llegan a GitHub siguen necesitando transferir los archivos a mano según [Actualización](README.md#actualización) del README.

## Ejemplo

```bash
TOKEN=vpss_...
curl -sk -H "Authorization: Bearer $TOKEN" https://203.0.113.5:20000/api/v1/status
curl -sk -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"unit": "vps-server-proxy.service"}' https://203.0.113.5:20000/api/v1/services/restart
```

La consola usa por defecto un certificado autofirmado, por lo que lo anterior usa `-k` para omitir la verificación. Los scripts deberían usar `--pinnedpubkey` o cambiar a un certificado válido (certificado IP o reenvío de dominios).
