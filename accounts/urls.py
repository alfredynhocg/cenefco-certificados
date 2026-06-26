from django.urls import path

from . import views

urlpatterns = [
    path("", views.lista_usuarios, name="lista_usuarios"),
    path("nuevo/", views.crear_usuario, name="crear_usuario"),
]
