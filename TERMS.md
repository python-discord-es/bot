# Términos de Uso y Política de Datos del Bot

> **⚠️ Aviso importante:** este documento es un **borrador técnico**, escrito
> para describir con precisión qué hace el bot con los datos que maneja. No
> es asesoría legal. Antes de publicarlo como política oficial de la
> comunidad, debe ser revisado por una persona con conocimientos legales en
> protección de datos (RGPD/GDPR u otra normativa aplicable según dónde
> resida la comunidad y sus miembros).
>
> Responsable del tratamiento de datos: **[COMPLETAR: nombre/contacto del
> equipo u organización responsable del servidor]**
> Contacto para consultas o solicitudes sobre tus datos: **[COMPLETAR:
> correo o canal de contacto]**

Este documento describe qué datos recopila y almacena el bot de moderación
de este servidor de Discord, con qué propósito, durante cuánto tiempo, y
qué opciones tienes respecto a tus propios datos.

## 1. Alcance

Este documento cubre únicamente los datos que **el bot** almacena por su
cuenta (en archivos de registro en el servidor donde corre). No cubre los
datos que Discord, como plataforma, almacena sobre tu cuenta, tus mensajes
o tu actividad — eso se rige por la [Política de Privacidad de
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

## 3. Qué el bot **no** vincula a tu identidad

Para detectar spam y contenido malicioso repetido, el bot guarda firmas del
propio contenido (el texto ya "aplanado", o el hash de una imagen) que se
ha confirmado como spam o estafa. Estas firmas **no incluyen quién las
envió** — son solo el contenido o su huella digital, sin ningún dato de
autor. Por eso no se consideran datos personales y se conservan
indefinidamente: sirven para reconocer el mismo contenido si vuelve a
aparecer, sin que eso implique guardar información sobre ninguna persona.

## 4. Cuánto tiempo se conservan los datos

- **Registros con datos personales** (tabla de la sección 2): se eliminan
  automáticamente pasados **30 días** desde su creación. Esto ocurre todos
  los días de forma automática; no requiere intervención manual.
- **Firmas de contenido/imágenes de spam** (sección 3): se conservan sin
  fecha de expiración, ya que no son datos personales.
- **Registro de solicitudes de eliminación** (sección 6): se conserva
  indefinidamente como constancia de que una solicitud fue atendida, pero
  solo contiene el ID de la persona afectada y un conteo de registros
  eliminados — nunca el contenido eliminado.

## 5. Quién tiene acceso

Los registros descritos en la sección 2 son visibles para el equipo de
moderación ("Coordinación") del servidor, a través de los canales y
comandos del bot. No se comparten con terceros ni se usan con fines
distintos a la moderación del servidor.

## 6. Tus derechos: acceso, rectificación y eliminación

Puedes solicitar en cualquier momento:

- **Saber qué datos tuyos están almacenados.**
- **Que se corrijan datos incorrectos.**
- **Que se eliminen todos tus datos** ("derecho al olvido").

Para ejercer cualquiera de estos derechos, contacta con
**[COMPLETAR: contacto]**. Una vez validada la solicitud, un miembro del
equipo de Coordinación puede ejecutar la eliminación mediante el comando
`%olvidar`, que:

1. Muestra un resumen de cuántos registros se encontraron para tu cuenta.
2. Requiere una confirmación explícita antes de eliminar nada.
3. Elimina esos registros de todos los archivos de datos personales
   descritos en la sección 2, de forma permanente e irreversible.
4. Dado que el bot identifica tus datos por tu ID de Discord (no por tu
   nombre de usuario, que puede cambiar), la eliminación cubre todos los
   registros asociados a tu cuenta, incluso si tu nombre de usuario fue
   distinto en el pasado.

Ten en cuenta que esto **no elimina tu historial dentro de Discord como
plataforma** (mensajes, roles, sanciones aplicadas directamente por
Discord, etc.) — solo lo que este bot almacena por su cuenta.

## 7. Cambios a este documento

Este documento puede actualizarse si cambia la forma en que el bot maneja
los datos. Se recomienda revisarlo periódicamente.
