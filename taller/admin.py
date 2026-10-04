from django.contrib import admin, messages
from django.urls import reverse
from django.utils.html import format_html

from . import services
from .models import Appointment, Client, Invoice, LaborRate, Order, Reminder

admin.site.site_header = "Agenda del taller"
admin.site.site_title = "Agenda del taller"
admin.site.index_title = "Citas, pedidos y avisos"


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ("name", "phone", "telegram_ok")
    search_fields = ("name", "phone")
    readonly_fields = ("telegram_enlace",)
    fields = ("name", "phone", "telegram_enlace")

    @admin.display(boolean=True, description="Telegram vinculado")
    def telegram_ok(self, obj):
        return obj.telegram_linked

    @admin.display(description="Enlace para vincular Telegram")
    def telegram_enlace(self, obj):
        if not obj.pk:
            return "Guarda el cliente para ver su enlace."
        if not obj.telegram_link:
            return "Configura TELEGRAM_BOT_USERNAME para generar el enlace."
        status = "ya vinculado" if obj.telegram_linked else "pendiente de vincular"
        return format_html(
            'Pásale este enlace al cliente ({}):<br><a href="{}">{}</a>',
            status, obj.telegram_link, obj.telegram_link,
        )


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    date_hierarchy = "date"
    list_display = ("date", "service", "vehicle", "client", "plate", "recambios", "ordered",
                    "status", "factura")
    list_filter = ("status", "ordered", "date")
    search_fields = ("note", "plate", "client__name", "vehicle")
    autocomplete_fields = ("client",)
    actions = ["pedir_recambios", "hecha_y_facturar"]
    fieldsets = (
        (None, {"fields": ("client", "date", "plate", "note")}),
        ("Interpretado automáticamente (puedes corregirlo)", {
            "fields": ("service", "vehicle", "parts", "repeat_months"),
            "description": "Se rellena solo al guardar a partir de la nota. Si lo cambias, se respeta.",
        }),
        ("Estado", {"fields": ("status", "ordered")}),
    )

    @admin.display(description="Recambios")
    def recambios(self, obj):
        return ", ".join(f"{p['qty']} {p['name']} {p.get('spec', '')}".strip() for p in obj.parts) or "—"

    @admin.display(description="Factura")
    def factura(self, obj):
        if hasattr(obj, "invoice"):
            return format_html('<a href="{}" target="_blank">{}</a>',
                               reverse("invoice", args=[obj.pk]), obj.invoice.number)
        return "—"

    @admin.action(description="Pedir ahora los recambios de las citas seleccionadas")
    def pedir_recambios(self, request, queryset):
        done = 0
        for appt in queryset.filter(ordered=False):
            if not appt.parts:
                continue
            try:
                services.order_parts(appt)
                done += 1
            except Exception as exc:
                self.message_user(request, f"Cita {appt.pk}: {exc}", messages.ERROR)
        self.message_user(request, f"Pedidos enviados: {done}")

    @admin.action(description="Marcar como hechas y generar factura")
    def hecha_y_facturar(self, request, queryset):
        for appt in queryset:
            services.complete_and_invoice(appt)
        self.message_user(request, f"Facturas generadas: {queryset.count()}")


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("created_at", "appointment", "supplier", "detail")
    readonly_fields = ("created_at",)


@admin.register(Reminder)
class ReminderAdmin(admin.ModelAdmin):
    list_display = ("send_on", "client", "sent", "detail")
    list_filter = ("sent",)


@admin.register(LaborRate)
class LaborRateAdmin(admin.ModelAdmin):
    list_display = ("service", "price")
    search_fields = ("service",)


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ("number", "created_at", "appointment", "total", "ver")
    readonly_fields = ("number", "created_at", "appointment", "lines", "subtotal", "iva", "total")

    @admin.display(description="Imprimir")
    def ver(self, obj):
        return format_html('<a href="{}" target="_blank">Ver factura</a>',
                           reverse("invoice", args=[obj.appointment_id]))
