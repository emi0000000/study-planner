# Guía para ponerlo en marcha

Esta guía explica, paso a paso, **qué necesitas**, **dónde conseguirlo** y **cómo dejar el planificador funcionando** en tu ordenador con Windows, con los avisos llegando a tu teléfono.

Calcula unos **30 minutos** la primera vez. Solo se hace una vez.

## Lo que pide el programa

| # | Qué necesitas | Dónde se consigue | Precio | Tiempo |
|---|---|---|---|---|
| 1 | **Python** (el lenguaje en que está hecho el programa) | Microsoft Store | Gratis | 5 min |
| 2 | **El programa** (esta carpeta) | GitHub | Gratis | 2 min |
| 3 | **Las librerías de Google** | Un comando en la terminal | Gratis | 1 min |
| 4 | **`credentials.json`** (el permiso para usar tu Google Calendar) | Google Cloud | Gratis, sin tarjeta | 10-15 min |
| 5 | **Google Calendar en el teléfono** | Play Store o App Store | Gratis | 2 min |
| 6 | **Clave de Gemini o de Claude** (solo si quieres el asistente con IA) | aistudio.google.com o platform.claude.com | Gemini: nivel gratuito. Claude: de pago | 5 min |

Lo único que lleva un poco más de trabajo es el paso 4. Los demás son instalar y listo. El asistente (paso 7) es opcional: todo lo demás funciona sin él.

---

## Paso 1. Instalar Python

> ¿Ya tienes Python? Abre PowerShell, escribe `python --version` y pulsa Enter. Si sale `Python 3.10` o un número más alto, sáltate este paso.

1. Abre la **Microsoft Store** (búscala en el menú Inicio).
2. Busca **Python Install Manager** (publicado por *Python Software Foundation*) y pulsa **Obtener**.
3. Cuando termine, abre **PowerShell**: pulsa la tecla Windows, escribe `PowerShell` y pulsa Enter.
4. Escribe esto y pulsa Enter:

   ```
   python --version
   ```

   La primera vez puede que te haga algunas preguntas o que instale Python solo. Acepta las opciones recomendadas (normalmente escribiendo `y` y pulsando Enter).

5. Debe aparecer `Python 3.` seguido de un número, por ejemplo `Python 3.14.6`. Cualquier versión desde la `3.10` vale.

**Si sale "no se reconoce como nombre de un cmdlet":** cierra PowerShell y ábrelo otra vez. Si sigue igual, reinicia el ordenador y vuelve a probar.

---

## Paso 2. Descargar el programa

**Si no tienes la carpeta en tu ordenador:**

1. Entra a <https://github.com/emi0000000/study-planner> con tu cuenta de GitHub.
2. Pulsa el botón verde **Code** y luego **Download ZIP**.
3. Ve a tu carpeta de Descargas, haz clic derecho en el ZIP y elige **Extraer todo**.
4. Mueve la carpeta que sale a un lugar fácil de encontrar, por ejemplo **Documentos**.

> A veces queda una carpeta dentro de otra con el mismo nombre (`study-planner-main\study-planner-main`). La buena es la que tiene **`planificador.py`** dentro.

**Si ya tenías la carpeta** (porque la descargaste antes con git), ábrela en la terminal (ver paso 3) y escribe `git pull` para traer la última versión.

> Si un día descargas el ZIP otra vez para actualizar, **copia a la carpeta nueva** tus archivos `config.json`, `credentials.json`, `token.json` y la carpeta `datos`. Ahí están tus ajustes, tus temas y tu permiso de Google.

---

## Paso 3. Instalar las librerías

1. Abre la carpeta del programa en el Explorador de archivos (la carpeta donde está `planificador.py`).
2. Haz clic derecho en un espacio vacío de la carpeta y elige **Abrir en Terminal**.
   (Si no aparece, abre PowerShell y escribe `cd ` seguido de la ruta de la carpeta, por ejemplo `cd "$HOME\Documents\study-planner-main"`.)
3. Escribe:

   ```
   python -m pip install -r requirements.txt
   ```

4. **Comprueba que todo está bien** con las pruebas automáticas:

   ```
   python -m unittest discover -s tests
   ```

   Al final debe decir **`OK`**. Si dice `FAILED`, copia el mensaje y pídeme ayuda.

A partir de aquí ya puedes usar el planificador **sin Google**: agregar temas, generar el plan y ver qué te toca cada día.

**Abre la ventana:** en la carpeta del programa, haz **doble clic en `Abrir planificador.bat`**. Pruébala:

1. En la pestaña **Temas**, escribe un tema (por ejemplo `Matemáticas`), elige su prioridad y sus minutos por semana, y pulsa **Guardar tema**. Repite con tus otros temas.
2. En la pestaña **Semana**, pulsa **Generar plan**. Verás tus sesiones repartidas día por día.
3. En la pestaña **Google Calendar**, pulsa **Ver qué se subiría**: te enseña lo que se crearía en el calendario, sin conectarse a nada.

> Si prefieres la terminal, lo mismo se hace con:
> `python planificador.py agregar "Matemáticas" --prioridad 5 --minutos 150`, luego `python planificador.py generar` y `python planificador.py subir --simular`.

---

## Paso 4. Conseguir `credentials.json` (el permiso de Google)

Este archivo le dice a Google que **tu** programa puede crear eventos en **tu** calendario. Se crea en Google Cloud, que es gratis para esto y no pide tarjeta.

> **Si tu Google Cloud está en español**, los menús tienen nombres parecidos a estos (pueden variar un poco):
>
> | En inglés | En español |
> |---|---|
> | New project | Proyecto nuevo |
> | Enable | Habilitar |
> | Google Auth platform | Google Auth Platform / Plataforma de autenticación |
> | Branding | Desarrollo de la marca |
> | Audience | Público |
> | Test users → Add users | Usuarios de prueba → Agregar usuarios |
> | Clients → Create client | Clientes → Crear cliente |
> | Desktop app | App de escritorio |
> | Download JSON | Descargar JSON |

### 4.1 Crear un proyecto

1. Entra a <https://console.cloud.google.com/> con la **misma cuenta de Google** que usas en el teléfono.
2. Si es tu primera vez, acepta las condiciones del servicio.
3. Arriba a la izquierda, junto al logo, pulsa el **selector de proyectos** y luego **New project**.
4. Ponle de nombre `planificador-estudio` y pulsa **Create**.
5. Espera unos segundos y comprueba que arriba aparece **planificador-estudio** como proyecto seleccionado. Si no, selecciónalo en ese mismo menú.

### 4.2 Activar la API de Google Calendar

1. Entra a <https://console.cloud.google.com/apis/library/calendar-json.googleapis.com>.
2. Comprueba que arriba sigue seleccionado **planificador-estudio**.
3. Pulsa **Enable**.

### 4.3 Configurar la pantalla de permiso

1. En el menú ☰ (arriba a la izquierda), entra a **Google Auth platform → Branding**.
   Si aparece *"Google Auth platform not configured yet"*, pulsa **Get started**.
2. **App information:** en *App name* escribe `Planificador de estudio`. En *User support email* elige tu correo. Pulsa **Next**.
3. **Audience:** elige **External**. Pulsa **Next**.
4. **Contact information:** escribe tu correo. Pulsa **Next**.
5. **Finish:** marca la casilla de aceptar la política de datos y pulsa **Continue** y después **Create**.
6. Ahora ve a **Google Auth platform → Audience**. Baja hasta **Test users**, pulsa **Add users**, escribe **tu propio correo** y pulsa **Save**.

> Este último punto es el que más se olvida. Si no lo haces, Google te dirá "Acceso bloqueado" al iniciar sesión.

### 4.4 Crear el cliente y descargar el archivo

1. Ve a **Google Auth platform → Clients** y pulsa **Create client**.
2. En **Application type** elige **Desktop app**. (No elijas *Web application*: con ese no funciona.)
3. Ponle cualquier nombre, por ejemplo `planificador`, y pulsa **Create**.
4. En la ventana que aparece, pulsa **Download JSON**. **Hazlo en ese momento**: puede que Google no te deje volver a descargarlo después. Si se te pasa, borra ese cliente y crea otro.

### 4.5 Poner el archivo en la carpeta

1. En Descargas habrá un archivo con un nombre largo, como `client_secret_1234-abcd.apps.googleusercontent.com.json`.
2. **Muévelo a la carpeta del programa** (junto a `planificador.py`).
3. **Cámbiale el nombre a `credentials.json`**.

> **Cuidado con Windows:** a veces oculta el final `.json` de los nombres. Si escribes `credentials.json`, el archivo queda como `credentials.json.json` y el programa no lo encuentra. Para evitarlo, en el Explorador abre el menú **Ver** y activa **Extensiones de nombre de archivo**; así ves el nombre completo.
>
> Si te equivocas, no pasa nada: el programa te dice qué archivo encontró y cómo renombrarlo.

**Privado:** `credentials.json` (y el `token.json` que se crea después) dan acceso a tu calendario. No los compartas ni los subas a internet. El programa ya está configurado para que git no los suba nunca.

---

## Paso 5. Primera conexión con Google

En la ventana, ve a la pestaña **Google Calendar**. Los dos primeros puntos de **1. Conexión** deben estar en verde (si no, debajo dice qué falta). Pulsa **Subir al calendario**.

(En la terminal sería: `python planificador.py subir`.)

Se abrirá el navegador:

1. Elige tu cuenta de Google.
2. Verás **"Google no ha verificado esta app"**. Es normal: la app es tuya y no está publicada. Pulsa **Continuar**.
   (Si no ves ese botón, pulsa **Configuración avanzada** y luego **Ir a Planificador de estudio**.)
3. Google te pide permiso para **ver y editar eventos** de tus calendarios. Si aparece una casilla junto al permiso, **márcala**. Luego pulsa **Continuar**.
4. Cuando el navegador diga **"Listo. Ya puedes cerrar esta pestaña"**, vuelve a la ventana.

La ventana dirá **¡Listo!** con el número de sesiones creadas. Abre <https://calendar.google.com> y verás eventos como **Estudiar: Matemáticas (1/6)**.

> Si en 5 minutos no aceptas el permiso, el programa deja de esperar y te avisa. Solo tienes que volver a pulsar **Subir al calendario**.

> **Cada 7 días** Google pide el permiso otra vez (porque la app está en modo de prueba). Cuando pase, el navegador se abrirá solo al subir o borrar sesiones: solo tienes que aceptar de nuevo.

---

## Paso 6. Recibir los avisos en el teléfono

1. Instala **Google Calendar** (Play Store en Android, App Store en iPhone).
2. Inicia sesión con la **misma cuenta de Google** que usaste en el paso 4.
3. Permite sus notificaciones: en el teléfono, ve a *Ajustes → Notificaciones → Google Calendar* y actívalas.
4. Abre Google Calendar en el teléfono y comprueba que ves las sesiones **Estudiar: …**.

Cada sesión te avisará **5 minutos antes** (puedes cambiarlo en `config.json`, clave `aviso_minutos_antes`).

---

## Paso 7. Activar el asistente (opcional)

El asistente es un chat dentro del planificador: le cuentas cómo te va ("hoy no pude estudiar química", "el viernes tengo examen de inglés") y él marca lo hecho, guarda tus metas y ajusta el plan. Funciona con una de estas dos inteligencias artificiales; elige **una**:

| | **Gemini** (de Google) | **Claude** (de Anthropic) |
|---|---|---|
| Precio | **Nivel gratuito** con límites (unos cuantos mensajes por minuto y por día). | **De pago** según el uso: compras saldo por adelantado (desde unos 5 USD) y cada mensaje cuesta unos céntimos. |
| Cuenta | Tu misma cuenta de Google. | Una cuenta de la plataforma de Anthropic (es distinta de una suscripción a Claude Pro o Max, que no incluye esto). |
| Recomendado si… | Quieres probarlo sin pagar. | Ya tienes saldo o prefieres Claude. |

### 7.1 Conseguir la clave de Gemini (gratis)

1. Entra a <https://aistudio.google.com/apikey> con tu cuenta de Google y acepta las condiciones si te las pide.
2. Pulsa **Create API key** (Crear clave de API). Si te pregunta por un proyecto, elige cualquiera (puede ser el `planificador-estudio` del paso 4) o deja que cree uno nuevo.
3. Copia la clave (empieza por `AIza…`). Guárdala en un sitio seguro: es como una contraseña.

> En el nivel gratuito, Google puede usar lo que envías para mejorar sus productos. No escribas en el chat nada que no quieras compartir.

### 7.2 Conseguir la clave de Claude (de pago)

1. Entra a <https://platform.claude.com> y crea una cuenta (o inicia sesión).
2. Ve a **Settings → Billing** y compra saldo (créditos). Sin saldo, la clave no funciona.
3. Ve a **Settings → API keys** y pulsa **Create key**. Ponle un nombre, por ejemplo `planificador`.
4. Copia la clave (empieza por `sk-ant-…`). **Solo se muestra una vez**: si la pierdes, crea otra.

### 7.3 Ponerla en el planificador

1. Abre la ventana y ve a la pestaña **Asistente**. La primera vez aparece directamente la configuración (después, botón **Cambiar IA o clave**).
2. Elige **Gemini** o **Claude**, pega la clave en **Clave** y deja el **Modelo** como está.
3. Pulsa **Guardar y empezar**.
4. Escribe algo, por ejemplo **«¿Cómo voy esta semana?»**, y pulsa **Enviar** (o usa los botones de ejemplo).

La clave se guarda solo en tu ordenador, en `datos/claves.json`. Lo que escribes en el chat y tus datos de estudio (temas, plan, progreso, metas) se envían a la IA elegida para que pueda responder.

> En la terminal: `python planificador.py clave gemini` (te pide la clave sin que se vea) y luego `python planificador.py asistente`.

---

## Lista de comprobación

- [ ] `python --version` muestra 3.10 o más.
- [ ] Tengo la carpeta del programa y dentro está `planificador.py`.
- [ ] `python -m unittest discover -s tests` termina en `OK`.
- [ ] La ventana se abre con doble clic en `Abrir planificador.bat`.
- [ ] En Google Cloud: proyecto creado, API de Calendar habilitada, mi correo en *Test users*.
- [ ] `credentials.json` está en la carpeta del programa, con ese nombre exacto.
- [ ] Subí el plan (botón **Subir al calendario**) y veo las sesiones en calendar.google.com.
- [ ] Google Calendar está en el teléfono, con la misma cuenta y las notificaciones activadas.
- [ ] (Opcional) El asistente responde en la pestaña **Asistente**.

Si marcaste todo, ya está funcionando.

---

## Uso de cada semana

| Cuándo | En la ventana | En la terminal |
|---|---|---|
| El domingo (o el primer día de tu semana) | **Semana → Generar plan** y luego **Google Calendar → Subir al calendario** | `python planificador.py generar` y luego `python planificador.py subir` |
| Cada día, para ver lo que te toca | Pestaña **Hoy** | `python planificador.py hoy` |
| Al terminar cada sesión (o si no pudiste) | Pestaña **Hoy**: botón **Hecha** o **No la hice** | `python planificador.py marcar hecha "Tema"` (o `marcar no "Tema"`) |
| Cuando tengas un examen o una entrega | Pestaña **Metas**: escríbela con su tema y fecha (o díselo al asistente) | `python planificador.py meta "Examen" --tema Química --fecha 2026-11-13` |
| Si cambias un tema a mitad de semana | Cambia el tema en **Temas**, pulsa **Generar plan** y **Subir al calendario** (te preguntará si reemplazar las sesiones anteriores: di que sí) | `python planificador.py generar` y luego `python planificador.py subir --reemplazar` |
| Para borrar del calendario las sesiones del plan | **Google Calendar → Borrar del calendario…** | `python planificador.py limpiar` |

Borrar solo quita las sesiones que creó esta app: tus otros eventos no se tocan.

**Por qué marcar las sesiones:** el plan de la semana siguiente añade el tiempo de las que marcaste como no hechas para que lo recuperes, y tus metas con fecha hacen que ese tema se estudie más y antes. Arriba del plan verás «Cómo se adaptó este plan» con lo que cambió.

Todos los comandos y ajustes están explicados en el [README](README.md).

---

## Si algo falla

| Lo que ves | Qué hacer |
|---|---|
| Doble clic en `Abrir planificador.bat` y no se abre nada | Abre la terminal en la carpeta del programa (paso 3) y escribe `python interfaz.py`: verás el mensaje de error. |
| `Faltan las librerías de Google` | Repite el paso 3. |
| `No encuentro credentials.json` | Repite el paso 4.5. Si el mensaje dice "Pero encontré…", renombra el archivo que indica. |
| En el navegador: **"Acceso bloqueado"** o **error 403: access_denied** | Falta tu correo en *Test users* (paso 4.3, punto 6). |
| `Google Calendar respondió con un error (403)` | La API no está habilitada, o el proyecto seleccionado no es el correcto (paso 4.2). |
| En el navegador: **error redirect_uri_mismatch** | Creaste el cliente como *Web application*. Crea otro como **Desktop app** (paso 4.4) y reemplaza `credentials.json`. |
| `Falta la clave de …` o `La clave de … no es válida` (asistente) | Repite el paso 7 y vuelve a pegar la clave en **Asistente → Cambiar IA o clave**. |
| `Tu cuenta de Claude no tiene saldo` | Compra saldo (paso 7.2, punto 2) o cambia a Gemini. |
| `Se acabó el límite gratuito de Gemini` | Espera un rato (o hasta el día siguiente) y vuelve a intentarlo. |
| `Ya hay N sesiones del planificador en tu calendario…` | Ya las habías subido. En la ventana, di que sí cuando te pregunte si reemplazarlas; en la terminal, usa `python planificador.py subir --reemplazar`. |
| No llegan avisos al teléfono | Revisa el paso 6: misma cuenta y notificaciones activadas. |
| Otra cosa | Copia el mensaje completo y pídeme ayuda. Hay más casos en la sección 12 del [README](README.md). |
