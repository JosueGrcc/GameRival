from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from . import riot, steam
from .forms import RegistroForm, RiotForm
from .models import CuentaVinculada
from juegos.estadisticas import perfil_lol, ultimas_estadisticas
from insignias.reglas import revisar_insignias
from insignias.views import avisar_nuevas


class IniciarSesionView(LoginView):
    template_name = 'usuarios/login.html'
    redirect_authenticated_user = True

    def form_valid(self, form):
        if not self.request.POST.get('recordarme'):
            self.request.session.set_expiry(0)
        return super().form_valid(form)


def registro(request):
    if request.user.is_authenticated:
        return redirect('inicio')

    if request.method == 'POST':
        form = RegistroForm(request.POST)
        if form.is_valid():
            usuario = form.save()
            login(request, usuario)
            return redirect('inicio')
    else:
        form = RegistroForm()

    return render(request, 'usuarios/registro.html', {'form': form})


@login_required
def inicio(request):
    plataforma = request.GET.get('plataforma', 'steam')
    if plataforma not in ('steam', 'lol'):
        plataforma = 'steam'

    progreso, nuevas = revisar_insignias(request.user)
    avisar_nuevas(request, nuevas)
    contexto = {
        'plataforma': plataforma,
        'insignias_obtenidas': sum(1 for fila in progreso if fila['obtenida']),
        'insignias_total': len(progreso),
    }

    if plataforma == 'lol':
        cuenta_riot = request.user.cuentas.filter(proveedor='riot').first()
        contexto['cuenta_riot'] = cuenta_riot
        if cuenta_riot:
            contexto['lol'] = perfil_lol(cuenta_riot)
    else:
        filas = ultimas_estadisticas(request.user)
        mas_horas = filas[0]['horas'] if filas else 0
        for fila in filas:
            fila['porcentaje'] = round(fila['horas'] / mas_horas * 100) if mas_horas else 0

        contexto.update({
            'steam': request.user.cuentas.filter(proveedor='steam').first(),
            'juegos': filas,
            'total_juegos': len(filas),
            'horas_totales': sum(fila['horas'] for fila in filas),
            'horas_recientes': sum(fila['horas_recientes'] for fila in filas),
            'actualizado': max((fila['fecha'] for fila in filas), default=None),
        })

    return render(request, 'inicio.html', contexto)
# ---------------- Cuentas vinculadas ----------------

def _pagina_cuentas(request, riot_form=None):
    cuentas = {cuenta.proveedor: cuenta for cuenta in request.user.cuentas.all()}
    return render(request, 'usuarios/cuentas.html', {
        'steam': cuentas.get('steam'),
        'riot': cuentas.get('riot'),
        'riot_form': riot_form or RiotForm(),
    })


def _vincular(request, proveedor, id_externo, nombre_visible, region=''):
    """Guarda la cuenta. Regresa False si ya la tiene otra persona."""
    ocupada = (
        CuentaVinculada.objects
        .filter(proveedor=proveedor, id_externo=id_externo)
        .exclude(usuario=request.user)
        .exists()
    )
    if ocupada:
        return False

    CuentaVinculada.objects.update_or_create(
        usuario=request.user,
        proveedor=proveedor,
        defaults={'id_externo': id_externo, 'nombre_visible': nombre_visible[:50], 'region': region},
    )
    return True


@login_required
def cuentas(request):
    return _pagina_cuentas(request)


@login_required
def steam_conectar(request):
    url_regreso = request.build_absolute_uri(reverse('steam_regreso'))
    url_sitio = request.build_absolute_uri('/')
    return redirect(steam.url_login(url_regreso, url_sitio))


@login_required
def steam_regreso(request):
    steam_id = steam.verificar(request.GET)
    if steam_id is None:
        messages.error(request, 'No pudimos confirmar tu cuenta de Steam. Intenta de nuevo.')
        return redirect('cuentas')

    nombre = steam.nombre_de_perfil(steam_id) or f'Steam {steam_id[-4:]}'
    if _vincular(request, 'steam', steam_id, nombre):
        messages.success(request, f'Cuenta de Steam "{nombre}" vinculada.')
    else:
        messages.error(request, 'Esa cuenta de Steam ya está vinculada a otro usuario de GameRival.')
    return redirect('cuentas')


@login_required
@require_POST
def riot_conectar(request):
    form = RiotForm(request.POST)
    if not form.is_valid():
        return _pagina_cuentas(request, form)

    try:
        cuenta = riot.buscar_cuenta(form.nombre, form.tag)
    except riot.ErrorRiot as error:
        form.add_error(None, str(error))
        return _pagina_cuentas(request, form)

    nombre = f"{cuenta['gameName']}#{cuenta['tagLine']}"
    if _vincular(request, 'riot', cuenta['puuid'], nombre, form.cleaned_data['region']):
        messages.success(request, f'Riot ID "{nombre}" vinculado.')
    else:
        messages.error(request, 'Ese Riot ID ya está vinculado a otro usuario de GameRival.')
    return redirect('cuentas')


@login_required
@require_POST
def desconectar(request, proveedor):
    borradas, _ = request.user.cuentas.filter(proveedor=proveedor).delete()
    if borradas:
        messages.success(request, 'Cuenta desvinculada.')
    return redirect('cuentas')