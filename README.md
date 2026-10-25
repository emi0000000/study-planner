# study-planner
“Study planner that splits your time into short sessions and syncs them with Google Calendar.”

# Planificador de estudio

Reparte tu tiempo de estudio entre temas en **sesiones cortas** (por defecto de 25 minutos) y las crea en **Google Calendar**, para que el **teléfono te avise** antes de cada una. No hace falta programar nada para el móvil: basta con la app de Google Calendar.

Qué hace esta primera versión:

- Guarda temas con su **prioridad** (1 a 5) y los **minutos por semana** que quieres dedicarles.
- Genera las **sesiones cortas de cada día** para los próximos 7 días, con descansos entre medias.
- Crea esas sesiones en **Google Calendar** (API gratuita) con un aviso tipo notificación.

---

## 1. Requisitos

- **Python 3.10 o más nuevo.** Para comprobarlo, abre PowerShell y escribe `python --version`.
- Una **cuenta de Google** (vale una de Gmail normal).
- En el teléfono, la app **Google Calendar** con esa misma cuenta (solo para recibir los avisos).

## 2. Instalación

1. Abre la carpeta del programa en el Explorador de archivos.
2. Haz clic derecho en un espacio vacío y elige **Abrir en Terminal** (o abre PowerShell y ve a la carpeta con `cd`).
3. Instala las librerías de Google:

```bash
python -m pip install -r requirements.txt
```

> Sin estas librerías la app funciona igual para guardar temas y generar el plan. Solo las necesita para `subir` y `limpiar`.

## 3. Uso rápido

```bash
python planificador.py agregar "Matemáticas" --prioridad 5 --minutos 150
```

```bash
python planificador.py agregar "Inglés" --prioridad 3 --minutos 90
```

```bash
python planificador.py generar
```

```bash
python planificador.py subir
```

Y cada día, para ver lo que te toca:

```bash
python planificador.py hoy
```

Ejemplo de lo que muestra `generar` con cuatro temas (Matemáticas 150 min, Química 110, Inglés 90 e Historia 60):

```
Plan de estudio del 26/10/2026 al 01/11/2026

Lunes 26/10
  18:00-18:25  Matemáticas (1/6)
  18:30-18:55  Química (1/5)
  19:00-19:25  Inglés (1/4)
  19:30-19:40  Historia (1/3)
  = 85 min de estudio

Martes 27/10
  18:00-18:25  Matemáticas (2/6)
  ...
Domingo 01/11  (libre)

Resumen por tema:
  Matemáticas: 150 de 150 min
  Química: 110 de 110 min
  ...
```

El `(2/6)` quiere decir "sesión 2 de las 6 que tiene ese tema esta semana".

## 4. Todos los comandos

| Comando | Qué hace |
|---|---|
| `agregar "Tema" -p 4 -m 120` | Agrega un tema con prioridad 4 y 120 min por semana. Si ya existe, lo actualiza. La prioridad es opcional (por defecto 3). |
| `temas` | Muestra los temas guardados y el total de minutos por semana. |
| `quitar "Tema"` | Quita un tema. No importan las mayúsculas ni las tildes. |
| `generar` | Crea el plan de los próximos 7 días y lo guarda. Empieza hoy, o mañana si tu hora de inicio de hoy ya pasó. |
| `generar --desde 2026-11-02` | Igual, pero empezando en esa fecha (formato AAAA-MM-DD). |
| `hoy` | Muestra las sesiones de hoy según el último plan generado. |
| `hoy --fecha 2026-11-04` | Muestra las sesiones de otro día. |
| `subir` | Crea las sesiones del plan en Google Calendar, cada una con su aviso. |
| `subir --simular` | Muestra lo que se crearía, **sin** conectarse a Google. Útil para probar. |
| `subir --reemplazar` | Si ya habías subido sesiones en esas fechas, las borra y sube las nuevas (por ejemplo, después de cambiar un tema). |
| `limpiar` | Borra del calendario las sesiones que creó esta app en las fechas del plan. **Nunca toca tus otros eventos.** |
| `limpiar --desde 2026-10-26 --hasta 2026-11-01` | Igual, para las fechas indicadas. |
| `config` | Muestra la configuración actual y dónde está el archivo. |

Todos se escriben después de `python planificador.py`. Para ver la ayuda de un comando: `python planificador.py subir -h`.

**Flujo semanal recomendado:** el domingo (o el primer día de tu semana) ejecuta `generar` y luego `subir`. Si cambias algo a mitad de semana, vuelve a ejecutar `generar` y `subir --reemplazar`.

## 5. Conectar con Google Calendar (solo una vez)

La API de Google Calendar es gratuita y no pide tarjeta. Necesitas crear un "proyecto" en Google Cloud y descargar un archivo de permisos llamado `credentials.json`. Se hace una sola vez y lleva unos 10 minutos.

### 5.1 Crear el proyecto y activar la API

1. Entra a <https://console.cloud.google.com/> con tu cuenta de Google.
2. Arriba, junto al logo, abre el selector de proyectos y pulsa **New project** (Proyecto nuevo). Ponle un nombre, por ejemplo `planificador-estudio`, y créalo.
3. Con ese proyecto seleccionado, ve a <https://console.cloud.google.com/apis/library/calendar-json.googleapis.com> y pulsa **Enable** (Habilitar).

### 5.2 Configurar la pantalla de permiso

1. En el menú ☰, ve a **Google Auth platform → Branding**. Si aparece "Google Auth platform not configured yet", pulsa **Get started**.
2. **App information:** escribe un nombre (por ejemplo `Planificador de estudio`) y elige tu correo como *User support email*. Pulsa **Next**.
3. **Audience:** elige **External** (con una cuenta de Gmail normal es la única opción). Pulsa **Next**.
4. **Contact information:** escribe tu correo. Pulsa **Next**.
5. **Finish:** acepta la política de datos y pulsa **Continue** y luego **Create**.
6. Ve a **Google Auth platform → Audience**, busca **Test users**, pulsa **Add users** y añade **tu propio correo**. Guarda.

> La app queda en modo *Testing* (prueba): solo pueden usarla los correos que pongas como test users. Para uso personal es justo lo que queremos.

### 5.3 Crear y descargar `credentials.json`

1. Ve a **Google Auth platform → Clients** y pulsa **Create client**.
2. En **Application type** elige **Desktop app**. Ponle un nombre cualquiera y pulsa **Create**.
3. En la ventana que aparece, pulsa **Download JSON**. Hazlo en ese momento: puede que Google no te deje descargarlo después. Si lo pierdes, crea otro cliente.
4. Mueve el archivo descargado a la carpeta del programa y **renómbralo a `credentials.json`** (junto a `planificador.py`).

### 5.4 Primer inicio de sesión

Ejecuta `python planificador.py subir`. Se abrirá el navegador:

1. Elige tu cuenta.
2. Verás un aviso **"Google no ha verificado esta app"**. Es normal: la app es tuya y no está publicada. Pulsa **Continuar**.
3. Acepta el permiso para **ver y editar eventos** de tus calendarios.
4. Cuando el navegador diga "Listo. Ya puedes cerrar esta pestaña", vuelve a la terminal.

La app guarda el permiso en `token.json`, así que las siguientes veces no se abre el navegador.

> **Importante:** en modo *Testing*, Google hace caducar el permiso cada **7 días**. Cuando pase, la app abrirá el navegador otra vez al usar `subir` o `limpiar`; solo tienes que volver a aceptar. Si te molesta, en **Google Auth platform → Audience** puedes pulsar **Publish app**; seguirá apareciendo el aviso de "app no verificada", pero el permiso dura más.

> **Privacidad:** `credentials.json` y `token.json` dan acceso a tu calendario. No los compartas ni los subas a internet.

## 6. Recibir los avisos en el teléfono

1. Instala **Google Calendar** en el teléfono (Android o iPhone) e inicia sesión con la **misma cuenta**.
2. Activa sus notificaciones: en el teléfono, *Ajustes → Notificaciones → Google Calendar → permitir*. Dentro de la app, en *Configuración → (tu cuenta)*, comprueba que las notificaciones de eventos estén activadas.
3. Listo: cada sesión creada con `subir` te avisará los minutos antes que diga `aviso_minutos_antes` (por defecto, 5).

Las sesiones aparecen con el título `Estudiar: Tema (2/6)` y con un color según la prioridad: rojo (5), naranja (4), amarillo (3), verde (2) y gris (1).

## 7. Configuración (`config.json`)

Puedes cambiar estos valores con el Bloc de notas. Respeta las comillas y las comas. Si te equivocas, la app te dirá qué línea revisar. Si borras el archivo, se vuelve a crear con los valores de abajo.

| Clave | Por defecto | Qué significa |
|---|---|---|
| `duracion_sesion` | `25` | Minutos de cada sesión corta. |
| `duracion_minima` | `10` | Si al partir un tema sobran menos minutos que esto, se suman a la última sesión en vez de crear una minúscula. |
| `descanso_corto` | `5` | Minutos de descanso entre sesiones. |
| `descanso_largo` | `15` | Minutos del descanso largo. |
| `sesiones_antes_de_descanso_largo` | `4` | Cada cuántas sesiones toca el descanso largo (`0` = nunca). |
| `maximo_minutos_por_dia` | `120` | Máximo de estudio por día, sin contar descansos (`0` = sin límite). |
| `horario` | lunes a viernes `18:00`, sábado `10:00` | Días en que estudias y a qué hora empiezas cada uno. Quita un día para no estudiar ese día. Ejemplo: `{"lunes": "17:30", "domingo": "11:00"}`. Las sesiones de un día terminan como muy tarde a medianoche, así que si empiezas tarde caben menos. |
| `aviso_minutos_antes` | `5` | Minutos antes de cada sesión en que suena el aviso (`0` = justo al empezar). |
| `id_calendario` | `"primary"` | Calendario de Google donde se crean las sesiones. `primary` es el principal. |

**Consejo: un calendario aparte para estudiar.** En Google Calendar (web), crea un calendario nuevo llamado "Estudio" (*Otros calendarios → + → Crear calendario*). Luego, en su *Configuración → Integrar el calendario*, copia el **ID del calendario** (algo como `abc123@group.calendar.google.com`) y pégalo en `id_calendario`. Así puedes ocultar o mostrar todas tus sesiones de un clic.

## 8. Cómo reparte el tiempo

1. **Parte cada tema en sesiones cortas.** Con sesiones de 25 min: 100 min → 4 sesiones de 25; 110 min → 4 de 25 y una de 10; 105 min → 3 de 25 y una de 30.
2. **Reparte las sesiones entre los días de estudio:**
   - Empieza por los temas de **mayor prioridad**. Si no cabe todo en la semana, se quedan fuera primero los de **menor prioridad**, y `generar` te avisa de cuántos minutos faltaron.
   - Un mismo tema va a **días distintos** y, si se puede, **no seguidos** (por ejemplo lunes, miércoles y viernes). Estudiar con espacio entre repasos ayuda a recordar.
   - Intenta que cada día tenga una **carga parecida**, sin pasar del máximo diario y terminando antes de medianoche.
3. **Ordena cada día:** primero lo más prioritario (cuando estás más fresco) y sin repetir el mismo tema dos veces seguidas si hay alternativa.
4. **Pone las horas:** desde tu hora de inicio, con descanso corto entre sesiones y uno largo cada 4.

## 9. Archivos de la carpeta

| Archivo | Para qué sirve |
|---|---|
| `planificador.py` | El programa que ejecutas: lee los comandos y muestra los resultados. |
| `repartidor.py` | El "motor": parte los temas en sesiones y las reparte por días. |
| `calendario_google.py` | La conexión con Google Calendar (iniciar sesión, crear y borrar eventos). |
| `almacen.py` | Guarda y lee los temas, la configuración y el plan. |
| `config.json` | Tus ajustes (ver sección 7). |
| `requirements.txt` | Lista de librerías de Google que hay que instalar. |
| `tests/` | Pruebas automáticas. |
| `datos/temas.json` | Tus temas (se crea al agregar el primero). |
| `datos/plan.json` | El último plan generado. |
| `credentials.json` | Lo descargas de Google (sección 5). **Privado.** |
| `token.json` | Lo crea la app tras iniciar sesión. **Privado.** Bórralo para cerrar sesión. |

El código está comentado línea por línea, por si quieres entender o cambiar cómo funciona.

## 10. Problemas frecuentes

| Mensaje o problema | Solución |
|---|---|
| `Faltan las librerías de Google` | Ejecuta `python -m pip install -r requirements.txt`. |
| `No encuentro credentials.json` | Sigue la sección 5.3 y comprueba que el archivo se llama exactamente `credentials.json` (Windows a veces oculta la extensión y queda `credentials.json.json`). |
| En el navegador: **"Acceso bloqueado"** o **error 403: access_denied** | No añadiste tu correo como *test user* (sección 5.2, paso 6). |
| `Google Calendar respondió con un error (403)` y habla de la API | La API no está habilitada en tu proyecto (sección 5.1, paso 3). |
| `Ya hay N sesiones del planificador en tu calendario...` | Ya habías subido sesiones en esas fechas. Usa `subir --reemplazar` para cambiarlas por las nuevas. |
| El navegador se abre otra vez para pedir permiso | Pasa cada 7 días en modo *Testing* (ver sección 5.4). Acepta otra vez. |
| Quiero usar otra cuenta de Google | Borra `token.json` y vuelve a ejecutar `subir`. |
| No me llegan los avisos al teléfono | Revisa la sección 6: misma cuenta en el teléfono, notificaciones de la app activadas y, si usas un calendario aparte, que esté marcado como visible en la app. |
| `no entraron N sesiones` al generar | Pides más minutos de los que caben. Sube `maximo_minutos_por_dia`, agrega días en `horario`, empieza más temprano (si estudias de noche) o baja minutos de algún tema. |
| `datos/temas.json está mal escrito` o `el plan guardado está dañado` | Alguien editó esos archivos a mano. Corrige el tema que indica el mensaje, o borra `datos/temas.json` y vuelve a agregar tus temas. Para el plan, basta con ejecutar `generar` otra vez. |
| Las tildes se ven como `�` | Pasa si rediriges la salida a otro programa. En una ventana normal de PowerShell o Terminal se ven bien. |

## 11. Pruebas automáticas

Para comprobar que todo funciona (no se conecta a Google; usa respuestas simuladas):

```bash
python -m unittest discover -s tests -v
```

Si las librerías de Google no están instaladas, las pruebas de conexión se saltan y el resto se ejecuta igual.

## 12. Fuera de esta versión

- Conectar con el calendario interno de Windows.
- App propia para el móvil.

## Licencia

MIT. Ver el archivo [LICENSE](LICENSE).
