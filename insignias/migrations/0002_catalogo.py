from django.db import migrations

CATALOGO = [
    # (codigo, nombre, descripcion, icono)
    ('primer_paso', 'Primer paso', 'Vincula tu primera cuenta de juegos.', '1'),
    ('doble_vida', 'Doble vida', 'Ten Steam y Riot vinculados al mismo tiempo.', 'x2'),
    ('centenario', 'Centenario', 'Juega 100 horas un solo juego de Steam.', '100'),
    ('maraton', 'Maratón', 'Juega 20 horas en Steam en dos semanas.', '20h'),
    ('racha_25', 'Racha de 25', 'Gana 25 partidas de League of Legends.', '25'),
    ('inmortal', 'Inmortal', 'Gana una partida de LoL sin morir ni una vez.', '0'),
    ('top_1', 'Top 1', 'Queda en primer lugar de horas en Steam en un grupo.', '#1'),
    ('lider', 'Líder de gremio', 'Crea un grupo y llega a 5 miembros.', '5'),
]


def crear_catalogo(apps, schema_editor):
    Insignia = apps.get_model('insignias', 'Insignia')
    for orden, (codigo, nombre, descripcion, icono) in enumerate(CATALOGO):
        Insignia.objects.update_or_create(
            codigo=codigo,
            defaults={'nombre': nombre, 'descripcion': descripcion, 'icono': icono, 'orden': orden},
        )


def borrar_catalogo(apps, schema_editor):
    Insignia = apps.get_model('insignias', 'Insignia')
    Insignia.objects.filter(codigo__in=[fila[0] for fila in CATALOGO]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('insignias', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(crear_catalogo, borrar_catalogo),
    ]