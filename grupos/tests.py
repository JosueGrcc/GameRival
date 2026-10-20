from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from juegos.models import EstadisticaSnapshot, Juego, MetricaSnapshot
from usuarios.models import CuentaVinculada, Usuario

from .models import Grupo, MiembroGrupo


def usuario(nombre):
    return Usuario.objects.create_user(username=nombre, email=f'{nombre}@x.com', password='CazadorWilds2026')


def horas_steam(u, horas_2_semanas, appid='730'):
    cuenta, _ = CuentaVinculada.objects.get_or_create(usuario=u, proveedor='steam', defaults={'id_externo': f'7656{u.pk:013d}', 'nombre_visible': u.username})
    juego, _ = Juego.objects.get_or_create(plataforma='steam', id_externo=appid, defaults={'nombre': 'CS2'})
    s = EstadisticaSnapshot.objects.create(cuenta=cuenta, juego=juego)
    MetricaSnapshot.objects.create(snapshot=s, nombre='horas_totales', valor=Decimal('100'))
    MetricaSnapshot.objects.create(snapshot=s, nombre='horas_2_semanas', valor=Decimal(horas_2_semanas))


def rango_lol(u, numero):
    cuenta = CuentaVinculada.objects.create(usuario=u, proveedor='riot', id_externo='p' * 70 + f'{u.pk:08d}', nombre_visible=f'{u.username}#LAN', region='la1')
    juego, _ = Juego.objects.get_or_create(plataforma='riot', id_externo='lol', defaults={'nombre': 'League of Legends'})
    s = EstadisticaSnapshot.objects.create(cuenta=cuenta, juego=juego)
    MetricaSnapshot.objects.create(snapshot=s, nombre='rango_solo', valor=Decimal(numero))


class GruposTests(TestCase):
    def setUp(self):
        self.yo = usuario('nova')
        self.client.force_login(self.yo)

    def test_crear_y_ser_admin(self):
        r = self.client.post(reverse('grupo_crear'), {'nombre': 'Los tilines'}, follow=True)
        grupo = Grupo.objects.get()
        self.assertContains(r, grupo.codigo)
        self.assertEqual(grupo.membresias.get().rol, 'admin')
        self.assertEqual(len(grupo.codigo), 6)

    def test_crear_sin_nombre(self):
        r = self.client.post(reverse('grupo_crear'), {'nombre': ''})
        self.assertContains(r, 'campo--error')
        self.assertFalse(Grupo.objects.exists())

    def test_unirse_con_codigo_en_minusculas(self):
        otro = usuario('kenji')
        g = Grupo.objects.create(nombre='Squad', creador=otro)
        MiembroGrupo.objects.create(grupo=g, usuario=otro, rol='admin')
        r = self.client.post(reverse('grupo_unirse'), {'codigo': f' {g.codigo.lower()} '}, follow=True)
        self.assertContains(r, 'Te uniste a')
        self.assertEqual(g.membresias.count(), 2)
        r = self.client.post(reverse('grupo_unirse'), {'codigo': g.codigo}, follow=True)
        self.assertContains(r, 'Ya eras parte')
        self.assertEqual(g.membresias.count(), 2)

    def test_codigo_que_no_existe(self):
        r = self.client.post(reverse('grupo_unirse'), {'codigo': 'ZZZZZZ'})
        self.assertContains(r, 'No existe ningún grupo')

    def test_no_miembro_no_ve_el_grupo(self):
        otro = usuario('kenji')
        g = Grupo.objects.create(nombre='Privado', creador=otro)
        MiembroGrupo.objects.create(grupo=g, usuario=otro, rol='admin')
        self.assertEqual(self.client.get(reverse('grupo_detalle', args=[g.pk])).status_code, 404)

    def test_ranking_steam_y_lol(self):
        kenji, mau = usuario('kenji'), usuario('mau')
        g = Grupo.objects.create(nombre='Los tilines', creador=self.yo)
        for u, rol in [(self.yo, 'admin'), (kenji, 'miembro'), (mau, 'miembro')]:
            MiembroGrupo.objects.create(grupo=g, usuario=u, rol=rol)
        horas_steam(self.yo, '21.1')
        horas_steam(kenji, '23.4')
        rango_lol(mau, 30245)
        rango_lol(self.yo, 20399)

        r = self.client.get(reverse('grupo_detalle', args=[g.pk]))
        ranking = r.context['ranking']
        self.assertEqual([f['usuario'].username for f in ranking], ['kenji', 'nova'])
        self.assertEqual([f['usuario'].username for f in r.context['sin_datos']], ['mau'])
        self.assertContains(r, '23.4 h')

        r = self.client.get(reverse('grupo_detalle', args=[g.pk]) + '?metrica=lol_rango')
        self.assertEqual([f['usuario'].username for f in r.context['ranking']], ['mau', 'nova'])
        self.assertContains(r, 'Oro II · 45 LP')
        self.assertContains(r, 'Plata I · 99 LP')

    def test_empates_comparten_lugar(self):
        a, b, c = usuario('a'), usuario('b'), usuario('c')
        g = Grupo.objects.create(nombre='Empate', creador=self.yo)
        for u in (self.yo, a, b, c):
            MiembroGrupo.objects.create(grupo=g, usuario=u)
        horas_steam(self.yo, '30'); horas_steam(a, '20'); horas_steam(b, '20'); horas_steam(c, '10')
        r = self.client.get(reverse('grupo_detalle', args=[g.pk]))
        self.assertEqual([f['puesto'] for f in r.context['ranking']], [1, 2, 2, 4])

    def test_salir_pasa_admin_y_borra_si_queda_vacio(self):
        kenji = usuario('kenji')
        g = Grupo.objects.create(nombre='Squad', creador=self.yo)
        MiembroGrupo.objects.create(grupo=g, usuario=self.yo, rol='admin')
        MiembroGrupo.objects.create(grupo=g, usuario=kenji, rol='miembro')
        self.client.post(reverse('grupo_salir', args=[g.pk]))
        self.assertEqual(g.membresias.get().usuario, kenji)
        self.assertEqual(g.membresias.get().rol, 'admin')

        self.client.force_login(kenji)
        self.client.post(reverse('grupo_salir', args=[g.pk]))
        self.assertFalse(Grupo.objects.exists())

    def test_salir_solo_post(self):
        g = Grupo.objects.create(nombre='Squad', creador=self.yo)
        MiembroGrupo.objects.create(grupo=g, usuario=self.yo, rol='admin')
        self.assertEqual(self.client.get(reverse('grupo_salir', args=[g.pk])).status_code, 405)

    def test_lista_y_perfil(self):
        g = Grupo.objects.create(nombre='Squad', creador=self.yo)
        MiembroGrupo.objects.create(grupo=g, usuario=self.yo, rol='admin')
        MiembroGrupo.objects.create(grupo=g, usuario=usuario('kenji'))
        r = self.client.get(reverse('grupos'))
        self.assertContains(r, 'Squad')
        self.assertContains(r, '2 miembros')
        self.assertContains(r, 'Admin')
        r = self.client.get(reverse('inicio'))
        self.assertContains(r, '<span class="kpi__valor">1</span>', html=False)
