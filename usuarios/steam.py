import re
from urllib.parse import urlencode

import requests
from django.conf import settings

STEAM_OPENID = 'https://steamcommunity.com/openid/login'
STEAM_API = 'https://api.steampowered.com'

class ErrorSteam(Exception):
    """Algo salio mal al hablar con Steam. El mensaje se le puede mostrar a la persona."""


def url_login(url_regreso, url_sitio):
    """Arma la direccion de la pagina de Steam donde la persona inicia sesion."""
    parametros = {
        'openid.ns': 'http://specs.openid.net/auth/2.0',
        'openid.mode': 'checkid_setup',
        'openid.return_to': url_regreso,
        'openid.realm': url_sitio,
        'openid.identity': 'http://specs.openid.net/auth/2.0/identifier_select',
        'openid.claimed_id': 'http://specs.openid.net/auth/2.0/identifier_select',
    }
    return f'{STEAM_OPENID}?{urlencode(parametros)}'


def verificar(datos):
    """Le pregunta a Steam si la respuesta es real. Regresa el SteamID o None."""
    if datos.get('openid.mode') != 'id_res':
        return None

    parametros = {clave: valor for clave, valor in datos.items() if clave.startswith('openid.')}
    parametros['openid.mode'] = 'check_authentication'

    try:
        respuesta = requests.post(STEAM_OPENID, data=parametros, timeout=10)
    except requests.RequestException:
        return None

    if 'is_valid:true' not in respuesta.text:
        return None

    encontrado = re.fullmatch(
        r'https://steamcommunity\.com/openid/id/(\d{17})',
        datos.get('openid.claimed_id', ''),
    )
    return encontrado.group(1) if encontrado else None


def nombre_de_perfil(steam_id):
    """Busca el nombre visible del perfil. Si no se puede, regresa None."""
    if not settings.STEAM_API_KEY:
        return None

    try:
        respuesta = requests.get(
            f'{STEAM_API}/ISteamUser/GetPlayerSummaries/v2/',
            params={'key': settings.STEAM_API_KEY, 'steamids': steam_id},
            timeout=10,
        )
        jugadores = respuesta.json()['response']['players']
    except (requests.RequestException, ValueError, KeyError):
        return None

    return jugadores[0]['personaname'] if jugadores else None

def juegos_de(steam_id):
    """Regresa la lista de juegos de la cuenta, con sus minutos jugados."""
    if not settings.STEAM_API_KEY:
        raise ErrorSteam('Falta configurar la llave de la API de Steam en el archivo .env.')

    try:
        respuesta = requests.get(
            f'{STEAM_API}/IPlayerService/GetOwnedGames/v1/',
            params={
                'key': settings.STEAM_API_KEY,
                'steamid': steam_id,
                'include_appinfo': 1,
                'include_played_free_games': 1,
            },
            timeout=15,
        )
    except requests.RequestException:
        raise ErrorSteam('No pudimos comunicarnos con Steam. Intenta de nuevo en un momento.')

    if respuesta.status_code in (401, 403):
        raise ErrorSteam('Steam no aceptó la llave de la API. Revisa la que pusiste en el .env.')
    if respuesta.status_code != 200:
        raise ErrorSteam('Steam respondió con un error. Intenta de nuevo más tarde.')

    datos = respuesta.json().get('response', {})
    if 'games' not in datos:
        raise ErrorSteam(
            'Steam no nos deja ver tus juegos. En Steam, ve a tu perfil > Editar perfil > '
            'Privacidad y pon "Detalles de juego" en Público.'
        )
    return datos['games']