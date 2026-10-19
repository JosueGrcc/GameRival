from urllib.parse import quote

import requests
from django.conf import settings


CONTINENTE_DE = {
    'la1': 'americas',
    'la2': 'americas',
    'na1': 'americas',
    'br1': 'americas',
    'euw1': 'europe',
}


class ErrorRiot(Exception):
    """Algo salio mal al hablar con Riot. El mensaje se le puede mostrar a la persona."""


def _pedir(servidor, ruta, params=None):
    """Hace una consulta a la API de Riot y regresa el JSON, o lanza ErrorRiot."""
    if not settings.RIOT_API_KEY:
        raise ErrorRiot('Falta configurar la llave de la API de Riot en el archivo .env.')

    url = f'https://{servidor}.api.riotgames.com{ruta}'
    try:
        respuesta = requests.get(
            url,
            params=params,
            headers={'X-Riot-Token': settings.RIOT_API_KEY},
            timeout=10,
        )
    except requests.RequestException:
        raise ErrorRiot('No pudimos comunicarnos con Riot. Intenta de nuevo en un momento.')

    if respuesta.status_code == 404:
        raise ErrorRiot('Riot no encontró esa cuenta. Revisa el nombre, el tag y la región.')
    if respuesta.status_code in (401, 403):
        raise ErrorRiot('La llave de la API de Riot no sirve o ya caducó. Genera una nueva.')
    if respuesta.status_code == 429:
        raise ErrorRiot('Hicimos demasiadas consultas a Riot. Espera un minuto y vuelve a intentar.')
    if respuesta.status_code != 200:
        raise ErrorRiot('Riot respondió con un error. Intenta de nuevo más tarde.')

    return respuesta.json()


def buscar_cuenta(nombre, tag):
    """Busca un Riot ID (Nombre#TAG). Regresa un diccionario con puuid, gameName y tagLine."""
    return _pedir('americas', f'/riot/account/v1/accounts/by-riot-id/{quote(nombre)}/{quote(tag)}')


def nivel_de(puuid, region):
    """Nivel de invocador en League of Legends."""
    datos = _pedir(region, f'/lol/summoner/v4/summoners/by-puuid/{puuid}')
    return datos.get('summonerLevel', 0)


def rangos_de(puuid, region):
    """Rangos de clasificatoria. Regresa un diccionario por cola: {'RANKED_SOLO_5x5': {...}}."""
    entradas = _pedir(region, f'/lol/league/v4/entries/by-puuid/{puuid}')
    return {entrada['queueType']: entrada for entrada in entradas}


def ids_de_partidas(puuid, region, cantidad=20):
    """Los identificadores de las ultimas partidas, de la mas nueva a la mas vieja."""
    continente = CONTINENTE_DE.get(region, 'americas')
    return _pedir(continente, f'/lol/match/v5/matches/by-puuid/{puuid}/ids', {'start': 0, 'count': cantidad})


def partida(id_partida, region):
    """Todos los datos de una partida."""
    continente = CONTINENTE_DE.get(region, 'americas')
    return _pedir(continente, f'/lol/match/v5/matches/{id_partida}')