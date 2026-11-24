"""Revisa paso por paso que Steam este regresando los logros.

Se corre asi:   python manage.py probar_logros
No guarda nada: solo imprime lo que contesta Steam en tus 3 juegos mas jugados.
Sirve para saber por que no aparecen logros (perfil privado, llave, juego sin logros...).
"""
from django.conf import settings
from django.core.management.base import BaseCommand

from juegos.estadisticas import ultimas_estadisticas
from usuarios import steam
from usuarios.models import CuentaVinculada


class Command(BaseCommand):
    help = 'Muestra lo que contesta Steam al pedir los logros (no guarda nada).'

    def add_arguments(self, parser):
        parser.add_argument('--juegos', type=int, default=3, help='Cuantos juegos revisar (default 3).')

    def handle(self, *args, juegos=3, **opciones):
        self.stdout.write(f'STEAM_API_KEY en .env: {"si" if settings.STEAM_API_KEY else "NO"}')
        cuentas = CuentaVinculada.objects.filter(proveedor='steam').select_related('usuario')
        if not cuentas:
            self.stdout.write('No hay cuentas de Steam vinculadas.')
            return

        for cuenta in cuentas:
            filas = ultimas_estadisticas(cuenta.usuario)
            self.stdout.write(f'\n== {cuenta.usuario.username} ({cuenta.nombre_visible}): {len(filas)} juegos guardados')
            if not filas:
                self.stdout.write('   No tiene juegos guardados: primero dale Actualizar en la pestana Steam.')
                continue

            for fila in filas[:juegos]:
                juego = fila['juego']
                self.stdout.write(f'\n   {juego.nombre} (appid {juego.id_externo}, {fila["horas"]} h)')

                codigo, datos = steam._pedir(
                    'ISteamUserStats/GetPlayerAchievements/v1/',
                    {'steamid': cuenta.id_externo, 'appid': juego.id_externo},
                )
                stats = datos.get('playerstats', {})
                todos = stats.get('achievements', [])
                desbloqueados = [l for l in todos if l.get('achieved')]
                self.stdout.write(
                    f'     Tus logros:   HTTP {codigo} | success={stats.get("success")} | '
                    f'{len(desbloqueados)} de {len(todos)} desbloqueados'
                    + (f' | error: {stats.get("error")}' if stats.get('error') else '')
                )

                info = steam.info_de_logros(juego.id_externo)
                self.stdout.write(f'     Nombres:      {len(info)} logros con nombre/icono')

                rareza = steam.rareza_de_logros(juego.id_externo)
                self.stdout.write(f'     Porcentajes:  {len(rareza)} logros con porcentaje')

                cruzados = [l for l in desbloqueados if l['apiname'] in rareza]
                self.stdout.write(f'     Se guardarian: {len(cruzados)} logros')
                if desbloqueados and not cruzados:
                    ejemplo = desbloqueados[0]['apiname']
                    otro = next(iter(rareza), None)
                    self.stdout.write(f'     OJO: no coinciden las claves. Ejemplo tuyo: {ejemplo!r} / ejemplo de porcentajes: {otro!r}')
