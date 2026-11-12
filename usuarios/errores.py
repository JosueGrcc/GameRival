import logging

# Los avisos tecnicos salen en la terminal de runserver (y en el log del servidor).
registro = logging.getLogger('gamerival')


class ErrorExterno(Exception):
    """Fallo al hablar con Steam o Riot.

    El mensaje es para cualquier usuario. El `detalle` es tecnico (por ejemplo "la llave caduco"):
    nunca se muestra en la pagina, solo sale en la terminal de runserver (el log del servidor).
    """

    def __init__(self, mensaje, detalle=''):
        super().__init__(mensaje)
        self.detalle = detalle
        if detalle:
            registro.error(detalle)


def mensaje_para(usuario, error):
    """El texto del error que ve esta persona en la pagina. Nunca incluye el detalle tecnico."""
    return str(error)
