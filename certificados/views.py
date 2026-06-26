import shutil
import threading
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.files import File
from django.db import close_old_connections
from django.db.models import Q
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import LoteForm
from .generador import (
    GeneradorError,
    analizar_excel,
    exportar_reporte_excel,
    generar_certificados_lote,
    generar_previsualizacion_png,
)
from .models import Lote


def _puede_ver(user, lote) -> bool:
    return user.es_admin or lote.propietario_id == user.id


@login_required
def dashboard(request):
    if request.user.es_admin:
        lotes = Lote.objects.select_related("propietario").all()
    else:
        lotes = Lote.objects.filter(propietario=request.user)

    busqueda = request.GET.get("q", "").strip()
    if busqueda:
        filtro = Q(curso__icontains=busqueda)
        if request.user.es_admin:
            filtro |= Q(propietario__username__icontains=busqueda)
        lotes = lotes.filter(filtro)

    estado = request.GET.get("estado", "").strip()
    if estado in Lote.Estado.values:
        lotes = lotes.filter(estado=estado)

    return render(request, "certificados/dashboard.html", {
        "lotes": lotes,
        "busqueda": busqueda,
        "estado_seleccionado": estado,
        "estados": Lote.Estado.choices,
    })


@login_required
def crear_lote(request):
    if request.method == "POST":
        form = LoteForm(request.POST, request.FILES)
        if form.is_valid():
            lote = form.save(commit=False)
            lote.propietario = request.user
            lote.save()
            return redirect("detalle_lote", pk=lote.pk)
    else:
        form = LoteForm()
    return render(request, "certificados/crear_lote.html", {"form": form, "lote": None})


@login_required
def editar_lote(request, pk):
    lote = get_object_or_404(Lote, pk=pk)
    if not _puede_ver(request.user, lote):
        raise Http404

    if request.method == "POST":
        form = LoteForm(request.POST, request.FILES, instance=lote)
        if form.is_valid():
            form.save()
            messages.success(request, "Lote actualizado correctamente.")
            return redirect("detalle_lote", pk=lote.pk)
    else:
        form = LoteForm(instance=lote)
    return render(request, "certificados/crear_lote.html", {"form": form, "lote": lote})


@login_required
def detalle_lote(request, pk):
    lote = get_object_or_404(Lote, pk=pk)
    if not _puede_ver(request.user, lote):
        raise Http404
    return render(request, "certificados/detalle_lote.html", {"lote": lote})


@login_required
def eliminar_lote(request, pk):
    lote = get_object_or_404(Lote, pk=pk)
    if not _puede_ver(request.user, lote):
        raise Http404

    if request.method == "POST":
        curso = lote.curso
        carpeta_lote = Path(settings.MEDIA_ROOT) / "lotes" / str(lote.pk)
        lote.delete()
        if carpeta_lote.exists():
            shutil.rmtree(carpeta_lote, ignore_errors=True)
        messages.success(request, f'Lote "{curso}" eliminado.')
        return redirect("dashboard")

    return render(request, "certificados/eliminar_lote.html", {"lote": lote})


@login_required
def duplicar_lote(request, pk):
    lote = get_object_or_404(Lote, pk=pk)
    if not _puede_ver(request.user, lote):
        raise Http404

    nuevo = Lote(
        propietario=request.user,
        curso=f"{lote.curso} (copia)",
        texto_x=lote.texto_x,
        texto_y=lote.texto_y,
        margen_izquierdo=lote.margen_izquierdo,
        margen_derecho=lote.margen_derecho,
        tamano_fuente=lote.tamano_fuente,
        tamano_fuente_min=lote.tamano_fuente_min,
        color_texto=lote.color_texto,
        fuente=lote.fuente,
    )
    with lote.excel.open("rb") as f:
        nuevo.excel.save(Path(lote.excel.name).name, File(f), save=False)
    with lote.plantilla.open("rb") as f:
        nuevo.plantilla.save(Path(lote.plantilla.name).name, File(f), save=False)
    nuevo.save()

    messages.success(request, f'Lote duplicado como "{nuevo.curso}".')
    return redirect("detalle_lote", pk=nuevo.pk)


@login_required
def previsualizar_lote(request, pk):
    lote = get_object_or_404(Lote, pk=pk)
    if not _puede_ver(request.user, lote):
        raise Http404
    try:
        png_bytes = generar_previsualizacion_png(lote)
    except GeneradorError:
        raise Http404
    return HttpResponse(png_bytes, content_type="image/png")


@login_required
def lista_estudiantes(request, pk):
    lote = get_object_or_404(Lote, pk=pk)
    if not _puede_ver(request.user, lote):
        raise Http404
    try:
        analisis = analizar_excel(Path(lote.excel.path))
    except Exception as exc:  # noqa: BLE001 - se muestra el error en pantalla
        analisis = None
        messages.error(request, f"No se pudo leer el Excel: {exc}")
    return render(request, "certificados/lista_estudiantes.html", {"lote": lote, "analisis": analisis})


@login_required
def exportar_reporte(request, pk):
    lote = get_object_or_404(Lote, pk=pk)
    if not _puede_ver(request.user, lote):
        raise Http404
    try:
        analisis = analizar_excel(Path(lote.excel.path))
    except Exception:
        raise Http404
    contenido = exportar_reporte_excel(analisis)
    respuesta = HttpResponse(contenido, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    respuesta["Content-Disposition"] = f'attachment; filename="reporte_{lote.curso}.xlsx"'
    return respuesta


def _generar_en_segundo_plano(lote_id):
    close_old_connections()
    lote = Lote.objects.get(pk=lote_id)

    def reportar(procesados, total):
        Lote.objects.filter(pk=lote_id).update(procesados=procesados, total_certificados=total)

    try:
        carpeta_salida = Path(settings.MEDIA_ROOT) / "lotes" / str(lote.pk) / "salida"
        if carpeta_salida.exists():
            shutil.rmtree(carpeta_salida, ignore_errors=True)
        cantidad, zip_path = generar_certificados_lote(lote, carpeta_salida, on_progreso=reportar)
        lote.refresh_from_db()
        lote.zip_resultado = zip_path.relative_to(settings.MEDIA_ROOT).as_posix()
        lote.total_certificados = cantidad
        lote.procesados = cantidad
        lote.archivos_expirados = False
        lote.estado = Lote.Estado.GENERADO
        lote.mensaje_error = ""
        lote.save()
    except GeneradorError as exc:
        Lote.objects.filter(pk=lote_id).update(estado=Lote.Estado.ERROR, mensaje_error=str(exc))
    except Exception as exc:  # noqa: BLE001 - se reporta como error de lote, no debe tumbar el hilo
        Lote.objects.filter(pk=lote_id).update(estado=Lote.Estado.ERROR, mensaje_error=f"Error inesperado: {exc}")
    finally:
        close_old_connections()


@login_required
def generar_lote(request, pk):
    lote = get_object_or_404(Lote, pk=pk)
    if not _puede_ver(request.user, lote):
        raise Http404

    lote.estado = Lote.Estado.PROCESANDO
    lote.procesados = 0
    lote.total_certificados = 0
    lote.mensaje_error = ""
    lote.generado_por = request.user
    lote.generado_en = timezone.now()
    lote.save()

    hilo = threading.Thread(target=_generar_en_segundo_plano, args=(lote.pk,), daemon=True)
    hilo.start()

    return redirect("detalle_lote", pk=lote.pk)


@login_required
def progreso_lote(request, pk):
    lote = get_object_or_404(Lote, pk=pk)
    if not _puede_ver(request.user, lote):
        raise Http404
    return JsonResponse({
        "estado": lote.estado,
        "procesados": lote.procesados,
        "total": lote.total_certificados,
        "mensaje_error": lote.mensaje_error,
        "tiene_zip": bool(lote.zip_resultado),
    })


@login_required
def descargar_zip(request, pk):
    lote = get_object_or_404(Lote, pk=pk)
    if not _puede_ver(request.user, lote):
        raise Http404
    if not lote.zip_resultado:
        raise Http404
    return FileResponse(
        lote.zip_resultado.open("rb"),
        as_attachment=True,
        filename=f"certificados_{lote.curso}.zip",
    )
