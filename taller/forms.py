from django import forms

from taller.domain.parts import parse_qty


class AppointmentForm(forms.Form):
    date = forms.DateField(
        label="Día", widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
        error_messages={"required": "Elige el día de la cita.", "invalid": "Fecha no válida."},
    )
    client_name = forms.CharField(
        label="Cliente", max_length=120,
        error_messages={"required": "Escribe el nombre del cliente."},
    )
    phone = forms.CharField(label="Teléfono", max_length=30, required=False)
    plate = forms.CharField(label="Matrícula", max_length=15, required=False)
    vehicle = forms.CharField(label="Coche (marca y modelo)", max_length=60, required=False)
    note = forms.CharField(
        label="Qué hay que hacer", widget=forms.Textarea(attrs={"rows": 2}),
        error_messages={"required": "Escribe qué hay que hacer, como en papel."},
    )

    def clean_plate(self):
        return self.cleaned_data["plate"].upper().strip()

    def clean_vehicle(self):
        return " ".join(self.cleaned_data["vehicle"].split())

    def clean_client_name(self):
        return " ".join(self.cleaned_data["client_name"].split())


class EditAppointmentForm(AppointmentForm):
    service = forms.CharField(label="Trabajo", max_length=120, required=False)
    repeat_months = forms.IntegerField(
        label="Avisar al cliente cada (meses)", min_value=0, max_value=120, required=False,
        help_text="0 = no se repite",
    )
    reinterpret = forms.BooleanField(
        label="Volver a interpretar la nota (cambia trabajo, vehículo, recambios y aviso)",
        required=False,
    )


def parts_from_post(post, pk):
    """Lee las líneas de recambios de un formulario (campos name_<pk>, spec_<pk>, ...).

    Las líneas sin nombre se descartan; así se borra una línea vaciándola.
    """
    names, specs = post.getlist(f"name_{pk}"), post.getlist(f"spec_{pk}")
    qtys, units = post.getlist(f"qty_{pk}"), post.getlist(f"unit_{pk}")
    parts = []
    for i, name in enumerate(names):
        name = " ".join(name.split())
        if not name:
            continue
        qty = parse_qty(qtys[i]) if i < len(qtys) else 1
        parts.append({
            "name": name,
            "spec": " ".join(specs[i].split()) if i < len(specs) else "",
            "qty": qty or 1,
            "unit": (units[i].strip() if i < len(units) else "") or "ud",
        })
    return parts
