from django.conf import settings
from django.db import models


def ruta_plantilla(instance, filename):
    return f"lotes/{instance.pk or 'tmp'}/plantilla_{filename}"


def ruta_excel(instance, filename):
    return f"lotes/{instance.pk or 'tmp'}/excel_{filename}"


class Lote(models.Model):
    class Estado(models.TextChoices):
        BORRADOR = "borrador", "Borrador"
        PROCESANDO = "procesando", "Procesando"
        GENERADO = "generado", "Generado"
        ERROR = "error", "Error"

    propietario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="lotes")
    curso = models.CharField(max_length=255)
    excel = models.FileField(upload_to=ruta_excel)
    plantilla = models.ImageField(upload_to=ruta_plantilla)

    texto_x = models.PositiveIntegerField(help_text="Posicion X en pixeles de la plantilla")
    texto_y = models.PositiveIntegerField(help_text="Posicion Y en pixeles de la plantilla")
    margen_izquierdo = models.PositiveIntegerField(default=40)
    margen_derecho = models.PositiveIntegerField(default=40)
    tamano_fuente = models.PositiveIntegerField(default=40)
    tamano_fuente_min = models.PositiveIntegerField(default=18)
    color_texto = models.CharField(max_length=7, default="#1a1a1a")
    fuente = models.CharField(max_length=50, default="Helvetica-Bold")

    estado = models.CharField(max_length=10, choices=Estado.choices, default=Estado.BORRADOR)
    total_certificados = models.PositiveIntegerField(default=0)
    procesados = models.PositiveIntegerField(default=0)
    zip_resultado = models.FileField(upload_to="lotes/resultados/", blank=True, null=True)
    mensaje_error = models.TextField(blank=True)
    archivos_expirados = models.BooleanField(
        default=False, help_text="Los PDF/ZIP generados se borraron por antiguedad; el registro del lote se conserva"
    )

    generado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="lotes_generados"
    )
    generado_en = models.DateTimeField(null=True, blank=True)

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-creado_en"]

    def __str__(self):
        return f"{self.curso} ({self.propietario})"
