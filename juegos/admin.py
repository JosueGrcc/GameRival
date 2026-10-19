from django.contrib import admin

from .models import EstadisticaSnapshot, Juego, MetricaSnapshot, PartidaLoL

admin.site.register(PartidaLoL)

admin.site.register(Juego)
admin.site.register(EstadisticaSnapshot)
admin.site.register(MetricaSnapshot)