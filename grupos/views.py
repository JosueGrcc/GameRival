from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Max
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from datetime import timedelta
from django.utils import timezone
from django.utils.timesince import timesince

from juegos.estadisticas import RAREZAS, logros_de_usuarios

from .forms import GrupoForm, UnirseForm
from .models import Grupo, MiembroGrupo
from .ranking import METRICAS, calcular_ranking, inicio_de_semana


def _pagina_lista(request, grupo_form=None, unirse_form=None):
    # Primero se cuentan los miembros y DESPUES se filtra por "mis grupos".
    # Al reves, Django solo contaria tu propia membresia y siempre saldria 1.
    grupos = list(
        Grupo.objects
        .annotate(num_miembros=Count('membresias'))
        .filter(membresias__usuario=request.user)
        .order_by('nombre')
    )
    roles = dict(request.user.membresias.values_list('grupo_id', 'rol'))
    for grupo in grupos:
        grupo.mi_rol = roles.get(grupo.id)
    return render(request, 'grupos/lista.html', {
        'grupos': grupos,
        'grupo_form': grupo_form or GrupoForm(),
        'unirse_form': unirse_form or UnirseForm(),
    })


@login_required
def lista(request):
    return _pagina_lista(request)


@login_required
@require_POST
def crear(request):
    form = GrupoForm(request.POST)
    if not form.is_valid():
        return _pagina_lista(request, grupo_form=form)

    grupo = form.save(commit=False)
    grupo.creador = request.user
    grupo.save()
    MiembroGrupo.objects.create(grupo=grupo, usuario=request.user, rol='admin')
    messages.success(request, f'Grupo "{grupo.nombre}" creado. Comparte el código {grupo.codigo} con tus amigos.')
    return redirect('grupo_detalle', pk=grupo.pk)


@login_required
@require_POST
def unirse(request):
    form = UnirseForm(request.POST)
    if not form.is_valid():
        return _pagina_lista(request, unirse_form=form)

    grupo = form.grupo
    _, nuevo = MiembroGrupo.objects.get_or_create(grupo=grupo, usuario=request.user)
    if nuevo:
        messages.success(request, f'Te uniste a "{grupo.nombre}".')
    else:
        messages.info(request, f'Ya eras parte de "{grupo.nombre}".')
    return redirect('grupo_detalle', pk=grupo.pk)


@login_required
def detalle(request, pk):
    # Solo los miembros pueden ver el grupo; a los demas les sale "no encontrado".
    grupo = get_object_or_404(request.user.grupos, pk=pk)

    metrica = request.GET.get('metrica', 'semana_steam')
    if metrica not in METRICAS:
        metrica = 'semana_steam'

    ranking, sin_datos = calcular_ranking(grupo, metrica)
    lunes = inicio_de_semana()

    # actualizado = la fecha mas reciente en que se bajaron las estadisticas de sus cuentas
    membresias = list(grupo.membresias.select_related('usuario').annotate(
        actualizado=Max('usuario__cuentas__ultima_actualizacion'),
    ))
    for membresia in membresias:
        # "3 horas", "1 dia": solo la unidad mas grande, para que se lea corto
        membresia.actualizado_hace = timesince(membresia.actualizado, depth=1) if membresia.actualizado else None

    # Pestana de logros: el logro mas dificil de cada quien y la lista de todo el grupo
    logros_grupo = None
    rareza = request.GET.get('rareza', 'todos')
    if rareza not in RAREZAS:
        rareza = 'todos'
    if metrica == 'steam_logros':
        usuarios = [membresia.usuario for membresia in membresias]
        mas_dificil = {}
        for logro in logros_de_usuarios(usuarios):
            mas_dificil.setdefault(logro.cuenta.usuario_id, logro)  # ya vienen ordenados
        for fila in ranking:
            fila['logro'] = mas_dificil.get(fila['usuario'].id)
        logros_grupo = logros_de_usuarios(usuarios, rareza)[:15]

    return render(request, 'grupos/detalle.html', {
        'rarezas': RAREZAS,
        'rareza': rareza,
        'logros_grupo': logros_grupo,
        'grupo': grupo,
        'membresias': membresias,
        'metricas': METRICAS,
        'metrica': metrica,
        'metrica_actual': METRICAS[metrica],
        'ranking': ranking,
        'sin_datos': sin_datos,
        'semana': {
            'inicio': lunes,
            'fin': lunes + timedelta(days=6),
            'dias_restantes': 7 - timezone.localtime().weekday(),
        },
    })


@login_required
@require_POST
def salir(request, pk):
    membresia = get_object_or_404(MiembroGrupo, grupo_id=pk, usuario=request.user)
    grupo = membresia.grupo
    era_admin = membresia.rol == 'admin'
    membresia.delete()

    restantes = grupo.membresias.all()
    if not restantes.exists():
        grupo.delete()
        messages.success(request, f'Saliste de "{grupo.nombre}". Como eras el último, el grupo se borró.')
    else:
        if era_admin and not restantes.filter(rol='admin').exists():
            nuevo_admin = restantes.first()  # el que lleva mas tiempo
            nuevo_admin.rol = 'admin'
            nuevo_admin.save()
        messages.success(request, f'Saliste de "{grupo.nombre}".')
    return redirect('grupos')