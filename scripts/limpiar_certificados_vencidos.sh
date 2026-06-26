#!/bin/bash
# Borra los PDF/ZIP de certificados generados hace mas de 1 mes (el registro
# del lote y la lista de estudiantes se conservan siempre). Pensado para
# correr a diario via cron en el VPS Ubuntu.
#
# Instalacion en el VPS:
#   1. Ajusta PROYECTO_DIR abajo a la ruta real del proyecto en el VPS.
#   2. chmod +x scripts/limpiar_certificados_vencidos.sh
#   3. crontab -e   y agrega esta linea (corre todos los dias a las 3:00 am):
#      0 3 * * * /ruta/al/proyecto/certicados-web/scripts/limpiar_certificados_vencidos.sh >> /var/log/cenefco_limpieza.log 2>&1

set -euo pipefail

PROYECTO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROYECTO_DIR"

source venv/bin/activate
python manage.py limpiar_certificados_vencidos --dias 30
