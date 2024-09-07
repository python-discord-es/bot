# Python Discord ES Bot

## Instalación y configuración

Sigue estos pasos para configurar y utilizar el bot:

### Prerequisitos

- Python 3.8 o superior debe estar instalado. Si no lo tienes instalado, 
puedes descargarlo desde [python.org](https://www.python.org/downloads/).

### 1. Crear un entorno virtual e instalar dependencias

Primero, crea un entorno virtual e instala los paquetes requeridos para 
ejecutar el bot:

```bash
python -m venv env
source env/bin/activate  # En Windows: env\Scripts\activate
pip install -r requirements.txt
```

### 2. Configurar el archivo `.toml`

El bot requiere un archivo de configuración `.toml` para funcionar 
correctamente. Debes crear un archivo `config.toml` en el directorio 
raíz del proyecto.

Puedes usar el archivo `config.toml.example` como referencia y ajustarlo 
según tus necesidades. A continuación, se muestra un ejemplo de la primera 
parte del archivo `config.toml`:

```toml
[bot]
# Reemplaza con el token de tu bot de Discord
token="TU_TOKEN_AQUI"

# Reemplaza con el ID de tu bot
id=123456789012345678

# Especifica la ruta donde se almacenará el archivo de logs
log_file="ruta/del/archivo.log"

[moderation]
# Especifica la ruta donde se almacenarán los logs de moderación
log_file="ruta/del/log_moderacion.log"

# ID del canal de moderación
channel_id=987654321098765432

# Nombre del rol de moderador
role="moderador"

# Nombre del rol para los usuarios silenciados
muted_role="silenciado"
```

Asegúrate de reemplazar `"TU_TOKEN_AQUI"`, `123456789012345678`, y otros 
valores por los datos correctos para tu bot y servidor.

### 3. Ejecutar el bot

Una vez configurado el archivo `config.toml`, puedes iniciar el bot con el 
siguiente comando:

```bash
python bot.py
```

### Verificación

Para asegurarte de que el bot está funcionando correctamente, puedes probarlo 
ejecutando el siguiente comando en tu servidor:

```
%ayuda
```

Si el bot responde con la lista de comandos disponibles, la instalación ha sido exitosa.

Actualmente el bot utilizado en el servidor tiene dos funcionalidades:

 * Encuestas
 * Moderación de canales de anuncios

El comando `%ayuda` mostrará algo distinto si es ejecutado en el canal
de `#moderación` u otro canal, para mostrar los comandos aceptados.

## Encuestas

Las encuestas consisten en dos formas:

 1. **Preguntas de Sí y No**:
    Al enviar solo un argumento el bot asumirá que es una pregunta de Sí y No:

    ```
    %encuesta "¿Te gusta el té?"
    ```

 2. **Preguntas con varias opciones**:
    Al enviar argumentos adicionales, se considerarán como opciones a la
    pregunta:

    ```
    %encuesta "¿Qué empanada te gusta más" "Carne" "Queso" "Espinaca"
    ```

Es muy importante que tanto la pregunta como opciones estén entre comillas
dobles, para que sean aceptadas como argumentos.

El voto de las encuestas se basa en reacciones al mensaje,
del cual el `bot` estará a cargo de borrar las reacciones que no corresponden
a opciones de la votación.

## Moderación Canales Anuncios

La moderación de anuncios consiste en una interacción entre 3 canales,
por ejemplo:

 * `#envio-anuncios`, para que las personas envíen sus anuncios, a lo que
   el bot responderá que el mensaje ya entró en moderación.
   Ambos mensajes serán borrados.
 * `#moderación`, con cada nuevo mensaje de envio-anuncios, el bot publicará
   un mensaje avisando a los moderadores, incluyendo el mensaje y las opciones
   para poder `%aceptar` o `%rechazar` el anuncio.
 * `#anuncios`, el bot publicará los anuncios aceptados en este canal,
   pero también los mensajes rechazados señalando la razón del rechazo.

Complementariamente en el canal de `#moderación` se podrán utilizar los
comandos:

 * `%mod` listar todos los mensajes pendientes de moderación
 * `%mod ID` mostrar información sobre el anuncio ID.
 * `%limpia N` para borrar N líneas del canal.

## Moderación automática

En los siguientes casos, el bot silenciará a las personas que rompan
unas de las siguientes reglas:

* **Spam**: Personas que envien mensajes de *phishing* con palabras como
  'discord', 'free', 'nitro', etc.
* **Flood**: Personas que envien el mismo mensaje en menos de una hora,
  por 3 veces o más.
* **Menciones**: Personas que envían mensajes con 3 menciones o más
  a roles o personas.

## Tengo una idea para el bot

Las futuras ideas del bot están definidas como 'Issues' en este repositorio.
Si tienes alguna sugerencia, te recomendamos que abras un nuevo 'Issue'.
