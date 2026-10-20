import secrets

from django.conf import settings
from django.db import models

# Sin letras que se confunden entre si (O y 0, I y 1)
ALFABETO_CODIGO = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'


def generar_codigo():
    """Un codigo de invitacion al azar, como 'K7QX2M'."""
    return ''.join(secrets.choice(ALFABETO_CODIGO) for _ in range(6))


class Grupo(models.Model):
    nombre = models.CharField(max_length=50)
    codigo = models.CharField(max_length=6, unique=True, default=generar_codigo)
    creador = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='grupos_creados',
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    miembros = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through='MiembroGrupo',
        related_name='grupos',
    )

    def __str__(self):
        return self.nombre


class MiembroGrupo(models.Model):
    ROLES = [
        ('admin', 'Administrador'),
        ('miembro', 'Miembro'),
    ]

    grupo = models.ForeignKey(Grupo, on_delete=models.CASCADE, related_name='membresias')
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='membresias',
    )
    rol = models.CharField(max_length=10, choices=ROLES, default='miembro')
    fecha_union = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['fecha_union']
        constraints = [
            models.UniqueConstraint(fields=['grupo', 'usuario'], name='miembro_unico_por_grupo'),
        ]

    def __str__(self):
        return f'{self.usuario} en {self.grupo}'
