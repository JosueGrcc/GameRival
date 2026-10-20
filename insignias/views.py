from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .reglas import revisar_insignias


def avisar_nuevas(request, nuevas):
    for insignia in nuevas:
        messages.success(request, f'¡Nueva insignia: {insignia.nombre}!')


@login_required
def lista(request):
    progreso, nuevas = revisar_insignias(request.user)
    avisar_nuevas(request, nuevas)
    obtenidas = sum(1 for fila in progreso if fila['obtenida'])
    return render(request, 'insignias/lista.html', {
        'progreso': progreso,
        'obtenidas': obtenidas,
        'total': len(progreso),
        'porcentaje': round(obtenidas / len(progreso) * 100) if progreso else 0,
    })