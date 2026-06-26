from django import forms

from .models import Lote

INPUT_CLASES = (
    "block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm shadow-sm "
    "focus:border-brand-500 focus:ring-2 focus:ring-brand-100 focus:outline-none"
)

FUENTES_DISPONIBLES = [
    ("Helvetica", "Helvetica"),
    ("Helvetica-Bold", "Helvetica Negrita"),
    ("Helvetica-Oblique", "Helvetica Italica"),
    ("Times-Roman", "Times Roman"),
    ("Times-Bold", "Times Negrita"),
    ("Times-Italic", "Times Italica"),
    ("Courier", "Courier"),
    ("Courier-Bold", "Courier Negrita"),
]


class LoteForm(forms.ModelForm):
    fuente = forms.ChoiceField(choices=FUENTES_DISPONIBLES, label="Fuente")

    class Meta:
        model = Lote
        fields = [
            "curso",
            "excel",
            "plantilla",
            "texto_x",
            "texto_y",
            "margen_izquierdo",
            "margen_derecho",
            "tamano_fuente",
            "tamano_fuente_min",
            "color_texto",
            "fuente",
        ]
        widgets = {
            "texto_x": forms.HiddenInput(),
            "texto_y": forms.HiddenInput(),
            "color_texto": forms.TextInput(attrs={"type": "color", "class": "h-10 w-16 rounded-md border border-slate-300 cursor-pointer p-1"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields["excel"].required = False
            self.fields["plantilla"].required = False
        for nombre, field in self.fields.items():
            if nombre in ("texto_x", "texto_y", "color_texto"):
                continue
            clases_previas = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = f"{clases_previas} {INPUT_CLASES}".strip()
