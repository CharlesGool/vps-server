---
name: project-design-es
description: Arquitectura y restricciones de diseño del proyecto
metadata:
  version: "2.0.0"
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

- [x] Gestionar herramientas opcionales y servicios independientes mediante una consola autenticada.
- [x] Separar código reemplazable y estado persistente y conservar ajustes dentro del mismo esquema.
- [x] Usar auxiliares privilegiados limitados para servicios, puertos y reglas, con resultados consultables en segundo plano.
- [x] Ofrecer chino simplificado, inglés y español y recursos de cliente con sumas fijas.

Fuera del alcance: plataforma general de contenedores, edición arbitraria de FRP, detección automática de IP pública o bloqueo completo de paquetes del sistema.

## Arquitectura

El navegador accede a páginas y endpoints autenticados de un servicio HTTP de la biblioteca estándar de Python. Los manejadores se separan en `src/web/features/`. Servicios systemd independientes ejecutan Singbox, FRPS, FRPC, Lucky y Tailscale. Web usa protecciones del sistema y delega acciones privilegiadas limitadas; el terminal del navegador inicia un PTY root tras verificar la contraseña.

Tras elegir el idioma, el instalador inicia la tarea `vps-server-install`. Guardar/renombrar FRPC devuelve primero una página de espera; la tarea valida y aplica la configuración y reinicia la instancia con retraso. La consulta se reintenta tras una interrupción del túnel y muestra el resultado real.

| Directorio | Responsabilidad |
| --- | --- |
| `src/` | Código Web, manejadores y recursos estáticos. |
| `deploy/` | Instalación, desinstalación, configuración de módulos y plantillas systemd. |
| `config/` | Versión, sumas de artefactos y procedencia. |
| `lang/` | Traducciones; el valor `zh_cn` selecciona chino simplificado. |
| `third_party/` | Ejecutables, archivos, licencias y procedencia. |
| `tools/` | Construcción de estilos, verificación y empaquetado sin conexión. |
| `doc/` | Diseño, estado, historia, cambios, avisos y traducciones. |

Los estilos se encuentran en `src/web/static/styles/` y generan `src/web/static/style.css`. `tools/build_offline/build_offline.py` produce el paquete en el directorio elegido con programa, instalador, artefactos y avisos; excluye estado privado, `.git` y archivos locales de depuración. `tools/build_offline/fetch_assets.py` verifica las descargas nftables en la máquina de construcción.

## Restricciones de diseño

- Los datos sensibles **DEBEN** exigir autenticación y la comprobación de contraseña requerida; el HTML inicial **NO DEBE** incluir credenciales ocultas reales. Los editores **DEBEN** cargar los valores actuales y conservar los no modificados.
- Los puertos **DEBEN** bloquearse y registrarse antes de activar; los fallos liberan reservas nuevas. **NO DEBEN** usurparse registros ajenos.
- Los cambios FRP **DEBEN** validarse y conservar o restaurar la configuración en caso de fallo. El editor **NO DEBE** descartar opciones avanzadas no soportadas.
- La cuota cuenta `(subida + bajada) × 2`; la ausencia de lecturas **NO DEBE** significar cuota agotada. Los reinicios de ciclo **DEBEN** reconstruir la cuota del núcleo.
- Los servidores iperf3 **DEBEN** tener duración limitada; detener Web cierra procesos temporales y reglas propias. **NO DEBE** restablecerse `ip_forward` global ni borrarse reglas ajenas.
- Las rutas públicas y de consola **DEBEN** permanecer separadas. Las cabeceras del proxy **NO DEBEN** autorizar acceso por IP sin contraseña.
- Las instalaciones del mismo esquema **DEBEN** conservar el estado; un esquema antiguo o localizador ausente **NO DEBE** sobrescribirse silenciosamente.
- Los artefactos **DEBEN** coincidir con sus sumas y conservar licencias y acceso al código correspondiente. Esto no fija todas las dependencias del sistema.

## Diseño de datos

| Ubicación | Datos |
| --- | --- |
| `/var/lib/vps-server` | Raíz predeterminada del esquema 1, localizada por `/etc/vps-server/state-dir`. |
| `admin_password.txt`, `console_port.txt`, `.env`, `paths.json`, `.layout-version` | Autenticación, puerto guardado, configuración y metadatos. |
| `certs/` | Certificados TLS y claves privadas. |
| `data/` | Base SQLite de visitantes, sesiones/secreto, estado, nodos y tareas. |
| `/etc/vps-server-proxy/config.json` | Configuración Singbox coordinada con el manifiesto de nodos. |
| `/etc/vps-server-frps/frps.toml` | Configuración del servidor FRPS. |
| `/etc/frp/frpc-<name>.toml` | Configuración de instancias FRPC; los nombres no ASCII usan alias estables. |
| `/etc/vps-server-lucky` | Configuración y tareas de Lucky. |
| `~/apps/PORTS.md`, `~/apps/.ports.lock` | Registro de puertos y bloqueo del host. |

Los permisos reflejan la sensibilidad; copias y configuraciones no se publican como recursos estáticos. Las tareas `data/frp-jobs/*.json` usan `0600`, eliminan credenciales de solicitud antes de ejecutar y guardan resultados. Las reglas se conservan como JSON propio y se reproducen al iniciar, sin guardar todo el cortafuegos. Consulte README para respaldo y restauración.

## Interfaces externas

- Las páginas/formularios sirven para administrar el proyecto; los endpoints de mostrar/copiar exigen autenticación. `/frp/client/structured` y `/frp/client/rename` son acciones POST, no páginas independientes.
- LibreSpeed usa `/speedtest/garbage`, `/speedtest/empty` y `/speedtest/getip` con un backend Python propio; mide la ruta actual entre cliente y servidor.
- Los auxiliares usan acciones permitidas para systemd, validación FRP, nft/iptables e instalación; no ofrecen una API de comandos arbitrarios. El PTY root exige verificación de contraseña.
- FRPC conecta al servidor configurado; el editor soporta proxies TCP/UDP simples con token.
- La CLI Tailscale comunica con el daemon local; autenticación y aprobación de rutas corresponden al servidor de control/Tailnet. Lucky usa su puerto nativo independiente.
- Las direcciones proceden de interfaces locales y del servidor FRPC configurado; el instalador no consulta servicios de IP pública.
