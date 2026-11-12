"""Actualiza las estadisticas de TODAS las cuentas vinculadas.

Se corre asi:   python manage.py actualizar_todo
Sirve para dejar el ranking semanal al dia aunque nadie le haya dado Actualizar
(por ejemplo, antes de una demo). En un servidor real se programaria para correr cada noche.
"""
import time

from django.core.management.base import BaseCommand

from juegos.estadisticas import sincronizar_lol, sincronizar_steam
from usuarios.errores import ErrorExterno
from usuarios.models import CuentaVinculada

SINCRONIZAR = {
    'steam': sincronizar_steam,
    'riot': sincronizar_lol,
}


class Command(BaseCommand):
    help = 'Baja las estadisticas de Steam y Riot de todas las cuentas vinculadas.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--solo', choices=['steam', 'riot'],
            help='Actualizar solo una plataforma.',
        )
        parser.add_argument(
            '--pausa', type=float, default=1.0,
            help='Segundos de espera entre cuenta y cuenta, para no saturar las APIs (default 1).',
        )

    def handle(self, *args, solo=None, pausa=1.0, **opciones):
        cuentas = CuentaVinculada.objects.select_related('usuario').order_by('proveedor', 'id')
        if solo:
            cuentas = cuentas.filter(proveedor=solo)

        bien = fallaron = 0
        for cuenta in cuentas:
            try:
                cantidad = SINCRONIZAR[cuenta.proveedor](cuenta)
            except ErrorExterno as error:
                fallaron += 1
                self.stderr.write(f'  x {cuenta}: {error.detalle or error}')
            else:
                bien += 1
                que = 'juegos' if cuenta.proveedor == 'steam' else 'partidas nuevas'
                self.stdout.write(f'  ok {cuenta}: {cantidad} {que}')
            time.sleep(pausa)

        resumen = f'Listo: {bien} cuentas actualizadas, {fallaron} con error.'
        self.stdout.write(self.style.SUCCESS(resumen) if not fallaron else self.style.WARNING(resumen))
