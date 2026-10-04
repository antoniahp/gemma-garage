import json
import os
import tempfile
from datetime import date
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

import dataclasses
from decimal import Decimal

from taller import container
from taller.application.complete_and_invoice_appointment.complete_and_invoice_appointment_command import (
    CompleteAndInvoiceAppointmentCommand,
)
from taller.application.create_appointment.create_appointment_command import CreateAppointmentCommand
from taller.application.find_labor_price.find_labor_price_query import FindLaborPriceQuery
from taller.application.process_telegram_update.process_telegram_update_command import (
    ProcessTelegramUpdateCommand,
)
from taller.application.process_telegram_update.process_telegram_update_command_handler import (
    ProcessTelegramUpdateCommandHandler,
)
from taller.application.run_daily.run_daily_command import RunDailyCommand
from taller.domain import business_calendar
from taller.infrastructure import ollama_note_parser as ollama_parser
from taller.infrastructure import telegram_api
from taller.infrastructure.repositories.db_client_repository import DbClientRepository
from taller.infrastructure.rules_note_parser import RulesNoteParser

from .models import Appointment, Client, Reminder

os.environ["TALLER_NO_LLM"] = "1"


# ---- ayudas: los tests entran por los casos de uso, igual que las vistas
def parse_note(note, use_llm=True, vehicle=""):
    parser = container.note_parser() if use_llm else RulesNoteParser()
    return dataclasses.asdict(parser.parse(note, vehicle=vehicle))


def run_daily(today=None):
    return container.run_daily_handler().handle(RunDailyCommand(today=today))


def complete_and_invoice(appointment, **kw):
    return container.complete_and_invoice_handler().handle(
        CompleteAndInvoiceAppointmentCommand(appointment_id=appointment.pk, **kw))


def labor_price(service):
    return container.find_labor_price_handler().handle(FindLaborPriceQuery(service=service))


def handle_update(update, reply):
    return ProcessTelegramUpdateCommandHandler(DbClientRepository(), reply).handle(
        ProcessTelegramUpdateCommand(update=update))


def make_appointment(client, day, note, plate="", vehicle="", **extra):
    """Crea una cita como lo hace la web: se interpreta la nota y se programa el aviso anual."""
    appt = container.create_appointment_handler().handle(CreateAppointmentCommand(
        date=day, client_name=client.name, note=note, phone=client.phone, plate=plate, vehicle=vehicle))
    if extra:
        Appointment.objects.filter(pk=appt.pk).update(**extra)
        appt.refresh_from_db()
    return appt


class OutboxMixin:
    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        override = override_settings(TALLER_OUTBOX=self.tmp.name, TELEGRAM_BOT_TOKEN="",
                                    TELEGRAM_OWNER_CHAT_ID="", TELEGRAM_BOT_USERNAME="MiTallerBot")
        override.enable()
        self.addCleanup(override.disable)

    def outbox(self, name):
        path = os.path.join(self.tmp.name, name)
        if not os.path.exists(path):
            return []
        with open(path, encoding="utf-8") as f:
            return [json.loads(line) for line in f]


class ParserTests(TestCase):
    def test_ejemplo_del_taller(self):
        r = parse_note("cambio aceite motor opel aceite 5w30", use_llm=False)
        self.assertEqual(r["service"], "cambio de aceite")
        self.assertEqual(r["vehicle"], "Opel")
        self.assertEqual(r["repeat_months"], 12)
        oil = [p for p in r["parts"] if p["name"] == "aceite motor"][0]
        self.assertEqual(oil["spec"], "5W30")

    def test_itv_no_lleva_recambios(self):
        r = parse_note("ITV seat leon", use_llm=False)
        self.assertEqual(r["parts"], [])
        self.assertEqual(r["repeat_months"], 12)


class DateTests(TestCase):
    def test_fin_de_mes(self):
        self.assertEqual(business_calendar.add_months(date(2028, 2, 29), 12), date(2029, 2, 28))

    def test_lunes_se_pide_el_viernes(self):
        self.assertEqual(business_calendar.previous_business_day(date(2026, 10, 12)), date(2026, 10, 9))


class PedidosTests(OutboxMixin, TestCase):
    def cita(self, day, note, **kw):
        client = Client.objects.create(name=kw.pop("name", "Pepe"), phone="+34600000000")
        return make_appointment(client, day, note, **kw)

    def test_la_nota_se_interpreta_al_guardar(self):
        a = self.cita(date(2026, 10, 6), "cambio aceite motor opel aceite 5w30")
        self.assertEqual(a.service, "cambio de aceite")
        self.assertEqual(a.vehicle, "Opel")
        self.assertEqual(a.parts[0]["spec"], "5W30")

    def test_pide_el_dia_antes_y_solo_una_vez(self):
        self.cita(date(2026, 10, 6), "cambio aceite motor opel aceite 5w30")  # martes
        self.assertEqual(run_daily(date(2026, 10, 3))["orders"], [])  # sábado: aún no
        self.assertEqual(len(run_daily(date(2026, 10, 5))["orders"]), 1)  # lunes
        pedido = self.outbox("pedidos.jsonl")[0]
        self.assertEqual(pedido["deliver_on"], "2026-10-06")
        self.assertTrue(any(p["spec"] == "5W30" for p in pedido["parts"]))
        self.assertEqual(run_daily(date(2026, 10, 5))["orders"], [])  # no duplica
        self.assertEqual(len(self.outbox("pedidos.jsonl")), 1)

    def test_si_no_se_ejecuto_antes_pide_el_mismo_dia(self):
        self.cita(date(2026, 10, 6), "cambio aceite opel")
        self.assertEqual(len(run_daily(date(2026, 10, 6))["orders"]), 1)

    def test_itv_no_genera_pedido(self):
        self.cita(date(2026, 10, 6), "ITV seat leon")
        self.assertEqual(run_daily(date(2026, 10, 5))["orders"], [])

    def test_si_el_proveedor_falla_no_se_marca_pedido(self):
        a = self.cita(date(2026, 10, 6), "cambio aceite opel")
        with mock.patch("taller.container.parts_supplier") as sup:
            sup.return_value.name = "x"
            sup.return_value.send_order.side_effect = RuntimeError("sin conexión")
            rep = run_daily(date(2026, 10, 5))
        self.assertEqual(rep["orders"], [])
        self.assertEqual(len(rep["errors"]), 1)
        a.refresh_from_db()
        self.assertFalse(a.ordered)


class AvisosTests(OutboxMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.client_obj = Client.objects.create(name="Ana", phone="+34611111111")
        make_appointment(self.client_obj, date(2026, 10, 6), "cambio aceite opel", plate="1234ABC")

    def test_aviso_una_semana_antes_del_ano_siguiente(self):
        self.assertEqual(Reminder.objects.get().send_on, date(2027, 9, 29))
        self.assertEqual(run_daily(date(2027, 9, 1))["reminders"], [])
        self.assertEqual(len(run_daily(date(2027, 9, 29))["reminders"]), 1)
        self.assertIn("06/10/2027", self.outbox("avisos.jsonl")[0]["text"])
        self.assertEqual(run_daily(date(2027, 9, 30))["reminders"], [])  # no se repite

    def test_itv_programa_aviso_aunque_no_haya_telegram(self):
        make_appointment(self.client_obj, date(2026, 10, 7), "ITV seat")
        self.assertEqual(Reminder.objects.count(), 2)


@override_settings(TELEGRAM_BOT_TOKEN="123:TEST", TELEGRAM_OWNER_CHAT_ID="999",
                   TELEGRAM_BOT_USERNAME="MiTallerBot")
class TelegramTests(TestCase):
    def setUp(self):
        self.cli = Client.objects.create(name="Ana", phone="+34611111111")
        self.sent = []
        patcher = mock.patch("taller.infrastructure.telegram_api.send", side_effect=lambda c, t: self.sent.append((c, t)))
        patcher.start()
        self.addCleanup(patcher.stop)

    def update(self, text, chat=555):
        return {"update_id": 1, "message": {"text": text, "chat": {"id": chat}}}

    def test_start_con_enlace_vincula_al_cliente(self):
        res = handle_update(self.update(f"/start {self.cli.link_token}"),
                                     reply=lambda c, t: self.sent.append((c, t)))
        self.assertEqual(res, f"vinculado:{self.cli.pk}")
        self.cli.refresh_from_db()
        self.assertEqual(self.cli.telegram_chat_id, 555)
        self.assertIn("https://t.me/MiTallerBot?start=", self.cli.telegram_link)

    def test_start_con_token_falso_no_vincula(self):
        res = handle_update(self.update("/start inventado"), reply=lambda c, t: None)
        self.assertEqual(res, "sin_enlace")
        self.cli.refresh_from_db()
        self.assertIsNone(self.cli.telegram_chat_id)

    def test_comando_id_devuelve_el_chat(self):
        replies = []
        handle_update(self.update("/id", chat=42), reply=lambda c, t: replies.append((c, t)))
        self.assertEqual(replies, [(42, "Tu id de chat es: 42")])

    def test_aviso_a_cliente_vinculado_va_a_su_chat(self):
        self.cli.telegram_chat_id = 555
        self.cli.save()
        make_appointment(self.cli, date(2026, 10, 6), "ITV seat")
        run_daily(date(2027, 9, 29))
        self.assertIn(555, [c for c, _ in self.sent])

    def test_cliente_sin_vincular_se_avisa_al_mecanico(self):
        make_appointment(self.cli, date(2026, 10, 6), "ITV seat")
        run_daily(date(2027, 9, 29))
        owner_msgs = [t for c, t in self.sent if str(c) == "999"]
        self.assertTrue(any("Avísale tú: Ana" in t for t in owner_msgs))
        self.assertTrue(Reminder.objects.get().sent)

    def test_error_de_telegram_no_marca_como_enviado(self):
        self.cli.telegram_chat_id = 555
        self.cli.save()
        make_appointment(self.cli, date(2026, 10, 6), "ITV seat")
        with mock.patch("taller.infrastructure.telegram_api.send", side_effect=telegram_api.TelegramError("caído")):
            rep = run_daily(date(2027, 9, 29))
        self.assertEqual(len(rep["errors"]), 1)
        self.assertFalse(Reminder.objects.get().sent)


class FacturaYAdminTests(OutboxMixin, TestCase):
    def setUp(self):
        super().setUp()
        cli = Client.objects.create(name="Pepe")
        self.appt = make_appointment(cli, date(2026, 10, 6), "cambio aceite opel 5w30", plate="1234ABC")
        self.staff = get_user_model().objects.create_user("mecanico", password="x", is_staff=True,
                                                          is_superuser=True)

    def test_factura_con_iva_y_una_por_cita(self):
        inv = complete_and_invoice(self.appt)
        self.assertEqual(inv.total, inv.subtotal + inv.iva)
        self.assertEqual(complete_and_invoice(self.appt).number, inv.number)
        self.appt.refresh_from_db()
        self.assertEqual(self.appt.status, "hecha")

    def test_la_factura_exige_ser_personal_del_taller(self):
        complete_and_invoice(self.appt)
        url = f"/factura/{self.appt.pk}/"
        self.assertEqual(self.client.get(url).status_code, 302)  # sin login -> redirige
        self.client.force_login(self.staff)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Factura 2026-0001" if date.today().year == 2026 else "Factura")

    def test_el_admin_carga(self):
        self.client.force_login(self.staff)
        for path in ["/admin/", "/admin/taller/appointment/", "/admin/taller/client/",
                     "/admin/taller/reminder/",
                     f"/admin/taller/client/{self.appt.client_id}/change/"]:
            self.assertEqual(self.client.get(path).status_code, 200, path)

    def test_accion_hecha_y_facturar_desde_el_admin(self):
        self.client.force_login(self.staff)
        r = self.client.post("/admin/taller/appointment/", {
            "action": "hecha_y_facturar", "_selected_action": [self.appt.pk]})
        self.assertEqual(r.status_code, 302)
        self.appt.refresh_from_db()
        self.assertEqual(self.appt.status, "hecha")

    # ---- frontal ----
    def test_el_frontal_pide_login(self):
        for path in ["/", "/semana/", "/clientes/", "/facturas/"]:
            r = self.client.get(path)
            self.assertEqual(r.status_code, 302, path)
            self.assertIn("/entrar/", r["Location"])
        self.assertEqual(self.client.get("/entrar/").status_code, 200)

    def test_las_pantallas_cargan(self):
        self.client.force_login(self.staff)
        for path in ["/", "/semana/", "/semana/?d=2026-10-06", "/semana/?d=basura",
                     "/clientes/", "/clientes/?q=pe", "/facturas/"]:
            self.assertEqual(self.client.get(path).status_code, 200, path)

    def test_semana_muestra_la_cita(self):
        self.client.force_login(self.staff)
        r = self.client.get("/semana/?d=2026-10-06")
        self.assertContains(r, "1234ABC")
        self.assertContains(r, "cambio de aceite")

    def test_apuntar_cita_desde_el_frontal(self):
        self.client.force_login(self.staff)
        r = self.client.post("/citas/nueva/", {
            "date": "2026-11-10", "client_name": "  ana   lopez ", "phone": "600",
            "plate": "5555 xyz", "note": "itv seat ibiza"})
        self.assertEqual(r.status_code, 302)
        a = Appointment.objects.get(plate="5555 XYZ")
        self.assertEqual(a.client.name, "ana lopez")
        self.assertEqual(a.service, "ITV")
        self.assertEqual(Reminder.objects.filter(appointment=a).count(), 1)
        # el mismo cliente (sin distinguir mayúsculas) se reutiliza
        self.client.post("/citas/nueva/", {"date": "2026-11-11", "client_name": "ANA LOPEZ",
                                           "note": "cambio aceite"})
        self.assertEqual(Client.objects.filter(name__iexact="ana lopez").count(), 1)

    def test_cita_invalida_vuelve_con_errores(self):
        self.client.force_login(self.staff)
        r = self.client.post("/citas/nueva/", {"date": "", "client_name": "", "note": ""})
        self.assertEqual(r.status_code, 400)
        self.assertContains(r, "Escribe el nombre del cliente", status_code=400)
        self.assertContains(r, "Escribe qué hay que hacer", status_code=400)

    def test_acciones_exigen_post_y_login(self):
        url = f"/citas/{self.appt.pk}/hecha/"
        self.assertEqual(self.client.post(url).status_code, 302)
        self.appt.refresh_from_db()
        self.assertEqual(self.appt.status, "pendiente")
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(url).status_code, 405)

    def test_hecha_y_facturar_y_redireccion_segura(self):
        self.client.force_login(self.staff)
        r = self.client.post(f"/citas/{self.appt.pk}/hecha/", {"next": "https://evil.example/"})
        self.assertEqual(r["Location"], "/")
        self.appt.refresh_from_db()
        self.assertEqual(self.appt.status, "hecha")
        r = self.client.post(f"/citas/{self.appt.pk}/hecha/", {"next": "/semana/"})
        self.assertEqual(r["Location"], "/semana/")

    def test_pedir_ahora_desde_el_frontal(self):
        self.client.force_login(self.staff)
        with tempfile.TemporaryDirectory() as tmp, override_settings(TALLER_OUTBOX=tmp):
            self.client.post(f"/citas/{self.appt.pk}/pedir/")
            self.client.post(f"/citas/{self.appt.pk}/pedir/")  # no duplica
        self.appt.refresh_from_db()
        self.assertTrue(self.appt.ordered)
        self.assertEqual(self.appt.orders.count(), 1)

    def test_interpretacion_en_vivo(self):
        self.client.force_login(self.staff)
        data = self.client.get("/interpretar/", {"note": "cambio aceite motor opel aceite 5w30"}).json()
        self.assertEqual(data["service"], "cambio de aceite")
        self.assertEqual(data["repeat_months"], 12)

    def test_estado_del_pedido(self):
        self.assertEqual(self.appt.order_state, "pedir_hoy" if self.appt.order_date <= date.today() else "por_pedir")
        self.assertEqual(self.appt.order_date, date(2026, 10, 5))
        complete_and_invoice(self.appt)
        self.appt.refresh_from_db()
        self.assertEqual(self.appt.order_state, "hecha")

    # ---- mejoras de comodidad ----
    def _future(self, note="cambio aceite motor opel aceite 5w30", plate="9999ZZZ", days=1, name="Luis"):
        from django.utils import timezone
        from datetime import timedelta

        cli, _ = Client.objects.get_or_create(name=name, defaults={"phone": "600 11 22 33"})
        return make_appointment(cli, timezone.localdate() + timedelta(days=days), note, plate=plate)

    def test_pedido_revisable_edita_y_envia(self):
        a = self._future()
        self.client.force_login(self.staff)
        self.assertContains(self.client.get("/pedido/"), "9999ZZZ")
        data = {"ids": [a.pk], "send": [a.pk], "do": "send",
                f"name_{a.pk}": ["aceite motor", "filtro de aceite", ""],
                f"spec_{a.pk}": ["5W30", "", ""], f"qty_{a.pk}": ["5,5", "0", "1"],
                f"unit_{a.pk}": ["L", "ud", "ud"]}
        with tempfile.TemporaryDirectory() as tmp, override_settings(TALLER_OUTBOX=tmp):
            self.client.post("/pedido/", data)
        a.refresh_from_db()
        self.assertTrue(a.ordered)
        self.assertEqual(a.parts[0]["qty"], 5.5)
        self.assertEqual(a.parts[1]["qty"], 1)  # cantidad 0 no vale: queda 1
        self.assertEqual(len(a.parts), 2)       # la línea vacía se descarta

    def test_un_pedido_fallido_se_ve_y_se_puede_reintentar(self):
        a = self._future()

        class Broken:
            name = "roto"

            def send_order(self, order):
                raise RuntimeError("proveedor caído")

        self.client.force_login(self.staff)
        with mock.patch("taller.container.parts_supplier", return_value=Broken()):
            self.client.post(f"/citas/{a.pk}/pedir/")
        a.refresh_from_db()
        self.assertFalse(a.ordered)
        self.assertEqual(a.order_error, "proveedor caído")
        self.assertEqual(a.order_state, "fallo")
        self.assertContains(self.client.get("/"), "no se ha podido enviar")
        with tempfile.TemporaryDirectory() as tmp, override_settings(TALLER_OUTBOX=tmp):
            self.client.post(f"/citas/{a.pk}/pedir/")
        a.refresh_from_db()
        self.assertTrue(a.ordered)
        self.assertEqual(a.order_error, "")

    def test_lista_de_compra_suma_recambios(self):
        a = self._future(plate="1111AAA")
        self._future(plate="2222BBB", name="Marta")
        self.client.force_login(self.staff)
        r = self.client.get(f"/compra/?d={a.date.isoformat()}")
        self.assertContains(r, "<strong>8</strong> L")  # 4 L + 4 L de 5W30
        self.assertContains(r, "1111AAA")
        self.assertContains(r, "2222BBB")

    def test_editar_cita_reprograma_el_aviso(self):
        a = self._future()
        self.assertEqual(Reminder.objects.filter(appointment=a).count(), 1)
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(f"/citas/{a.pk}/editar/").status_code, 200)
        new_day = a.date.replace(year=a.date.year + 0) if False else a.date
        from datetime import timedelta
        new_day = a.date + timedelta(days=10)
        r = self.client.post(f"/citas/{a.pk}/editar/", {
            "date": new_day.isoformat(), "client_name": "Luis", "phone": "600112233",
            "plate": "9999zzz", "note": a.note, "service": "cambio de aceite", "vehicle": "Opel",
            "repeat_months": "6", f"name_{a.pk}": ["aceite motor"], f"spec_{a.pk}": ["5W30"],
            f"qty_{a.pk}": ["4"], f"unit_{a.pk}": ["L"]})
        self.assertEqual(r.status_code, 302)
        a.refresh_from_db()
        self.assertEqual(a.date, new_day)
        self.assertEqual(len(a.parts), 1)
        rem = Reminder.objects.get(appointment=a)
        self.assertEqual(rem.send_on, business_calendar.add_months(new_day, 6) - __import__("datetime").timedelta(days=7))

    def test_historial_y_buscador_por_matricula(self):
        self.client.force_login(self.staff)
        data = self.client.get("/historial/", {"plate": "1234-abc"}).json()
        self.assertTrue(data["found"])
        self.assertEqual(data["client"], "Pepe")
        self.assertFalse(self.client.get("/historial/", {"plate": "0000XXX"}).json()["found"])
        self.assertContains(self.client.get("/buscar/", {"q": "1234 abc"}), "cambio de aceite")
        self.assertContains(self.client.get("/buscar/", {"q": "zzzz"}), "No he encontrado")

    def test_enlaces_de_llamada_y_whatsapp(self):
        c = Client(name="X", phone="600 11 22 33")
        self.assertEqual(c.whatsapp_url, "https://wa.me/34600112233")
        self.assertEqual(c.tel_url, "tel:+34600112233")
        self.assertEqual(Client(name="Y", phone="+44 7700 900123").phone_digits, "447700900123")
        self.assertEqual(Client(name="Z").whatsapp_url, "")

    def test_copia_de_seguridad(self):
        self.client.force_login(self.staff)
        r = self.client.get("/copia/")
        self.assertIn("attachment", r["Content-Disposition"])
        self.assertIn("1234ABC", r.content.decode())

    def test_tarifas_de_mano_de_obra(self):
        from decimal import Decimal

        self.client.force_login(self.staff)
        page = self.client.get("/tarifas/")
        self.assertContains(page, "cambio de aceite")
        self.assertNotContains(page, "filtro de aceite")  # los recambios no tienen precio
        self.assertEqual(labor_price("cambio de aceite"), Decimal("45.00"))
        self.assertEqual(labor_price("Cambio de aceite y filtro"), Decimal("45.00"))
        bad = self.client.post("/tarifas/", {"p_name": ["ITV"], "p_price": ["abc"]})
        self.assertContains(bad, "Revisa el precio")
        self.client.post("/tarifas/", {"p_name": ["ITV", "cambio de aceite"], "p_price": ["32,5", ""],
                                       "new_name": "alineación", "new_price": "50"})
        self.assertEqual(labor_price("ITV"), Decimal("32.50"))
        self.assertIsNone(labor_price("cambio de aceite"))  # precio vacío = sin tarifa
        self.assertEqual(labor_price("alineación"), Decimal("50.00"))

    def test_facturar_con_precios_de_recambios_escritos_a_mano(self):
        self.client.force_login(self.staff)
        url = f"/citas/{self.appt.pk}/facturar/"
        page = self.client.get(url)
        self.assertContains(page, "45,00")  # mano de obra de la tarifa, editable
        self.assertContains(page, 'data-iva="0.21')  # con punto: el JS no entiende la coma
        self.assertContains(page, "IVA (21 %)")
        bad = self.client.post(url, {"price_0": "x", "price_1": "", "labor": "45"})
        self.assertEqual(bad.status_code, 400)
        r = self.client.post(url, {"price_0": "10,50", "price_1": "8", "labor": "40",
                                   "extra_concept": "desplazamiento", "extra_price": "5"})
        self.assertEqual(r.status_code, 302)
        inv = self.appt.invoice
        self.assertEqual(str(inv.subtotal), "95.00")  # 4 x 10,50 + 8 + 40 + 5
        self.assertEqual(str(inv.total), "114.95")
        self.assertEqual(self.client.get(url).status_code, 302)  # ya facturada: va a la factura

    def test_factura_sin_precios_no_inventa_precios_de_recambios(self):
        inv = complete_and_invoice(self.appt)
        parts = [l for l in inv.lines if not l["concept"].startswith("Mano de obra")]
        self.assertTrue(all(l["unit_price"] == "0.00" for l in parts))
        self.assertEqual(inv.subtotal, labor_price(self.appt.service))

    def test_filtros_nombrados_y_sin_viscosidad_inventada(self):
        r = parse_note("cambio aceite y filtros de aire aceite y gasolina", use_llm=False)
        names = [p["name"] for p in r["parts"]]
        self.assertEqual(r["service"], "cambio de aceite y filtros")
        for expected in ("aceite motor", "filtro de aceite", "filtro de aire", "filtro de combustible"):
            self.assertIn(expected, names)
        self.assertEqual(names.count("filtro de aceite"), 1)
        self.assertEqual([p for p in r["parts"] if p["name"] == "aceite motor"][0]["spec"], "")
        solo = parse_note("cambio filtro de aire y habitáculo seat leon", use_llm=False)
        self.assertEqual([p["name"] for p in solo["parts"]], ["filtro de aire", "filtro de habitáculo"])

    def test_la_vista_previa_usa_gemma_si_esta_activo(self):
        self.client.force_login(self.staff)
        fake = {"service": "cambio de aceite", "vehicle": "Opel", "repeat_months": 12,
                "parts": [{"name": "aceite motor", "spec": "5W30", "qty": 4, "unit": "L"}]}
        with mock.patch.dict(os.environ, {"TALLER_NO_LLM": "0"}), \
                mock.patch("taller.infrastructure.ollama_note_parser._ask_ollama", return_value=fake):
            data = self.client.get("/interpretar/", {"note": "lo que sea"}).json()
        self.assertTrue(data["engine"].startswith("ollama:"))
        self.assertEqual(data["parts"][0]["spec"], "5W30")
        # sin Ollama (o desactivado) cae a las reglas y lo dice
        data = self.client.get("/interpretar/", {"note": "cambio aceite"}).json()
        self.assertEqual(data["engine"], "reglas")

    def test_explica_por_que_no_se_uso_gemma(self):
        import urllib.error

        with mock.patch.dict(os.environ, {"TALLER_NO_LLM": "0"}):
            with mock.patch("taller.infrastructure.ollama_note_parser._ask_ollama", side_effect=urllib.error.URLError(ConnectionRefusedError())):
                self.assertIn("Ollama", parse_note("cambio aceite")["llm_error"])
            with mock.patch("taller.infrastructure.ollama_note_parser._ask_ollama", side_effect=TimeoutError()):
                self.assertIn("tardó", parse_note("cambio aceite")["llm_error"])
            with mock.patch("taller.infrastructure.ollama_note_parser._ask_ollama", side_effect=ValueError("x")):
                self.assertIn("válida", parse_note("cambio aceite")["llm_error"])
        self.assertIn("desactivada", parse_note("cambio aceite")["llm_error"])
        self.assertEqual(parse_note("cambio aceite", use_llm=False)["llm_error"], "")

    def test_coche_del_formulario_manda_sobre_la_nota(self):
        self.client.force_login(self.staff)
        self.client.post("/citas/nueva/", {"date": "2030-01-10", "client_name": "Rosa", "vehicle": "  seat   leon ",
                                           "plate": "1111AAA", "note": "cambio aceite opel 5w30"})
        a = Appointment.objects.get(plate="1111AAA")
        self.assertEqual(a.vehicle, "seat leon")  # lo escrito en el formulario, no la marca de la nota
        data = self.client.get("/interpretar/", {"note": "cambio aceite", "vehicle": "Ford Focus"}).json()
        self.assertEqual(data["vehicle"], "Ford Focus")

    def test_limpieza_de_lo_que_devuelve_gemma(self):
        from taller.domain.note_cleaning import clean_parts as _clean_parts, clean_vehicle as _clean_vehicle

        self.assertEqual(_clean_vehicle("Vehículo Desconocido"), "")
        parts = _clean_parts([
            {"name": "Filtro de Aire", "spec": "Filtro de aire de motor", "qty": 1, "unit": "ud"},
            {"name": "Aceite 10W30", "spec": "Aceite para motor de gasolina", "qty": "4", "unit": "L"},
            {"name": "filtro de aire", "spec": "", "qty": 1, "unit": "ud"},  # repetido
            {"name": "aceite motor", "spec": "10w30", "qty": 4, "unit": "L"},
        ])
        self.assertEqual([p["name"] for p in parts], ["filtro de aire", "aceite 10w30", "aceite motor"])
        self.assertEqual(parts[0]["spec"], "")
        self.assertEqual(parts[2]["spec"], "10W30")

    def test_el_prompt_lleva_el_coche_y_temperatura_cero(self):
        captured = {}

        class Resp:
            def read(self):
                return json.dumps({"response": json.dumps({"service": "mantenimiento", "vehicle": "Vehículo Desconocido",
                                                           "repeat_months": 0, "parts": []})}).encode()

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        def fake_urlopen(req, timeout=None):
            captured["body"] = json.loads(req.data)
            return Resp()

        ollama_parser._CACHE.clear()
        with mock.patch.dict(os.environ, {"TALLER_NO_LLM": "0"}), \
                mock.patch("taller.infrastructure.ollama_note_parser.urllib.request.urlopen", fake_urlopen):
            r = parse_note("cambio aceite y filtros", vehicle="Opel Corsa")
        self.assertIn("Vehículo: Opel Corsa", captured["body"]["prompt"])
        self.assertIn("Nota: cambio aceite y filtros", captured["body"]["prompt"])
        self.assertEqual(captured["body"]["options"]["temperature"], 0)
        self.assertEqual(captured["body"]["keep_alive"], "30m")
        self.assertEqual(r["vehicle"], "Opel Corsa")
        self.assertEqual(r["service"], "cambio de aceite")  # "mantenimiento" es demasiado genérico
        self.assertTrue(r["engine"].startswith("ollama:"))

    def test_gemma_no_se_llama_dos_veces_con_la_misma_nota(self):
        calls = []

        def fake(note, vehicle="", timeout=None):
            calls.append(note)
            return {"service": "cambio de aceite", "vehicle": "", "repeat_months": 12, "parts": []}

        ollama_parser._CACHE.clear()
        with mock.patch.dict(os.environ, {"TALLER_NO_LLM": "0"}), \
                mock.patch("taller.infrastructure.ollama_note_parser._ask_ollama_uncached", fake):
            parse_note("cambio aceite raro", vehicle="Opel")
            parse_note("cambio aceite raro", vehicle="Opel")  # p. ej. al guardar tras la vista previa
            parse_note("cambio aceite raro", vehicle="Seat")
        self.assertEqual(len(calls), 2)
