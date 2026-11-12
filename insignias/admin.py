from django.contrib import admin, messages

from .models import Insignia, InsigniaObtenida
from .reglas import REGLAS


@admin.register(Insignia)
class InsigniaAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'codigo', 'orden', 'tiene_regla']
    ordering = ['orden']

    @admin.display(boolean=True, description='¿Tiene regla?')
    def tiene_regla(self, insignia):
        return insignia.codigo in REGLAS

    def save_model(self, request, insignia, form, change):
        super().save_model(request, insignia, form, change)
        # La regla para ganarla vive en reglas.py, no en la base de datos.
        # Sin regla la insignia no sale en la pagina, asi que avisamos en vez de quedarnos callados.
        if insignia.codigo not in REGLAS:
            messages.warning(
                request,
                f'La insignia "{insignia.nombre}" se guardó, pero todavía NO aparece en la página: '
                f'falta escribir su regla en insignias/reglas.py y agregarla a REGLAS con el código "{insignia.codigo}".',
            )


@admin.register(InsigniaObtenida)
class InsigniaObtenidaAdmin(admin.ModelAdmin):
    list_display = ['usuario', 'insignia', 'grupo', 'fecha']
    list_filter = ['insignia']
