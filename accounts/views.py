from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import redirect, render

from .forms import UsuarioCreationForm
from .models import Usuario


def es_admin(user):
    return user.is_authenticated and user.es_admin


@login_required
@user_passes_test(es_admin)
def lista_usuarios(request):
    usuarios = Usuario.objects.all().order_by("username")
    return render(request, "accounts/lista_usuarios.html", {"usuarios": usuarios})


@login_required
@user_passes_test(es_admin)
def crear_usuario(request):
    if request.method == "POST":
        form = UsuarioCreationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Usuario creado correctamente.")
            return redirect("lista_usuarios")
    else:
        form = UsuarioCreationForm()
    return render(request, "accounts/crear_usuario.html", {"form": form})
