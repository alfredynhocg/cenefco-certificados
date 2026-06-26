# Despliegue en VPS (Ubuntu 24.04, sin Docker)

Guia paso a paso para instalar el proyecto de certificados en el VPS
(`vmi3392869`), sin contenedores, usando los servicios nativos de Ubuntu:
PostgreSQL, Nginx y systemd (gunicorn como servidor WSGI).

El VPS ya corre Moodle y Nginx Proxy Manager (NPM) en Docker, ocupando los
puertos 80, 81, 443 y 8080. Este proyecto corre **aparte, sin Docker**, en
el puerto 8001, sin tocar nada de lo existente.

## Estructura final en el VPS

```
/root/certificados/
└── app/                    <- codigo del proyecto Django
    ├── venv/                <- entorno virtual Python
    ├── manage.py
    ├── config/
    ├── accounts/
    ├── certificados/
    ├── templates/
    ├── media/               <- excels, plantillas, PDFs generados
    ├── .env                 <- configuracion real (no se versiona)
    └── scripts/
```

Servicios que se crean:
- `postgresql` (apt) -- base de datos `certificados_cenefco`
- `certificados-gunicorn.service` (systemd) -- corre la app Django
- `nginx` (apt, nativo) -- proxy en el puerto 8001 hacia gunicorn
- cron diario -- limpieza de certificados vencidos (>30 dias)

---

## Paso 0 -- Resumen de lo ya confirmado en el VPS

| Item | Estado |
|---|---|
| Sistema | Ubuntu 24.04 (noble) |
| Python | 3.12.3 nativo (`/usr/bin/python3.12`) |
| PostgreSQL | No instalado (se instala nativo via apt) |
| Nginx | No instalado nativo (se instala via apt, puerto 8001 propio) |
| Docker | Solo para Moodle + NPM, no se toca |
| Puertos libres | 8001 (elegido para este proyecto) |
| RAM / Disco | 11GB RAM, 185GB libres -- sobra espacio |

---

## Paso 1 -- Instalar dependencias del sistema

```bash
apt update && apt install -y python3.12-venv python3-pip postgresql postgresql-contrib nginx git
```

Verificar que los servicios quedaron activos:

```bash
systemctl status postgresql --no-pager | head -5
systemctl status nginx --no-pager | head -5
```

---

## Paso 2 -- Crear la base de datos PostgreSQL

```bash
sudo -u postgres psql
```

Dentro del prompt de `psql`:

```sql
CREATE DATABASE certificados_cenefco;
ALTER USER postgres PASSWORD '5dv4rrgq8au7';
\q
```

> Nota: se reutiliza la misma base/credenciales que en el entorno local
> para simplificar. Si prefieres una contraseña distinta en el VPS,
> usa esa y ajusta el `.env` del Paso 5 acorde.

Verificar conexion:

```bash
psql -h 127.0.0.1 -U postgres -d certificados_cenefco -c "SELECT 1;"
```

---

## Paso 3 -- Subir el codigo del proyecto

Opcion recomendada: copiar el proyecto local al VPS via `scp` (no hay
repositorio Git todavia). Desde la maquina local (Windows, en Git Bash):

```bash
mkdir -p /root/certificados   # en el VPS, antes de copiar
scp -r "c:\Users\maxcell\projects\cenefco\certicados-web" root@TU_IP_VPS:/root/certificados/app
```

Esto copia todo, incluyendo `venv/` y `db.sqlite3` de Windows, que **no
sirven en Linux** y se deben descartar. En el VPS, despues de copiar:

```bash
cd /root/certificados/app
rm -rf venv db.sqlite3 server.log __pycache__
find . -name "__pycache__" -type d -exec rm -rf {} +
```

> Alternativa mas prolija a futuro: subir el proyecto a un repositorio Git
> (privado) y hacer `git clone` en el VPS en vez de `scp`. Mas facil de
> actualizar despues con `git pull`.

---

## Paso 4 -- Entorno virtual y dependencias Python

```bash
cd /root/certificados/app
python3.12 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install django gunicorn psycopg2-binary python-decouple pillow reportlab openpyxl pymupdf
```

---

## Paso 5 -- Configurar `.env` de produccion

```bash
nano /root/certificados/app/.env
```

Contenido:

```env
DEBUG=False
SECRET_KEY=GENERAR_UNA_CLAVE_NUEVA_AQUI
ALLOWED_HOSTS=TU_IP_VPS,127.0.0.1,localhost

DB_ENGINE=django.db.backends.postgresql
DB_NAME=certificados_cenefco
DB_USER=postgres
DB_PASSWORD=5dv4rrgq8au7
DB_HOST=127.0.0.1
DB_PORT=5432
```

Generar una `SECRET_KEY` nueva (no reusar la de desarrollo local):

```bash
source venv/bin/activate
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Copiar el resultado dentro del `.env` en `SECRET_KEY=`.

> `DEBUG=False` es obligatorio en produccion -- evita que Django muestre
> tracebacks con informacion sensible si algo falla.

---

## Paso 6 -- Migraciones, superusuario y archivos estaticos

```bash
cd /root/certificados/app
source venv/bin/activate
python manage.py migrate
python manage.py createsuperuser
python manage.py collectstatic --noinput
```

`collectstatic` junta el CSS/JS de Django admin en una carpeta `staticfiles/`
que Nginx servira directamente (Paso 8).

Agregar a `config/settings.py` (si no existe ya) antes de correr
`collectstatic`:

```python
STATIC_ROOT = BASE_DIR / "staticfiles"
```

---

## Paso 7 -- Gunicorn + systemd

Crear el archivo de servicio:

```bash
nano /etc/systemd/system/certificados-gunicorn.service
```

Contenido:

```ini
[Unit]
Description=Gunicorn - Certificados CENEFCO
After=network.target postgresql.service

[Service]
User=root
Group=root
WorkingDirectory=/root/certificados/app
EnvironmentFile=/root/certificados/app/.env
ExecStart=/root/certificados/app/venv/bin/gunicorn \
    --workers 3 \
    --bind 127.0.0.1:8001 \
    --timeout 120 \
    config.wsgi:application
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

> `--timeout 120` da margen para lotes grandes (cientos de certificados);
> la generacion real corre en un hilo en segundo plano, asi que esto es
> solo margen para la respuesta HTTP inicial.

Activar y arrancar:

```bash
systemctl daemon-reload
systemctl enable certificados-gunicorn
systemctl start certificados-gunicorn
systemctl status certificados-gunicorn --no-pager
```

Ver logs en vivo si algo falla:

```bash
journalctl -u certificados-gunicorn -f
```

---

## Paso 8 -- Nginx como proxy (puerto 8001 externo)

Gunicorn escucha en `127.0.0.1:8001` (solo localhost). Nginx escucha en
`0.0.0.0:8001`... espera, **mismo puerto no puede usarse dos veces**. Ajuste:
gunicorn escucha en un socket interno (`127.0.0.1:8002`) y Nginx expone el
puerto **8001** hacia afuera. Corregir el `ExecStart` del Paso 7 a
`--bind 127.0.0.1:8002` antes de continuar aqui.

```bash
nano /etc/nginx/sites-available/certificados
```

Contenido:

```nginx
server {
    listen 8001;
    server_name _;

    client_max_body_size 25M;

    location /static/ {
        alias /root/certificados/app/staticfiles/;
    }

    location /media/ {
        alias /root/certificados/app/media/;
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

Activar el sitio:

```bash
ln -s /etc/nginx/sites-available/certificados /etc/nginx/sites-enabled/
nginx -t
systemctl reload nginx
```

Abrir el puerto en el firewall si usas `ufw`:

```bash
ufw allow 8001/tcp
```

Acceder desde el navegador: `http://TU_IP_VPS:8001`

---

## Paso 9 -- Cron para limpieza de certificados vencidos

El script ya existe en `scripts/limpiar_certificados_vencidos.sh` (copiado
junto con el proyecto en el Paso 3). Darle permisos y programarlo:

```bash
chmod +x /root/certificados/app/scripts/limpiar_certificados_vencidos.sh
crontab -e
```

Agregar esta linea (corre todos los dias a las 3:00 am):

```
0 3 * * * /root/certificados/app/scripts/limpiar_certificados_vencidos.sh >> /var/log/cenefco_limpieza.log 2>&1
```

Probar manualmente que funciona antes de confiar en el cron:

```bash
/root/certificados/app/scripts/limpiar_certificados_vencidos.sh
cat /var/log/cenefco_limpieza.log
```

---

## Paso 10 -- Verificacion final

- [ ] `http://TU_IP_VPS:8001/login/` carga la pantalla de login
- [ ] Login con el superusuario creado en el Paso 6 funciona
- [ ] Crear un lote de prueba, generar certificados, descargar ZIP
- [ ] `systemctl status certificados-gunicorn` esta `active (running)`
- [ ] `systemctl status nginx` esta `active (running)`
- [ ] Moodle (`:8080`) y NPM (`:80`/`:81`/`:443`) siguen funcionando igual que antes

---

## Cuando tengas el dominio

Cuando decidas el (sub)dominio para certificados, los pasos cambian asi:

1. En **Nginx Proxy Manager** (la UI de NPM en `:81`), agregar un Proxy
   Host nuevo apuntando a `127.0.0.1:8001` (el Nginx nativo de este
   proyecto) con el dominio elegido, y activar SSL (Let's Encrypt) ahi.
2. Actualizar `ALLOWED_HOSTS` en el `.env` del proyecto agregando el
   dominio nuevo.
3. Reiniciar: `systemctl restart certificados-gunicorn`.

No hace falta tocar el Nginx nativo del proyecto ni gunicorn -- NPM
simplemente reenvia trafico HTTPS del dominio hacia el puerto 8001 que ya
esta funcionando.

---

## Mantenimiento futuro

**Actualizar el codigo** (si se sube a Git, mas adelante):
```bash
cd /root/certificados/app
git pull
source venv/bin/activate
pip install -r requirements.txt   # si se agrega ese archivo
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
tar -czf media_backup_$(date +%Y%m%d).tar.gz /root/certificados/app/media
```
