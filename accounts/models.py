from django.contrib.auth.models import AbstractUser
from django.db import models


class Usuario(AbstractUser):
    class Rol(models.TextChoices):
        ADMIN = "admin", "Administrador"
        USUARIO = "usuario", "Usuario"

    rol = models.CharField(max_length=10, choices=Rol.choices, default=Rol.USUARIO)

    @property
    def es_admin(self) -> bool:
        return self.rol == self.Rol.ADMIN or self.is_superuser
