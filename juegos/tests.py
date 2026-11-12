from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from grupos.models import Grupo, MiembroGrupo
from usuarios.models import CuentaVinculada, Usuario


def juegos_falsos(steam_id):
    return [{'appid': 730, 'name': 'Counter-Strike 2', 'playtime_forever': 600, 'playtime_2weeks': 120}]


class ActualizarTodoTests(TestCase):
    """G001: el comando actualizar_todo baja las estadisticas de todos sin que nadie le de Actualizar."""

    def setUp(self):
        self.nova = Usuario.objects.create_user(username='nova', email='nova@x.com', password='x-2026-gr-x')
        self.kenji = Usuario.objects.create_user(username='kenji', email='kenji@x.com', password='x-2026-gr-x')
        self.steam_nova = CuentaVinculada.objects.create(usuario=self.nova, proveedor='steam', id_externo='76561198000000001', nombre_visible='Nova')
        self.steam_kenji = CuentaVinculada.objects.create(usuario=self.kenji, proveedor='steam', id_externo='76561198000000002', nombre_visible='Kenji')
        CuentaVinculada.objects.create(usuario=self.kenji, proveedor='riot', id_externo='p' * 78, nombre_visible='Kenji#LAN', region='la1')

    def correr(self, *args):
        salida, errores = StringIO(), StringIO()
        call_command('actualizar_todo', '--pausa', '0', *args, stdout=salida, stderr=errores)
        return salida.getvalue(), errores.getvalue()

    @override_settings(RIOT_API_KEY='')
    def test_actualiza_a_todos_y_sigue_aunque_uno_falle(self):
        with mock.patch('usuarios.steam.juegos_de', side_effect=juegos_falsos), self.assertLogs('gamerival', 'ERROR'):
            salida, errores = self.correr()
        self.assertIn('2 cuentas actualizadas, 1 con error', salida)
        self.assertIn('RIOT_API_KEY', errores)        # el detalle tecnico va al registro
        for cuenta in (self.steam_nova, self.steam_kenji):
            cuenta.refresh_from_db()
            self.assertIsNotNone(cuenta.ultima_actualizacion)
            self.assertEqual(cuenta.snapshots.count(), 1)

    def test_solo_una_plataforma(self):
        with mock.patch('usuarios.steam.juegos_de', side_effect=juegos_falsos):
            salida, _ = self.correr('--solo', 'steam')
        self.assertIn('2 cuentas actualizadas, 0 con error', salida)

    def test_el_grupo_muestra_cuando_se_actualizo_cada_quien(self):
        g = Grupo.objects.create(nombre='Squad', creador=self.nova)
        MiembroGrupo.objects.create(grupo=g, usuario=self.nova, rol='admin')
        MiembroGrupo.objects.create(grupo=g, usuario=self.kenji)
        with mock.patch('usuarios.steam.juegos_de', side_effect=juegos_falsos):
            self.correr('--solo', 'steam', )
        CuentaVinculada.objects.filter(usuario=self.kenji).update(ultima_actualizacion=None)
        self.client.force_login(self.nova)
        r = self.client.get(reverse('grupo_detalle', args=[g.pk]))
        self.assertContains(r, 'Datos de ', count=1)
        self.assertContains(r, 'Sin actualizar todavía', count=1)
        self.assertContains(r, 'El ranking se reinicia cada lunes')


class SelectorDeMetricaTests(TestCase):
    """G002: en celular, el grupo trae una lista desplegable con todas las metricas."""

    def test_la_lista_trae_todas_las_metricas_y_marca_la_actual(self):
        from grupos.ranking import METRICAS
        nova = Usuario.objects.create_user(username='nova', email='nova@x.com', password='x-2026-gr-x')
        g = Grupo.objects.create(nombre='Squad', creador=nova)
        MiembroGrupo.objects.create(grupo=g, usuario=nova, rol='admin')
        self.client.force_login(nova)
        r = self.client.get(reverse('grupo_detalle', args=[g.pk]) + '?metrica=lol_kda')
        self.assertContains(r, 'id="selector-metrica"')
        for clave in METRICAS:
            self.assertContains(r, f'<option value="{clave}"')
        self.assertContains(r, '<option value="lol_kda" selected>')
