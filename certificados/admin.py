from django.contrib import admin

from .models import Lote


@admin.register(Lote)
class LoteAdmin(admin.ModelAdmin):
    list_display = ("curso", "propietario", "estado", "total_certificados", "creado_en")
    list_filter = ("estado", "propietario")
    search_fields = ("curso", "propietario__username")
