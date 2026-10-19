from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('juegos/', include('juegos.urls')),
    path('', include('usuarios.urls')),
]