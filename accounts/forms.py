from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from .models import Usuario

INPUT_CLASES = (
    "block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm shadow-sm "
    "focus:border-brand-500 focus:ring-2 focus:ring-brand-100 focus:outline-none"
)


def _aplicar_estilos(form):
    for field in form.fields.values():
        clases_previas = field.widget.attrs.get("class", "")
        field.widget.attrs["class"] = f"{clases_previas} {INPUT_CLASES}".strip()


class LoginForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _aplicar_estilos(self)


class UsuarioCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = Usuario
        fields = ("username", "first_name", "last_name", "email", "rol")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _aplicar_estilos(self)
