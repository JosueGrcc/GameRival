from django.contrib import admin

from .models import EstadisticaSnapshot, Juego, LogroSteam, MetricaSnapshot, PartidaLoL

admin.site.register(PartidaLoL)

admin.site.register(Juego)
admin.site.register(EstadisticaSnapshot)
admin.site.register(MetricaSnapshot)

@admin.register(LogroSteam)
class LogroSteamAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'juego', 'cuenta', 'rareza', 'fecha')
    list_filter = ('juego',)
    search_fields = ('nombre', 'juego__nombre', 'cuenta__nombre_visible')