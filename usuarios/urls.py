from django.contrib.auth import views as auth_views
from django.contrib.auth.views import LogoutView
from django.urls import path, reverse_lazy

from . import views

urlpatterns = [
    path('', views.inicio, name='inicio'),
    path('entrar/', views.IniciarSesionView.as_view(), name='login'),
    path('registro/', views.registro, name='registro'),
    path('salir/', LogoutView.as_view(), name='logout'),

    # "¿Olvidaste tu contraseña?": Django ya trae las 4 vistas, solo les damos nuestras plantillas.
    path('contrasena/olvide/', auth_views.PasswordResetView.as_view(
        template_name='usuarios/contrasena_pedir.html',
        email_template_name='usuarios/correo_contrasena.txt',
        subject_template_name='usuarios/correo_contrasena_asunto.txt',
        success_url=reverse_lazy('contrasena_enviada'),
    ), name='contrasena_olvide'),
    path('contrasena/enviada/', auth_views.PasswordResetDoneView.as_view(
        template_name='usuarios/contrasena_enviada.html',
    ), name='contrasena_enviada'),
    path('contrasena/nueva/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name='usuarios/contrasena_nueva.html',
        success_url=reverse_lazy('contrasena_lista'),
    ), name='contrasena_nueva'),
    path('contrasena/lista/', auth_views.PasswordResetCompleteView.as_view(
        template_name='usuarios/contrasena_lista.html',
    ), name='contrasena_lista'),
    path('cuentas/', views.cuentas, name='cuentas'),
    path('cuentas/steam/', views.steam_conectar, name='steam_conectar'),
    path('cuentas/steam/regreso/', views.steam_regreso, name='steam_regreso'),
    path('cuentas/riot/', views.riot_conectar, name='riot_conectar'),
    path('cuentas/<str:proveedor>/desconectar/', views.desconectar, name='desconectar'),
]