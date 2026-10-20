// Boton del ojito: muestra u oculta la contrasena del campo donde esta.
document.querySelectorAll("[data-ver-contrasena]").forEach(function (boton) {
    boton.addEventListener("click", function () {
        var input = boton.parentElement.querySelector("input");
        var mostrar = input.type === "password";

        input.type = mostrar ? "text" : "password";
        boton.setAttribute("aria-pressed", mostrar);
        boton.setAttribute("aria-label", mostrar ? "Ocultar contraseña" : "Mostrar contraseña");
    });
});

// Portadas e iconos que no cargan: en vez del icono de imagen rota,
// se pone una imagen transparente y queda el fondo de la tarjeta.
var TRANSPARENTE = "data:image/gif;base64,R0lGODlhAQABAAAAACH5BAEKAAEALAAAAAABAAEAAAICTAEAOw==";

function usarRespaldo(imagen) {
    if (imagen.src !== TRANSPARENTE) {
        imagen.src = TRANSPARENTE;
    }
}

document.querySelectorAll("img[data-portada]").forEach(function (imagen) {
    // Si ya fallo antes de que cargara este archivo
    if (imagen.complete && imagen.naturalWidth === 0) {
        usarRespaldo(imagen);
    }
    imagen.addEventListener("error", function () {
        usarRespaldo(imagen);
    });
});

// Formularios que tardan (como Actualizar): al enviarlos se desactiva el boton
// para que no se manden dos veces si la persona da clic otra vez.
document.querySelectorAll("form[data-un-solo-envio]").forEach(function (formulario) {
    formulario.addEventListener("submit", function () {
        var boton = formulario.querySelector("button[type=submit]");
        if (boton) {
            boton.disabled = true;
            boton.textContent = "Actualizando…";
        }
    });
});

// Boton "Copiar": copia el texto del elemento indicado (como el codigo del grupo).
document.querySelectorAll("[data-copiar]").forEach(function (boton) {
    boton.addEventListener("click", function () {
        var texto = document.querySelector(boton.dataset.copiar).textContent.trim();
        navigator.clipboard.writeText(texto).then(function () {
            boton.textContent = "¡Copiado!";
            setTimeout(function () { boton.textContent = "Copiar"; }, 2000);
        });
    });
});

// Formularios que piden confirmacion antes de enviarse (como Salir del grupo).
document.querySelectorAll("form[data-confirmar]").forEach(function (formulario) {
    formulario.addEventListener("submit", function (evento) {
        if (!window.confirm(formulario.dataset.confirmar)) {
            evento.preventDefault();
        }
    });
});
