---
name: project-changelog-es
description: Historial de cambios
metadata:
  version: "2.0.0"
  lang: "es"
---

# Historial de cambios

## Multilingüe

[简体中文](../CHANGELOG.md) | [English](../en/CHANGELOG.md) | **Español**

## Documentación

- Descripción general del proyecto: [README](README.md)

- Justificación del diseño: [DESIGN](DESIGN.md)

- Estado del proyecto: [LOG](LOG.md)
- Registros históricos: [HISTORY](HISTORY.md)
- Historial de cambios: [CHANGELOG](CHANGELOG.md)

- Avisos de terceros: [THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES.md)

## Historial de cambios

### v7.2.0 — 2026-11-20

Añade monitorización de recursos, gestión del sistema, un gestor de archivos y gestión central. El comando de actualización no cambia y la configuración y los datos se conservan; las funciones nuevas vienen activadas y se pueden desactivar en la página de inicio.

#### Añadido

- **Recursos.** La página de inicio muestra CPU, memoria, disco y carga, actualizados cada 5 segundos. La página Recursos tiene gráficos en vivo (el último minuto, un punto cada 5 segundos) y de 15 minutos (un punto por minuto), uso por disco, velocidad de las interfaces, temperaturas y GPU NVIDIA (si se pueden leer). Las alertas de recursos al final envían por Bark cuando el disco o la memoria superan un umbral, la CPU sigue alta o falla un servicio de vps-server, FRPC o Tailscale, como mucho una vez al día por evento.
- **Sistema.** Información del sistema y cambio del nombre de host (también donde aparece el nombre antiguo en `/etc/hosts`).
- **Actualizaciones.** Paquetes actualizables y `apt-get upgrade` con un clic en segundo plano, con su salida.
- **Procesos, servicios y puertos en escucha** tienen su propia página: los procesos se pueden finalizar; los servicios de systemd se pueden iniciar, detener, reiniciar, activar al arrancar y ver sus últimas 200 líneas de registro (el servicio de la propia consola no se puede detener); los puertos muestran su uso según el registro de puertos. Las listas largas muestran 50 filas por página.
- **Archivos.** Explore y gestione los archivos del servidor como root: subir, descargar (carpetas como archivo comprimido), crear, renombrar, copiar, mover, eliminar, cambiar permisos y propietario, comprimir y extraer (zip, tar.gz) y editar archivos de texto de hasta 1 MiB. Las carpetas del sistema no se pueden eliminar, mover ni renombrar.
- **Gestión central.** Vea si otros hosts están en línea, su versión, recursos y tráfico, y actualícelos o haga copias a la vez; en la misma página cree tokens de API para que otros hosts o scripts gestionen este. Los tokens son de solo lectura o de lectura y escritura; vea [API](API.md).
- Sistema, actualizaciones, procesos, servicios, puertos, archivos y gestión central piden primero la contraseña de administrador, como el terminal root; cada cambio queda en el registro de seguridad.
- Recursos, las páginas del sistema, archivos, gestión central, copias de seguridad y tareas programadas tienen interruptores en el inicio. Desactivadas, las copias y las tareas pausan sus programaciones, y la gestión central también detiene la API de tokens.

#### Cambiado

- "Visitantes recientes" pasa a llamarse "Visitas recientes" y añade los accesos SSH de los últimos 7 días (correctos, fallidos y las direcciones con más fallos).
- Las tarjetas de módulos del inicio ya no dicen que un módulo no está instalado; lo muestra el interruptor. La tarjeta del registro de cambios no tiene interruptor.

#### Corregido

- Las etiquetas largas del eje de los gráficos (como 195.31 KiB/s) se salían de la tarjeta.

#### Verificación

Todas las pruebas automáticas pasan (diseño, tipos, pruebas de navegador con capturas y comprobaciones de diseño, pruebas unitarias de Python). Las versiones de prueba se instalaron en dos hosts de prueba de casa y se probaron como root real: cambiar el nombre de host y volver, todas las operaciones de archivos, reiniciar un servicio, finalizar un proceso, actualizar las listas de paquetes, la API de tokens, añadir un host a la gestión central de otro y leer su estado, y una copia en lote. `apt-get upgrade` y la actualización en lote no se ejecutaron en un host.

### v7.1.2 — 2026-11-19

Los hosts instalados al principio pasan a una CA de cliente con el nombre del host, para que la selección automática en un Mac también los distinga. El comando de actualización no cambia, la configuración y los datos se conservan y los certificados emitidos siguen siendo válidos.

#### Corregido

- **Los hosts instalados al principio compartían un nombre de CA, así que los navegadores no distinguían sus certificados.** Sus CA se llaman todas "vps-server console client CA" y los navegadores distinguen los certificados por el nombre de la CA, así que con la regla compartida de v7.1.1 un Mac podía enviar a estos hosts el certificado equivocado. Ahora un host así crea una CA nueva con el nombre del host la próxima vez que emite un certificado y firma con ella; la CA antigua sigue siendo de confianza, así que los certificados que firmó (en Windows, teléfonos y otros dispositivos) siguen funcionando. La CA nueva solo se usa tras pasar una prueba con la biblioteca TLS del host; si no, se mantiene la antigua.

#### Migración

Igual que en v7.1.1: en el Mac, para cada host, emite un certificado nuevo e instala su perfil nuevo, luego quita el perfil antiguo y revoca el certificado antiguo. Los hosts ya migrados con v7.1.1 no se ven afectados.

#### Verificación

Se simularon en Chromium dos hosts antiguos con el mismo nombre de CA, con los certificados antiguos y nuevos de ambos instalados y la regla compartida: cada host recibió su propio certificado nuevo sin selector y los certificados antiguos siguen verificándose. 2 pruebas unitarias nuevas; la comprobación completa pasa.

### v7.1.1 — 2026-11-19

Chrome y Edge en un Mac eligen solos el certificado de cliente de cada host. El comando de actualización no cambia y la configuración y los datos se conservan. En un Mac hay que volver a emitir los certificados; consulta los pasos de migración.

#### Corregido

- **Con los perfiles de varios hosts instalados en un Mac, solo un host elegía su certificado solo.** macOS solo aplica el valor de un perfil para cada política del navegador, así que las reglas de cada host se sobrescribían y los demás hosts pedían elegir entre todos los certificados tras cada reinicio del navegador. Ahora la consola solo nombra su propia CA en el handshake TLS, así que el navegador solo considera los certificados de ese host; los nuevos certificados de dispositivo llevan la organización vps-server y el perfil de macOS de cada host escribe la misma regla, de modo que ya no se sobrescriben. En Windows y Linux el selector también muestra solo el certificado de ese host.
- El perfil de macOS que solo activa la selección automática ya no reemplaza al perfil que contiene un certificado (reemplazarlo también borraba el certificado).

#### Migración

Primero actualiza todos los hosts a v7.1.1. Después, en el Mac, para cada host: emite un certificado nuevo e instala su perfil nuevo, luego quita el perfil antiguo de ese host y revoca el certificado antiguo. Instalar primero el nuevo mantiene accesibles los hosts que solo admiten certificado. Las claves privadas antiguas no se pueden exportar del llavero, así que la única opción es volver a emitirlas. Un host sin actualizar no nombra ninguna CA, y un Mac con el perfil nuevo puede enviarle el certificado equivocado, con lo que la conexión falla. Windows y Linux no necesitan migración.

#### Verificación

Probado en Chromium con los certificados de dos hosts y la regla compartida: sin la lista de CA el certificado equivocado iba al otro host y la conexión se rechazaba; con ella cada host recibía el suyo sin selector. La comprobación completa (diseño, tipos, pruebas de navegador y pruebas unitarias de Python) pasa, con 5 pruebas unitarias nuevas.

### v7.1.0 — 2026-11-19

La consola pasa a un nuevo diseño de una sola página, con varias funciones surgidas del uso real. El backend, la configuración y los formatos de datos siguen siendo compatibles; el comando de actualización no cambia y la configuración y los datos se conservan.

#### Cambiado

- **Todas las páginas usan la nueva interfaz.** Inicio, ajustes, seguridad, módulos, registros detallados, prueba de velocidad, iPerf 3, reenvío de puertos, visitantes recientes, terminal, Mini Drive, copia y restauración, tareas programadas, Tailscale, reenvío de dominios (con su registro de accesos), certificado IP, FRPS, FRPC y nodos Singbox comparten ahora una interfaz de una sola página con tarjetas, temas claro/oscuro y tres idiomas. El servidor solo ofrece una API JSON; las antiguas páginas generadas en el servidor se han eliminado y las direcciones antiguas (como `/anytls` y `/frp/client/edit`) llevan a las nuevas.
- **La barra superior muestra la etiqueta del servidor.** La etiqueta de Ajustes aparece junto a la versión y se puede seleccionar y copiar; los títulos de las pestañas empiezan por ella, así se distinguen varias consolas.
- **Los enlaces del pie muestran su destino** (github/CharlesGool, etc.) en lugar de solo "Autor" y "Repositorio".
- **Las dos tarjetas de Mini Drive se llaman** "Descarga remota" y "Subida local".
- **Tailscale muestra solo la cuenta cuando el nombre de la tailnet es el mismo** (como en las cuentas personales); la tailnet de una organización sigue mostrando ambas filas.

#### Añadido

- **Reinicios de tráfico según el calendario.** Los límites de tráfico de cada función y el total de Inicio pueden reiniciarse en días de la semana elegidos, un día del mes o un día del año, a una hora elegida (hora local del servidor), con las mismas reglas que las tareas programadas; una función también puede reiniciarse una sola vez. El antiguo "cada N días/meses/años" y el "día del mes (UTC)" del total siguen funcionando hasta que se cambien en la página.
- **Fechas más flexibles en las tareas programadas.** Las programaciones mensuales aceptan los días 1 a 31 (en un mes más corto, su último día) y hay un tipo anual.
- **Varias claves de envío de Bark** (una por dispositivo); cada aviso se envía a todas. La página muestra los cuatro primeros y cuatro últimos caracteres de cada clave para distinguirlas, y cada una se puede eliminar.
- **Los registros de certificados de cliente revocados se pueden eliminar.** La lista de certificados tiene una columna de estado y se pagina a partir de 10 filas.
- **Cada origen del tráfico total de Inicio tiene una barra de uso.**

#### Corregido

- **La biblioteca de traducción de la interfaz vuelve a una versión con las correcciones de seguridad.** Al pasar a la nueva interfaz, la plantilla devolvió vue-i18n a 11.4.13 (v5.6.1 la había subido a 11.4.18 por dos avisos XSS); ahora es 11.4.23. El código nunca usa entradas del usuario como plantilla de traducción, así que no era explotable.
- Las instancias FRPC con nombre en chino no cargaban su tráfico en la página de edición.
- En la tabla de dispositivos de Tailscale, la IPv4 y la IPv6 de un dispositivo aparecían juntas en una línea.
- Los botones "Gestionar módulos", "Ver registros" y "Abrir ajustes de seguridad" de Ajustes no estaban alineados a la derecha; en tarjetas lado a lado, los botones inferiores ahora quedan a la misma altura.
- Los grupos del historial de cambios escritos como un párrafo (como "Verificación") no se mostraban; ahora sí, y los grupos vacíos muestran "-".
- Una petición JSON con un sustituto aislado fallaba con 500 al usar un campo; ahora se rechaza (400).

#### Verificación

Todas las comprobaciones automáticas pasan: comprobación de diseño, de tipos, 1637 pruebas en navegador (capturas, maquetación y accesibilidad) y 240 pruebas unitarias de Python. Una instalación limpia en un contenedor Debian 13 desechable superó 77 comprobaciones de la API. Las versiones de prueba se instalaron sobre la máquina virtual de pruebas de casa y el VPS de producción de Macao (Debian 11) y se revisaron página por página en un navegador real: verificación de administrador, un comando en el terminal, prueba de conexión y edición de FRPC, activar y ejecutar la prueba de velocidad, instalar iperf3 y abrir y cerrar su ventana, cambiar de idioma, los diálogos de tráfico total y de límites de tráfico, y las listas de certificados y claves de Bark; los 12 comentarios del servidor de Macao se corrigieron y confirmaron.

Sin verificar en un servidor real: que un reinicio de calendario llegue a su momento (solo pruebas unitarias), envíos reales a varias claves de Bark, operaciones de reenvío de dominios con datos reales, restaurar una copia e iniciar sesión en Tailscale.

#### Problemas conocidos

- Al volver a una versión anterior: un total con la nueva programación de reinicio empieza un periodo nuevo, varias claves de Bark se tratan como no configuradas y las versiones anteriores no entienden el nuevo formato de reinicio por función.
- Parte del texto chino heredado mezcla puntuación de ancho completo y medio; la ayuda del modo de inicio de sesión muestra comillas invertidas literales alrededor de un comando.
- Las tareas programadas y las copias solo se pueden fijar al minuto en la página (el servidor sigue admitiendo segundos).

### v7.0.5 — 2026-11-17

Correcciones de diseño en la sección de tráfico de la página FRPS. El comando de actualización no cambia y se conservan la configuración y los datos.

#### Corregido

- **La sección de tráfico de la página FRPS no ocupaba todo el ancho de la tarjeta.** El título estaba centrado y las cuatro casillas eran más estrechas que la tarjeta. Ahora usa el mismo diseño de tarjeta de tráfico que las páginas de Tailscale y FRPC: título a la izquierda y casillas a todo el ancho.
- **El botón «Gestión de acceso» tocaba las casillas de arriba.** Ahora hay un espacio entre ambos.

#### Verificación

Comprobado iniciando sesión y renderizando la página FRPS en el servidor de Macao. Pasa toda la suite automática.

### v7.0.4 — 2026-11-17

Refuerzo de seguridad: se corrigen tres problemas hallados en una revisión de código. El comando de actualización no cambia y se conservan la configuración y los datos.

#### Seguridad

- **Tiempos de espera de lectura.** Tras el handshake TLS, un cliente silencioso o muy lento podía mantener un hilo y una conexión para siempre, y con suficientes la consola dejaba de responder (sin necesidad de certificado). Ahora las conexiones se cierran tras 60 s (consola) o 30 s (página pública 80/443) sin datos; el límite es por lectura o escritura, así que las descargas largas y las pruebas de velocidad no se ven afectadas.
- **«Descargar desde URL» ya no puede apuntar a esta máquina ni a una dirección de metadatos de la nube.** Se rechazan las direcciones de bucle local (127.x, ::1), de enlace local (169.254.x, que incluye los metadatos de la nube), no especificadas y multicast, también cuando una redirección lleva a ellas; las direcciones de la LAN siguen funcionando. Un mensaje nuevo lo explica.
- **Restaurar una copia ya no sobrescribe la clave de publicación fijada.** `release-key.pub` de una copia se omite al restaurar, así que una copia subida no puede cambiar la clave de firma en la que confía este host.

#### Verificación

Seis pruebas nuevas y una de copias; pasa toda la suite. En la VM doméstica, una conexión que envió media petición y calló se cerró a los 60 s, y las páginas de la consola funcionan. La comprobación de direcciones solo tiene pruebas unitarias; la VM doméstica tiene la página Archivos desactivada, así que no se probó en una página real.

#### Problemas conocidos

- La comprobación de direcciones se hace antes de empezar la descarga; no protege frente a un nombre que se resuelva distinto después (DNS rebinding).
- Restaurar una copia aún puede escribir unidades systemd dentro del conjunto permitido; requiere acceso de administrador.

### v7.0.3 — 2026-11-17

El botón «Elegir archivo» de la tarjeta de subida de la página Copias de seguridad sigue la plantilla. El comando de actualización no cambia y se conservan la configuración y los datos.

#### Corregido

- **El botón «Elegir archivo» no cumplía las reglas de diseño.** Era el campo de archivo del navegador (distinto en cada navegador y diferente de los demás botones). Ahora es el mismo botón independiente con borde de la página Archivos, con el nombre del archivo elegido al lado («Ningún archivo» si no hay) y el botón Subir a la derecha.

#### Verificación

Se renderizó la página de copias en la VM doméstica y se comprobó el diseño; la comprobación de diseño pasa. No se probó en un navegador real que se muestre el nombre tras elegir ni la redirección tras subir.

### v7.0.2 — 2026-11-17

Los controles de fecha y hora siguen la plantilla y se corrigen varias tarjetas que no ocupaban todo el ancho. El comando de actualización no cambia y se conservan la configuración y los datos.

#### Mejorado

- **Controles de fecha y hora.** Antes eran los controles propios del navegador (de 12 horas con AM/PM, con un aspecto distinto en cada navegador). Ahora la hora es una entrada segmentada de 24 horas "hora : minuto : segundo" y la fecha una entrada segmentada "año - mes - día" con un calendario emergente (los días pasados aparecen atenuados y no se pueden elegir). Se puede escribir (salta al siguiente segmento tras dos dígitos), cambiar con las flechas arriba y abajo, y los valores fuera de rango se ajustan; se ve igual en todos los navegadores y con el mismo estilo que los desplegables y otros controles. Se usa en la programación de las tareas programadas y de la copia programada.

#### Corregido

- **Tarjetas que no ocupaban todo el ancho.** La tarjeta de "tráfico" de páginas como Tailscale estaba limitada a unos 44rem y la tarjeta de nodo de Singbox a 42rem, dejando un gran espacio vacío a la derecha en pantallas anchas; ahora tienen el ancho del contenido.
- **Un hueco entre las tarjetas pequeñas dentro de la tarjeta de nodo.** Las tres tarjetas "Puerto / SNI / Destinos accesibles" estaban en una cuadrícula de dos columnas, así que la última ocupaba solo media fila. Ahora se reparten toda la fila según su número, también si es impar; en el móvil siguen siendo dos por fila.

#### Verificación

Los controles nuevos se manejaron en un navegador real en una máquina virtual doméstica: escribir hora, minuto y segundo da 12:30:10, las flechas cambian y limitan el valor y un valor incompleto no se envía; el calendario se abre, los días pasados no se pueden elegir, elegir un día rellena año, mes y día, una fecha no válida (30 de febrero) no se envía y una válida sí. Las mediciones de la página confirman que la tarjeta de nodo de Singbox y la tarjeta de tráfico de Tailscale tienen el ancho del contenido, y se vio la tarjeta de nodo en anchos de escritorio y de móvil. 209 pruebas automáticas; los controles del front-end no tienen prueba automática y se verificaron uno a uno con un script de navegador.

#### Problemas conocidos

- El ajuste "próxima hora de reinicio" del nodo sigue usando el control de fecha y hora del navegador; esta vez no se cambió.

### v7.0.1 — 2026-11-17

Se rehace el flujo de restauración de copias y las claves de copias tienen botones de copiar. El comando de actualización no cambia y se conservan la configuración y los datos.

#### Mejorado

- **Restaurar primero muestra una vista previa y luego pide confirmar.** "Restaurar" abre una vista previa con el equipo de origen, la versión, el tipo, la fecha de creación y el número de archivos de la copia. Una copia de otro equipo o de una versión más nueva se considera de riesgo y hay que marcar la confirmación para restaurarla; el servidor lo vuelve a decidir antes de actuar.
- **La clave privada solo se necesita al restaurar.** Descargar y subir una copia cifrada no requieren la clave privada (el servidor no la tiene y no puede comprobarla); se introduce en la vista previa tras pulsar "Restaurar", una clave errónea se indica al instante y no se cambia nada. Al subir una copia se pasa directamente a esta vista previa.
- **Las copias cifradas registran su clave de destino.** Una copia cifrada nueva lleva en la cabecera con qué clave pública está sellada; tras cambiar la clave de copias, las copias cifradas anteriores se marcan como "Otra clave" en la lista. Las copias cifradas del formato anterior se siguen pudiendo restaurar.
- **El resultado de la restauración es visible.** El resultado (cuántos archivos se restauraron, o por qué falló y que "la configuración actual no se modificó") aparece arriba en la página de copias.

#### Nuevo

- **Las copias programadas y las tareas programadas comparten una misma programación.** La parte "Cuándo ejecutar" es igual en ambas páginas: se elige primero el tipo (repetida, o solo una vez); en una repetida se elige la frecuencia (cada cierto tiempo, cada día, cada semana, cada mes, cron personalizado), luego los días y por último la hora, **exacta al segundo**, por ejemplo "cada semana, miércoles, 12:30:10". La copia programada ahora también puede hacerse cada semana, cada mes, cada pocas horas, o una sola vez en un momento elegido.
- **Programaciones de una sola vez.** Además de las tareas repetidas hay tareas y copias que se ejecutan solo una vez: se elige fecha y hora (una hora pasada se rechaza); después la tarea se marca como "Hecha" y se desactiva (sigue en la lista, y la copia programada se apaga sola); una perdida por más de 2 minutos porque la consola no estaba en marcha se registra como "Perdida" en lugar de ejecutarse a posteriori.
- **Botones de copiar junto a las claves de copias.** Al generar una clave de copias, la clave privada y la pública tienen cada una un botón de copiar, con la función de copiar que ya tienen otras páginas de la consola.

#### Verificación

Verificado en una máquina virtual doméstica con la consola real: vistas previas de copias en claro y cifradas; claves privadas erróneas o mal formadas rechazadas al instante sin cambiar datos; la clave correcta restaura con el resultado en la página de copias; tras cambiar el nombre de equipo dentro de una copia, la vista previa avisa y pide marcar la casilla, el servidor se niega a restaurar sin ella sin cambiar nada y con ella la restauración funciona; tras cambiar la clave de copias, una copia cifrada anterior se marca como "Otra clave"; descargar copias en claro o cifradas y subir cifradas no requieren clave privada, y los archivos basura se siguen rechazando. Un clic real en el botón de copiar copia exactamente la clave privada. El nuevo formulario de programación de las tareas programadas y de la copia programada se verificó en la consola real: semanal miércoles 12:30:10, diaria con segundos, mensual, por intervalo y cron se guardan y se muestran bien; una tarea de una sola vez fijada 25 segundos después se ejecutó una vez a su hora, quedó marcada como hecha y desactivada y no volvió a ejecutarse; se rechazaron una hora pasada, una fecha no válida y el formulario antiguo; una copia programada de una sola vez hizo una copia a su hora y apagó su programación. 209 pruebas automáticas. El servidor de Macao no se probó antes de esta versión.

#### Problemas conocidos

- La consola mira las programaciones cada segundo; una programación diaria, semanal, mensual o de una sola vez perdida por no más de 2 minutos aún se ejecuta, más tiempo no se recupera (la de una sola vez se registra como perdida).
- Una copia cifrada subida no se puede comprobar antes de restaurarla (si está dañada) ni saber qué clave privada necesita (la cabecera anterior no lo registra).
- Restaurar una copia de otro equipo trae consigo la clave de datos, el método de acceso y los certificados de ese equipo; la vista previa lo avisa y antes se hace una copia del estado actual.

### v7.0.0 — 2026-11-16

Los datos de estado se guardan cifrados, las copias se pueden cifrar con una clave propia y hay cuatro métodos de acceso. Esta versión migra un formato de datos: el comando de actualización no cambia y se conservan la configuración y los datos, pero para volver a una versión anterior hay que descifrar antes (véase abajo).

#### Nuevo

- **Calibración del tráfico total.** El total de la página de inicio incluye "Calibrar": introduzca el uso que muestra el panel del proveedor para este periodo y la consola guarda la diferencia como "calibración", la muestra en su propia barra (con signo), la incluye en el total y la borra al empezar el siguiente periodo. Déjelo vacío y guarde para borrarla.
- **Cifrado de datos.** El instalador crea la clave de datos `/etc/vps-server/data.key` y la consola guarda cifrados la contraseña de administrador, las sesiones, la clave de alertas (Bark), los registros de auditoría, las direcciones que han iniciado sesión, la lista de acceso a la consola, las IP permitidas, el índice de Mini Drive, las tareas programadas, los ajustes de copias, la clave privada TLS y la clave privada de la CA de clientes. Los archivos en claro de una versión anterior se leen tal cual y se convierten en cifrados al arrancar. La página de copias incluye una tarjeta "Cifrado de datos" con el estado. Protege frente a una copia del directorio de estado, una imagen de disco o una copia sin la clave, no frente a quien ya es root en el equipo. La configuración de nodos, FRP, reenvío de dominios y Tailscale la leen esos programas directamente, y los archivos de Mini Drive y la base de datos de visitantes no se cifran.
- **Cifrado de copias.** Genere un par de claves en la página de copias: el servidor solo guarda la clave pública y las copias nuevas se cifran con ella como `.sealed`, por lo que no puede abrirlas; al restaurar se pide la clave privada que guardó (se muestra una vez y no se almacena). Las copias cifradas llevan la clave de datos y se restauran en cualquier equipo; sin clave pública las copias van en claro y no incluyen la clave de datos.
- **Cuatro métodos de acceso.** Ajustes > Acceso > Certificados de cliente: solo contraseña, solo certificado, contraseña o certificado, o contraseña + certificado. El antiguo "exigir certificados de cliente" pasa a "solo certificado" y, si estaba desactivado, a "contraseña o certificado". Antes de cambiar a un método que necesita certificado debe haber abierto los ajustes con un certificado activo, para no quedarse fuera.

#### Cambios

- **Se corrigen el inicio y el criterio del tráfico total.** Antes el total contaba desde el momento en que la consola lo registró por primera vez, así que no coincidía con el tráfico del periodo que muestran las páginas (una página de nodo con decenas de GiB frente a un total de unos cientos de MiB). Ahora el periodo cuenta desde el día de reinicio e incluye lo que cada origen ya ha usado en su ciclo actual; las estadísticas de versiones anteriores se reconstruyen solas tras la actualización (se conservan el límite y el día de reinicio). Cada fila muestra "tráfico bruto × multiplicador = uso facturado", lo que explica por qué es el doble de la cifra de la página. Cambiar el día de reinicio recalcula el periodo desde el nuevo día. Las instalaciones nuevas usan por defecto el día 1 del mes.
- **Antes de volver a una versión anterior a v7.0.0**, ejecute `python3 /root/apps/vps-server/src/web/secure_store.py decrypt-all`; `upgrade.py` rechaza una versión anterior mientras existan archivos cifrados. Guarde bien la clave de datos (`secure_store.py export-key`): sin ella no se pueden recuperar los archivos de estado cifrados.
- La copia de configuración automática previa a la actualización a v7.0.0 sigue en claro (se hace antes de que exista la clave de datos); elimínela cuando la actualización parezca correcta.
- El acceso con contraseña, con certificado y con "contraseña + certificado" se decide ahora según el método de acceso; se han ajustado las páginas de copias y de seguridad.

#### Verificación

Verificado en una máquina virtual doméstica con la consola real: tras la actualización el instalador creó la clave de datos y al arrancar 10 archivos de estado (incluidas las claves privadas TLS y de la CA) pasaron a estar cifrados, con HTTPS, acceso con certificado y emisión de un certificado nuevo con la clave de CA cifrada funcionando, y el estado se mantuvo tras reiniciar. Se comprobó qué permite y qué rechaza cada uno de los cuatro métodos de acceso (incluido que un dispositivo sin certificado no puede cambiar a un método que lo necesita, contraseñas erróneas y dispositivos sin certificado bloqueados), y se restauró el ajuste original. Una copia en claro no lleva la clave de datos; una copia cifrada es totalmente ilegible, una clave privada ausente, incorrecta o mal formada se rechaza sin cambiar nada, la clave correcta restaura con los servicios en marcha y el archivo temporal de la clave eliminado; subir una copia cifrada funciona. 191 pruebas automáticas, con los vectores de los RFC y contraste con una biblioteca de referencia. El servidor de Macao no se probó antes de esta versión.

#### Problemas conocidos

- Una clave privada de copias o una clave de datos perdida no se puede recuperar; guarde una copia aparte de cada una.
- La configuración de nodos, FRP, reenvío de dominios y Tailscale, los archivos de Mini Drive y la base de datos de visitantes no se cifran (véase arriba).
- La clave está en el mismo equipo que los datos, así que no protege frente a quien ya tiene root en él.

### v6.6.0 — 2026-11-16

Las actualizaciones ahora se verifican: un equipo que ha fijado la clave del mantenedor solo se actualiza a versiones firmadas con ella. El comando de actualización cambia, véase abajo. Se conservan la configuración y los datos.

#### Nuevo

- **Versiones firmadas.** El `SHA256SUMS` de la versión lleva una firma Ed25519, `SHA256SUMS.sig`. La clave privada se guarda cifrada en otro equipo del mantenedor; la máquina de compilación solo recibe la firma y nunca tiene la clave. Huella de la clave de versiones: `e6d9:e0c2:55dc:3f8c:b673:defd:9043:d5a0`.
- **Un comando de actualización que verifica.** `python3 /root/apps/vps-server/src/web/upgrade.py` verifica primero la firma, luego el SHA-256 del paquete, lo desempaqueta con seguridad, comprueba que la versión interna coincide con la etiqueta y solo entonces ejecuta el instalador del paquete nuevo; no confía en ningún script del paquete nuevo. Se rechaza una firma incorrecta, una suma que no coincide, una versión más antigua o un paquete cuya clave difiera de la fijada. Admite `--version`, `--variant online`, `--from DIR` (usar archivos ya descargados, sin red) y `--dry-run`.
- **Clave de versiones fijada.** La primera vez que el instalador ve un paquete con clave, fija `config/release-key.pub` como `<raíz del estado>/release-key.pub` y muestra la huella. Desde entonces el instalador también rechaza, con el comando antiguo, un paquete de un fork o uno sin clave. Un cambio de clave exige `--accept-key-change NUEVA-HUELLA`. Cualquiera puede publicar sus versiones con su clave; un equipo con la suya fijada no se actualizará a las de otros.

#### Cambios

- **La primera actualización a v6.6.0 sigue usando el comando anterior**; después use `upgrade.py`. La primera fijación es confianza en el primer uso: compare la huella que muestra el instalador con la de arriba.
- La verificación es Python puro de la biblioteca estándar (RFC 8032); los equipos no necesitan dependencias.

#### Verificación

Ensayado en una máquina virtual doméstica con la clave de firma real: instalar v6.6.0 con el comando antiguo fijó la clave (modo 0600, huella coincidente); en el equipo con la clave fijada, instalar con el comando antiguo un paquete sin clave y otro con otra clave se rechazó en ambos casos y la clave y la versión fijadas no cambiaron; `upgrade.py` rechazó una lista firmada por otro, un paquete manipulado y una versión más antigua, verificó el paquete auténtico con `--dry-run` y actualizó a v6.6.1 con los servicios en marcha y el directorio temporal eliminado. 104 pruebas automáticas, con firmas contrastadas con OpenSSL. La descarga directa desde GitHub (sin `--from`) y el servidor de Macao no se probaron antes de esta versión.

#### Problemas conocidos

- La huella fijada por ahora solo se lee con `python3 src/web/release_trust.py show --state-dir <raíz del estado>`; la consola aún no la muestra.
- Si se pierde la clave privada, los equipos que la fijaron solo pueden aceptar las versiones de una clave nueva mediante `--accept-key-change`.
- Volver a una versión anterior a v6.6.0 exige borrar antes `<raíz del estado>/release-key.pub`.

### v6.5.0 — 2026-11-16

Se añaden la copia de configuración y las tareas programadas, y una actualización ahora copia solo la configuración. El comando de actualización no cambia y se conservan la configuración y los datos.

#### Nuevo

- **Copia de configuración.** La página de inicio incluye "Copia de seguridad": copiar con un clic o automáticamente cada día a una hora fijada, conservando solo las últimas copias programadas (por defecto a las 03:00 cada día, conservando 7). Una copia contiene toda la configuración y el estado: ajustes de la consola, certificados y claves, nodos, FRP, reenvío de dominios, la sesión de Tailscale y los archivos de servicio; no contiene el código del programa ni los archivos de Mini Drive. Puede descargarla, subir una copia anterior y restaurar desde la página (antes se hace una copia del estado actual y después se reinician los servicios afectados). Los archivos contienen claves y tienen modo 0600.
- **Tareas programadas.** La página de inicio incluye "Tareas programadas": fije cuándo se ejecutan en términos cotidianos, sin cron: cada cierto número de minutos, horas o días, cada día a una hora fija, en días de la semana elegidos o un día del mes; la expresión cron sigue disponible. Los comandos se ejecutan en la hora local del servidor, cada tarea tiene tiempo límite, se puede activar, desactivar, ejecutar ahora y avisar por Bark si falla; no se inicia de nuevo mientras la ejecución anterior sigue en marcha; se conservan las últimas 20 ejecuciones por tarea (estado, código de salida, final de la salida). La copia de configuración también aparece en la lista.

#### Mejorado

- **El uso por origen bajo el total de la página de inicio también muestra barras de progreso**, de modo que se ve de un vistazo la parte de cada origen sobre el límite (o sobre el total si no hay límite). Las páginas de Copia de seguridad y Tareas programadas se rediseñaron: etiquetas de estado, diseño por bloques y orden también en el móvil.
- **Una actualización copia solo la configuración.** Antes de actualizar, el instalador guarda la configuración en `<raíz del estado>/backups/` (se conservan las 3 últimas), de modo que ya no hace falta copiar directorios enteros a mano. La copia no incluye el código (siempre disponible en GitHub) ni los archivos de Mini Drive. Un fallo de la copia solo avisa y no detiene la actualización.

#### Verificación

Verificado en una máquina virtual doméstica con la consola real: contenido de la copia (con la sesión de Tailscale, sin archivos de Mini Drive), descarga, subida (se rechazan archivos que no son copias y paquetes con rutas fuera de la configuración), la copia programada se dispara a su hora y elimina las antiguas por número, la restauración devuelve los archivos modificados a su contenido guardado con los servicios en marcha, y las tareas programadas se ejecutan como root según lo programado, con fallos, tiempos agotados y solapamientos omitidos registrados. La restauración y la copia programada se verificaron en la máquina virtual doméstica, no en el servidor de Macao. 72 pruebas automáticas.

#### Problemas conocidos

- Una restauración devuelve los contadores de tráfico a su valor en el momento de la copia.
- Las tareas programadas que se pierden mientras se reinicia la consola no se recuperan.

### v6.4.0 — 2026-11-16

FRP incorpora el modo stcp, los nodos de Singbox pueden limitar a dónde se conectan, la página de inicio muestra una barra de tráfico total y un fallo breve de nft ya no detiene frps ni el proxy. El comando de actualización no cambia y se conservan la configuración y los datos.

#### Nuevo

- **FRP admite stcp.** Un proxy tcp abre el servicio de su casa directamente en la IP pública y el puerto, accesible para cualquiera; un proxy stcp requiere una clave secreta y se accede mediante un visitor en otra máquina. Las instancias FRPC pueden añadir proxies stcp y visitors (solo escuchan en 127.0.0.1); la clave debe tener al menos 16 caracteres y nunca se vuelve a mostrar.
- **Alcance de acceso de los nodos de Singbox.** Cada nodo puede no tener restricciones, solo internet (se rechazan loopback, red local y direcciones locales) o limitarse a IP, IP:puerto, rangos CIDR o dominios concretos. Las reglas se escriben en las rutas de sing-box y se eliminan con el nodo; las demás reglas escritas a mano se conservan.
- **Barra de tráfico total en la página de inicio.** La parte superior muestra el tráfico combinado de todos los elementos medidos del periodo actual, con un límite total configurable (GiB) y un día de reinicio mensual (1-28). Por ahora el límite solo muestra un aviso; no limita ni desconecta al superarse.

#### Corregido

- **Un fallo breve de nft detenía frps y el proxy.** Los medidores terminaban en la primera llamada fallida a nft, y frps y el proxy dependen de ellos, por lo que todo se detenía y no se recuperaba. Los medidores de FRPS y de nodos ahora reintentan durante 60 segundos, tiempo en el que los límites ya instalados siguen vigentes; solo un fallo más largo los detiene, como estaba previsto.

#### Verificación

STCP y el alcance de acceso de los nodos se verificaron de extremo a extremo en una máquina virtual doméstica: la clave correcta conecta, una incorrecta se rechaza, los puertos de visitor escuchan solo en loopback y un nodo restringido rechaza de verdad loopback y red local. La corrección de los medidores se verificó con inyección de fallos: un fallo de nft de 20 segundos no interrumpió los servicios de nodos y uno de 76 segundos aún los detiene. La barra total se verificó con la consola real. Hay 34 pruebas automáticas.

#### Problemas conocidos

- El límite total solo avisa; si nadie abre la página de inicio al cambiar de mes, el nuevo periodo empieza algo tarde.
- En Debian 11 (nftables 0.9.8), crear o eliminar una instancia FRPC puede bloquear nft ocasionalmente; el reintento cubre los fallos breves.

### v6.3.3 — 2026-11-12

El paquete en línea ya se instala en servidores de China continental. El comando de actualización no cambia y se conservan la configuración y los datos.

#### Mejorado

- **El paquete en línea pasa a espejos cuando las descargas van lentas.** El paquete en línea descarga sing-box, frp y Caddy de GitHub durante la instalación, lo que podía atascarse en servidores de China continental (un problema conocido de v6.3.2). Ahora, si una descarga de GitHub sigue por debajo de 200 KB/s tras 15 segundos, la instalación pasa a los espejos gh-proxy.com y luego ghfast.top; venga de donde venga, la descarga se verifica con el mismo SHA-256. Defina `VPSSRV_GITHUB_MIRROR=https://su.espejo/` para probar antes su propio espejo, o `none` para no usar espejos. El README también explica cómo descargar el paquete a través de un espejo desde China continental. Tailscale no se descarga de GitHub y no se ve afectado.

#### Verificación

Una actualización en línea en un servidor de Alibaba Cloud en Cantón pasó al espejo para los tres componentes y terminó en 87 segundos (antes se atascaba); en otro servidor de China continental se descargaron y verificaron todos los componentes. El cambio de origen también se verificó en una simulación local.

### v6.3.2 — 2026-11-12

Corrige dos problemas del certificado IP. El comando de actualización no cambia y se conservan la configuración y los datos.

#### Corregido

- **Instalar desde la página del certificado IP activaba el reenvío de dominios.** El certificado IP y el reenvío de dominios funcionan sobre el módulo Caddy, y el botón de instalar de la página del certificado IP instalaba Caddy directamente y luego iba a la página de reenvío de dominios con este activado. Ahora el reenvío de dominios sigue desactivado: la instalación solicita el certificado IP y vuelve a su página, y si la solicitud falla Caddy se detiene y 80/443 vuelven a la página pública. Instalar desde la página de reenvío de dominios no cambia. El reenvío de dominios que ya se activó así no se desactiva al actualizar; desactívelo en la página de inicio si no lo necesita.
- **Los servidores en la nube tras NAT uno a uno no tenían IPv4 pública.** Servidores como Alibaba Cloud ECS solo tienen una dirección privada en su interfaz, así que el certificado IP indicaba que no había IPv4 pública y el reenvío de dominios no escribía registros A. Ahora, cuando la IPv4 del equipo es privada, la dirección de salida se obtiene de `www.cloudflare.com` por IPv4 y se guarda en caché 10 minutos.

#### Verificación

Se actualizó desde v6.3.1 un servidor Debian de Alibaba Cloud tras NAT uno a uno: se encontró su IPv4 pública, se emitió un certificado IP de Let's Encrypt y el puerto de la consola superó la verificación normal del certificado. La instalación desde la página del certificado IP solo se verificó en una simulación local, no pulsándola en un equipo sin Caddy.

#### Problemas conocidos

- El paquete en línea descarga sing-box, frp y Caddy de GitHub durante la instalación, lo que puede atascarse en servidores de China continental; use allí el paquete sin conexión.

### v6.3.1 — 2026-11-12

Corrige dos problemas con las instancias FRPC en la contabilidad de tráfico, y el aviso que muestra el script de configuración de Windows al ejecutarse desde una ubicación de red. El comando de actualización no cambia y se conservan la configuración y los datos.

#### Corregido

- **Las instancias FRPC que usan el mismo servidor se cuentan juntas.** La contabilidad cuenta FRPC por sus conexiones con la dirección y el puerto de un servidor, así que las instancias que usan el mismo servidor no se distinguen: en v6.3.0 cada una de sus entradas contaba el mismo tráfico, y limitar o cortar una afectaba a la otra. Ahora comparten una entrada para contar y limitar; la tarjeta de cada instancia la muestra e indica qué instancias la comparten. Al actualizar, las entradas por instancia de v6.3.0 se fusionan en ella, conservando totales y límites.
- **Las instancias FRPC con nombres no ingleses (en chino, por ejemplo) no tenían contabilidad de tráfico.** Ahora se acepta cualquier nombre que permita la gestión de FRPC.
- **Script de configuración en un clic de Windows.** El script pasa su propia ruta a PowerShell en una variable de entorno en lugar de la línea de comandos, así que funciona con una ruta que contenga una comilla simple; al ejecutarse desde una ubicación de red (como un recurso compartido del NAS) indica que el aviso de CMD sobre rutas UNC no admitidas se puede ignorar.

#### Verificación

Verificado con tráfico real en un contenedor Debian 13 desechable y en dos máquinas virtuales Debian 13 de la red local: conteo, reducción a unos 1 Mbps al llegar al límite, corte y recuperación para el reenvío de puertos, Tailscale (local y reenviado), FRPC e iperf3, además de la actualización in situ de ambas máquinas virtuales desde v6.1.0. La agrupación de FRPC y la migración de entradas antiguas se verificaron en una simulación local y en una máquina virtual; el lanzador del script de configuración se verificó en Windows desde una ruta UNC (con letras chinas y paréntesis, con un directorio de trabajo UNC), sin una importación completa del certificado en Windows.

### v6.3.0 — 2026-11-12

Mini nube, la prueba de velocidad, el reenvío de dominios, iperf3, el reenvío de puertos, FRPC y Tailscale tienen ahora la misma contabilidad y los mismos límites de tráfico que los nodos Singbox. El comando de actualización no cambia y se conservan la configuración y los datos; la instalación añade el servicio `vps-server-traffic-meter`.

#### Añadido

- **Límites de tráfico en todas las funciones que mueven tráfico.** La página de cada función tiene una tarjeta "Tráfico" con la subida, la bajada y lo contabilizado; en "Límites de tráfico" se configura un límite de tráfico (al alcanzarlo, reducir a 1 Mbps o cortar), límites de velocidad de subida y bajada, un periodo de validez y un ciclo de reinicio, igual que en los nodos Singbox. Las páginas de la consola, el terminal web y SSH no cuentan.
  - Mini nube (enlaces de descarga, subidas, descargas del servidor) y la prueba de velocidad comparten el puerto de la consola, así que la consola los cuenta y limita; al cortarse, los enlaces y la prueba de velocidad responden 503 y se rechazan las subidas y descargas del servidor.
  - Reenvío de dominios: el 80/443 de Caddy en conjunto. iperf3: su puerto. FRPC: la conexión de cada instancia con su servidor. Cada byte cuenta una vez.
  - Reenvío de puertos: cada regla por separado; el tráfico reenviado entra y sale del servidor, así que cuenta dos veces.
  - Tailscale: el tráfico de la interfaz `tailscale0`; lo que reenvía el servidor (nodo de salida, rutas de subred) cuenta dos veces.
- El nuevo servicio `vps-server-traffic-meter` (tabla nft `vps_server_traffic`) se ocupa de las últimas cinco. Si falla, lo registra y reintenta y nunca detiene esas funciones; la medición de nodos y FRPS no cambia y sigue deteniendo su servicio ante un fallo.

#### Verificación

En un servidor de pruebas público: el reenvío de dominios bajó a unos 1 Mbps (0.13 MiB/s) al llegar al límite, no conectaba al cortarse y se recuperó al quitar el límite; las descargas de Mini nube fueron a 1.01 MiB/s con un límite de bajada de 8 Mbps y respondieron 503 al cortarse; una prueba de velocidad de 20 MiB contó 20 MiB; guardar y quitar límites desde la página funcionó; las reglas de reenvío de puertos y FRPC (con límites de velocidad, límite de tráfico y corte) pasaron la comprobación del núcleo. Las reglas de nodos y FRPS no cambian ni un byte. Sin verificar: tráfico real de reenvío de puertos y FRPC, los límites de Tailscale una vez alcanzados, tráfico real de iperf3. Conocido: las descargas de Mini nube por un dominio cuentan tanto para Mini nube como para el reenvío de dominios.

### v6.2.1 — 2026-11-12

Corrige que direcciones como los enlaces de descarga de Mini nube apuntaran a `127.0.0.1` al abrir la consola por un dominio. El comando de actualización no cambia y se conservan la configuración y los datos.

#### Corregido

- Al abrir la consola por el reenvío de dominios (un sitio cuyo destino es "Esta consola"), Caddy pasaba a la consola su propia dirección de conexión `127.0.0.1:puerto`, así que todas las direcciones que la consola generaba con ella eran incorrectas: los enlaces de descarga de Mini nube y los de suscripción de Clash apuntaban a `127.0.0.1`, y el terminal web fallaba la comprobación de origen. Ahora Caddy pasa el dominio que usó el visitante; solo los dominios del propio sitio llegan así a la consola. Tras actualizar basta con recargar la página; no hace falta volver a crear los enlaces de descarga existentes.
- Con Caddy en marcha, el enlace "Página pública" del inicio apuntaba al dominio cuando la consola se abría por uno, pero Caddy muestra esa página solo para la IP del servidor. El enlace usa ahora la IPv4 pública.

#### Verificación

En un servidor de pruebas público, un certificado de cliente temporal inició sesión en la consola por un dominio: todos los enlaces de descarga de Mini nube usaban ese dominio y "Página pública" llevaba a la IP del servidor; el acceso por la IP y el puerto de la consola no cambia. Sin verificar: el terminal web por un dominio.

### v6.2.0 — 2026-11-12

Nueva Mini nube: guarda archivos temporalmente en el servidor y crea enlaces de descarga sin contraseña, por ejemplo para que un servidor que no llega a GitHub descargue desde aquí. El certificado IP pasa a ser un interruptor propio en el inicio y ya no exige configurar antes un dominio; la página pública de accesibilidad también funciona mientras Caddy está en marcha; el reenvío de dominios admite varios tokens de Cloudflare. El comando de actualización no cambia y se conservan la configuración y los datos.

#### Añadido

- **Mini nube (desactivada por defecto).** Los archivos se pueden subir desde el navegador o indicando un enlace http/https para que el servidor los descargue por sí mismo (en segundo plano; se puede cerrar el navegador). Cada archivo puede tener varios enlaces de descarga, con caducidad de 5, 10 o 30 minutos, 1, 2 o 5 horas, 1, 7 o 30 días, o sin caducidad, además de un límite de descargas opcional, y cualquiera se puede revocar en todo momento. Quien tenga el enlace no necesita contraseña ni certificado de cliente, y `curl -O`, `wget` y las descargas reanudadas funcionan. El límite de capacidad es de 5 GiB por defecto y siempre quedan al menos 500 MiB libres en el disco. Se puede fijar un límite de velocidad de descarga, que todos los enlaces juntos no superan. Una subida interrumpida o sin datos durante 2 minutos descarta el archivo parcial, y los restos se limpian cada 10 minutos.
- **Interruptor propio para el certificado IP.** El inicio tiene una tarjeta nueva «Certificado IP» que solicita un certificado de Let's Encrypt para la IPv4 pública del equipo, útil también en equipos cuyo certificado no está ligado a un dominio. Comparte Caddy con el reenvío de dominios (requiere instalar el módulo de reenvío de dominios); cada uno tiene su interruptor y Caddy funciona mientras cualquiera de los dos esté activado.
- **Varios tokens de Cloudflare.** Si los dominios están en cuentas de Cloudflare distintas, se pueden añadir varios tokens (hasta 20, con nombre). Cada sitio usa automáticamente el token que gestiona su dominio principal. Los tokens que Cloudflare rechaza no se guardan. El token único anterior se convierte automáticamente la primera vez que se cambian los tokens.

#### Cambiado

- **La página pública de accesibilidad ya no se desactiva mientras Caddy está en marcha.** Ahora la devuelve Caddy directamente: el puerto 80 la muestra para la IP y para los nombres no configurados (sin redirigir a HTTPS, para poder comprobar el propio puerto 80), y el puerto 443 la muestra para `https://IP-del-equipo/` cuando el certificado IP está activado. Las solicitudes HTTP de los sitios con dominio siguen redirigiéndose a HTTPS.
- **Un solo interruptor «Página pública» en el inicio.** Las tarjetas «Página HTTP» y «Página HTTPS» se fusionan; un solo interruptor activa o desactiva ambas páginas, y la tarjeta permite abrir por separado la página HTTP y la HTTPS.
- El apartado «No elegir el certificado cada vez» de la página de emisión de certificados de cliente y de los ajustes de seguridad se muestra desplegado directamente; se ha ordenado la maquetación de Mini nube y de la página del certificado IP.

#### Corregido

- Cuando el menú desplegable era más estrecho que sus opciones, el texto de las opciones se rompía en una letra por línea: el ancho del menú ahora lo determinan las opciones.

#### Verificación

Verificado en un equipo de prueba con acceso público, desplegando cada versión de prueba por copia de archivos: subida a Mini nube, descarga del servidor (recurso de GitHub Release), descarga con los enlaces sin certificado, tanto por el puerto de la IP como por el dominio, con el requisito de certificado de cliente activo, límite de descargas, caducidad y límite de velocidad (una descarga y dos simultáneas cumplen lo configurado); las cuatro combinaciones de los interruptores de certificado IP y reenvío de dominios; la página pública de accesibilidad por http/https con la IP (validando estrictamente el certificado IP), mientras las solicitudes con dominio siguen redirigiéndose; conversión del token antiguo con varios tokens y sincronización DNS, y tokens rechazados por Cloudflare que no se guardan; el interruptor de página pública con Caddy en marcha. En el equipo local se verificaron con interfaces y conexiones simuladas la elección de token entre cuentas y que las subidas bloqueadas o interrumpidas no dejan archivos. Sin verificar: un token real de una segunda cuenta de Cloudflare; el cambio de ambos puertos con un solo interruptor de «Página pública» sin Caddy; subidas bloqueadas en una red real; registros IPv6.

### v6.1.0 — 2026-11-11

Iniciar sesión con certificado de cliente cuesta menos: los archivos de configuración en un clic importan el certificado y hacen que el navegador lo elija solo, sin buscarlo en el selector en cada inicio de sesión; ahora los certificados se importan en macOS. El comando de actualización no cambia y se conservan la configuración y los datos.

#### Añadido

- **Archivos de configuración en un clic.** El primer paso de la página que aparece tras emitir un certificado ofrece archivos para Windows (`.cmd`), macOS (`.mobileconfig`) y Linux (`.sh`). Importan el certificado y, mediante la política del navegador `AutoSelectCertificateForUrls`, hacen que Chrome y Edge (y Chromium en Linux) lo elijan solos en cada dirección de la consola (la dirección actual y los dominios e IP que apuntan a la consola). Un dispositivo que ya tiene el certificado puede descargar una versión sin él en Configuración > Seguridad > Certificados de cliente para activar solo la selección automática. Los pasos manuales con el `.p12` pasan a "Importación manual" en la página de emisión.
- **Los nombres de los certificados incluyen el nombre del host.** Las CA y los certificados de dispositivo nuevos llevan el nombre del host, así que en el selector se distinguen los certificados de varios hosts. Las CA existentes conservan su nombre y los certificados emitidos siguen funcionando.

#### Corregido

- macOS indicaba contraseña incorrecta al importar un certificado (tanto en Llavero como en perfiles): el paquete del certificado usa ahora un cifrado que macOS admite (SHA1/3DES). Los certificados emitidos antes deben volver a emitirse para usarlos en un Mac.
- Cuando la conexión no presenta certificado, la tarjeta de certificados indica que un dispositivo nuevo genere el suyo abajo.
- Los botones de editar, registro de accesos y eliminar al pie de las tarjetas de sitios del reenvío de dominios quedan en una fila con el mismo estilo.

#### Verificación

El operador verificó la configuración de Windows en una máquina real. Linux se verificó de extremo a extremo en Ubuntu 22.04 con Chrome 157 (importación, escritura de la política, y las direcciones de IP y de dominio de la consola enviando el certificado sin selector). El operador importó en macOS, mediante el perfil, un certificado con el nuevo cifrado e inició sesión. Sin verificar: Chromium de snap (almacén de certificados aparte, no admitido por el script) y Firefox (no lee estas políticas). Limitación conocida: en un mismo Mac, los perfiles de dos hosts entran en conflicto por la política del navegador.

### v6.0.0 — 2026-11-11

Añade un módulo de reenvío de dominios (con Caddy incluido) que sustituye al módulo Lucky, eliminado: HTTPS por subdominio hacia un puerto local o la consola, con certificados automáticos y registros DNS mantenidos en Cloudflare. La consola también puede obtener un certificado de confianza para la IP del servidor. El comando de actualización no cambia y se conservan la configuración y los datos; el módulo Lucky se elimina durante la actualización.

#### Añadido

- **Reenvío de dominios (módulo `caddy`).** En la página Dominios se añade un subdominio (eligiendo entre los dominios principales que gestiona el token de Cloudflare) y se reenvía a un puerto local (por ejemplo, un puerto de frps) o a la propia consola. El Caddy 2.11.9 incluido obtiene y renueva certificados de Let's Encrypt, por lo que ocupa los puertos 80/443 y la página pública de alcance se desactiva mientras funciona. Los registros A/AAAA (solo DNS) se crean y eliminan con la API de Cloudflare; la IP pública se comprueba cada 5 minutos y los registros la siguen.
- **Gestión de sitios.** Cada sitio se puede desactivar y editar; el backend puede usar HTTPS (sin comprobar su certificado, para NAS o routers autofirmados) y puede recibir como Host el nombre original o su propia dirección. Hasta 8 nombres adicionales por sitio, límites por dirección o red de origen y una contraseña de acceso (solo se guarda el hash). Cada sitio tiene un registro de acceso (últimas 200 peticiones).
- **Historial y avisos.** Se registran los cambios de sitios, activaciones, registros DNS y cambios de IP pública. Un cambio de IP, un fallo de DNS o un certificado a punto de caducar sin renovar se notifica con la configuración de Bark de la consola, como mucho una vez al día por evento.
- **Consola en un dominio.** Un sitio puede apuntar a "esta consola": Caddy entrega el certificado de cliente a la consola y "exigir certificado de cliente" sigue aplicándose.
- **Certificado HTTPS para el acceso por IP.** Al activarlo en la página Dominios se obtiene un certificado de Let's Encrypt para la IPv4 pública (unos 6 días, Caddy lo renueva) y la dirección actual de la consola, `https://IP:puerto`, pasa a usarlo, de modo que el navegador deja de avisar. Los puertos 80/443 no sirven la consola para la IP sola.

#### Eliminado

- **Módulo Lucky (incompatible).** Las funciones de DDNS, proxy inverso y certificados que se usaban las cubre el reenvío de dominios. La actualización detiene y elimina Lucky tras archivar su configuración en `data/module-backup-lucky-*.tar.gz` del directorio de estado; `lucky` en `VPSSRV_MODULES` se ignora.

#### Corregido

- La comprobación del instalador en línea daba por ausentes los certificados de CA guardados en directorios con hash.

#### Verificación

Instalado y actualizado desde una versión anterior en contenedores de sistema Ubuntu 24.04 desechables, probando activación, edición, backends HTTPS, la elección de Host, límites de dirección, contraseñas, nombres adicionales, registros de acceso y la deduplicación de avisos. En un servidor de pruebas público con una zona real de Cloudflare y Let's Encrypt: certificados para subdominios y nombres adicionales, contraseñas, límites de dirección, activación, limpieza de DNS al eliminar, la consola en un dominio y la emisión del certificado de IP y su adopción por la consola (una reemisión forzada se adoptó sola). Sin verificar: la renovación natural del certificado de IP de 6 días, el envío real por Bark (solo simulado), los registros IPv6 y la apertura de 80/443 en ufw/firewalld. No se admiten certificados comodín ni la exportación de certificados; el DNS es solo Cloudflare.

### v5.8.0 — 2026-11-08

FRPS obtiene la misma contabilidad y límites de tráfico que los nodos Singbox; los certificados de cliente se firman ahora con un OpenSSL incluido, lo que corrige autoridades de certificación inválidas en equipos con un openssl antiguo. El comando de actualización no cambia y se conservan la configuración y los datos.

#### Añadido

- **Contabilidad y límites de tráfico de FRPS.** Igual que un nodo Singbox: uso de subida/bajada, cuota de tráfico (limitar a 1 Mbps o bloquear al superarla), límites de velocidad de subida y bajada, vigencia y ciclo de reinicio; la cuota cuenta `(subida + bajada) × 2`. FRPS se mide en su bindPort, por el que pasan todos los túneles frpc. El uso aparece en la página de FRPS y se edita en el diálogo "Límites". Un servicio nuevo, `vps-server-frps-meter`, hace la medición y detiene FRPS si la contabilidad falla. Por ello el módulo FRPS necesita nftables: el paquete sin conexión lo incluye y, para el paquete en línea, el instalador lo instala con apt si falta.
- **Versiones mínimas de dependencias.** Antes de cambiar cualquier servicio, el instalador comprueba Bash 4.1, systemd 240, SQLite 3.24 y la biblioteca OpenSSL 1.1.1 que usa Python, `/usr/bin/python3` 3.9+ y comandos básicos (flock, sha256sum, base64, getent, install, mktemp, systemd-run); el paquete en línea también comprueba los certificados CA. Si algo no se cumple, la instalación se detiene e indica qué falta.
- `python3 /root/apps/vps-server/src/web/client_cert.py check` muestra el openssl usado para firmar certificados y el resultado de la autoprueba de la autoridad de certificación.

#### Mejorado

- Los certificados de cliente los firma el OpenSSL 3.5.9 LTS estático incluido en el paquete, con una configuración mínima propia, así que la versión de openssl y el openssl.cnf del equipo ya no influyen; el instalador ya no instala openssl con apt.
- Un `ip`/`ss` del equipo sin rutas JSON o sin `-H` cede ante la copia incluida; un iperf3 del equipo solo se usa si no hay copia incluida y debe ser 3.1+.

#### Corregido

- En equipos con OpenSSL 1.1.1k u otras versiones antiguas, la autoridad de certificados de cliente se creaba con Basic Constraints duplicado y fallaba incluso su propia verificación, por lo que el inicio de sesión con certificado no funcionaba. Ahora una autoridad nueva debe pasar una autoprueba de TLS mutuo con la biblioteca TLS del equipo; una autoridad inválida existente se reemplaza la próxima vez que se emite un certificado, sus certificados se marcan como revocados y se desactiva "Exigir certificado de cliente".
- El estado de conexión de FRPC siempre aparecía como desconectado en equipos que solo tienen el `ss` incluido.
- El `sha256sum -c SHA256SUMS` de la instalación sin conexión del README fallaba si solo se descargaba el paquete sin conexión; ahora usa `--ignore-missing`.

#### Verificación

OpenSSL 1.1.1k reprodujo el problema original en local y se confirmó la corrección; las comprobaciones de dependencias y la emisión de certificados pasaron en un contenedor Debian 11 (Python 3.9, libssl 1.1.1w). En un contenedor de sistema Debian 13, el paquete sin conexión instaló web, proxy y frps: todos los servicios funcionaron, la consola se usó por HTTPS, los límites de FRPS se aplicaron en las reglas del kernel, los límites de nodos siguieron funcionando y la desinstalación completa no dejó restos. El operador actualizó un VPS en el sitio con `v5.8.0-test.1` y confirmó la emisión e inicio de sesión con certificado y la contabilidad y cuota de FRPS. No se verificó en un equipo real cuya biblioteca TLS sea OpenSSL 1.1.1k, ni se midió en un equipo real la velocidad del límite de 1 Mbps. Tras cambiar el bindPort de FRPS, el nuevo puerto queda sin medir hasta unos 2 segundos.

### v5.7.0 — 2026-11-08

Más seguridad en el inicio de sesión de la consola. El comando de actualización no cambia y se conservan la configuración y los datos; el instalador menciona 4 variables opcionales nuevas, y si no se definen se usan los valores predeterminados. La nueva configuración está en Configuración > Seguridad.

#### Añadido

- **Interruptor del bloqueo por fallos.** Activado por defecto. Desactivado no bloquea, pero sigue contando los fallos de cada IP y marca la que alcanza el umbral como "umbral alcanzado, sin bloqueo", para comprobar que la detección funciona. Los registros se pueden borrar.
- **Bloqueos crecientes.** Cada nuevo bloqueo de la misma IP en un día dura diez veces más: 30 segundos, 5 minutos, 50 minutos, unas 8 horas, como máximo 24 horas (`VPSSRV_LOGIN_LOCKOUT_MAX_SECONDS`). Un inicio de sesión correcto lo reinicia.
- **Agrupación IPv6 por /64 y límite global.** Las direcciones del mismo /64 cuentan juntas. Si todas las fuentes suman 20 fallos en 60 segundos, las direcciones que nunca iniciaron sesión no pueden usar la contraseña durante 5 minutos (`VPSSRV_LOGIN_GLOBAL_MAX_ATTEMPTS`, `VPSSRV_LOGIN_GLOBAL_LOCKOUT_SECONDS`); las direcciones conocidas, el acceso con certificado y el acceso por IP no se ven afectados.
- **Límite de acceso a la consola.** Desactivado por defecto. Activado, solo las IP o redes de la lista pueden conectarse a la consola; las demás se cortan antes del saludo TLS. No se puede activar ni quitar una entrada de forma que deje fuera la conexión actual. Si queda fuera, ejecute como root `python3 /root/apps/vps-server/src/web/console_access.py disable`; no hace falta reiniciar.
- **Dispositivos conectados.** Muestra los dispositivos con sesión (navegador, sistema, IP, inicio y última actividad) y permite cerrar la sesión de uno o de todos los demás. La sesión termina tras 2 horas sin actividad (`VPSSRV_SESSION_IDLE_SECONDS`); escribir en el terminal cuenta como actividad.
- **Registro de seguridad y avisos de Bark.** Registra inicios de sesión, bloqueos, aperturas del terminal root y cambios de seguridad, y muestra los 50 más recientes. Con una clave de Bark, los inicios de sesión desde una dirección nueva y los bloqueos se envían al móvil; la clave nunca se muestra en la página.

#### Mejorado

- Las respuestas de la consola llevan una Content-Security-Policy que solo permite los scripts propios y prohíben que otros sitios la incrusten. El antiguo script en línea pasó a un archivo propio.

#### Corregido

- Detrás de un proxy inverso (`VPSSRV_TRUST_PROXY=1`), la dirección del cliente es ahora la última entrada de `X-Forwarded-For` añadida por el proxy, así que un encabezado falsificado ya no afecta al límite de intentos, los registros ni el límite de acceso.
- La página de inicio de sesión deja espacio entre el botón de acceso con certificado y la etiqueta de la contraseña.
- Los comandos de extracción del README y la extracción interna del instalador indican el filtro `tar` de forma explícita, lo que elimina el `DeprecationWarning` de Python 3.12 y 3.13.

#### Verificación

Las pruebas locales cubren bloqueos, el interruptor, la agrupación IPv6, la pausa global, el límite de acceso, los dispositivos, el registro de seguridad y los avisos de Bark con un servidor simulado; 15 páginas no muestran bloqueos de CSP en un navegador sin interfaz. El operador instaló por red `v5.7.0-test.1` y `v5.7.0-test.2` en un equipo de prueba de la LAN y confirmó el recuento de fallos, el marcado con el bloqueo desactivado, el bloqueo activado y el nuevo diseño. Aún no se ha probado con una cuenta real de Bark ni detrás de un proxy inverso real.

### v5.6.3 — 2026-11-06

**Se recomienda actualizar a todos, sobre todo en equipos instalados con el paquete offline.** El comando de actualización no cambia y se conservan la configuración y los datos. Ejecute la actualización por SSH, no en el terminal integrado de la consola.

#### Corregido

- pcre2 del entorno de sistema incluido en el paquete offline (nft, iptables, `ip`, `ss`) se actualiza a la versión de seguridad de Debian 10.46-1~deb13u3, que corrige una reserva excesiva de pila JIT (GHSA-r9hj-j2rw-4q3m). Antes los paquetes se tomaban solo del archivo principal de Debian y faltaba el de seguridad; los otros 31 paquetes se revisaron uno a uno y coinciden con Debian 13 actual. Las actualizaciones sustituyen el entorno instalado.
- Al actualizar desde el terminal integrado de la consola solo aparecía `Terminated`, sin indicar si la instalación seguía en marcha. Ahora avisa de antemano de que el terminal se desconecta cuando la consola se reinicia mientras la instalación continúa en segundo plano, e indica el comando para ver el resultado; si la vista del progreso se interrumpe, también lo explica.
- Los reinicios de la consola ya no se bloquean 90 segundos: los terminales abiertos se cuelgan correctamente al apagar.

#### Mejorado

- Tras generar un certificado de cliente, la página muestra cuatro pasos: descargar, importar en el almacén de certificados del sistema (con Windows, macOS, Android e iOS explicados por separado, y el almacén propio de Firefox), cerrar y reabrir el navegador por completo, y confirmar que el certificado está en uso antes de activar Exigir certificado de cliente. Los ajustes de seguridad explican las causas habituales cuando hay certificados pero la conexión actual no presentó ninguno.

#### Mantenimiento interno

- Los binarios de terceros como sing-box, frp, Lucky y Tailscale ya no se guardan en el repositorio; la compilación offline los descarga desde direcciones fijadas y verifica cada SHA-256. El contenido de los paquetes no cambia. La instalación desde código descarga estos programas al instalar, como el paquete en línea.

#### Verificación

Verificado en un contenedor Debian 13 desechable: actualizaciones desde v5.6.2 dentro del grupo de control del terminal de la consola y desde un shell normal; nft, iptables, `ip` y `ss` del nuevo entorno funcionan; un paquete offline compilado desde un clon nuevo contiene programas idénticos byte a byte e instaló y ejecutó el módulo de proxy. Los pasos de importación del certificado solo se revisaron como contenido de la página y aún no se probaron en macOS, Android ni iOS.

### v5.6.2 — 2026-11-06

**Se recomienda encarecidamente actualizar, sobre todo en equipos con el módulo Tailscale.** El comando de actualización no cambia y se conservan la configuración y los datos.

#### Cambiado

- Componentes incluidos actualizados: Tailscale 1.102.4 → 1.104.5, sing-box 1.13.14 → 1.13.21, frp (FRPS, FRPC) 0.71.0 → 0.72.0. Los tres coinciden con las sumas publicadas por los proyectos originales.
  - Tailscale 1.104.4 corrige los boletines de seguridad TS-2026-014 a 017 (Tailscale SSH y serve). Este proyecto no activa ninguna de las dos funciones, así que el uso predeterminado no se ve afectado; los equipos donde se activó Tailscale SSH manualmente deben actualizar cuanto antes.
  - frp 0.72.0 corrige la pérdida de configuración de frpc al reconectar, un bucle de CPU tras cerrar la sesión y una condición de carrera que podía bloquear el proceso.
- Las actualizaciones sustituyen ahora el cliente FRPC anterior instalado por este proyecto (`/usr/local/bin/frpc`) y reinician las instancias en ejecución; un frpc colocado o modificado por el usuario no se toca. La desinstalación sigue reconociendo el cliente anterior.

### v5.6.1 — 2026-11-06

**Se recomienda encarecidamente actualizar.** Esta versión solo actualiza una dependencia relacionada con la seguridad; los pasos de actualización no cambian y la configuración y los datos no se ven afectados.

#### Corregido

- vue-i18n del frontend de la consola pasa de 11.4.13 a 11.4.18 y corrige dos avisos de cross-site scripting (XSS) (GHSA-8rc2-428q-7ww3, GHSA-83rm-6c8r-g728). El análisis del código actual no encontró una vía explotable, porque la consola no activa `escapeParameter` ni muestra traducciones como HTML; la actualización evita dejar en los sistemas instalados una dependencia con avisos abiertos.

### v5.6.0 — 2026-11-06

#### Añadido

- Inicio de sesión con certificado de cliente. Configuración > Seguridad > Certificados de cliente emite un certificado `.p12` por dispositivo (la contraseña de importación se muestra una sola vez); una vez importado en el sistema, el navegador inicia sesión con él en lugar de la contraseña. Los certificados se revocan uno a uno y el servidor nunca guarda la clave privada de un dispositivo. Con "Exigir certificado de cliente" activado, un dispositivo sin certificado válido solo ve una página de bloqueo (el acceso por IP sin contraseña también necesita certificado), la contraseña solo sirve para volver a verificar el terminal root y la configuración de seguridad, y las suscripciones de Clash siguen funcionando. No se puede activar si la conexión actual no presenta un certificado, y mientras se exige no se puede revocar el certificado en uso; si se pierde un certificado, root ejecuta `python3 /root/apps/vps-server/src/web/client_cert.py disable` para recuperar el acceso con contraseña. Se verificaron en Chrome para Windows la emisión, la importación, el inicio de sesión con certificado y la activación del requisito.

- Si el equipo no tiene un nftables funcional, instalar Singbox desde el instalador o desde una tarea de módulo de la consola lo instala primero con apt, sin pedir un comando manual; solo se detiene con un motivo si no hay apt o la instalación falla. Las tarjetas de módulos no instalados de la consola indican que se instalará automáticamente.

#### Cambiado

- La consola solo se sirve por HTTPS. `VPSSRV_CONSOLE_TLS=0` ya no tiene efecto y una instalación que funcionaba por HTTP pasa a HTTPS al actualizar, con el mismo puerto. El instalador instala `openssl` con apt si falta, para emitir certificados.

### v5.5.1 — 2026-10-23

#### Corregido

- El paquete sin conexión ya no anuncia una descarga durante la instalación: si los componentes ya están en el paquete no se descarga ni se avisa, y el aviso aparece solo cuando de verdad hay que descargar.

### v5.5.0 — 2026-10-23

#### Añadido

- Cada versión publica dos paquetes. El paquete sin conexión incluye todos los programas de terceros y herramientas del sistema; el destino no necesita red, curl, Git, tar ni gzip, solo Python 3.9+. El paquete en línea pesa unos 4 MB: el instalador descarga Singbox, Lucky, FRP y Tailscale para los módulos elegidos, verifica cada uno con SHA-256 e instala con apt los iptables, iproute2 y nftables que falten. Al añadir más tarde el módulo FRPC o Tailscale desde la consola, se descargan igual.

- El entorno incluido en el paquete sin conexión ahora trae iproute2 (`ss`, `ip`) y sus bibliotecas. Si el equipo no tiene esos comandos se usan los incluidos y ya no aparece la advertencia de `ss` o `ip` ausentes.

- La pregunta de idioma al inicio de la instalación continúa con el valor predeterminado tras 5 segundos sin respuesta, así que las instalaciones desatendidas terminan solas. `VPSSRV_PROMPT_TIMEOUT` cambia los segundos; `0` espera indefinidamente.

#### Cambiado

- La instalación ya no depende de curl, tar ni gzip: el comando de instalación en una línea, la extracción de los entornos de Tailscale y nftables y las comprobaciones del equipo usan tarfile y urllib de Python. Las imágenes mínimas no necesitan instalar esos comandos antes.

- El paquete sin conexión pasó de unos 98 MB a unos 167 MB porque incluye iproute2 y su código fuente.

- El separador del título de la pestaña del navegador cambió del guion largo `—` al guion corto `-`.

- El script de compilación reintenta cuando falla la descarga de paquetes Debian.

### v5.4.0 — 2026-10-21

#### Añadido

- El paquete completo incluye nftables 1.1.3 e iptables 1.8.11 de Debian 13 junto con glibc, iniciados por el cargador incluido. En equipos Debian 11+ y Ubuntu 20.04+ sin nftables ni iptables, o sin conexión, la contabilidad de tráfico de nodos, los límites de velocidad y el reenvío de puertos siguen funcionando. Se sigue prefiriendo una versión del equipo que pueda leer las reglas; las instalaciones solo de Web también reciben este entorno.

- Se comprueban los requisitos del equipo antes de instalar un módulo: Singbox necesita nftables funcional y Tailscale necesita `/dev/net/tun` y que no haya otro tailscaled en ejecución. El instalador, las tareas de instalación de la consola y las tarjetas y páginas de instalación de módulos no instalados comparten estas comprobaciones; si falta alguna, la instalación se detiene antes de cambiar nada y muestra el motivo y la solución en lugar de un simple "error".

- En la primera instalación, el comando queda en primer plano siguiendo la tarea en segundo plano y muestra solo los pasos clave y, al final, la dirección de la consola y la contraseña inicial; si falla, muestra el motivo y algunas líneas relacionadas del registro. Ctrl-C o una desconexión SSH solo detienen la vista; la instalación continúa.

- Las páginas de funciones de un módulo ausente permiten instalarlo directamente y muestran el progreso en la misma página.

- Un guardado de ajustes fallido muestra un toast durante 8 segundos y la página ya no repite el mismo error.

#### Cambiado

- Las instalaciones nuevas sirven la consola por HTTPS con un certificado autofirmado y las cookies de sesión llevan `Secure`; las actualizaciones conservan el ajuste anterior.

- Instalar Singbox, Lucky o Tailscale desde la consola instala solo ese módulo; Web y los demás módulos siguen funcionando.

- Antes de detener cualquier servicio, el instalador comprueba la versión de Python (se detiene por debajo de 3.9) e iptables, `ss` e `ip` (avisa si faltan e indica las funciones afectadas).

- Los errores de la contabilidad de nodos incluyen ahora el mensaje de error propio de nft.

#### Corregido

- En equipos Debian 13 sin nftables del sistema, la contabilidad de nodos se reiniciaba en bucle y detenía Singbox: el antiguo nft 0.9.8 incluido no puede leer reglas escritas por iptables-nft reciente, y la verificación previa solo ejecutaba `nft --version`, por lo que no lo detectó. La verificación previa y las comprobaciones en ejecución leen ahora realmente el conjunto de reglas.

- Los formularios de reenvío de puertos e iperf3 no tenían tokens CSRF, por lo que una página en otro puerto del mismo equipo podía enviarlos.

- Las conexiones inactivas que abren los navegadores por adelantado podían hacer que la consola HTTPS y la página pública dejaran de responder: los handshakes TLS se ejecutan ahora en el hilo de trabajo de cada conexión con un límite de 10 segundos.

- Cambiar el puerto de la consola reiniciaba Web manteniendo un bloqueo, por lo que el nuevo proceso agotaba el tiempo al liberar un registro de puerto iperf3 pendiente y fallaba; un fallo al liberar registros pendientes ya no impide que Web se inicie.

- Instalar Lucky desde la consola detenía Singbox; tras desinstalar Lucky su página ya no ofrecía el botón de instalación.

- Una primera instalación fallida de Tailscale dejaba su archivo de unidad y sus binarios, y la reversión podía no liberar registros de puertos.

- El estado de la página pública en el resumen de instalación no coincidía con los interruptores de la consola; las instalaciones de FRPS/Lucky fallaban y se revertían ante una regla de cortafuegos que ya no existía; el archivo de configuración del proxy pasa a 0600 y BBR usa su propio archivo sysctl, que la desinstalación completa elimina.

- La página del terminal y las páginas de FRPS y FRPC no instalados usaban el icono de pestaña de inicio.

### v5.3.1 — 2026-10-07

#### Corregido

- Instalar con un `VPSSRV_MODULES` más corto (como la instalación rápida del README) eliminaba módulos instalados del registro y detenía sing-box por la dependencia del medidor de nodos: una lista explícita ahora solo añade módulos y los módulos que siguen en disco se vuelven a contar.

- Un proceso ajeno en un puerto de la página pública abortaba todas las instalaciones y tareas de módulos de una instalación existente; ahora es una advertencia. Si falta el paquete del frontend, la instalación se detiene antes de escribir nada, en lugar de dejar un directorio de estado parcial que bloqueaba instalaciones posteriores.

- Desinstalar Singbox eliminaba todos los nodos: ahora conserva la configuración de sing-box y el inventario de nodos y solo libera el servicio, las reglas del cortafuegos y los registros de puertos. Al reinstalar se registran de nuevo los puertos de los nodos conservados (falla limpiamente si alguno está en uso) y se reabren sus reglas. La confirmación de desinstalación ahora indica que la configuración se conserva.

- Reinstalar Lucky fallaba con "Address already in use" porque las conexiones recién cerradas por la consola estaban en TIME_WAIT: los scripts de instalación de Lucky y FRPS y las comprobaciones de puertos de nodos, FRP e iperf3 ahora sondean con `SO_REUSEADDR` como los servidores.

- Desinstalar FRPC detenía todas las instancias y reinstalar no las recuperaba: la desinstalación ahora recuerda qué instancias estaban activas y la reinstalación las activa de nuevo, salvo que todo el grupo FRPC esté desactivado.

### v5.3.0 — 2026-10-07

#### Añadido

- Componentes de interfaz compartidos: la cabecera y el nuevo pie de página (perfil de GitHub, repositorio del proyecto) se desplazan elemento por elemento al cambiar el tamaño de la ventana; la navegación de secciones de ajustes sigue el desplazamiento con suavidad y pasa a una barra superior en pantallas estrechas; el icono de la pestaña sigue el color del tema y el modo claro/oscuro; Apariencia incorpora "Seguir el sistema"; la insignia de la etiqueta del servidor enlaza con el panel.

- El código QR de Clash se abre desde un botón en un diálogo; las confirmaciones al desinstalar, vaciar el historial de registros, eliminar un proxy y borrar visitantes usan el diálogo propio de la consola en lugar del aviso del navegador.

#### Cambiado

- El frontend Web usa ahora la plantilla compartida (Vue 3, Vite, TypeScript, Tailwind CSS): tokens de diseño unificados, ocho colores de tema y diseño adaptable, con el contenido de la página tan ancho como la cabecera. El frontend se compila en `web/` y el paquete completo incluye el resultado; la instalación desde código debe ejecutar antes `npm ci && npm run check` en `web/` (Node.js 24).

- La esquina superior izquierda de la cabecera muestra solo el nombre del proyecto, sin el logotipo (excepción del proyecto registrada en `doc/LOG.md`).

- La página pública (80/443) devuelve una sola línea de texto plano, "El servidor ve tu dirección IP".

- Al recargar, el diseño de reserva generado por el servidor permanece oculto hasta que la cabecera compartida y los menús desplegables con estilo están listos, por lo que ya no parpadean el diseño antiguo ni los menús nativos.

- Se reorganizaron las páginas de iPerf 3, Singbox, FRPS, FRPC, Lucky, Tailscale y Terminal: título de iPerf 3 con tarjetas Servidor y Cliente, contadores de Singbox alineados a la izquierda, título de instancias de FRPC y botón de nueva instancia en la misma fila, y un terminal más grande con fuente más pequeña. La página de administración de Lucky y las tarjetas HTTP y HTTPS del inicio se abren en una pestaña nueva. El botón de conexión de Tailscale pasa a la misma fila, la versión muestra solo el número de publicación y las listas de rutas y nodos de salida ya no tienen la entrada "Borrar".

- Los directorios de herramientas usan nombres con guiones (por ejemplo `tools/build-offline`), se añadió la comprobación estática compartida `tools/check-project` y la CI fija sus Actions; los comandos de instalación no cambian.

#### Corregido

- Al instalar o conmutar iperf3, el reinicio de Web coincidía con la carga de la página de estado y esta se quedaba en el estado anterior.

- El instalador abortaba durante una actualización porque los sockets TIME_WAIT de conexiones recién cerradas se tomaban por puertos 80/443 en uso.

- Fallaban los clics repetidos en "Conectar" de Tailscale: solo se ejecuta una conexión a la vez, se espera la dirección de inicio de sesión y el botón se desactiva tras el clic (Tailscale funciona en el equipo real, confirmado por el operador).

- Franja negra al pie del terminal, tarjeta vacía en las páginas de módulos cerrados, destino erróneo del control de retroceso en el registro detallado e iconos de página duplicados.

### v5.2.3 — 2026-10-05

#### Cambios

- Se reescribió la documentación conforme a las normas actuales, en chino simplificado, inglés y español.

- Se simplificó la instalación rápida a un comando que instala solo Web por defecto, y se añadieron pasos sin conexión bajo la instalación normal.

- Se añadieron 16 capturas reales al README, agrupadas en secciones desplegables con direcciones y credenciales ocultas.

### v5.2.2 — 2026-10-05

#### Cambiado

- La instalación continúa en una tarea systemd independiente tras elegir el idioma, con registro y código de salida, incluso al desconectar.

#### Corregido

- Unifica fuentes y controles de Configuración, iperf3, Singbox, FRPC y Tailscale; corrige desplegables, pantallas estrechas y filtros. Añade acceso a registros detallados junto al historial de inicio.

- Los editores cargan valores actuales; editar/eliminar comparten fila y los botones de eliminar tienen fondo rojo y respuesta visible. FRPC muestra IP del servidor y destino con visibilidad sincronizada; FRPS oculta direcciones por defecto.

- Guardar/renombrar FRPC devuelve una espera y reintenta el resultado tras reiniciar el túnel, evitando respuestas vacías pese al éxito. Configuraciones inválidas conservan/restauran valores y se eliminan credenciales antes de ejecutar.

- Tailscale confirma la salida con diálogo y usa selección única para rutas/salida; corrige textos largos, formulario sin sesión y controles de clave.

### v5.2.1 — 2026-10-05

#### Corregido

- Incluye y verifica Tailscale 1.102.4 en código, conserva recursos al instalar solo Web e informa si falta el archivo.

- La eliminación completa limpia ajustes/tareas Lucky y restos FRPS/proxy; conserva el modo de retención. Si falla el cortafuegos, detiene el borrado y guarda pertenencia.

### v5.2.0 — 2026-10-05

#### Añadido

- Añade terminal root con verificación, módulo Tailscale sin conexión, registros detallados y limpieza de visitantes; incluye entorno nftables y fuentes Debian correspondientes.

#### Cambiado

- Mueve el estado a `/var/lib/vps-server` y lo conserva en reinstalaciones del mismo esquema; no migra automáticamente v5.1.0 o anteriores. Unifica AnyTLS en Singbox, mueve módulos a Configuración y cuenta `(subida + bajada) × 2`.

#### Corregido

- Corrige edición FRPS sin registro de puerto, nodos, sincronización Lucky, tamaño/desplazamiento del terminal y retorno tras verificar. Prefiere nft operativo y registra puertos mediante auxiliares.

### v5.1.0 — 2026-10-04

#### Añadido

- Incluye artefactos FRPC, FRPS e iperf3 x86-64 Linux con sumas fijas.

#### Cambiado

- Limita idiomas a chino simplificado, inglés y español, elimina COMMITS.md, usa x86-64 Linux y solo edita nodos gestionados. La eliminación limpia instancias/plantillas/puertos FRPC; el modo de retención conserva configuraciones.

#### Corregido

- Soporta contraseñas no ASCII, reconstruye cuotas al reiniciar ciclos, revierte reenvíos parciales, unifica puertos/versión y corrige estado FRPC e identificación de versiones de prueba.

### v5.0.0 — 2026-10-03

#### Añadido

- Añade pruebas iperf3 TCP/UDP temporales, controles públicos independientes y nombre persistente del servidor.

#### Cambiado

- Completa la instalación inicial en terminal con solo Web; separa código/estilos por función y conserva sesiones vigentes al reiniciar.

#### Corregido

- Soporta nombres Unicode FRPC, conserva nodos/estado y corrige mensajes y código de salida al eliminar.

### v4.0.0 — 2026-09-29

#### Añadido

- Añade asistente HTTPS temporal, tareas de módulos y gestión/prueba/edición simple FRPC; separa FRPS/FRPC en inicio.

#### Cambiado

- Añade interruptores independientes, mueve módulos a Configuración, ajusta formularios/temas, elimina animaciones de navegación y cambia reenvío sin reiniciar Web.

#### Corregido

- No exige índice al crear proxies FRPC, detiene recopilación desactivada y conserva campos de nodos al reabrir.

### v3.0.0 — 2026-09-28

#### Añadido

- Añade nodos de cinco protocolos, enlaces/QR, cuotas/límites/reinicios/caducidad y lista de IP privadas sin contraseña.

#### Cambiado

- Unifica diseño, temas/colores y ocultación; separa estado iperf3 de edición y conserva entrada/módulos al actualizar.

### v2.0.0 — 2026-09-27

#### Añadido

- Añade proxy de cuatro protocolos, asistente inicial y módulos experimentales FRPS/Lucky con licencias y sumas.

#### Cambiado

- Mueve instalación a `deploy/`, Web a `src/web/`, dependencias a `third_party/` y metadatos a `config/`; organiza documentos/traducciones en directorios estándar.

### v1.1.2 — 2026-09-21

#### Corregido

- Corrige actualizaciones que terminaban silenciosamente tras una pregunta nueva, antes de copiar o actualizar servicios.

### v1.1.1 — 2026-09-20

#### Corregido

- Corrige comandos README que descargaban v1.0.4 en vez de v1.1.0.

### v1.1.0 — 2026-09-19

#### Añadido

- Añade reenvío TCP/UDP, DNAT/MASQUERADE, reproducción al iniciar y comprobación de conflictos.

### v1.0.4 — 2026-09-12

#### Cambiado

- Muestra direcciones de salida/interfaces y mantiene un marcador sin abortar si falla la detección.

### v1.0.3 — 2026-09-12

#### Corregido

- Reintenta actualización/instalación ante índices obsoletos y sustituye marcadores de repositorio/versión.

### v1.0.2 — 2026-09-12

#### Corregido

- Intenta instalar iperf3 aunque falle actualizar repositorios, reintenta y conserva errores.

### v1.0.1 — 2026-09-12

#### Corregido

- Deja de mostrar comentarios HTML de mantenimiento en el historial.

### v1.0.0 — 2026-09-12

#### Añadido

- Primera versión: pruebas Web con contraseña, visitantes, AnyTLS, accesibilidad pública 80/443, iperf3 temporal, configuración con prefijo y desinstalación con retención.
