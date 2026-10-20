from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

from juegos.estadisticas import numero_a_rango, ultimas_estadisticas
from juegos.models import EstadisticaSnapshot, MetricaSnapshot, PartidaLoL

METRICAS = {
    # Esta semana (se reinicia cada lunes)
    'semana_steam': {'titulo': 'Horas Steam', 'detalle': 'Horas jugadas desde el lunes', 'periodo': 'semana'},
    'semana_lol': {'titulo': 'Victorias LoL', 'detalle': 'Partidas ganadas desde el lunes', 'periodo': 'semana'},
    # General
    'steam_horas': {'titulo': 'Horas 2 semanas', 'detalle': 'Horas jugadas en las últimas 2 semanas', 'periodo': 'general'},
    'lol_rango': {'titulo': 'Rango LoL', 'detalle': 'Clasificatoria Solo/Dúo', 'periodo': 'general'},
    'lol_winrate': {'titulo': 'Winrate LoL', 'detalle': 'Últimas 20 partidas', 'periodo': 'general'},
    'lol_kda': {'titulo': 'KDA LoL', 'detalle': 'Últimas 20 partidas', 'periodo': 'general'},
}
# Que metrica guardada en MetricaSnapshot corresponde a cada opcion de LoL
METRICA_LOL = {
    'lol_rango': 'rango_solo',
    'lol_winrate': 'winrate',
    'lol_kda': 'kda',
}

def inicio_de_semana():
    """El lunes de esta semana a las 00:00, en la hora de Mexico."""
    ahora = timezone.localtime()
    lunes = ahora - timedelta(days=ahora.weekday())
    return lunes.replace(hour=0, minute=0, second=0, microsecond=0)


def horas_de_la_semana(usuario, desde):
    """Horas de Steam jugadas desde `desde`. None si no tiene datos de Steam."""
    fotos = list(
        MetricaSnapshot.objects
        .filter(snapshot__cuenta__usuario=usuario, snapshot__cuenta__proveedor='steam', nombre='horas_totales')
        .order_by('snapshot__fecha')
        .values_list('snapshot__juego_id', 'snapshot__fecha', 'valor')
    )
    if not fotos:
        return None

    antes = {}      # horas de cada juego en la ultima foto ANTES del lunes
    primera = {}    # horas de cada juego en la primera foto de esta semana
    ahora = {}      # horas de cada juego en la foto mas reciente
    for juego_id, fecha, horas in fotos:
        if fecha < desde:
            antes[juego_id] = horas
        else:
            primera.setdefault(juego_id, horas)
        ahora[juego_id] = horas

    # Si nunca actualizo antes del lunes, se cuenta desde su primera foto de la semana
    if not antes:
        antes = primera

    total = sum(horas - antes.get(juego_id, Decimal('0')) for juego_id, horas in ahora.items())
    return max(total, Decimal('0'))


def victorias_de_la_semana(usuario, desde):
    """Partidas de LoL ganadas desde `desde`. None si no tiene cuenta de Riot."""
    if not usuario.cuentas.filter(proveedor='riot').exists():
        return None
    return PartidaLoL.objects.filter(cuenta__usuario=usuario, victoria=True, fecha__gte=desde).count()


def valor_de(usuario, metrica):
    if metrica == 'semana_steam':
        return horas_de_la_semana(usuario, inicio_de_semana())
    if metrica == 'semana_lol':
        return victorias_de_la_semana(usuario, inicio_de_semana())

    """El numero con el que se compara a esta persona. None si no tiene datos."""
    if metrica == 'steam_horas':
        filas = ultimas_estadisticas(usuario)
        return sum(fila['horas_recientes'] for fila in filas) if filas else None

    snapshot = (
        EstadisticaSnapshot.objects
        .filter(cuenta__usuario=usuario, juego__plataforma='riot', juego__id_externo='lol')
        .order_by('-fecha')
        .first()
    )
    if snapshot is None:
        return None
    metrica_guardada = snapshot.metricas.filter(nombre=METRICA_LOL[metrica]).first()
    return metrica_guardada.valor if metrica_guardada else None


def como_texto(metrica, valor):
    """Como se le ensena el numero a la persona."""
    if metrica in ('steam_horas', 'semana_steam'):
        return f'{valor:.1f} h'
    if metrica == 'semana_lol':
        return f'{valor} victoria{"s" if valor != 1 else ""}'
    if metrica == 'lol_rango':
        return numero_a_rango(valor)
    if metrica == 'lol_winrate':
        return f'{valor:.0f}%'
    return f'{valor:.2f}'


def calcular_ranking(grupo, metrica):
    """Regresa dos listas: los que tienen datos (ordenados) y los que no."""
    filas = []
    for membresia in grupo.membresias.select_related('usuario'):
        filas.append({
            'usuario': membresia.usuario,
            'valor': valor_de(membresia.usuario, metrica),
        })

    con_datos = sorted(
        (fila for fila in filas if fila['valor'] is not None),
        key=lambda fila: fila['valor'],
        reverse=True,
    )
    sin_datos = [fila for fila in filas if fila['valor'] is None]

    mas_alto = con_datos[0]['valor'] if con_datos else 0
    for posicion, fila in enumerate(con_datos, start=1):
        # Si empata con el de arriba, comparten lugar (1, 2, 2, 4...)
        if posicion > 1 and fila['valor'] == con_datos[posicion - 2]['valor']:
            fila['puesto'] = con_datos[posicion - 2]['puesto']
        else:
            fila['puesto'] = posicion
        fila['texto'] = como_texto(metrica, fila['valor'])
        fila['porcentaje'] = round(fila['valor'] / mas_alto * 100) if mas_alto else 0

    return con_datos, sin_datos