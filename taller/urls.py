from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("semana/", views.week, name="week"),
    path("clientes/", views.clients, name="clients"),
    path("facturas/", views.invoices, name="invoices"),
    path("citas/nueva/", views.appointment_create, name="appointment_create"),
    path("pedido/", views.order_review, name="order_review"),
    path("compra/", views.shopping, name="shopping"),
    path("buscar/", views.search, name="search"),
    path("historial/", views.history, name="history"),
    path("tarifas/", views.prices, name="prices"),
    path("copia/", views.backup, name="backup"),
    path("citas/<int:pk>/editar/", views.appointment_edit, name="appointment_edit"),
    path("citas/<int:pk>/pedir/", views.appointment_order, name="appointment_order"),
    path("citas/<int:pk>/facturar/", views.appointment_invoice, name="appointment_invoice"),
    path("citas/<int:pk>/hecha/", views.appointment_done, name="appointment_done"),
    path("hoy/ejecutar/", views.run_daily_view, name="run_daily"),
    path("interpretar/", views.interpret, name="interpret"),
    path("factura/<int:appointment_id>/", views.invoice, name="invoice"),
    path("entrar/", auth_views.LoginView.as_view(template_name="taller/login.html",
                                                  redirect_authenticated_user=True), name="login"),
    path("salir/", auth_views.LogoutView.as_view(), name="logout"),
]
