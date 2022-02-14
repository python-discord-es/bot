# Python Discord ES Bot

Para configurar y utilizar el bot solo hay que instalar los requerimientos
del bot en un entorno virtual, y ejectuar el archivo `bot.py`:

```
python -m venv env
source env/bin/activate
pip install -r requirements.txt

python bot.py
```

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
