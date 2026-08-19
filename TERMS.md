# Términos de Uso y Política de Datos del Bot

*Última actualización: 2026-08-17*

Este documento describe qué datos recopila y almacena **LlamaBot**, bot
oficial de moderación del servidor de Discord **Python en Español**, con
qué propósito, durante cuánto tiempo, y qué opciones tienes respecto a tus
propios datos. LlamaBot no está en funcionamiento en ningún otro servidor;
este documento se refiere únicamente a su uso en Python en Español.

Puedes consultar este documento en cualquier momento con el comando
`%terminos`.

## 1. Alcance

Este documento cubre únicamente los datos que **LlamaBot** almacena por su
cuenta (en archivos de registro en el servidor donde corre). No cubre los
datos que Discord, como plataforma, almacena sobre tu cuenta, tus mensajes
o tu actividad - eso se rige por la [Política de Privacidad de
Discord](https://discord.com/privacy). El bot no puede eliminar ni
controlar esos datos.

## 2. Qué datos recopila el bot

| Dato | De dónde sale | Para qué se usa |
|---|---|---|
| ID de usuario de Discord | Autor de mensajes/comandos | Identificar de forma estable a quién pertenece cada registro (a diferencia del nombre de usuario, el ID no cambia). |
| Nombre de usuario de Discord | Autor de mensajes/comandos | Mostrar de forma legible a quién pertenece un registro en los canales de moderación. |
| Contenido de mensajes enviados para moderación | Canales de "envío" de contenido | Permitir que el equipo de moderación revise, acepte o rechace el contenido antes de publicarlo. |
| Decisión de moderación (aceptado/rechazado) y motivo del rechazo | Acción del equipo de moderación | Mantener trazabilidad de qué se decidió y por qué. |
| Registro general de mensajes del servidor (autor, canal, contenido, fecha) | Toda la actividad del servidor | Auditoría e investigación de incidentes de moderación. |

**Base legal (RGPD/GDPR):** el bot procesa estos datos por **interés
legítimo** del servidor en poder moderar su propio contenido y prevenir
abuso/spam - es la funcionalidad esencial por la que el bot existe. No se
usan para ningún otro fin (marketing, perfilado, venta a terceros, etc.).

LlamaBot solo solicita a Discord el permiso ("intent") de **contenido de
mensajes**, que es el mínimo necesario para las funciones descritas
arriba. No solicita acceso a la lista de miembros del servidor ni a datos
de presencia/actividad (en línea, jugando, etc.).

## 3. Qué el bot **no** vincula a tu identidad

Para detectar spam y contenido malicioso repetido, el bot guarda firmas del
propio contenido (el texto ya "aplanado", o el hash de una imagen) que se
ha confirmado como spam o estafa. Estas firmas **no incluyen quién las
envió** — son solo el contenido o su huella digital, sin ningún dato de
autor. Por eso no se consideran datos personales y se conservan
indefinidamente: sirven para reconocer el mismo contenido si vuelve a
aparecer, sin que eso implique guardar información sobre ninguna persona.

## 4. Archivado de canales

El comando `%archivar` (uso exclusivo del equipo de moderación) genera una
copia del historial completo de un canal - incluyendo autor, ID de autor y
contenido de cada mensaje - y la publica como archivo adjunto en el canal
privado de moderación. Es una función que se usa **rara vez, típicamente
solo al cerrar/archivar un canal de forma permanente**, no como parte de
la moderación cotidiana descrita en la sección 2.

Por su distinto propósito (dejar un registro histórico del canal cerrado,
no auditar actividad reciente), este archivo se trata de forma separada:

- El bot **no conserva una copia propia**: el archivo se sube al canal de
  moderación y se borra inmediatamente del servidor donde corre el bot.
  La única copia que persiste es ese mensaje en el canal de moderación,
  sujeto a los mismos controles de acceso que el resto de esa sección
  (solo Coordinación) y a la propia retención de datos de Discord.
- No está sujeto al borrado automático de 30 días de la sección 5, ya
  que su propósito es servir como referencia histórica a largo plazo, no
  como registro operativo reciente.
- Una solicitud de eliminación (sección 6) no puede editar automáticamente
  un archivo ya publicado en Discord. Si nos pides eliminar tus datos de
  un canal ya archivado, el equipo de Coordinación evaluará el pedido caso
  por caso (por ejemplo, editando o eliminando manualmente ese archivo).

## 5. Cuánto tiempo se conservan los datos

- **Registros con datos personales** (tabla de la sección 2): se eliminan
  automáticamente pasados **30 días** desde su creación. Esto ocurre todos
  los días de forma automática; no requiere intervención manual.
- **Firmas de contenido/imágenes de spam** (sección 3): se conservan sin
  fecha de expiración, ya que no son datos personales.
- **Archivos de canales cerrados** (sección 4): se conservan sin fecha de
  expiración fija, como registro histórico, únicamente en el canal de
  moderación.
- **Registro de solicitudes de eliminación y de exportación** (sección 6):
  se conservan indefinidamente como constancia de que una solicitud fue
  atendida, pero solo contienen el ID de la persona afectada y un conteo
  de registros — nunca el contenido eliminado o exportado.

## 6. Quién tiene acceso

Los registros descritos en la sección 2 son visibles para el equipo de
moderación ("Coordinación") del servidor, a través de los canales y
comandos del bot. No se comparten con terceros ni se usan con fines
distintos a la moderación del servidor. LlamaBot no utiliza ningún
servicio externo (analítica, IA, hosting de terceros con acceso a los
datos, etc.) para procesar estos datos: corre en un único servidor
administrado por el equipo de Python en Español, y los registros se
guardan como archivos de texto sin cifrar en ese mismo servidor. El
acceso al servidor está restringido a las personas del equipo de
Coordinación que lo administran.

## 7. Tus derechos: acceso, rectificación y eliminación

Puedes solicitar en cualquier momento:

- **Saber qué datos tuyos están almacenados** ("derecho de acceso").
- **Que se corrijan datos incorrectos.**
- **Que se eliminen todos tus datos** ("derecho al olvido").

Para ejercer cualquiera de estos derechos, contacta con
**contacto@hablemospython.dev**. Una vez validada la solicitud, un miembro
del equipo de Coordinación puede:

- **Exportar tus datos** mediante el comando `%exportar`, que genera un
  archivo `.zip` con todas tus filas en los registros de datos personales
  descritos en la sección 2, y lo entrega de forma privada a quien hizo la
  solicitud.
- **Eliminar tus datos** mediante el comando `%olvidar`, que:
  1. Muestra un resumen de cuántos registros se encontraron para tu cuenta.
  2. Requiere una confirmación explícita antes de eliminar nada.
  3. Elimina esos registros de todos los archivos de datos personales
     descritos en la sección 2, de forma permanente e irreversible.
  4. Dado que el bot identifica tus datos por tu ID de Discord (no por tu
     nombre de usuario, que puede cambiar), la eliminación cubre todos los
     registros asociados a tu cuenta, incluso si tu nombre de usuario fue
     distinto en el pasado.

Ten en cuenta que ninguno de los dos comandos alcanza a los archivos de
canales cerrados (sección 4) ni elimina tu historial dentro de Discord
como plataforma (mensajes, roles, sanciones aplicadas directamente por
Discord, etc.) — solo lo que este bot almacena por su cuenta.

## 8. Menores de edad

LlamaBot no está dirigido a, ni recopila datos intencionalmente de,
personas menores de 13 años, en línea con los [Términos de Servicio de
Discord](https://discord.com/terms). Si tomamos conocimiento de que se
almacenaron datos de una persona menor de 13 años, los eliminaremos de
forma inmediata al ser notificados, usando el mismo mecanismo de la
sección 7.

## 9. Cambios a este documento

Este documento puede actualizarse si cambia la forma en que el bot maneja
los datos. La fecha de "Última actualización" al inicio refleja la
versión vigente; se recomienda revisarlo periódicamente. Cambios
relevantes serán anunciados en el servidor de Python en Español.
