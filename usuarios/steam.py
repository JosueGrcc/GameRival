import re
from urllib.parse import urlencode

import requests
from django.conf import settings

from .errores import ErrorExterno

STEAM_OPENID = 'https://steamcommunity.com/openid/login'
STEAM_API = 'https://api.steampowered.com'

NO_DISPONIBLE = 'Las estadísticas de Steam no están disponibles por el momento. Intenta más tarde.'


class ErrorSteam(ErrorExterno):
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
        raise ErrorSteam(NO_DISPONIBLE, 'Falta STEAM_API_KEY en el archivo .env.')

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
        raise ErrorSteam('No pudimos comunicarnos con Steam. Intenta de nuevo en un momento.', 'Sin conexion con api.steampowered.com.')

    if respuesta.status_code in (401, 403):
        raise ErrorSteam(
            NO_DISPONIBLE,
            f'Steam rechazo la STEAM_API_KEY (HTTP {respuesta.status_code}). Revisa la del .env '
            'o saca otra en https://steamcommunity.com/dev/apikey',
        )
    if respuesta.status_code != 200:
        raise ErrorSteam('Steam respondió con un error. Intenta de nuevo más tarde.', f'GetOwnedGames respondio HTTP {respuesta.status_code}.')

    datos = respuesta.json().get('response', {})
    if 'games' not in datos:
        raise ErrorSteam(
            'Steam no nos deja ver tus juegos. En Steam, ve a tu perfil > Editar perfil > '
            'Privacidad y pon "Detalles de juego" en Público.'
        )
    return datos['games']

# ===================== Logros =====================

def _pedir(ruta, parametros, con_llave=True):
    """GET a la API de Steam. Regresa (codigo_http, json). Si no hay conexion lanza ErrorSteam."""
    if con_llave:
        if not settings.STEAM_API_KEY:
            raise ErrorSteam(NO_DISPONIBLE, 'Falta STEAM_API_KEY en el archivo .env.')
        parametros = {'key': settings.STEAM_API_KEY, **parametros}
    try:
        respuesta = requests.get(f'{STEAM_API}/{ruta}', params=parametros, timeout=15)
    except requests.RequestException:
        raise ErrorSteam('No pudimos comunicarnos con Steam. Intenta de nuevo en un momento.', 'Sin conexion con api.steampowered.com.')
    if respuesta.status_code == 401:
        raise ErrorSteam(NO_DISPONIBLE, 'Steam rechazo la STEAM_API_KEY (HTTP 401). Revisa la del .env.')
    try:
        datos = respuesta.json()
    except ValueError:
        datos = {}
    return respuesta.status_code, datos


def logros_de(steam_id, app_id):
    """Los logros que la persona YA desbloqueo en un juego: [{'clave', 'fecha'}].

    Si el juego no tiene logros, Steam responde con error 400; eso no es un problema,
    simplemente se regresa una lista vacia.
    """
    codigo, datos = _pedir('ISteamUserStats/GetPlayerAchievements/v1/', {'steamid': steam_id, 'appid': app_id})
    estadisticas = datos.get('playerstats', {})

    if codigo == 403 or 'not public' in str(estadisticas.get('error', '')).lower():
        raise ErrorSteam(
            'Steam no nos deja ver tus logros. En Steam, ve a tu perfil > Editar perfil > '
            'Privacidad y pon "Detalles de juego" en Público.'
        )
    if codigo != 200 or not estadisticas.get('success'):
        return []  # el juego no tiene logros

    return [
        {'clave': logro['apiname'], 'fecha': logro.get('unlocktime') or None}
        for logro in estadisticas.get('achievements', [])
        if logro.get('achieved')
    ]


def info_de_logros(app_id):
    """Nombre, descripcion e icono de cada logro del juego, en espanol: {clave: {...}}."""
    codigo, datos = _pedir('ISteamUserStats/GetSchemaForGame/v2/', {'appid': app_id, 'l': 'spanish'})
    if codigo != 200:
        return {}
    logros = datos.get('game', {}).get('availableGameStats', {}).get('achievements', [])
    return {
        logro['name']: {
            'nombre': logro.get('displayName') or logro['name'],
            'descripcion': logro.get('description', ''),
            'icono': logro.get('icon', ''),
        }
        for logro in logros
    }


def rareza_de_logros(app_id):
    """Que porcentaje de los jugadores tiene cada logro: {clave: 12.5}. No necesita llave."""
    codigo, datos = _pedir(
        'ISteamUserStats/GetGlobalAchievementPercentagesForApp/v2/',
        {'gameid': app_id},
        con_llave=False,
    )
    if codigo != 200:
        return {}
    logros = datos.get('achievementpercentages', {}).get('achievements', [])
    # Steam a veces manda el porcentaje como texto ("12.5"), por eso el float()
    return {logro['name']: float(logro['percent']) for logro in logros}