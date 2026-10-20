from django.db.models import Count

from grupos.models import Grupo
from grupos.ranking import calcular_ranking
from juegos.estadisticas import ultimas_estadisticas
from juegos.models import PartidaLoL

from .models import Insignia, InsigniaObtenida


def primer_paso(usuario):
    return usuario.cuentas.count(), 1, None


def doble_vida(usuario):
    plataformas = usuario.cuentas.values('proveedor').distinct().count()
    return plataformas, 2, None


def centenario(usuario):
    filas = ultimas_estadisticas(usuario)
    mas_horas = max((fila['horas'] for fila in filas), default=0)
    return mas_horas, 100, None


def maraton(usuario):
    filas = ultimas_estadisticas(usuario)
    return sum(fila['horas_recientes'] for fila in filas), 20, None


def racha_25(usuario):
    victorias = PartidaLoL.objects.filter(cuenta__usuario=usuario, victoria=True).count()
    return victorias, 25, None


def inmortal(usuario):
    perfectas = PartidaLoL.objects.filter(cuenta__usuario=usuario, victoria=True, muertes=0).count()
    return perfectas, 1, None


def top_1(usuario):
    for grupo in usuario.grupos.all():
        ranking, _ = calcular_ranking(grupo, 'steam_horas')
        if len(ranking) >= 2 and ranking[0]['usuario'] == usuario and ranking[0]['puesto'] != ranking[1]['puesto']:
            return 1, 1, grupo
    return 0, 1, None


def lider(usuario):
    grupo = (
        Grupo.objects
        .filter(creador=usuario)
        .annotate(num_miembros=Count('membresias'))
        .order_by('-num_miembros')
        .first()
    )
    if grupo is None:
        return 0, 5, None
    return grupo.num_miembros, 5, grupo


REGLAS = {
    'primer_paso': primer_paso,
    'doble_vida': doble_vida,
    'centenario': centenario,
    'maraton': maraton,
    'racha_25': racha_25,
    'inmortal': inmortal,
    'top_1': top_1,
    'lider': lider,
}


def revisar_insignias(usuario):
    ya_tiene = {obtenida.insignia_id: obtenida for obtenida in usuario.insignias.all()}
    progreso = []
    nuevas = []

    for insignia in Insignia.objects.all():
        regla = REGLAS.get(insignia.codigo)
        if regla is None:
            continue

        obtenida = ya_tiene.get(insignia.id)
        if obtenida is None:
            actual, meta, grupo = regla(usuario)
            if actual >= meta:
                obtenida = InsigniaObtenida.objects.create(usuario=usuario, insignia=insignia, grupo=grupo)
                nuevas.append(insignia)
        else:
            actual, meta = 1, 1

        progreso.append({
            'insignia': insignia,
            'obtenida': obtenida,
            'actual': min(actual, meta),
            'meta': meta,
            'porcentaje': round(min(actual, meta) / meta * 100),
        })

    return progreso, nuevas