from django.urls import path

from . import views

urlpatterns = [
    path("dashboard/", views.dashboard, name="dashboard"),
    path("lotes/nuevo/", views.crear_lote, name="crear_lote"),
    path("lotes/<int:pk>/", views.detalle_lote, name="detalle_lote"),
    path("lotes/<int:pk>/editar/", views.editar_lote, name="editar_lote"),
    path("lotes/<int:pk>/eliminar/", views.eliminar_lote, name="eliminar_lote"),
    path("lotes/<int:pk>/duplicar/", views.duplicar_lote, name="duplicar_lote"),
    path("lotes/<int:pk>/previsualizar/", views.previsualizar_lote, name="previsualizar_lote"),
    path("lotes/<int:pk>/estudiantes/", views.lista_estudiantes, name="lista_estudiantes"),
    path("lotes/<int:pk>/estudiantes/exportar/", views.exportar_reporte, name="exportar_reporte"),
    path("lotes/<int:pk>/generar/", views.generar_lote, name="generar_lote"),
    path("lotes/<int:pk>/progreso/", views.progreso_lote, name="progreso_lote"),
    path("lotes/<int:pk>/descargar/", views.descargar_zip, name="descargar_zip"),
]
