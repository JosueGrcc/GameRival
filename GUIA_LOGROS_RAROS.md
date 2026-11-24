# Guía: logros más raros de Steam en GameRival

Esta guía es la parte de Python. Las plantillas y el CSS ya están en tu carpeta:

- `templates/perfil/steam.html`: sección nueva "Mis logros más raros" con filtros.
- `templates/grupos/detalle.html`: pestaña "Logros" en el grupo y lista de los logros más difíciles de todos.
- `templates/partes/logro.html` (nuevo): cómo se dibuja cada logro.
- `static/css/gamerival.css`: estilos de los logros, al final antes de las pantallas medianas.

Todo esto ya lo probé en una copia del proyecto: las 24 pruebas que ya tenías siguen pasando y agregué 7 nuevas. Si copias el código tal cual, te debe dar lo mismo.

## Cómo funciona la idea

Steam no te dice directamente cuáles son tus logros más difíciles. Hay que juntar tres cosas por cada juego:

1. **`GetPlayerAchievements`**: qué logros desbloqueaste tú y cuándo.
2. **`GetSchemaForGame`**: el nombre, la descripción y el icono de cada logro (en español, con `l=spanish`).
3. **`GetGlobalAchievementPercentagesForApp`**: qué porcentaje de todos los jugadores tiene cada logro. Esta no necesita llave.

Se cruzan las tres y cada logro tuyo queda con su porcentaje. Entre más bajo el porcentaje, más difícil: si un logro tiene 0.8%, solo 8 de cada 1000 jugadores lo tienen.

Como son tres llamadas **por juego**, no se revisa toda tu biblioteca, solo tus 10 juegos más jugados. Por eso es un botón aparte ("Actualizar logros") y no va dentro del Actualizar normal: tarda unos segundos.

Para comparar en el grupo se usa la **rareza promedio**: el promedio del porcentaje de tus 10 logros más difíciles. Aquí gana el número **más bajo**, al revés que en las demás pestañas.

---

## Paso 1. El modelo (`juegos/models.py`)

Pega esto al final del archivo:

```python
class LogroSteam(models.Model):
    """Un logro de Steam que la persona ya desbloqueo, con que tan raro es."""
    cuenta = models.ForeignKey(
        'usuarios.CuentaVinculada',
        on_delete=models.CASCADE,
        related_name='logros',
    )
    juego = models.ForeignKey(Juego, on_delete=models.CASCADE, related_name='logros')
    clave = models.CharField(max_length=100, help_text='Nombre interno del logro en Steam (apiname)')
    nombre = models.CharField(max_length=150)
    descripcion = models.CharField(max_length=255, blank=True)
    icono_url = models.URLField(max_length=300, blank=True)
    rareza = models.DecimalField(
        max_digits=5, decimal_places=2,
        help_text='Porcentaje de jugadores de ese juego que tienen el logro. Menos = mas dificil.',
    )
    fecha = models.DateTimeField(null=True, blank=True, help_text='Cuando lo desbloqueo')

    class Meta:
        ordering = ['rareza', '-fecha']
        constraints = [
            models.UniqueConstraint(fields=['cuenta', 'juego', 'clave'], name='logro_unico_por_cuenta'),
        ]

    def __str__(self):
        return f'{self.nombre} ({self.rareza}%)'

    @property
    def nivel(self):
        """Que tan raro es, en palabras. Se usa para el color de la etiqueta."""
        if self.rareza < 1:
            return 'ultra'
        if self.rareza < 5:
            return 'muy-raro'
        if self.rareza < 10:
            return 'raro'
        return 'comun'
```

Lo que hay que entender:

- **`cuenta` y `juego`**: los logros se ligan a tu cuenta de Steam y al juego, igual que las fotos de estadísticas.
- **`clave`**: el nombre interno que usa Steam (por ejemplo `ACH_DEAD_GOD`). Con eso se cruzan las tres llamadas.
- **`rareza`**: el porcentaje. Es `DecimalField` y no `FloatField` para que no salgan cosas como `0.8000000001`.
- **`UniqueConstraint`**: no deja que el mismo logro se guarde dos veces para la misma cuenta.
- **`ordering = ['rareza', ...]`**: cuando pides logros, vienen del más raro al más común sin que lo tengas que pedir.
- **`nivel`**: no se guarda en la base. Es una propiedad que regresa `ultra`, `muy-raro`, `raro` o `comun`, y la plantilla la usa para el color (oro, morado, azul o gris).

Después crea la tabla en MySQL:

```
python manage.py makemigrations juegos
python manage.py migrate
```

Te debe crear algo como `juegos/migrations/0003_logrosteam.py`.

## Paso 2. Que se vea en el panel de admin (`juegos/admin.py`)

En el import agrega `LogroSteam`:

```python
from .models import EstadisticaSnapshot, Juego, LogroSteam, MetricaSnapshot, PartidaLoL
```

Y al final:

```python
@admin.register(LogroSteam)
class LogroSteamAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'juego', 'cuenta', 'rareza', 'fecha')
    list_filter = ('juego',)
    search_fields = ('nombre', 'juego__nombre', 'cuenta__nombre_visible')
```

Así en `/admin/` ves los logros en una tabla con columnas, un filtro por juego y un buscador.

## Paso 3. Hablar con Steam (`usuarios/steam.py`)

Pega esto al final del archivo:

```python
# ===================== Logros =====================

def _pedir(ruta, parametros, con_llave=True):
    """GET a la API de Steam. Regresa (codigo_http, json). Si no hay conexion lanza ErrorSteam."""
    if con_llave:
        if not settings.STEAM_API_KEY:
            raise ErrorSteam(NO_DISPONIBLE, 'Falta STEAM_API_KEY en el archivo .env.')
        parametros = {'key': settings.STEAM_API_KEY, **parametros}
    try:
        respuesta = requests.get(f'{STEAM_API}/{ruta}', params=parametros, timeout=15)
    except requests.RequestException:
        raise ErrorSteam('No pudimos comunicarnos con Steam. Intenta de nuevo en un momento.', 'Sin conexion con api.steampowered.com.')
    if respuesta.status_code == 401:
        raise ErrorSteam(NO_DISPONIBLE, 'Steam rechazo la STEAM_API_KEY (HTTP 401). Revisa la del .env.')
    try:
        datos = respuesta.json()
    except ValueError:
        datos = {}
    return respuesta.status_code, datos


def logros_de(steam_id, app_id):
    """Los logros que la persona YA desbloqueo en un juego: [{'clave', 'fecha'}].

    Si el juego no tiene logros, Steam responde con error 400; eso no es un problema,
    simplemente se regresa una lista vacia.
    """
    codigo, datos = _pedir('ISteamUserStats/GetPlayerAchievements/v1/', {'steamid': steam_id, 'appid': app_id})
    estadisticas = datos.get('playerstats', {})

    if codigo == 403 or 'not public' in str(estadisticas.get('error', '')).lower():
        raise ErrorSteam(
            'Steam no nos deja ver tus logros. En Steam, ve a tu perfil > Editar perfil > '
            'Privacidad y pon "Detalles de juego" en Público.'
        )
    if codigo != 200 or not estadisticas.get('success'):
        return []  # el juego no tiene logros

    return [
        {'clave': logro['apiname'], 'fecha': logro.get('unlocktime') or None}
        for logro in estadisticas.get('achievements', [])
        if logro.get('achieved')
    ]


def info_de_logros(app_id):
    """Nombre, descripcion e icono de cada logro del juego, en espanol: {clave: {...}}."""
    codigo, datos = _pedir('ISteamUserStats/GetSchemaForGame/v2/', {'appid': app_id, 'l': 'spanish'})
    if codigo != 200:
        return {}
    logros = datos.get('game', {}).get('availableGameStats', {}).get('achievements', [])
    return {
        logro['name']: {
            'nombre': logro.get('displayName') or logro['name'],
            'descripcion': logro.get('description', ''),
            'icono': logro.get('icon', ''),
        }
        for logro in logros
    }


def rareza_de_logros(app_id):
    """Que porcentaje de los jugadores tiene cada logro: {clave: 12.5}. No necesita llave."""
    codigo, datos = _pedir(
        'ISteamUserStats/GetGlobalAchievementPercentagesForApp/v2/',
        {'gameid': app_id},
        con_llave=False,
    )
    if codigo != 200:
        return {}
    logros = datos.get('achievementpercentages', {}).get('achievements', [])
    # Steam a veces manda el porcentaje como texto ("12.5"), por eso el float()
    return {logro['name']: float(logro['percent']) for logro in logros}
```

Lo que hay que entender:

- **`_pedir`** es un ayudante para no repetir lo mismo en las tres funciones: pone la llave, hace la petición y si no hay internet lanza `ErrorSteam` con el mensaje amigable (lo mismo que hicimos en la corrección P001). El guion bajo al inicio del nombre quiere decir "esta función es de uso interno de este archivo".
- **`logros_de`**: cuando un juego no tiene logros, Steam responde con error 400. Eso es normal, así que se regresa una lista vacía en lugar de marcar error. El único error real es el 403, que quiere decir que tu perfil es privado, y para ese sí se le dice al usuario qué hacer.
- **`info_de_logros`** usa `l: 'spanish'` para que los nombres salgan en español cuando el juego los tiene traducidos.
- **`rareza_de_logros`**: Steam a veces manda el porcentaje como texto (`"12.5"`) y a veces como número. El `float()` lo convierte en los dos casos.

## Paso 4. Guardar y consultar los logros (`juegos/estadisticas.py`)

En el import de modelos agrega `LogroSteam`:

```python
from .models import EstadisticaSnapshot, Juego, LogroSteam, MetricaSnapshot, PartidaLoL
```

Y pega esto **justo antes** de la línea `# ===================== League of Legends =====================`:

```python
# ===================== Logros de Steam =====================

JUEGOS_CON_LOGROS = 10   # solo se revisan tus juegos mas jugados, porque es una llamada por juego
LOGROS_PARA_PROMEDIO = 10

# Filtro de rareza: clave -> (texto, porcentaje maximo)
RAREZAS = {
    'todos': ('Todos', None),
    'raros': ('Raros (menos de 10%)', 10),
    'muy_raros': ('Muy raros (menos de 5%)', 5),
    'ultra': ('Ultra raros (menos de 1%)', 1),
}


def sincronizar_logros(cuenta, cuantos=JUEGOS_CON_LOGROS):
    """Baja los logros desbloqueados de tus juegos mas jugados. Regresa cuantos logros guardo."""
    juegos = [fila['juego'] for fila in ultimas_estadisticas(cuenta.usuario)[:cuantos]]

    nuevos = []
    for juego in juegos:
        obtenidos = steam.logros_de(cuenta.id_externo, juego.id_externo)
        if not obtenidos:
            continue  # el juego no tiene logros o no has sacado ninguno
        info = steam.info_de_logros(juego.id_externo)
        rareza = steam.rareza_de_logros(juego.id_externo)

        for logro in obtenidos:
            clave = logro['clave']
            if clave not in rareza:
                continue  # sin porcentaje no se puede saber que tan dificil es
            datos = info.get(clave, {})
            nuevos.append(LogroSteam(
                cuenta=cuenta,
                juego=juego,
                clave=clave[:100],
                nombre=(datos.get('nombre') or clave)[:150],
                descripcion=(datos.get('descripcion') or '')[:255],
                icono_url=(datos.get('icono') or '')[:300],
                rareza=Decimal(str(rareza[clave])).quantize(Decimal('0.01')),
                fecha=datetime.fromtimestamp(logro['fecha'], tz=zona_utc.utc) if logro['fecha'] else None,
            ))

    # Se borran los logros viejos de esos juegos y se guardan los nuevos de un jalon
    with transaction.atomic():
        cuenta.logros.filter(juego__in=juegos).delete()
        LogroSteam.objects.bulk_create(nuevos)
        _marcar_actualizada(cuenta)

    return len(nuevos)


def logros_de_usuarios(usuarios, rareza='todos', juego_id=None):
    """Logros de una o varias personas, del mas dificil al mas facil, con el filtro aplicado."""
    logros = (
        LogroSteam.objects
        .filter(cuenta__usuario__in=usuarios)
        .select_related('juego', 'cuenta__usuario')
        .order_by('rareza', '-fecha')
    )
    maximo = RAREZAS.get(rareza, RAREZAS['todos'])[1]
    if maximo is not None:
        logros = logros.filter(rareza__lt=maximo)
    if juego_id:
        logros = logros.filter(juego_id=juego_id)
    return logros


def rareza_promedio(usuario):
    """Promedio de rareza de tus 10 logros mas dificiles. None si no tienes logros.

    Entre MAS BAJO, mas dificiles son tus logros: un 2% quiere decir que, en promedio,
    solo 2 de cada 100 jugadores tienen esos logros.
    """
    valores = list(
        LogroSteam.objects
        .filter(cuenta__usuario=usuario)
        .order_by('rareza')
        .values_list('rareza', flat=True)[:LOGROS_PARA_PROMEDIO]
    )
    if not valores:
        return None
    return (sum(valores) / len(valores)).quantize(Decimal('0.01'))
```

Lo que hay que entender:

- **`RAREZAS`** es el filtro. Cada opción tiene el texto que se ve en la lista desplegable y el porcentaje máximo. "Todos" tiene `None` porque no filtra nada. Si quieres otro nivel, como "menos de 20%", solo agregas una línea aquí y aparece solo en el perfil y en el grupo.
- **`sincronizar_logros`** toma tus 10 juegos con más horas, pide los logros de cada uno y los cruza con su porcentaje. Si un logro no trae porcentaje, se salta, porque sin eso no se puede saber qué tan difícil es.
- Al final **borra los logros viejos de esos juegos y guarda los nuevos de un jalón** (`bulk_create`). Así, si le das Actualizar dos veces, no se duplican. Todo va dentro de `transaction.atomic()`: si algo falla a la mitad, no se queda la mitad borrada.
- **`logros_de_usuarios`** recibe una **lista** de usuarios. En el perfil le pasas solo a ti (`[request.user]`) y en el grupo a todos los miembros, así que la misma función sirve para las dos pantallas. `rareza__lt=maximo` quiere decir "rareza menor que el máximo" (`lt` es *less than*).
- **`rareza_promedio`** toma tus 10 logros más raros (ya vienen ordenados) y saca el promedio. Si no tienes logros regresa `None`, y así el ranking te pone en "Sin datos" en lugar de con 0%, que te haría ganar sin tener nada.

## Paso 5. El botón "Actualizar logros" (`juegos/views.py`)

En el import:

```python
from .estadisticas import sincronizar_logros, sincronizar_lol, sincronizar_steam
```

En la función `actualizar`, después de la parte que busca la cuenta de Steam (el `if cuenta is None: ... return redirect('cuentas')`) y **antes** del `try:` que llama a `sincronizar_steam`, pega:

```python
    if plataforma == 'logros':
        try:
            cantidad = sincronizar_logros(cuenta)
        except steam.ErrorSteam as error:
            messages.error(request, mensaje_para(request.user, error))
        else:
            messages.success(request, f'Listo: {cantidad} logros de tus juegos más jugados.')
        return redirect(f'{destino}#logros')
```

El botón de la plantilla manda `plataforma=logros`. Si llega eso, se bajan los logros y se regresa al perfil. El `#logros` al final de la dirección hace que la página baje sola hasta la sección de logros.

## Paso 6. Los logros en tu perfil (`usuarios/views.py`)

Cambia el import de `juegos.estadisticas` por estos dos:

```python
from juegos.models import Juego
from juegos.estadisticas import RAREZAS, logros_de_usuarios, perfil_lol, rareza_promedio, ultimas_estadisticas
```

En la función `inicio`, dentro del `else:` (la parte de Steam), después del `contexto.update({...})` que ya tienes, pega:

```python
        # Logros mas raros, con los filtros que eligio la persona
        rareza = request.GET.get('rareza', 'todos')
        if rareza not in RAREZAS:
            rareza = 'todos'
        juego_id = request.GET.get('juego', '')
        juego_id = int(juego_id) if juego_id.isdigit() else None

        mis_logros = logros_de_usuarios([request.user])
        contexto.update({
            'rarezas': RAREZAS,
            'rareza': rareza,
            'juego_filtro': juego_id,
            'juegos_con_logros': Juego.objects.filter(logros__cuenta__usuario=request.user).distinct().order_by('nombre'),
            'logros': logros_de_usuarios([request.user], rareza, juego_id)[:12],
            'total_logros': mis_logros.count(),
            'rareza_promedio': rareza_promedio(request.user),
        })
```

Lo que hay que entender:

- Los filtros llegan en la dirección: `/?plataforma=steam&rareza=ultra&juego=5`. Por eso se leen con `request.GET`.
- Nunca confíes en lo que viene en la dirección: si alguien escribe `rareza=loquesea`, se regresa a `todos`. Y el juego solo se usa si es un número (`isdigit()`).
- **`juegos_con_logros`** es la lista para el filtro de juego. Solo salen los juegos donde tienes logros, para que no aparezcan opciones vacías. El `distinct()` es para que cada juego salga una sola vez.
- **`[:12]`**: en el perfil solo se muestran los 12 más raros, para que la página no quede kilométrica.

## Paso 7. La pestaña "Logros" en el ranking (`grupos/ranking.py`)

Son cuatro cambios chicos.

**a)** En el import agrega `rareza_promedio`:

```python
from juegos.estadisticas import numero_a_rango, rareza_promedio, ultimas_estadisticas
```

**b)** En el diccionario `METRICAS`, después de `'lol_kda'`, agrega:

```python
    # orden 'menor': aqui gana el numero MAS BAJO (menos % de jugadores = logro mas dificil)
    'steam_logros': {
        'titulo': 'Logros',
        'detalle': 'Promedio de rareza de sus 10 logros más difíciles. Entre menos %, más difíciles',
        'periodo': 'general',
        'orden': 'menor',
    },
```

Con solo agregarlo aquí ya aparece la pestaña en el grupo, porque la plantilla dibuja una pestaña por cada métrica del diccionario.

**c)** En `valor_de`, justo después del texto `"""El numero con el que se compara..."""`, agrega:

```python
    if metrica == 'steam_logros':
        return rareza_promedio(usuario)
```

Y en `como_texto`, después del `if` de `lol_winrate`:

```python
    if metrica == 'steam_logros':
        return f'{valor:.2f}%'
```

**d)** En `calcular_ranking` está el cambio más importante. Hasta ahora siempre ganaba el número más alto (`reverse=True`). Aquí gana el más bajo. Cambia el `sorted(...)` y la línea de `mas_alto` por esto:

```python
    gana_el_menor = METRICAS[metrica].get('orden') == 'menor'
    con_datos = sorted(
        (fila for fila in filas if fila['valor'] is not None),
        key=lambda fila: fila['valor'],
        reverse=not gana_el_menor,
    )
    sin_datos = [fila for fila in filas if fila['valor'] is None]

    mejor = con_datos[0]['valor'] if con_datos else 0
```

Y la línea de `fila['porcentaje'] = ...` (la altura de la barra) por:

```python
        # Altura de la barra: el mejor tiene la barra completa
        if gana_el_menor:
            fila['porcentaje'] = round(mejor / fila['valor'] * 100) if fila['valor'] else 100
        else:
            fila['porcentaje'] = round(fila['valor'] / mejor * 100) if mejor else 0
```

Por qué la división está al revés: si tú tienes 2% y tu amigo 8%, tú vas ganando, así que tu barra debe ser la más alta. `2 / 2 = 100%` para ti y `2 / 8 = 25%` para él. `.get('orden')` regresa `None` en las demás métricas, así que esas siguen funcionando igual que antes.

## Paso 8. El grupo (`grupos/views.py`)

Arriba, con los imports:

```python
from juegos.estadisticas import RAREZAS, logros_de_usuarios
```

En `detalle`, antes del `return render(...)`, pega:

```python
    # Pestana de logros: el logro mas dificil de cada quien y la lista de todo el grupo
    logros_grupo = None
    rareza = request.GET.get('rareza', 'todos')
    if rareza not in RAREZAS:
        rareza = 'todos'
    if metrica == 'steam_logros':
        usuarios = [membresia.usuario for membresia in membresias]
        mas_dificil = {}
        for logro in logros_de_usuarios(usuarios):
            mas_dificil.setdefault(logro.cuenta.usuario_id, logro)  # ya vienen ordenados
        for fila in ranking:
            fila['logro'] = mas_dificil.get(fila['usuario'].id)
        logros_grupo = logros_de_usuarios(usuarios, rareza)[:15]
```

Y dentro del diccionario del `render(...)` agrega estas tres líneas:

```python
        'rarezas': RAREZAS,
        'rareza': rareza,
        'logros_grupo': logros_grupo,
```

Lo que hay que entender:

- Solo se calcula si estás en la pestaña de logros, para no hacer consultas de más en las otras pestañas.
- **`mas_dificil`**: como los logros vienen ordenados del más raro al más común, el **primero** que aparece de cada persona es su más difícil. `setdefault` guarda solo el primero y los siguientes los ignora. Eso es lo que sale abajo del nombre en el ranking ("Su más difícil: ...").
- **`logros_grupo`**: la lista de los 15 logros más difíciles de todo el grupo, con el filtro de rareza aplicado. Aquí es donde comparas tus logros con los de tus amigos: cada logro dice de quién es.

## Paso 9 (opcional). El comando `actualizar_todo`

Si quieres que el comando también baje los logros de todos antes de la presentación, en `juegos/management/commands/actualizar_todo.py`:

- En el import agrega `sincronizar_logros`.
- En `add_arguments` agrega:

```python
        parser.add_argument(
            '--logros', action='store_true',
            help='Tambien bajar los logros de Steam (tarda mas: una llamada por juego).',
        )
```

- En `handle` agrega `logros=False` a los parámetros, y después de `cantidad = SINCRONIZAR[cuenta.proveedor](cuenta)`:

```python
                if logros and cuenta.proveedor == 'steam':
                    sincronizar_logros(cuenta)
```

Se usa así: `python manage.py actualizar_todo --logros`. Sin `--logros` funciona igual que antes.

## Paso 10. Las pruebas (`juegos/tests.py`)

Pega esto al final del archivo:

```python
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
```

Las pruebas **no** se conectan a Steam. Con `mock.patch` se reemplazan las tres funciones de `steam.py` por versiones falsas que siempre regresan lo mismo. Así se prueba tu lógica (que se cruce bien, que no se dupliquen, que gane el menor) sin depender de internet ni de tu llave.

Corre todo:

```
python manage.py test
```

Te debe salir **`Ran 31 tests ... OK`**: tus 24 de antes y 7 nuevas.

## Paso 11. Probarlo de verdad

1. Prende MySQL y corre `python manage.py runserver`.
2. En Steam revisa que tu perfil tenga **Detalles de juego en Público** (Perfil > Editar perfil > Privacidad). Si no, te sale el aviso de privacidad.
3. Entra a tu perfil, pestaña Steam, baja hasta "Mis logros más raros" y dale **Actualizar logros**. Tarda unos segundos.
4. Prueba los filtros de rareza y de juego.
5. Entra a tu grupo y dale a la pestaña **Logros**. Para que haya con quién compararte, tus amigos también tienen que darle Actualizar logros en su perfil.

Si `GetSchemaForGame` tarda mucho o algún juego no trae nombres en español, el logro sale con su clave interna. No es error, así lo manda Steam.
