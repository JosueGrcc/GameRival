from datetime import datetime
from datetime import timezone as zona_utc  # se renombra para no chocar con django.utils.timezone
from decimal import Decimal

from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from usuarios import riot, steam

from .models import EstadisticaSnapshot, Juego, MetricaSnapshot, PartidaLoL

PORTADA_STEAM = 'https://cdn.akamai.steamstatic.com/steam/apps/{}/header.jpg'


def sincronizar_steam(cuenta):
    """Pide los juegos a Steam y guarda una foto de hoy. Regresa cuantos juegos guardo."""
    juegos = steam.juegos_de(cuenta.id_externo)
    jugados = [dato for dato in juegos if dato.get('playtime_forever', 0) > 0]
    inicio_de_hoy = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)

    with transaction.atomic():
        for dato in jugados:
            app_id = str(dato['appid'])
            juego, _ = Juego.objects.update_or_create(
                plataforma='steam',
                id_externo=app_id,
                defaults={
                    'nombre': (dato.get('name') or f'App {app_id}')[:100],
                    'imagen_url': PORTADA_STEAM.format(app_id),
                },
            )

            # Una sola foto por juego al dia: si ya hay una de hoy, se actualiza.
            snapshot = cuenta.snapshots.filter(juego=juego, fecha__gte=inicio_de_hoy).first()
            if snapshot is None:
                snapshot = EstadisticaSnapshot.objects.create(cuenta=cuenta, juego=juego)

            _guardar_horas(snapshot, 'horas_totales', dato['playtime_forever'])
            _guardar_horas(snapshot, 'horas_2_semanas', dato.get('playtime_2weeks', 0))

    return len(jugados)


def _guardar_horas(snapshot, nombre, minutos):
    horas = (Decimal(minutos) / 60).quantize(Decimal('0.01'))
    MetricaSnapshot.objects.update_or_create(
        snapshot=snapshot,
        nombre=nombre,
        defaults={'valor': horas},
    )


def ultimas_estadisticas(usuario):
    """La foto mas reciente de cada juego del usuario, ordenada por horas."""
    snapshots = (
        EstadisticaSnapshot.objects
        .filter(cuenta__usuario=usuario, cuenta__proveedor='steam')
        .select_related('juego')
        .prefetch_related('metricas')
        .order_by('-fecha')
    )

    mas_reciente = {}
    for snapshot in snapshots:
        mas_reciente.setdefault(snapshot.juego_id, snapshot)

    filas = []
    for snapshot in mas_reciente.values():
        metricas = {metrica.nombre: metrica.valor for metrica in snapshot.metricas.all()}
        filas.append({
            'juego': snapshot.juego,
            'horas': metricas.get('horas_totales', Decimal('0')),
            'horas_recientes': metricas.get('horas_2_semanas', Decimal('0')),
            'fecha': snapshot.fecha,
        })

    filas.sort(key=lambda fila: fila['horas'], reverse=True)
    return filas

# ===================== League of Legends =====================

TIERS = ['IRON', 'BRONZE', 'SILVER', 'GOLD', 'PLATINUM', 'EMERALD',
         'DIAMOND', 'MASTER', 'GRANDMASTER', 'CHALLENGER']
TIERS_ES = ['Hierro', 'Bronce', 'Plata', 'Oro', 'Platino', 'Esmeralda',
            'Diamante', 'Maestro', 'Gran Maestro', 'Retador']
DIVISIONES = ['IV', 'III', 'II', 'I']


def rango_a_numero(entrada):
    """Convierte un rango en un numero para poder guardarlo y ordenarlo.

    Cada tier vale 10,000 y cada division 100, mas los LP.
    Ejemplo: Oro II con 45 LP -> 3 * 10000 + 2 * 100 + 45 = 30245.
    En Maestro, Gran Maestro y Retador no hay divisiones y los LP pueden
    pasar de 1000, por eso cada tier tiene tanto espacio.
    """
    tier = TIERS.index(entrada['tier'])
    numero = tier * 10000 + entrada['leaguePoints']
    if tier < 7:
        numero += DIVISIONES.index(entrada['rank']) * 100
    return numero


def numero_a_rango(numero):
    """Lo contrario: 30245 -> 'Oro II · 45 LP'."""
    tier, resto = divmod(int(numero), 10000)
    if tier >= 7:
        return f'{TIERS_ES[tier]} · {resto} LP'
    division, puntos = divmod(resto, 100)
    return f'{TIERS_ES[tier]} {DIVISIONES[division]} · {puntos} LP'


def sincronizar_lol(cuenta, cantidad=20):
    """Trae nivel, rangos y las ultimas partidas. Regresa cuantas partidas nuevas guardo."""
    puuid, region = cuenta.id_externo, cuenta.region

    nivel = riot.nivel_de(puuid, region)
    rangos = riot.rangos_de(puuid, region)
    ids = riot.ids_de_partidas(puuid, region, cantidad)

    # Solo pedimos a Riot las partidas que todavia no tenemos guardadas.
    guardadas = set(cuenta.partidas_lol.filter(id_partida__in=ids).values_list('id_partida', flat=True))
    nuevas = []
    for id_partida in ids:
        if id_partida in guardadas:
            continue
        datos = riot.partida(id_partida, region)['info']
        if datos['gameDuration'] < 300:
            continue  # remake: la partida se cancelo en los primeros minutos
        yo = next(jugador for jugador in datos['participants'] if jugador['puuid'] == puuid)
        nuevas.append(PartidaLoL(
            cuenta=cuenta,
            id_partida=id_partida,
            fecha=datetime.fromtimestamp(datos['gameEndTimestamp'] / 1000, tz=zona_utc.utc),
            cola=datos['queueId'],
            duracion=datos['gameDuration'],
            campeon=yo['championName'],
            campeon_id=yo['championId'],
            victoria=yo['win'],
            asesinatos=yo['kills'],
            muertes=yo['deaths'],
            asistencias=yo['assists'],
        ))

    with transaction.atomic():
        PartidaLoL.objects.bulk_create(nuevas, ignore_conflicts=True)

        juego, _ = Juego.objects.get_or_create(
            plataforma='riot',
            id_externo='lol',
            defaults={'nombre': 'League of Legends'},
        )
        inicio_de_hoy = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
        snapshot = cuenta.snapshots.filter(juego=juego, fecha__gte=inicio_de_hoy).first()
        if snapshot is None:
            snapshot = EstadisticaSnapshot.objects.create(cuenta=cuenta, juego=juego)

        resumen = resumen_de_partidas(cuenta.partidas_lol.all()[:cantidad])
        valores = {
            'nivel': nivel,
            'horas_recientes': resumen['horas'],
            'partidas': resumen['partidas'],
            'winrate': resumen['winrate'],
            'kda': resumen['kda'],
        }
        if 'RANKED_SOLO_5x5' in rangos:
            valores['rango_solo'] = rango_a_numero(rangos['RANKED_SOLO_5x5'])
        if 'RANKED_FLEX_SR' in rangos:
            valores['rango_flex'] = rango_a_numero(rangos['RANKED_FLEX_SR'])

        for nombre, valor in valores.items():
            MetricaSnapshot.objects.update_or_create(
                snapshot=snapshot,
                nombre=nombre,
                defaults={'valor': Decimal(str(valor)).quantize(Decimal('0.01'))},
            )

    return len(nuevas)


def resumen_de_partidas(partidas):
    """Horas, victorias, winrate y KDA de una lista de partidas."""
    partidas = list(partidas)
    total = len(partidas)
    victorias = sum(1 for p in partidas if p.victoria)
    asesinatos = sum(p.asesinatos for p in partidas)
    muertes = sum(p.muertes for p in partidas)
    asistencias = sum(p.asistencias for p in partidas)
    return {
        'partidas': total,
        'victorias': victorias,
        'derrotas': total - victorias,
        'winrate': round(victorias / total * 100) if total else 0,
        'kda': round((asesinatos + asistencias) / max(muertes, 1), 2),
        'asesinatos': round(asesinatos / total, 1) if total else 0,
        'muertes': round(muertes / total, 1) if total else 0,
        'asistencias': round(asistencias / total, 1) if total else 0,
        'horas': round(sum(p.duracion for p in partidas) / 3600, 1),
    }


def perfil_lol(cuenta, cantidad=20):
    """Todo lo que necesita la pestana de League of Legends."""
    partidas = list(cuenta.partidas_lol.all()[:cantidad])

    snapshot = (
        cuenta.snapshots
        .filter(juego__plataforma='riot', juego__id_externo='lol')
        .prefetch_related('metricas')
        .order_by('-fecha')
        .first()
    )
    metricas = {m.nombre: m.valor for m in snapshot.metricas.all()} if snapshot else {}

    campeones = list(
        cuenta.partidas_lol
        .filter(id__in=[p.id for p in partidas])
        .values('campeon', 'campeon_id')
        .annotate(jugadas=Count('id'), ganadas=Count('id', filter=Q(victoria=True)))
        .order_by('-jugadas', '-ganadas')[:5]
    )
    for campeon in campeones:
        campeon['winrate'] = round(campeon['ganadas'] / campeon['jugadas'] * 100)

    return {
        'partidas': partidas,
        'resumen': resumen_de_partidas(partidas),
        'campeones': campeones,
        'nivel': int(metricas['nivel']) if 'nivel' in metricas else None,
        'rango_solo': numero_a_rango(metricas['rango_solo']) if 'rango_solo' in metricas else None,
        'rango_flex': numero_a_rango(metricas['rango_flex']) if 'rango_flex' in metricas else None,
        'actualizado': snapshot.fecha if snapshot else None,
    }