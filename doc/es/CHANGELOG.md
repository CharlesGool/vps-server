---
name: project-changelog-es
description: Historial de cambios
metadata:
  version: "1.0.0"
  lang: "es"
---

# Historial de cambios

## Multilingüe

[简体中文](../CHANGELOG.md) | [English](../en/CHANGELOG.md) | [繁體中文(台灣)](../zh-TW/CHANGELOG.md) | [繁體中文(香港)](../zh-HK/CHANGELOG.md) | [हिन्दी](../hi/CHANGELOG.md) | **Español** | [العربية](../ar/CHANGELOG.md) | [Français](../fr/CHANGELOG.md)

## Documentación

- Descripción general del proyecto: [README](README.md)

- Justificación del diseño: [DESIGN](DESIGN.md)

- Estado del proyecto: [LOG](LOG.md)
- Registros históricos: [HISTORY](HISTORY.md)
- Historial de cambios: [CHANGELOG](CHANGELOG.md)
- Historial de commits: [COMMITS](COMMITS.md)

- Avisos de terceros: [THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES.md)

## Historial de cambios

<a id="vps-changelog"></a>

Aquí solo se enumeran los lanzamientos etiquetados. Las siguientes entradas conservan el historial completo del registro de cambios anterior y registran el contenido de la versión actual.

### v5.0.0 — 2026-10-03

#### Añadido

- La consola puede iniciar una prueba TCP o UDP de duración limitada contra otro servidor iperf3 y muestra comandos breves para servidor y cliente.
- Las páginas públicas HTTP y HTTPS tienen interruptores y entradas independientes en Home; la identidad del servidor se guarda y aparece en la navegación y el título del navegador.

#### Cambiado

- La primera instalación se completa en el terminal y, de forma predeterminada, instala solo la consola Web; los demás módulos se instalan según sea necesario desde Modules. La habilitación de FRPC es independiente de que estén ejecutándose instancias del cliente.
- Los controladores Web y los estilos se organizan por función, con recursos estáticos en `src/web/static/`; la documentación se divide en fuentes en chino simplificado, registros históricos, historial de cambios y traducciones.
- Un reinicio normal del servicio Web conserva las sesiones vigentes; cambiar la contraseña invalida las sesiones anteriores.

#### Corregido

- Los nombres de instancias FRPC admiten letras y dígitos Unicode; reinstalar módulos conserva los nodos y el estado de servicio existentes y comunica el resultado de un interruptor antes de reiniciar.
- La desinstalación completa muestra su mensaje final traducido y termina correctamente tras borrar el directorio de instalación.

### v4.0.0 — 2026-09-29

#### Añadido

- La configuración inicial desde el navegador permite elegir módulos, idioma, autenticación y puertos mediante un servidor HTTPS temporal y una contraseña de un solo uso. Una vez instalada, la consola permite instalar o quitar módulos opcionales desde Ajustes y muestra el estado y el registro de cada tarea.
- Se pueden crear, renombrar, editar, activar, desactivar, probar y eliminar instancias locales de FRPC. El editor admite proxies TCP y UDP sencillos con autenticación por token, verifica los cambios con `frpc` y restaura la configuración anterior si falla su aplicación. FRPC se instala independientemente de FRPS; su ejecutable cliente, fijado por suma de verificación, se distribuye como recurso independiente de Release `frpc-0.71.0-linux-amd64`.
- Home ofrece entradas y páginas separadas para FRPS y FRPC. Las páginas de funciones desactivadas llevan a una página de cierre traducida.

#### Cambiado

- Home presenta las nueve funciones principales como tarjetas con interruptores individuales. La gestión de módulos pasó a Ajustes ordinarios; los Ajustes de seguridad siguen exigiendo una verificación reciente de la contraseña del administrador.
- Las tarjetas de FRPC y de nodos proxy tienen controles más claros para editar, probar, revelar datos y confirmar acciones. Al editar una instancia se conservan la dirección y el token actuales del servidor salvo que se cambien; los campos del proxy distinguen los puertos locales de los del servidor.
- La navegación de acceso y Ajustes, los iconos de página, los controles de contraseña, las opciones de tema y el diseño adaptable siguen el diseño actual de la consola. El texto principal usa fuentes del sistema para mantener sus dimensiones durante la recarga. Tras los comentarios del operador se retiró la animación entre páginas; permanece el movimiento al cambiar el tamaño de la ventana.
- Los interruptores de reenvío de puertos aplican las reglas en el proceso Web en ejecución sin reiniciar la consola. Los envíos repetidos de una acción de módulo regresan a la página solicitante, y las conexiones POST rechazadas se cierran correctamente para que una solicitud posterior no se interprete mal.

#### Corregido

- Añadir un proxy FRPC ya no exige el índice que solo se utiliza para editarlo o eliminarlo. La recopilación de visitantes se detiene mientras la función está desactivada, y los controles de nodos proxy conservan los valores guardados al volver a abrirlos.

#### Verificación y límites

- La batería local superó 341 pruebas, con 8 omitidas. En el host de prueba designado se comprobaron las rutas autenticadas, la separación de las páginas FRPS y FRPC, los interruptores de módulos, la redirección a la página de cierre, la validación de la configuración FRPC y el proxy TCP solicitado por el usuario en el puerto remoto redacted-remote-port. El operador consideró adecuado el comportamiento actual durante la recarga. El host sigue ejecutando una compilación de prueba parcheada; esta etiqueta formal del código fuente no actualiza por sí sola esa instalación.
- Siguen sin verificarse el funcionamiento en un dispositivo móvil real, la persistencia tras reiniciar, una instalación completa en un host limpio desde esta etiqueta final y todas las combinaciones de políticas de proxy o reenvío con tráfico real. Los tres grandes ejecutables publicados anteriormente no han cambiado desde v3.0.0. El cliente FRPC es un nuevo recurso de Release de 16,593,080 bytes con SHA-256 `f79fff8de3089ec711ff8bdd4b73e00dfe491a1c3d754983c8b0f8d58c21b068`; el instalador comprueba ese resumen antes de utilizarlo.

### v3.0.0 — 2026-09-28

#### Añadido

- Los nodos AnyTLS, VMess, VLESS, Trojan y Shadowsocks administrados se pueden crear, editar, deshabilitar, restablecer y eliminar individualmente. Los números de visualización permanecen contiguos; Los UUID ocultos preservan la identidad. Los detalles de la conexión se pueden copiar o importar a Clash Meta para Android mediante un enlace o un código QR.
- Cada nodo rastrea el tráfico de carga y descarga y admite un límite de GiB, límites de velocidad direccionales separados, reinicios recurrentes en días, meses o años y un período de validez opcional. Un límite alcanzado puede limitar ambas direcciones a 1 Mbps o bloquear el acceso; un período de validez vencido bloquea el acceso.
- El acceso sin contraseña está disponible para una lista permitida de IP privada explícita. La configuración de seguridad requiere una verificación reciente de la contraseña del administrador, incluso para sesiones de solo IP, antes de exponer o cambiar las credenciales y las reglas de acceso.

#### Cambiado

- Se unificó la consola y los diseños de inicio de sesión, las tarjetas de nodo responsivas, la navegación del panel y la configuración. La configuración general ahora ofrece ocho colores de acento persistentes y modos de luz/oscuridad independientes. Las credenciales almacenadas y los puertos configurados están enmascarados hasta que se muestran o se utilizan con autorización.
- La vista iperf3 separa el estado del servicio de su puerto editable. Las actualizaciones del instalador conservan el punto de entrada web en tiempo de ejecución y los módulos preparados. Los resúmenes de configuración de proxy enumeran la interfaz y las direcciones opcionales de Tailscale sin búsqueda de IP pública. Se repararon fragmentos de documentos traducidos y enlaces a fuentes de terceros.

#### Verificación y límites

- El operador informa que se pasaron las pruebas funcionales. La suite local pasó 311 pruebas (8 omitidas); el host de prueba designado proporcionó los nuevos recursos de inicio de sesión y tema con servicios web, proxy, medidor de nodos y AnyTLS activos y habilitados para el arranque. En la preparación de esta versión no se presenciaron de forma independiente un reinicio real ni cada transferencia de política en vivo.
- No se agregó ningún blob nuevo o modificado de más de 10 MB. Los ejecutables existentes de sing-box (57,995,520 bytes), frps (20,332,728 bytes) y Lucky (10,883,644 bytes) tienen los mismos ID de blob Git que en `v2.0.0`; los registros de procedencia y licencia permanecen en [THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES.md). frps y Lucky siguen siendo experimentales.

### v2.0.0 — 2026-09-27

#### Changed

- Las rutas de entrada del instalador y el desinstalador se trasladaron a `deploy/install.sh` y `deploy/uninstall.sh`; el código web, a `src/web/`; las dependencias incluidas, a `third_party/`; y los metadatos de versión, a `config/`. Los scripts que usaban las rutas anteriores del repositorio deben actualizarse; los datos de ejecución instalados permanecen en sus ubicaciones actuales.
- Los antiguos documentos de tareas pendientes, estado, decisiones e historial de cambios se consolidaron en `DESIGN.md` y `LOG.md`; se migraron los ocho conjuntos de idiomas y los enlaces locales a la estructura documental estándar. Los textos de la interfaz están ahora en `lang/`, con nombres de archivo BCP-47.

#### Added

- Se incorporaron el módulo proxy de cuatro protocolos, su página compartida en la consola, los controles de restablecimiento de credenciales por protocolo y el asistente de configuración en el navegador.
- Se incorporaron los instaladores experimentales de frps y Lucky y sus ejecutables incluidos. Los archivos de licencia originales y los hashes de los artefactos constan en el inventario de terceros.

#### Verification and limits

- Pruebas unitarias locales: 271 aprobadas y 8 omitidas. Se superaron las comprobaciones de hashes de dependencias, documentación y estructura multilingüe. El verificador de documentos notificó cuatro advertencias sobre las etiquetas de navegación de los documentos en inglés.
- El 2026-09-27, las copias de los siete artefactos incluidos en el repositorio coincidían con los archivos de las publicaciones originales correspondientes; los archivos de licencia originales de los ejecutables incluidos coincidían con los de esas publicaciones. No se obtuvo una interpretación jurídica independiente.
- Siguen pendientes la aceptación de esta organización del repositorio en un servidor real con systemd y la revisión independiente de las traducciones por hablantes nativos. frps y Lucky son experimentales en esta versión.

### v1.1.2 — 2026-09-21

#### Fixed

- Una actualización mediante `install.sh` desde una versión anterior a un ajuste nuevo (como los ajustes de reenvío de puertos de v1.1.0 para quienes estaban en v1.0.4) podía interrumpirse silenciosamente justo tras la última pregunta de ajustes nuevos, antes de copiar archivos, actualizar `VERSION` o reiniciar el servicio, sin mensaje de error; el servidor permanecía en la versión antigua aunque la instalación pareciese terminar normalmente.

### v1.1.1 — 2026-09-20

#### Fixed

- La sección de instalación del README todavía clonaba `--branch v1.0.4` tanto en la instalación rápida de una línea como en el comando paso a paso; quien siguiera esas instrucciones justo después de publicarse v1.1.0 habría instalado la versión anterior sin reenvío de puertos.

### v1.1.0 — 2026-09-19

<a id="vps-release-v1-1-0"></a>

#### Added

- **Reenvío de puertos gestionado desde la consola.** Una nueva página «Reenvío de puertos» permite reenviar un puerto público TCP/UDP de este servidor a un dispositivo accesible por Tailscale o LAN, útil si este equipo tiene una IP pública y el dispositivo de destino no. Desde la consola se pueden añadir, habilitar, deshabilitar y eliminar reglas; antes de aplicar cada una se comprueba que no entre en conflicto con los puertos que ya utiliza esta instalación (consola, página pública, iperf3, anytls). Las reglas usan DNAT + MASQUERADE de `iptables` y se reaplican automáticamente cada vez que arranca el servicio, de modo que tanto reiniciar el servicio como el servidor recupera los reenvíos habilitados en lugar de perderlos. `net.ipv4.ip_forward` se activa automáticamente la primera vez que se necesita. Establecer `VPSSRV_PORTFWD_ENABLE=0` elimina por completo esta función de una instalación.

### v1.0.4 — 2026-09-12

#### Changed

- El resumen final del instalador muestra ahora las direcciones IP reales del equipo en vez de un marcador literal `<this-server>` que había que sustituir manualmente para usar las URL. La dirección que realmente usaría el núcleo para salir del equipo figura en las líneas de página pública y consola; en un equipo con varias interfaces, las demás direcciones aparecen debajo, etiquetadas con su interfaz, para que sea visible un nodo accesible únicamente por ZeroTier o Tailscale. Si no puede leerse ninguna dirección se muestra el antiguo marcador de posición, evitando que un problema de presentación haga fallar una instalación correcta.

### v1.0.3 — 2026-09-12

#### Fixed

- `install_iperf3()` aún podía fallar después de la corrección de v1.0.2. `apt-get update` puede informar de éxito mientras la CDN de `security.debian.org` devuelve un índice de paquetes obsoleto, por lo que el siguiente `apt-get install` recibe un 404 al intentar descargar un `.deb` que ese índice afirmaba que existía; ocurrió en un servidor real al actualizar de v1.0.1 a v1.0.2. Un único reintento de `update` no lo resolvía de forma fiable, pues podía llegar al mismo nodo obsoleto. El instalador ahora reintenta el par completo actualización-instalación hasta tres veces, y funciona cuando un intento posterior alcanza una réplica sincronizada.
- La sección `## Install` del README aún contenía marcadores de plantilla sin rellenar: un `<repo-url>` literal y una etiqueta de ejemplo `v0.1.0` que nunca ha correspondido a una publicación del proyecto. Ambos tienen ahora los valores reales: la URL de GitHub del proyecto y la etiqueta de la versión vigente.

### v1.0.2 — 2026-09-12

#### Fixed

- `install.sh` podía no instalar iperf3 sin avisar: encadenaba la actualización e instalación de apt descartando toda la salida, así que un repositorio ajeno defectuoso (un archivo `.list` de terceros obsoleto, como ocurrió en un VPS real) hacía fallar la actualización y omitía por completo la instalación sin mostrar la causa. Ahora reintenta la actualización, intenta instalar independientemente del resultado de esta y ya no oculta los errores de apt si la instalación realmente falla.

### v1.0.1 — 2026-09-12

#### Fixed

- La página de cambios mostraba como párrafos normales en los tres idiomas el comentario del responsable al final del archivo CHANGELOG (que indica qué encabezados permanecen en inglés), incluidos los
  `<!--` y `-->` escapados. El procesador no contemplaba los comentarios. Solo afectaba a la visualización.

### v1.0.0 — 2026-09-12

Primera publicación. Combina dos proyectos existentes —una consola de pruebas de velocidad VPS protegida por contraseña y un instalador `anytls` de sing-box— y añade dos capacidades que ninguno tenía: una ventana iperf3 bajo demanda y una página pública para que cualquiera compruebe si tu IP responde por web.

#### Added

- **Página pública de accesibilidad en los puertos 80 y 443, sin inicio de sesión.** Dale a alguien la IP; si aparece la página, tus puertos web son accesibles desde donde está. Indica su dirección de origen, la hora del servidor y el puerto y protocolo de llegada, sin revelar ningún otro dato sobre el servidor. Servir en ambos puertos es deliberado: distingue «no se puede acceder al servidor» de «el 443 está bloqueado específicamente».
- **Ventana iperf3 bajo demanda.** La consola abre una ventana de duración limitada; `iperf3` solo funciona durante ese periodo, abre su puerto en el cortafuegos activo y cierra ambos al expirar la ventana, cuando se solicita o al detenerse el servicio. No existe la opción de «dejarlo funcionando», pues un servidor iperf3 abierto permite a cualquier desconocido saturar el enlace de salida. La página pública anuncia la ventana abierta para indicar a quien hace la prueba cuándo conectarse.
- **Prueba de velocidad en navegador y registro de visitantes**, desde la consola: medición de subida y descarga con el motor LibreSpeed y registro de todas las conexiones TCP entrantes por cualquier puerto, no solo HTTP, leído de la tabla de conexiones del núcleo.
- **Módulo proxy anytls.** sing-box con certificado autofirmado y BBR. La consola muestra el puerto, contraseña y SNI del nodo, ofrece su entrada Clash y enlace `anytls://` con botones de copia y permite rotar las credenciales.
- **Instalador con selección de módulos.** web, iperf3 y anytls se eligen independientemente, de manera interactiva o mediante `VPSSRV_MODULES` para ejecuciones desatendidas. Rechaza los puertos ocupados por otros procesos en vez de competir por ellos y omite anytls en arquitecturas distintas de x86-64 para no instalar un binario incompatible.
- **Reinstalación adaptada a las actualizaciones.** Al ejecutarlo de nuevo detecta la instalación existente, ofrece conservar su configuración, recupera los ajustes registrados en la unidad de servicio, conserva las credenciales del nodo anytls y pregunta solo por los ajustes ausentes en la versión instalada. Para las instalaciones anteriores a ese registro, lee la lista de módulos del disco.
- **Tres idiomas de interfaz**: inglés, chino simplificado y chino tradicional; se eligen durante la instalación, pueden cambiarse en cada visita y se recuerdan.
- **Instalación sin acceso a servicios externos.** El binario sing-box viene en el repositorio, por lo que basta con acceder al repositorio de paquetes de la distribución.

**Notas de publicación (v1.0.0):**

- Todo el proyecto es GPL-3.0 porque redistribuye el binario sing-box con licencia GPL-3.0. Las licencias de los componentes y los enlaces al código fuente correspondiente que exige la GPL están en [THIRD_PARTY_NOTICES.md][local-link-007].
- TLS en 443 utiliza un certificado autofirmado: sin dominio ni ACME. La advertencia del navegador también demuestra que el puerto responde, que es la pregunta para la que existe la página.
- `mean_rtt` en la salida JSON de iperf3 procede de `TCP_INFO` del núcleo: un cliente Linux muestra el tiempo de ida y vuelta; uno que no puede leerlo (por ejemplo, iperf3 en Cygwin bajo Windows) solo muestra el caudal. El modo UDP (`-u`) muestra la fluctuación y pérdida en todas las plataformas.
- El módulo anytls solo admite x86-64. Los módulos web e iperf3 no dependen de la arquitectura.