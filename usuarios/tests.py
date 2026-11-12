import re
from unittest import mock

from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from . import riot, steam
from .errores import mensaje_para
from .models import CuentaVinculada, Usuario


class RecuperarContrasenaTests(TestCase):
    """A001: '¿Olvidaste tu contraseña?' manda un link por correo para crear una nueva."""

    def setUp(self):
        self.usuario = Usuario.objects.create_user(username='nova', email='nova@x.com', password='Vieja-2026-gr')

    def test_el_login_tiene_el_link(self):
        r = self.client.get(reverse('login'))
        self.assertContains(r, reverse('contrasena_olvide'))

    def test_flujo_completo(self):
        r = self.client.post(reverse('contrasena_olvide'), {'email': 'nova@x.com'})
        self.assertRedirects(r, reverse('contrasena_enviada'))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('nova', mail.outbox[0].body)

        link = re.search(r'https?://[^/]+(/contrasena/nueva/\S+)', mail.outbox[0].body).group(1)
        r = self.client.get(link, follow=True)       # Django cambia el token por "set-password"
        self.assertContains(r, 'Nueva contraseña')
        r = self.client.post(r.redirect_chain[-1][0], {
            'new_password1': 'Nueva-2026-gr', 'new_password2': 'Nueva-2026-gr',
        })
        self.assertRedirects(r, reverse('contrasena_lista'))
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password('Nueva-2026-gr'))

        # El link solo sirve una vez
        r = self.client.get(link, follow=True)
        self.assertContains(r, 'Este link ya no sirve')

    def test_correo_que_no_existe_no_lo_dice(self):
        # Por seguridad no revelamos si un correo esta registrado
        r = self.client.post(reverse('contrasena_olvide'), {'email': 'nadie@x.com'})
        self.assertRedirects(r, reverse('contrasena_enviada'))
        self.assertEqual(len(mail.outbox), 0)


def respuesta(codigo, datos=None):
    return mock.Mock(status_code=codigo, json=mock.Mock(return_value=datos or {}))


class MensajesDeErrorTests(TestCase):
    """P001: si la llave de una API falla, el usuario ve un mensaje amigable y el admin el detalle."""

    def setUp(self):
        self.yo = Usuario.objects.create_user(username='nova', email='nova@x.com', password='x-2026-gr-x')
        self.admin = Usuario.objects.create_user(username='jefe', email='jefe@x.com', password='x-2026-gr-x', is_staff=True)

    @override_settings(RIOT_API_KEY='RGAPI-vieja')
    def test_llave_de_riot_caducada(self):
        with mock.patch('usuarios.riot.requests.get', return_value=respuesta(403)), \
             self.assertLogs('gamerival', 'ERROR') as log:
            with self.assertRaises(riot.ErrorRiot) as ctx:
                riot.buscar_cuenta('Nova', 'LAN')
        error = ctx.exception
        self.assertEqual(str(error), riot.NO_DISPONIBLE)
        self.assertNotIn('llave', str(error).lower())
        self.assertIn('RIOT_API_KEY', log.output[0])
        self.assertEqual(mensaje_para(self.yo, error), riot.NO_DISPONIBLE)
        self.assertEqual(mensaje_para(self.admin, error), riot.NO_DISPONIBLE)   # ni el admin lo ve en la pagina

    @override_settings(STEAM_API_KEY='')
    def test_sin_llave_de_steam(self):
        with self.assertLogs('gamerival', 'ERROR'), self.assertRaises(steam.ErrorSteam) as ctx:
            steam.juegos_de('76561198000000000')
        self.assertEqual(str(ctx.exception), steam.NO_DISPONIBLE)

    @override_settings(RIOT_API_KEY='RGAPI-vieja')
    def test_al_actualizar_lol_el_usuario_ve_el_mensaje_amigable(self):
        CuentaVinculada.objects.create(usuario=self.yo, proveedor='riot', id_externo='p' * 78, nombre_visible='Nova#LAN', region='la1')
        self.client.force_login(self.yo)
        with mock.patch('usuarios.riot.requests.get', return_value=respuesta(401)), self.assertLogs('gamerival', 'ERROR'):
            r = self.client.post(reverse('actualizar_estadisticas'), {'plataforma': 'lol'}, follow=True)
        self.assertContains(r, 'no están disponibles por el momento')
        self.assertNotContains(r, 'RIOT_API_KEY')
