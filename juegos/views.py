from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.urls import reverse
from django.views.decorators.http import require_POST

from usuarios import riot, steam
from usuarios.errores import mensaje_para

from .estadisticas import sincronizar_logros, sincronizar_lol, sincronizar_steam


@login_required
@require_POST
def actualizar(request):
    plataforma = request.POST.get('plataforma', 'steam')
    destino = f"{reverse('inicio')}?plataforma={'lol' if plataforma == 'lol' else 'steam'}"

    if plataforma == 'lol':
        cuenta = request.user.cuentas.filter(proveedor='riot').first()
        if cuenta is None:
            messages.error(request, 'Primero vincula tu Riot ID.')
            return redirect('cuentas')
        try:
            nuevas = sincronizar_lol(cuenta)
        except riot.ErrorRiot as error:
            messages.error(request, mensaje_para(request.user, error))
        else:
            messages.success(request, f'Listo: {nuevas} partidas nuevas de League of Legends.')
        return redirect(destino)

    cuenta = request.user.cuentas.filter(proveedor='steam').first()
    if cuenta is None:
        messages.error(request, 'Primero vincula tu cuenta de Steam.')
        return redirect('cuentas')

    if plataforma == 'logros':
        try:
            cantidad = sincronizar_logros(cuenta)
        except steam.ErrorSteam as error:
            messages.error(request, mensaje_para(request.user, error))
        else:
            if cantidad:
                messages.success(request, f'Listo: {cantidad} logros de tus juegos más jugados.')
            else:
                messages.info(
                    request,
                    'No encontramos logros en tus juegos más jugados. Revisa que en Steam tengas '
                    '"Detalles de juego" en Público y vuelve a intentar.',
                )
        return redirect(f'{destino}#logros')
    try:
        cantidad = sincronizar_steam(cuenta)
    except steam.ErrorSteam as error:
        messages.error(request, mensaje_para(request.user, error))
    else:
        messages.success(request, f'Listo: se actualizaron {cantidad} juegos de Steam.')
    return redirect(destino)