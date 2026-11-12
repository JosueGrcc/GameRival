from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Insignia


class AdminDeInsigniasTests(TestCase):
    """I001: el admin avisa cuando una insignia no tiene regla (y por eso no sale en la pagina)."""

    def setUp(self):
        self.admin = get_user_model().objects.create_superuser(username='jefe', email='jefe@x.com', password='x-2026-gr-x')
        self.client.force_login(self.admin)

    def test_columna_tiene_regla(self):
        r = self.client.get(reverse('admin:insignias_insignia_changelist'))
        self.assertContains(r, '¿Tiene regla?')

    def test_aviso_al_guardar_insignia_sin_regla(self):
        r = self.client.post(reverse('admin:insignias_insignia_add'), {
            'codigo': 'loco_logros', 'nombre': 'Loco por los Logros',
            'descripcion': 'Consigue 100 logros.', 'icono': '100', 'orden': 9,
        }, follow=True)
        self.assertTrue(Insignia.objects.filter(codigo='loco_logros').exists())
        self.assertContains(r, 'todavía NO aparece en la página')

    def test_sin_aviso_si_tiene_regla(self):
        insignia = Insignia.objects.get(codigo='centenario')
        r = self.client.post(reverse('admin:insignias_insignia_change', args=[insignia.pk]), {
            'codigo': 'centenario', 'nombre': 'Centenario', 'descripcion': insignia.descripcion,
            'icono': '100', 'orden': insignia.orden,
        }, follow=True)
        self.assertNotContains(r, 'todavía NO aparece')

    def test_la_pagina_de_insignias_no_cambia(self):
        Insignia.objects.create(codigo='loco_logros', nombre='Loco por los Logros', descripcion='x', icono='100', orden=9)
        r = self.client.get(reverse('insignias'))
        self.assertNotContains(r, 'Loco por los Logros')
