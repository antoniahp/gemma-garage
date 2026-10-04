"""Graba capturas, GIFs y un vídeo de todos los flujos del Taller.

Uso (con el servidor en marcha y los datos de ejemplo cargados):

    python manage.py demo --reset
    python manage.py createsuperuser            # o usa uno existente
    python manage.py runserver 8000             # en otra terminal
    pip install playwright && playwright install chromium
    TALLER_USER=mecanico TALLER_PASS=... python docs/record_demo.py

Variables: TALLER_BASE (http://127.0.0.1:8000), TALLER_USER, TALLER_PASS,
TALLER_OUT (docs/media), CAPTIONS (en | es, por defecto en).
Si Ollama/Gemma está activo, el panel «Lo que he entendido» sale verde
(«Entendido con Gemma»); si no, sale gris («reglas simples»). El script
no inventa nada: graba lo que pasa en tu pantalla.
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = os.environ.get("TALLER_BASE", "http://127.0.0.1:8000").rstrip("/")
USER = os.environ.get("TALLER_USER", "mecanico")
PASS = os.environ.get("TALLER_PASS", "demo1234")
OUT = Path(os.environ.get("TALLER_OUT", Path(__file__).parent / "media")).resolve()
LANG = os.environ.get("CAPTIONS", "en")
W, H = 1180, 760
NOTE = "cambio aceite 5w30 y filtro de aceite, seat ibiza"   # la misma nota se calienta antes (la app cachea respuestas)
TMP = OUT / "_tmp"

CAPS = {
    "en": {
        "board": "Today's board: every job, its parts and its order status",
        "plate": "Type a plate: the app recognises the returning customer",
        "note": "Write the job as you'd say it. The model reads it live",
        "saved": "Saved. The parts will be ordered the business day before",
        "review": "Review the order before it goes out. Edit anything",
        "sending": "Sending the order to the distributor…",
        "sent": "Order sent. Failed ones can be retried",
        "shop": "Shopping list for the day, grouped by part",
        "invoice": "Job done: type the part prices from the delivery note",
        "total": "Labour comes from your tariffs; VAT and total are live",
        "invoiced": "Invoice created, numbered and ready to print",
        "prices": "Labour tariffs: you set the price of each job once",
        "search": "Search by plate, customer, phone or what you wrote",
        "week": "The whole week at a glance",
        "clients": "Customers, with call / WhatsApp and Telegram status",
        "mobile": "Works on the phone, in the workshop",
    },
    "es": {
        "board": "Tablero de hoy: cada trabajo, sus recambios y el estado del pedido",
        "plate": "Escribe la matrícula: reconoce al cliente que vuelve",
        "note": "Escribe el trabajo como lo dirías. El modelo lo lee en vivo",
        "saved": "Guardada. Los recambios se piden el día laborable anterior",
        "review": "Revisa el pedido antes de enviarlo. Edita lo que quieras",
        "sending": "Enviando el pedido al distribuidor…",
        "sent": "Pedido enviado. Los que fallan se pueden reintentar",
        "shop": "Lista de compra del día, agrupada por recambio",
        "invoice": "Trabajo hecho: escribe los precios del albarán",
        "total": "La mano de obra sale de tus tarifas; IVA y total, en vivo",
        "invoiced": "Factura creada, numerada y lista para imprimir",
        "prices": "Tarifas de mano de obra: fijas el precio de cada trabajo una vez",
        "search": "Busca por matrícula, cliente, teléfono o lo que escribiste",
        "week": "Toda la semana de un vistazo",
        "clients": "Clientes, con llamar / WhatsApp y estado de Telegram",
        "mobile": "Funciona en el móvil, en el taller",
    },
}[LANG]

INIT = """
(() => {
  const css = `
  #__cur{position:fixed;z-index:99999;width:20px;height:20px;border-radius:50%;
    background:rgba(230,60,40,.8);border:2px solid #fff;pointer-events:none;
    left:-40px;top:-40px;transform:translate(-50%,-50%);transition:transform .08s}
  #__cur.down{transform:translate(-50%,-50%) scale(.7)}
  #__cap{position:fixed;z-index:99998;left:50%;bottom:22px;transform:translateX(-50%);
    max-width:86%;padding:10px 18px;border-radius:10px;background:rgba(20,22,26,.92);
    color:#fff;font:600 17px/1.3 system-ui,sans-serif;text-align:center;pointer-events:none}`;
  function mount(){
    if(document.getElementById('__cur')) return;
    const s=document.createElement('style'); s.textContent=css; document.head.appendChild(s);
    const d=document.createElement('div'); d.id='__cur'; document.body.appendChild(d);
    const c=document.createElement('div'); c.id='__cap'; document.body.appendChild(c);
    let p=null; try{p=JSON.parse(sessionStorage.getItem('__pos')||'null')}catch(e){}
    if(p){d.style.left=p[0]+'px';d.style.top=p[1]+'px'}
    let t=''; try{t=sessionStorage.getItem('__capt')||''}catch(e){}
    c.textContent=t; c.style.display=t?'block':'none';
    document.addEventListener('mousemove',e=>{d.style.left=e.clientX+'px';d.style.top=e.clientY+'px';
      try{sessionStorage.setItem('__pos',JSON.stringify([e.clientX,e.clientY]))}catch(_){}});
    document.addEventListener('mousedown',()=>d.classList.add('down'));
    document.addEventListener('mouseup',()=>d.classList.remove('down'));
  }
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',mount); else mount();
})();
"""


def caption(pg, text):
    for _ in range(5):          # si la página está navegando, se espera y se reintenta
        try:
            pg.evaluate(
                """t=>{try{sessionStorage.setItem('__capt',t)}catch(e){}
                const c=document.getElementById('__cap'); if(c){c.textContent=t;c.style.display=t?'block':'none'}}""",
                text)
            return
        except Exception:
            pg.wait_for_timeout(600)
            try:
                pg.wait_for_load_state("domcontentloaded")
            except Exception:
                pass


def glide(pg, loc, pause=350):
    loc.scroll_into_view_if_needed()
    bb = loc.bounding_box()
    pg.mouse.move(bb["x"] + bb["width"] / 2, bb["y"] + bb["height"] / 2, steps=22)
    pg.wait_for_timeout(pause)


def click(pg, loc, **kw):
    glide(pg, loc)
    loc.click(**kw)


def type_slow(pg, loc, text, delay=55):
    glide(pg, loc, 200)
    loc.click()
    loc.press_sequentially(text, delay=delay)


def goto(pg, path):
    pg.goto(BASE + path)
    pg.wait_for_load_state("domcontentloaded")
    pg.wait_for_timeout(500)


def login(pg):
    """Las escenas ya arrancan con la sesión iniciada (no se graba el login)."""
    return


def real_login(pg):
    goto(pg, "/entrar/")
    pg.fill("#id_username", USER)
    pg.fill("#id_password", PASS)
    pg.click("button.btn.main")
    pg.wait_for_load_state("domcontentloaded")
    pg.wait_for_timeout(600)


def shot(pg, name, full=False):
    if full:  # en capturas de página entera el rótulo fijo saldría a mitad de página
        pg.evaluate("document.querySelectorAll('#__cap,#__cur').forEach(e=>e.style.visibility='hidden')")
    pg.screenshot(path=str(OUT / f"{name}.png"), full_page=full)
    if full:
        pg.evaluate("document.querySelectorAll('#__cap,#__cur').forEach(e=>e.style.visibility='')")


def wait_understood(pg):
    pg.wait_for_selector("#read-box .engine", timeout=90000)
    pg.wait_for_timeout(900)


class Scene:
    """Una escena = un contexto con vídeo; al cerrar se convierte en GIF."""

    def __init__(self, browser, name, size=(W, H), mobile=False):
        self.name = name
        d = TMP / name
        shutil.rmtree(d, ignore_errors=True)
        kw = dict(viewport={"width": size[0], "height": size[1]}, storage_state=str(TMP / "state.json"),
                  record_video_dir=str(d), record_video_size={"width": size[0], "height": size[1]})
        if mobile:
            kw.update(device_scale_factor=2, is_mobile=True, has_touch=True)
        self.ctx = browser.new_context(**kw)
        self.ctx.add_init_script(INIT)
        self.pg = self.ctx.new_page()
        self.dir = d

    def close(self):
        video = self.pg.video
        self.ctx.close()
        src = Path(video.path())
        webm = TMP / f"{self.name}.webm"
        shutil.move(src, webm)
        gif(webm, OUT / f"{self.name}.gif")
        return webm


def gif(webm, out, width=800, fps=12):
    pal = TMP / "pal.png"
    vf = f"fps={fps},scale={width}:-1:flags=lanczos"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(webm), "-vf", vf + ",palettegen=max_colors=96",
                    str(pal)], check=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(webm), "-i", str(pal), "-lavfi",
                    vf + "[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=4", str(out)], check=True)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    TMP.mkdir(parents=True, exist_ok=True)
    webms = []
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context()
        pg = ctx.new_page()
        real_login(pg)
        ctx.storage_state(path=str(TMP / "state.json"))
        # Calienta Gemma (la primera petición carga el modelo) y comprueba qué motor responde
        engine = ""
        for _ in range(3):
            r = ctx.request.get(BASE + "/interpretar/", params={"note": NOTE, "vehicle": "Seat Ibiza"},
                                timeout=120000)
            engine = (r.json() or {}).get("engine", "")
            if engine.startswith("ollama"):
                break
        print("Motor:", engine or "desconocido")
        if not engine.startswith("ollama") and not os.environ.get("ALLOW_RULES"):
            sys.exit("Gemma no responde (¿ollama serve y ollama pull gemma3?). Para grabar igualmente con las "
                     "reglas simples: ALLOW_RULES=1")
        ctx.close()

        # 1. Tablero + nueva cita con Gemma
        s = Scene(b, "01-nueva-cita"); pg = s.pg
        login(pg); goto(pg, "/")
        caption(pg, CAPS["board"]); pg.wait_for_timeout(1800)
        shot(pg, "01-hoy")
        shot(pg, "01-hoy-completo", full=True)
        pg.evaluate("document.getElementById('id_plate').scrollIntoView({block:'center'})")
        caption(pg, CAPS["plate"])
        type_slow(pg, pg.locator("#id_plate"), "1234 BCD")
        pg.wait_for_selector("#hist .hist", timeout=10000); pg.wait_for_timeout(700)
        shot(pg, "02-matricula-historial")
        click(pg, pg.locator("#usar")); pg.wait_for_timeout(500)
        caption(pg, CAPS["note"])
        type_slow(pg, pg.locator("#id_note"), NOTE, delay=14)   # rápido: solo se interpreta la nota entera
        wait_understood(pg)
        pg.evaluate("document.getElementById('read-box').scrollIntoView({block:'center'})")
        pg.wait_for_timeout(600)
        shot(pg, "03-nueva-cita-entendido")
        pg.wait_for_timeout(1200)
        caption(pg, CAPS["saved"])
        click(pg, pg.locator("button:has-text('Apuntar cita')"))
        pg.wait_for_load_state("domcontentloaded"); pg.wait_for_timeout(1800)
        webms.append(s.close())

        # 2. Revisar y enviar el pedido (con spinner)
        s = Scene(b, "02-pedido"); pg = s.pg
        login(pg); goto(pg, "/pedido/")
        caption(pg, CAPS["review"]); pg.wait_for_timeout(1800)
        shot(pg, "04-revisar-pedido", full=True)
        caption(pg, CAPS["sending"])
        btn = pg.locator("button[value='send']")
        glide(pg, btn, 500)
        btn.click(no_wait_after=True)
        pg.wait_for_timeout(450)
        shot(pg, "05-pidiendo-recambios")
        pg.wait_for_load_state("domcontentloaded"); pg.wait_for_timeout(1200)
        caption(pg, CAPS["sent"]); pg.wait_for_timeout(2200)
        shot(pg, "06-pedido-enviado", full=True)
        webms.append(s.close())

        # 3. Lista de compra
        s = Scene(b, "03-compra"); pg = s.pg
        login(pg); goto(pg, "/compra/")
        caption(pg, CAPS["shop"]); pg.wait_for_timeout(2200)
        shot(pg, "07-lista-compra", full=True)
        webms.append(s.close())

        # 4. Hecha y facturar
        s = Scene(b, "04-factura"); pg = s.pg
        login(pg); goto(pg, "/semana/")
        link = pg.locator("article:has-text('Peugeot 208') a:has-text('Hecha y facturar')")
        if not link.count():                      # la cita puede caer en la semana siguiente
            click(pg, pg.locator("a.btn:has-text('Siguiente')"))
            pg.wait_for_load_state("domcontentloaded"); pg.wait_for_timeout(600)
        click(pg, link)
        pg.wait_for_load_state("domcontentloaded"); pg.wait_for_timeout(700)
        caption(pg, CAPS["invoice"])
        shot(pg, "08-facturar-vacio")
        first = pg.locator("input[name^='price_']").first
        type_slow(pg, first, "119,90", delay=90)
        pg.wait_for_timeout(500)
        lab = pg.locator("#id_labor")
        if not lab.input_value():                 # este trabajo no tiene tarifa: se escribe aquí
            type_slow(pg, lab, "35", delay=120)
        pg.wait_for_timeout(500)
        caption(pg, CAPS["total"])
        pg.wait_for_timeout(1800)
        shot(pg, "09-facturar-total", full=True)
        click(pg, pg.locator("button:has-text('Hecha y facturar')"))
        pg.wait_for_url(lambda u: "/facturar/" not in u, timeout=30000)
        pg.wait_for_load_state("load"); pg.wait_for_timeout(1200)
        caption(pg, CAPS["invoiced"]); pg.wait_for_timeout(1500)
        shot(pg, "10-factura-creada")
        href = pg.locator("a:has-text('abrir e imprimir')").get_attribute("href")
        goto(pg, href)
        caption(pg, CAPS["invoiced"]); pg.wait_for_timeout(2200)
        shot(pg, "10-factura", full=True)
        webms.append(s.close())

        # 5. Tarifas, búsqueda, semana, clientes
        s = Scene(b, "05-tarifas-busqueda"); pg = s.pg
        login(pg); goto(pg, "/tarifas/")
        caption(pg, CAPS["prices"]); pg.wait_for_timeout(1800)
        shot(pg, "11-tarifas", full=True)
        goto(pg, "/semana/")
        caption(pg, CAPS["week"]); pg.wait_for_timeout(1800)
        shot(pg, "12-semana", full=True)
        search = pg.locator("input[name=q]").first
        caption(pg, CAPS["search"])
        type_slow(pg, search, "1234 BCD", delay=90)
        search.press("Enter")
        pg.wait_for_load_state("domcontentloaded"); pg.wait_for_timeout(1800)
        shot(pg, "13-busqueda", full=True)
        goto(pg, "/clientes/")
        caption(pg, CAPS["clients"]); pg.wait_for_timeout(2200)
        shot(pg, "14-clientes", full=True)
        webms.append(s.close())

        # 6. Móvil
        s = Scene(b, "06-movil", size=(390, 800), mobile=True); pg = s.pg
        login(pg); goto(pg, "/")
        caption(pg, CAPS["mobile"]); pg.wait_for_timeout(1500)
        shot(pg, "15-movil")
        pg.evaluate("window.scrollTo({top:700,behavior:'smooth'})"); pg.wait_for_timeout(1500)
        shot(pg, "16-movil-2")
        webms.append(s.close())
        b.close()

    # vídeo completo: se normalizan todas las escenas a 1180x760 y se concatenan
    norm = []
    for w in webms:
        if "movil" in w.name:                 # la escena móvil es vertical: solo va en su GIF
            continue
        n = TMP / (w.stem + ".norm.mp4")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", "0.5", "-i", str(w), "-vf",
                        f"scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=0x14161a,fps=25",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "24", str(n)], check=True)
        norm.append(n)
    lst = TMP / "list.txt"
    lst.write_text("".join(f"file '{n}'\n" for n in norm))
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
                    "-c", "copy", str(OUT / "taller-demo.mp4")], check=True)
    shutil.rmtree(TMP, ignore_errors=True)
    print("Listo:", OUT)


if __name__ == "__main__":
    sys.exit(main())
