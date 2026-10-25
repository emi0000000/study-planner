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

Lo único que lleva un poco más de trabajo es el paso 4. Los demás son instalar y listo.

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

## Paso 3. Instalar las librerías de Google

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

A partir de aquí ya puedes usar el planificador **sin Google**: agregar temas, generar el plan y ver qué te toca cada día. Pruébalo:

```
python planificador.py agregar "Matemáticas" --prioridad 5 --minutos 150
python planificador.py generar
python planificador.py subir --simular
```

`subir --simular` te enseña lo que se crearía en el calendario, sin conectarse a nada.

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

En la terminal, dentro de la carpeta del programa:

```
python planificador.py subir
```

Se abrirá el navegador:

1. Elige tu cuenta de Google.
2. Verás **"Google no ha verificado esta app"**. Es normal: la app es tuya y no está publicada. Pulsa **Continuar**.
   (Si no ves ese botón, pulsa **Configuración avanzada** y luego **Ir a Planificador de estudio**.)
3. Google te pide permiso para **ver y editar eventos** de tus calendarios. Si aparece una casilla junto al permiso, **márcala**. Luego pulsa **Continuar**.
4. Cuando el navegador diga **"Listo. Ya puedes cerrar esta pestaña"**, vuelve a la terminal.

En la terminal debe aparecer `Listo: N sesiones creadas en Google Calendar`. Abre <https://calendar.google.com> y verás eventos como **Estudiar: Matemáticas (1/6)**.

> **Cada 7 días** Google pide el permiso otra vez (porque la app está en modo de prueba). Cuando pase, el navegador se abrirá solo al usar `subir` o `limpiar`: solo tienes que aceptar de nuevo.

---

## Paso 6. Recibir los avisos en el teléfono

1. Instala **Google Calendar** (Play Store en Android, App Store en iPhone).
2. Inicia sesión con la **misma cuenta de Google** que usaste en el paso 4.
3. Permite sus notificaciones: en el teléfono, ve a *Ajustes → Notificaciones → Google Calendar* y actívalas.
4. Abre Google Calendar en el teléfono y comprueba que ves las sesiones **Estudiar: …**.

Cada sesión te avisará **5 minutos antes** (puedes cambiarlo en `config.json`, clave `aviso_minutos_antes`).

---

## Lista de comprobación

- [ ] `python --version` muestra 3.10 o más.
- [ ] Tengo la carpeta del programa y dentro está `planificador.py`.
- [ ] `python -m unittest discover -s tests` termina en `OK`.
- [ ] En Google Cloud: proyecto creado, API de Calendar habilitada, mi correo en *Test users*.
- [ ] `credentials.json` está en la carpeta del programa, con ese nombre exacto.
- [ ] `python planificador.py subir` creó las sesiones y las veo en calendar.google.com.
- [ ] Google Calendar está en el teléfono, con la misma cuenta y las notificaciones activadas.

Si marcaste todo, ya está funcionando.

---

## Uso de cada semana

| Cuándo | Qué escribir |
|---|---|
| El domingo (o el primer día de tu semana) | `python planificador.py generar` y luego `python planificador.py subir` |
| Cada día, para ver lo que te toca | `python planificador.py hoy` |
| Si cambias un tema a mitad de semana | `python planificador.py generar` y luego `python planificador.py subir --reemplazar` |
| Para borrar del calendario las sesiones del plan | `python planificador.py limpiar` (solo borra las que creó esta app) |

Todos los comandos y ajustes están explicados en el [README](README.md).

---

## Si algo falla

| Lo que ves | Qué hacer |
|---|---|
| `Faltan las librerías de Google` | Repite el paso 3. |
| `No encuentro credentials.json` | Repite el paso 4.5. Si el mensaje dice "Pero encontré…", renombra el archivo que indica. |
| En el navegador: **"Acceso bloqueado"** o **error 403: access_denied** | Falta tu correo en *Test users* (paso 4.3, punto 6). |
| `Google Calendar respondió con un error (403)` | La API no está habilitada, o el proyecto seleccionado no es el correcto (paso 4.2). |
| En el navegador: **error redirect_uri_mismatch** | Creaste el cliente como *Web application*. Crea otro como **Desktop app** (paso 4.4) y reemplaza `credentials.json`. |
| `Ya hay N sesiones del planificador en tu calendario…` | Ya las habías subido. Usa `python planificador.py subir --reemplazar`. |
| No llegan avisos al teléfono | Revisa el paso 6: misma cuenta y notificaciones activadas. |
| Otra cosa | Copia el mensaje completo y pídeme ayuda. Hay más casos en la sección 10 del [README](README.md). |
