# Gemma Garage

*Agenda local para un taller mecánico.*

Una agenda para un taller mecánico que se encarga sola del papeleo:

1. **Apuntas la cita como en papel**: `cambio aceite motor opel aceite 5w30`.
2. Un **modelo de IA abierto y local** (Gemma, vía Ollama) entiende la nota: servicio, marca, recambios y cada cuánto se repite.
3. **El día laborable antes de la cita, pide los recambios** al proveedor (el lunes para el martes; el viernes para el lunes).
4. Si el servicio se repite (ITV, aceite: cada 12 meses), **avisa al cliente por Telegram** una semana antes de que se cumpla el año.
5. Al terminar, **genera la factura** imprimible con IVA.

Tiene un **frontal propio** (pantallas *Hoy*, *Semana*, *Clientes* y *Facturas*, también en el móvil) y, para lo avanzado, el **admin de Django** en `/admin/`. Base de datos **Postgres**.

> *English summary:* a local-first appointment book for a car workshop, built with Django (admin as the UI) and Postgres. A local open-weight model (Gemma via Ollama) parses free-text notes into parts and recurrence; parts are ordered automatically the business day before; yearly reminders go out through a free Telegram bot; invoices are generated. No cloud AI: customer data stays on the machine. Falls back to simple rules if no model is running.

## Así se ve

Vídeo completo: [`docs/media/taller-demo.mp4`](docs/media/taller-demo.mp4). Todas las capturas son de los datos de ejemplo (clientes y matrículas inventados).

**1. Apuntar una cita.** Escribes la matrícula y reconoce al cliente que vuelve; escribes la nota como la dirías y el panel *Lo que he entendido* muestra el trabajo, el coche, los recambios y el aviso anual.

![Apuntar una cita](docs/media/01-nueva-cita.gif)

Con Gemma activo, el panel lo dice (la captura es real, con `gemma3` en local):

![Entendido con Gemma](docs/media/gemma-interpretation.png)

**2. Revisar y pedir los recambios**, con aviso de «Pidiendo recambios…» mientras se envía. Si el distribuidor falla, la cita queda marcada para reintentar.

![Pedido](docs/media/02-pedido.gif)

**3. Lista de compra del día**

![Lista de compra](docs/media/03-compra.gif)

**4. Hecha y facturar.** Escribes los precios de los recambios del albarán (no se guardan: dependen del distribuidor); la mano de obra sale de tus tarifas; el total se actualiza en vivo.

![Factura](docs/media/04-factura.gif)

**5. Tarifas, semana, búsqueda y clientes**

![Tarifas y búsqueda](docs/media/05-tarifas-busqueda.gif)

**6. En el móvil**

<img src="docs/media/06-movil.gif" width="260" alt="Vista móvil">

> Las capturas y GIFs se generan con `docs/record_demo.py`. Si Ollama está activo, el panel sale verde (Gemma); si no, gris (reglas simples). El script graba lo que ve, no retoca nada.

## Probarlo con datos de ejemplo

```bash
python manage.py demo            # solo si la base está vacía
python manage.py demo --reset    # borra clientes, citas y facturas (antes guarda una copia .json)
```

Para regenerar las capturas y vídeos con Gemma (Ollama encendido, entorno activado):

```bash
bash docs/grabar.sh
```

Pone los datos de ejemplo (guardando antes una copia de los tuyos), arranca el servidor solo, graba y lo para. Si Gemma no responde, se detiene en vez de grabar con las reglas simples (`ALLOW_RULES=1` para forzarlo).

## Arrancar desde cero

Necesitas: **Python 3.10+**, **Git** y **Docker** (para Postgres). Ollama es opcional.

**1. Descarga el proyecto y entra en la carpeta**

```bash
git clone https://github.com/antoniahp/gemma-garage.git
cd gemma-garage
```

**2. Crea un entorno de Python e instala las dependencias**

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

**3. Arranca Postgres**

```bash
docker compose up -d
```

**4. Carga la configuración**

```bash
cp .env.example .env               # Windows: copy .env.example .env
set -a; source .env; set +a        # carga las variables en esta terminal
```

En Windows (PowerShell), en lugar de la última línea:

```powershell
Get-Content .env | Where-Object { $_ -match '^[A-Z]' } | ForEach-Object { $k,$v = $_ -split '=',2; Set-Item "env:$k" $v }
```

Las variables solo valen para la terminal donde las cargas: si abres otra, vuelve a cargarlas.

**5. Crea las tablas y tu usuario**

```bash
python manage.py migrate
python manage.py createsuperuser   # te pide usuario y contraseña
```

**6. (Opcional) Carga citas de ejemplo**

```bash
python manage.py demo
```

**7. Abre la agenda**

```bash
python manage.py runserver
```

Entra en <http://127.0.0.1:8000> con el usuario que creaste. Verás el tablero **Hoy**; arriba está *Nueva cita*, que va interpretando lo que escribes. Pedidos, avisos y otros datos se gestionan en <http://127.0.0.1:8000/admin/>.

**8. Apunta una cita**

En **Hoy → Nueva cita**: elige el día, escribe el cliente y la nota (`cambio aceite motor opel aceite 5w30`). Al lado ves lo que ha entendido (trabajo, recambios, aviso anual). Los clientes nuevos se crean solos; puedes corregir cualquier dato en `/admin/`. Si el servicio se repite, ya queda programado el aviso para el año siguiente.

**9. Lanza el trabajo diario**

```bash
python manage.py run_daily
```

Pide los recambios de las citas de mañana y envía los avisos que toquen. Sin configurar nada más, **no sale nada al exterior**: los pedidos y avisos se guardan en la carpeta `outbox/` para que puedas comprobarlos. En cada ficha hay botones *Pedir ahora* y *Hecha y facturar*.

**10. Prográmalo cada mañana**

Linux/macOS (cron, 8:00 de lunes a viernes; ajusta rutas):

```
0 8 * * 1-5  cd /ruta/taller-agenda && set -a && . ./.env && set +a && .venv/bin/python manage.py run_daily
```

Windows: Programador de tareas → ejecutar `.venv\Scripts\python.exe manage.py run_daily` en la carpeta del proyecto (con las variables definidas). Si un día no se ejecuta, la siguiente ejecución pide lo que falte.

## Comodidades del frontal

- **Pedido** (`/pedido/`): revisa y corrige los recambios (cantidades, líneas) antes de enviarlos al proveedor. Si un pedido falla, aparece en rojo en *Hoy* para reintentarlo.
- **Lista de compra** (`/compra/`): todos los recambios de un día, sumados y listos para imprimir.
- **Editar cita**: botón *Editar* en cada ficha. Al cambiar la fecha o la repetición, el aviso anual se reprograma.
- **Historial por matrícula**: al escribir una matrícula en *Nueva cita* aparecen las visitas anteriores y se puede reutilizar el cliente.
- **Buscador** (cuadro de arriba): por matrícula, cliente, teléfono, vehículo o nota.
- **Llamar / WhatsApp**: enlaces en cada ficha y en *Clientes* (a un teléfono de 9 cifras se le pone el +34).
- **Tarifas** (`/tarifas/`): lo que cobras de mano de obra por cada trabajo (cambio de aceite 45 €, ITV 30 €…). Los recambios no tienen precio guardado, porque dependen del distribuidor: al pulsar *Hecha y facturar* escribes el precio de cada uno según su albarán, y la mano de obra sale ya rellena (puedes cambiarla para esa cita).
- **Copia** (arriba a la derecha): descarga todos los datos en un archivo `.json`. Para restaurarlos: `python manage.py loaddata copia-taller-AAAA-MM-DD.json` (en una base de datos recién migrada).

Si actualizas desde una versión anterior, ejecuta `python manage.py migrate` (añade el campo del último error de pedido y las tarifas de mano de obra).

## Avisos por Telegram (gratis)

Un bot de Telegram **no puede escribir a un cliente que no haya hablado antes con él**. Por eso cada cliente debe abrir un enlace una sola vez.

1. En Telegram habla con **@BotFather**, escribe `/newbot` y sigue los pasos. Te da un **token** y un nombre de usuario.
2. Rellena en `.env` `TELEGRAM_BOT_TOKEN` y `TELEGRAM_BOT_USERNAME`, y vuelve a cargar las variables.
3. Deja el bot escuchando en una terminal aparte: `python manage.py telegram_bot`.
4. **Tu chat de mecánico:** escribe `/id` a tu bot, copia el número en `TELEGRAM_OWNER_CHAT_ID` y recarga. Recibirás un resumen diario y los avisos de clientes sin Telegram.
5. **Cada cliente:** abre la pantalla **Clientes**, copia su **enlace** y pásaselo (por WhatsApp o impreso). Cuando lo abra y pulse *Iniciar*, queda vinculado.

Si a un cliente le toca un aviso y aún no ha vinculado Telegram, el bot **te lo manda a ti** con su teléfono para que le llames.

## Pedido al proveedor

Por defecto es de prueba (`outbox/pedidos.jsonl`). Con `TALLER_SUPPLIER=email` y las variables `SMTP_*` y `SUPPLIER_EMAIL` (ver `.env.example`) se envía por correo. Bosch, Lozano y otros distribuidores no suelen ofrecer una API pública estándar; lo habitual es pedir por correo o por su portal. Para un portal concreto, crea otra clase con `send_order()` en `taller/channels.py`.

## IA local (opcional pero recomendada)

Instala [Ollama](https://ollama.com) y ejecuta `ollama pull gemma3`. Con Ollama en marcha, el programa lo usa solo. Sin él funciona igual con reglas para los casos habituales (aceite, ITV, frenos, filtros, neumáticos, batería, correa). Variables: `TALLER_MODEL`, `OLLAMA_URL`, `TALLER_NO_LLM=1` para desactivarla.

## Seguridad

- Pensado para usarse en el equipo del taller. Para un servidor accesible desde internet: `DJANGO_DEBUG=0`, un `DJANGO_SECRET_KEY` largo y aleatorio, HTTPS y `DJANGO_ALLOWED_HOSTS`.
- Los datos de clientes quedan en tu Postgres. Con Gemma local, las notas no salen del equipo.
- Revisa las tarifas de mano de obra en *Tarifas*; los precios de los recambios los escribes al facturar. La factura es un borrador imprimible y no sustituye a un programa de facturación homologado.
- Haz copias de seguridad de la base de datos.

## Tests

```bash
python manage.py test taller
```

Funcionan con Postgres (si tienes las variables cargadas) o con SQLite.

## Licencia

MIT.
