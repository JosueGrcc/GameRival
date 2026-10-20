from django.conf import settings
from django.db import models


class Insignia(models.Model):
    codigo = models.SlugField(max_length=30, unique=True)
    nombre = models.CharField(max_length=30)
    descripcion = models.CharField(max_length=150)
    icono = models.CharField(max_length=4, help_text='Texto corto que va dentro del circulo, como "100"')
    orden = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['orden']

    def __str__(self):
        return self.nombre


class InsigniaObtenida(models.Model):
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='insignias')
    insignia = models.ForeignKey(Insignia, on_delete=models.CASCADE, related_name='obtenidas')
    grupo = models.ForeignKey('grupos.Grupo', on_delete=models.SET_NULL, null=True, blank=True,
                              related_name='insignias_ganadas')
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-fecha']
        constraints = [
            models.UniqueConstraint(fields=['usuario', 'insignia'], name='insignia_unica_por_usuario'),
        ]

    def __str__(self):
        return f'{self.usuario} - {self.insignia}'