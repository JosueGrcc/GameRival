from django.urls import path

from . import views

urlpatterns = [
    path('', views.lista, name='grupos'),
    path('crear/', views.crear, name='grupo_crear'),
    path('unirse/', views.unirse, name='grupo_unirse'),
    path('<int:pk>/', views.detalle, name='grupo_detalle'),
    path('<int:pk>/salir/', views.salir, name='grupo_salir'),
]