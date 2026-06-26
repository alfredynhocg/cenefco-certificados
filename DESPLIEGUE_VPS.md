# Despliegue en VPS (Ubuntu 24.04, sin Docker)

Guia paso a paso -- ya ejecutada una vez en el VPS `vmi3392869` -- para
instalar el proyecto de certificados sin contenedores, usando los
servicios nativos de Ubuntu: PostgreSQL, Nginx y systemd (gunicorn como
servidor WSGI).

El VPS ya corre Moodle y Nginx Proxy Manager (NPM) en Docker, ocupando los
puertos 80, 81, 443 y 8080. Este proyecto corre **aparte, sin Docker**, en
el puerto 8001, sin tocar nada de lo existente.

> **Importante sobre la ruta de instalacion:** el proyecto NO debe vivir
> dentro de `/root/`. Nginx corre como usuario `www-data`, y `/root` tiene
> permisos `drwx------` (solo el propio root puede atravesarlo), asi que
> `www-data` no puede servir nada de `/media/` o `/static/` si el proyecto
> esta ahi -- da `403 Forbidden`. Por eso el proyecto final vive en
> `/srv/cenefco-certificados`, que es la ruta estandar de Linux para datos
> servidos por la maquina.

## Estructura final en el VPS

```
/srv/cenefco-certificados/
├── venv/                <- entorno virtual Python (creado en el VPS, no se copia)
├── manage.py
├── config/
├── accounts/
├── certificados/
├── templates/
├── scripts/
├── media/               <- excels, plantillas, PDFs generados (no versionado)
├── staticfiles/         <- generado por collectstatic (no versionado)
└── .env                 <- configuracion real (no versionado)
```

Servicios:
- `postgresql` (apt) -- base de datos `certificados_cenefco`
- `certificados-gunicorn.service` (systemd) -- corre la app Django en `127.0.0.1:8002`
- `nginx` (apt, nativo, **distinto del nginx de NPM en Docker**) -- proxy publico en el puerto 8001
- cron diario -- limpieza de certificados vencidos (>30 dias)

---

## Paso 0 -- Resumen del entorno

| Item | Valor |
|---|---|
| Sistema | Ubuntu 24.04 (noble) |
| Python | 3.12.3 nativo (`/usr/bin/python3.12`) |
| IP publica del VPS | `161.97.181.140` |
| Puerto de acceso (sin dominio aun) | `8001` |
| Repositorio | `git@github.com:alfredynhocg/cenefco-certificados.git` |
| Docker existente | Moodle (`:8080`) + NPM (`:80`/`:81`/`:443`) -- no se toca |

---

## Paso 1 -- Dependencias del sistema

```bash
apt update && apt install -y python3.12-venv python3-pip postgresql postgresql-contrib nginx git
```

**Gotcha encontrado:** Nginx nativo no arranca de entrada porque su sitio
`default` intenta usar el puerto 80, que ya esta ocupado por NPM (Docker).
Hay que desactivarlo (este proyecto nunca necesita el puerto 80):

```bash
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl restart nginx
systemctl status nginx --no-pager | head -5
```

---

## Paso 2 -- Base de datos PostgreSQL

```bash
sudo -u postgres psql -c "CREATE DATABASE certificados_cenefco;"
sudo -u postgres psql -c "ALTER USER postgres PASSWORD '5dv4rrgq8au7';"
psql -h 127.0.0.1 -U postgres -d certificados_cenefco -c "SELECT 1;"
```

---

## Paso 3 -- Clonar el proyecto

El codigo se versiona en GitHub. En el VPS:

```bash
mkdir -p /srv
cd /srv
git clone git@github.com:alfredynhocg/cenefco-certificados.git
mv cenefco-certificados/* cenefco-certificados/.git cenefco-certificados/.gitignore /srv/cenefco-certificados 2>/dev/null || true
```

> Si clonas directo en `/srv/cenefco-certificados` desde el inicio
> (`git clone <repo> /srv/cenefco-certificados`) te ahorras el paso de
> mover -- es lo recomendado para una instalacion nueva.

El `.gitignore` del repo ya excluye `venv/`, `media/`, `.env`,
`staticfiles/` y `db.sqlite3` -- esos se generan/configuran en el propio
VPS, nunca se traen del repositorio.

---

## Paso 4 -- Entorno virtual y dependencias Python

```bash
cd /srv/cenefco-certificados
python3.12 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install django gunicorn psycopg2-binary python-decouple pillow reportlab openpyxl pymupdf
```

> Si en algun momento se mueve la carpeta del proyecto a otra ruta, el
> `venv` debe **recrearse**, no copiarse -- los scripts dentro de
> `venv/bin/` (como `gunicorn`) tienen la ruta absoluta vieja grabada en
> el shebang (`#!/ruta/vieja/venv/bin/python3.12`) y fallan con
> `status=203/EXEC` en systemd si no se regeneran.

---

## Paso 5 -- Archivo `.env` de produccion

```bash
nano /srv/cenefco-certificados/.env
```

Contenido (generar una `SECRET_KEY` propia, ver mas abajo):

```env
DEBUG=False
SECRET_KEY=cj0pf5#$rj*u=yaplejfnrbi7233-i18fk%b&lx-a-48kbmmn6
ALLOWED_HOSTS=161.97.181.140,127.0.0.1,localhost

DB_ENGINE=django.db.backends.postgresql
DB_NAME=certificados_cenefco
DB_USER=postgres
DB_PASSWORD=5dv4rrgq8au7
DB_HOST=127.0.0.1
DB_PORT=5432

CSRF_TRUSTED_ORIGINS=http://161.97.181.140:8001
```

> **Recomendado usar `nano` en vez de `cat << 'EOF' > .env`** al pegar por
> SSH: los heredocs con caracteres especiales (`$`, `&`, `#`) y pegado
> multilinea por terminal suelen romperse o concatenar lineas mal. `nano`
> es mas confiable para esto.

Generar una `SECRET_KEY` nueva (no reusar la de desarrollo local):

```bash
source venv/bin/activate
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

`CSRF_TRUSTED_ORIGINS` es **obligatorio** al acceder por IP:puerto sin
HTTPS -- sin esto, Django 4+ devuelve `403 Forbidden / La verificacion
CSRF ha fallado` en cualquier formulario (login incluido).

---

## Paso 6 -- Migraciones, superusuario, estaticos

```bash
cd /srv/cenefco-certificados
source venv/bin/activate
python manage.py migrate
python manage.py createsuperuser
python manage.py collectstatic --noinput
```

(`STATIC_ROOT = BASE_DIR / "staticfiles"` ya esta en `config/settings.py`
en el repo).

---

## Paso 7 -- Gunicorn + systemd

```bash
nano /etc/systemd/system/certificados-gunicorn.service
```

```ini
[Unit]
Description=Gunicorn - Certificados CENEFCO
After=network.target postgresql.service

[Service]
User=root
Group=root
WorkingDirectory=/srv/cenefco-certificados
EnvironmentFile=/srv/cenefco-certificados/.env
ExecStart=/srv/cenefco-certificados/venv/bin/gunicorn \
    --workers 3 \
    --bind 127.0.0.1:8002 \
    --timeout 120 \
    config.wsgi:application
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

> Gunicorn escucha en el puerto **8002** (interno, solo localhost).
> Nginx expone el **8001** hacia afuera y reenvia a gunicorn -- no pueden
> ser el mismo puerto.

```bash
systemctl daemon-reload
systemctl enable certificados-gunicorn
systemctl start certificados-gunicorn
systemctl status certificados-gunicorn --no-pager
```

Logs en vivo si algo falla: `journalctl -u certificados-gunicorn -f`

---

## Paso 8 -- Nginx (puerto 8001 publico)

```bash
nano /etc/nginx/sites-available/certificados
```

```nginx
server {
    listen 8001;
    server_name _;

    client_max_body_size 25M;

    location /static/ {
        alias /srv/cenefco-certificados/staticfiles/;
    }

    location /media/ {
        alias /srv/cenefco-certificados/media/;
    }

    location / {
        proxy_pass http://127.0.0.1:8002;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```bash
ln -s /etc/nginx/sites-available/certificados /etc/nginx/sites-enabled/
nginx -t
systemctl reload nginx
ufw allow 8001/tcp
```

Acceder desde el navegador: `http://161.97.181.140:8001`

---

## Paso 9 -- Cron para limpieza de certificados vencidos

```bash
chmod +x /srv/cenefco-certificados/scripts/limpiar_certificados_vencidos.sh
crontab -e
```

Agregar (corre todos los dias a las 3:00 am):

```
0 3 * * * /srv/cenefco-certificados/scripts/limpiar_certificados_vencidos.sh >> /var/log/cenefco_limpieza.log 2>&1
```

Probar manualmente antes de confiar en el cron:

```bash
/srv/cenefco-certificados/scripts/limpiar_certificados_vencidos.sh
cat /var/log/cenefco_limpieza.log
```

---

## Paso 10 -- Verificacion final

- [ ] `http://161.97.181.140:8001/login/` carga la pantalla de login
- [ ] Login con el superusuario funciona (sin error 403 de CSRF)
- [ ] Las imagenes de plantilla cargan en `/lotes/<id>/editar/` (si dan
      403, revisar permisos de la ruta -- ver nota del Paso 0)
- [ ] Crear un lote de prueba, generar certificados, descargar ZIP
- [ ] `systemctl status certificados-gunicorn` -> `active (running)`
- [ ] `systemctl status nginx` -> `active (running)`
- [ ] Moodle (`:8080`) y NPM (`:80`/`:81`/`:443`) siguen funcionando igual

---

## Cuando tengas el dominio

1. En **Nginx Proxy Manager** (UI en `:81`), agregar un Proxy Host nuevo
   apuntando a `127.0.0.1:8001` con el dominio elegido, y activar SSL
   (Let's Encrypt) ahi.
2. Agregar el dominio a `ALLOWED_HOSTS` y a `CSRF_TRUSTED_ORIGINS`
   (con `https://`) en el `.env`.
3. `systemctl restart certificados-gunicorn`

No hace falta tocar el Nginx nativo del proyecto -- NPM solo reenvia
trafico HTTPS del dominio hacia el puerto 8001 que ya funciona.

---

## Mantenimiento futuro

**Actualizar el codigo:**
```bash
cd /srv/cenefco-certificados
git pull origin main
source venv/bin/activate
python manage.py migrate
python manage.py collectstatic --noinput
systemctl restart certificados-gunicorn
```

**Ver logs de la aplicacion:**
```bash
journalctl -u certificados-gunicorn -n 100 --no-pager
```

**Backup de la base de datos:**
```bash
pg_dump -h 127.0.0.1 -U postgres certificados_cenefco > backup_$(date +%Y%m%d).sql
```

**Backup de archivos generados (media/):**
```bash
tar -czf media_backup_$(date +%Y%m%d).tar.gz /srv/cenefco-certificados/media
```

---

## Seguridad pendiente

- La contrasena de PostgreSQL (`5dv4rrgq8au7`) quedo expuesta en commits
  viejos del historial de Git (ya corregido hacia adelante, pero visible
  en el historial). **Cambiarla** despues de terminar el despliegue:
  ```bash
  sudo -u postgres psql -c "ALTER USER postgres PASSWORD 'NUEVA_CLAVE';"
  ```
  y actualizar `DB_PASSWORD` en el `.env` + `systemctl restart certificados-gunicorn`.
