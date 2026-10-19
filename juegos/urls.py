from django.urls import path

from . import views

urlpatterns = [
    path('actualizar/', views.actualizar, name='actualizar_estadisticas'),
]