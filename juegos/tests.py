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


# ===================== Logros de Steam =====================

from decimal import Decimal  # noqa: E402

from juegos.estadisticas import rareza_promedio, sincronizar_logros, sincronizar_steam  # noqa: E402
from juegos.models import Juego, LogroSteam  # noqa: E402


def dos_juegos(steam_id):
    return [
        {'appid': 250900, 'name': 'The Binding of Isaac: Rebirth', 'playtime_forever': 19860},
        {'appid': 413150, 'name': 'Stardew Valley', 'playtime_forever': 6000},
    ]


def logros_falsos(steam_id, app_id):
    if app_id == '413150':
        return []  # como si el juego no tuviera logros
    return [{'clave': 'DEAD_GOD', 'fecha': 1760000000}, {'clave': 'MOM', 'fecha': 1700000000}, {'clave': 'SIN_PORCENTAJE', 'fecha': None}]


def info_falsa(app_id):
    return {'DEAD_GOD': {'nombre': 'Dead God', 'descripcion': 'Desbloquea todo', 'icono': 'https://x/icono.jpg'}}


def rareza_falsa(app_id):
    return {'DEAD_GOD': 0.8, 'MOM': '45.5'}  # Steam a veces manda texto


@mock.patch('usuarios.steam.rareza_de_logros', side_effect=rareza_falsa)
@mock.patch('usuarios.steam.info_de_logros', side_effect=info_falsa)
@mock.patch('usuarios.steam.logros_de', side_effect=logros_falsos)
class LogrosSteamTests(TestCase):

    def setUp(self):
        self.nova = Usuario.objects.create_user(username='nova', email='nova@x.com', password='x-2026-gr-x')
        self.cuenta = CuentaVinculada.objects.create(usuario=self.nova, proveedor='steam', id_externo='76561198000000001', nombre_visible='Nova')
        with mock.patch('usuarios.steam.juegos_de', side_effect=dos_juegos):
            sincronizar_steam(self.cuenta)

    def test_guarda_solo_los_que_tienen_porcentaje(self, *mocks):
        self.assertEqual(sincronizar_logros(self.cuenta), 2)
        dead_god = LogroSteam.objects.get(clave='DEAD_GOD')
        self.assertEqual(dead_god.nombre, 'Dead God')
        self.assertEqual(dead_god.rareza, Decimal('0.80'))
        self.assertEqual(dead_god.nivel, 'ultra')
        # sin nombre en espanol se usa la clave
        self.assertEqual(LogroSteam.objects.get(clave='MOM').nombre, 'MOM')

    def test_actualizar_dos_veces_no_duplica(self, *mocks):
        sincronizar_logros(self.cuenta)
        sincronizar_logros(self.cuenta)
        self.assertEqual(LogroSteam.objects.count(), 2)

    def test_rareza_promedio(self, *mocks):
        self.assertIsNone(rareza_promedio(self.nova))
        sincronizar_logros(self.cuenta)
        self.assertEqual(rareza_promedio(self.nova), Decimal('23.15'))  # (0.8 + 45.5) / 2

    def test_filtro_del_perfil(self, *mocks):
        sincronizar_logros(self.cuenta)
        self.client.force_login(self.nova)
        r = self.client.get(reverse('inicio'), {'plataforma': 'steam', 'rareza': 'ultra'})
        self.assertContains(r, 'Dead God')
        self.assertNotContains(r, '45.50%')
        r = self.client.get(reverse('inicio'), {'plataforma': 'steam', 'rareza': 'todos'})
        self.assertContains(r, '45.50%')

    def test_boton_actualizar_logros(self, *mocks):
        self.client.force_login(self.nova)
        r = self.client.post(reverse('actualizar_estadisticas'), {'plataforma': 'logros'}, follow=True)
        self.assertContains(r, 'Listo: 2 logros')
        self.assertContains(r, 'Mis logros más raros')

    def test_sin_logros_avisa(self, *mocks):
        mocks[0].side_effect = lambda steam_id, app_id: []  # ningun juego regresa logros
        self.client.force_login(self.nova)
        r = self.client.post(reverse('actualizar_estadisticas'), {'plataforma': 'logros'}, follow=True)
        self.assertContains(r, 'No encontramos logros')


class RankingLogrosTests(TestCase):
    """En la pestana de logros gana el que tiene el promedio MAS BAJO."""

    def setUp(self):
        self.nova = Usuario.objects.create_user(username='nova', email='nova@x.com', password='x-2026-gr-x')
        self.kenji = Usuario.objects.create_user(username='kenji', email='kenji@x.com', password='x-2026-gr-x')
        self.mau = Usuario.objects.create_user(username='mau', email='mau@x.com', password='x-2026-gr-x')
        self.grupo = Grupo.objects.create(nombre='Squad', creador=self.nova)
        juego = Juego.objects.create(nombre='Hollow Knight', plataforma='steam', id_externo='367520')
        for usuario, rarezas in ((self.nova, ['30', '20']), (self.kenji, ['0.5', '3.5']), (self.mau, [])):
            MiembroGrupo.objects.create(grupo=self.grupo, usuario=usuario)
            cuenta = CuentaVinculada.objects.create(usuario=usuario, proveedor='steam', id_externo=f'7656119800000000{usuario.id}', nombre_visible=usuario.username)
            for i, rareza in enumerate(rarezas):
                LogroSteam.objects.create(cuenta=cuenta, juego=juego, clave=f'L{i}', nombre=f'Logro {usuario.username} {i}', rareza=Decimal(rareza))

    def test_gana_el_menor_y_sin_logros_va_aparte(self):
        from grupos.ranking import calcular_ranking
        ranking, sin_datos = calcular_ranking(self.grupo, 'steam_logros')
        self.assertEqual([fila['usuario'] for fila in ranking], [self.kenji, self.nova])
        self.assertEqual(ranking[0]['texto'], '2.00%')
        self.assertEqual(ranking[0]['porcentaje'], 100)
        self.assertEqual([fila['usuario'] for fila in sin_datos], [self.mau])

    def test_pagina_del_grupo_con_filtro(self):
        self.client.force_login(self.nova)
        url = reverse('grupo_detalle', args=[self.grupo.pk])
        r = self.client.get(url, {'metrica': 'steam_logros'})
        self.assertContains(r, 'Los logros más difíciles del grupo')
        self.assertContains(r, 'Su más difícil: Logro kenji 0')
        r = self.client.get(url, {'metrica': 'steam_logros', 'rareza': 'ultra'})
        self.assertContains(r, 'Logro kenji 0')
        self.assertNotContains(r, '3.50%')
