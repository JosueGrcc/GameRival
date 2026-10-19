from django.contrib.auth.models import AbstractUser
from django.db import models
from django.conf import settings


class Usuario(AbstractUser):
    email = models.EmailField(unique=True)
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

class CuentaVinculada(models.Model):
    PROVEEDORES = [
        ('steam', 'Steam'),
        ('riot', 'Riot Games'),
    ]

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='cuentas',
    )
    proveedor = models.CharField(max_length=10, choices=PROVEEDORES)
    id_externo = models.CharField(max_length=100)
    nombre_visible = models.CharField(max_length=50)
    region = models.CharField(max_length=10, blank=True)
    fecha_vinculacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['usuario', 'proveedor'], name='una_cuenta_por_proveedor'),
            models.UniqueConstraint(fields=['proveedor', 'id_externo'], name='cuenta_externa_unica'),
        ]

    def __str__(self):
        return f'{self.nombre_visible} ({self.get_proveedor_display()})'

