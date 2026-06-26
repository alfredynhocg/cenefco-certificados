"""Borra los PDF/ZIP generados de lotes antiguos para liberar espacio en disco.

El registro del lote (curso, quien lo genero, lista de nombres en el Excel)
NUNCA se borra, solo los archivos pesados de resultado. Pensado para correr
periodicamente (ver tarea programada).
"""

import shutil
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from certificados.models import Lote

DIAS_RETENCION_DEFECTO = 30


class Command(BaseCommand):
    help = "Borra los certificados (PDF/ZIP) de lotes generados hace mas de N dias, conservando el registro del lote."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dias",
            type=int,
            default=DIAS_RETENCION_DEFECTO,
            help=f"Antiguedad en dias a partir de la cual se borran los archivos (default: {DIAS_RETENCION_DEFECTO}).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Solo muestra que lotes se limpiarian, sin borrar nada.",
        )

    def handle(self, *args, **options):
        dias = options["dias"]
        dry_run = options["dry_run"]
        limite = timezone.now() - timedelta(days=dias)

        candidatos = Lote.objects.filter(
            estado=Lote.Estado.GENERADO,
            archivos_expirados=False,
            generado_en__lt=limite,
        )

        total_candidatos = candidatos.count()
        if total_candidatos == 0:
            self.stdout.write("No hay lotes con certificados vencidos por limpiar.")
            return

        for lote in candidatos:
            carpeta_salida = Path(settings.MEDIA_ROOT) / "lotes" / str(lote.pk) / "salida"
            self.stdout.write(
                f"Lote #{lote.pk} '{lote.curso}' generado el {lote.generado_en:%d/%m/%Y} -> "
                f"{'se borraria' if dry_run else 'borrando'} {carpeta_salida}"
            )
            if dry_run:
                continue

            if carpeta_salida.exists():
                shutil.rmtree(carpeta_salida, ignore_errors=True)
            if lote.zip_resultado:
                lote.zip_resultado.delete(save=False)
            lote.archivos_expirados = True
            lote.save(update_fields=["archivos_expirados", "zip_resultado"])

        if not dry_run:
            self.stdout.write(self.style.SUCCESS(f"Limpieza completada: {total_candidatos} lote(s) procesados."))
