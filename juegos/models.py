from django.db import models


class Juego(models.Model):
    PLATAFORMAS = [
        ('steam', 'Steam'),
        ('riot', 'Riot Games'),
    ]

    nombre = models.CharField(max_length=100)
    plataforma = models.CharField(max_length=10, choices=PLATAFORMAS)
    id_externo = models.CharField(max_length=50)
    imagen_url = models.URLField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['plataforma', 'id_externo'], name='juego_unico_por_plataforma'),
        ]

    def __str__(self):
        return self.nombre


class EstadisticaSnapshot(models.Model):
    cuenta = models.ForeignKey(
        'usuarios.CuentaVinculada',
        on_delete=models.CASCADE,
        related_name='snapshots',
    )
    juego = models.ForeignKey(Juego, on_delete=models.CASCADE, related_name='snapshots')
    fecha = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.cuenta} - {self.juego} ({self.fecha:%d/%m/%Y})'


class MetricaSnapshot(models.Model):
    snapshot = models.ForeignKey(
        EstadisticaSnapshot,
        on_delete=models.CASCADE,
        related_name='metricas',
    )
    nombre = models.CharField(max_length=50)
    valor = models.DecimalField(max_digits=14, decimal_places=2)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['snapshot', 'nombre'], name='metrica_unica_por_snapshot'),
        ]

    def __str__(self):
        return f'{self.nombre}: {self.valor}'

class PartidaLoL(models.Model):
    COLAS = {
        420: 'Clasificatoria Solo/Dúo',
        440: 'Clasificatoria Flexible',
        400: 'Normal',
        430: 'Normal',
        490: 'Partida rápida',
        450: 'ARAM',
        1700: 'Arena',
    }

    cuenta = models.ForeignKey(
        'usuarios.CuentaVinculada',
        on_delete=models.CASCADE,
        related_name='partidas_lol',
    )
    id_partida = models.CharField(max_length=30)
    fecha = models.DateTimeField()
    cola = models.PositiveIntegerField()
    duracion = models.PositiveIntegerField(help_text='En segundos')
    campeon = models.CharField(max_length=30)
    campeon_id = models.PositiveIntegerField()
    victoria = models.BooleanField()
    asesinatos = models.PositiveSmallIntegerField()
    muertes = models.PositiveSmallIntegerField()
    asistencias = models.PositiveSmallIntegerField()

    class Meta:
        ordering = ['-fecha']
        constraints = [
            models.UniqueConstraint(fields=['cuenta', 'id_partida'], name='partida_unica_por_cuenta'),
        ]

    def __str__(self):
        return f'{self.campeon} ({"Victoria" if self.victoria else "Derrota"})'

    @property
    def nombre_cola(self):
        return self.COLAS.get(self.cola, 'Otra modalidad')

    @property
    def kda(self):
        return (self.asesinatos + self.asistencias) / max(self.muertes, 1)

    @property
    def minutos(self):
        return self.duracion // 60