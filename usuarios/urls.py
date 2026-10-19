from django.contrib.auth.views import LogoutView
from django.urls import path

from . import views

urlpatterns = [
    path('', views.inicio, name='inicio'),
    path('entrar/', views.IniciarSesionView.as_view(), name='login'),
    path('registro/', views.registro, name='registro'),
    path('salir/', LogoutView.as_view(), name='logout'),
    path('cuentas/', views.cuentas, name='cuentas'),
    path('cuentas/steam/', views.steam_conectar, name='steam_conectar'),
    path('cuentas/steam/regreso/', views.steam_regreso, name='steam_regreso'),
    path('cuentas/riot/', views.riot_conectar, name='riot_conectar'),
    path('cuentas/<str:proveedor>/desconectar/', views.desconectar, name='desconectar'),
]