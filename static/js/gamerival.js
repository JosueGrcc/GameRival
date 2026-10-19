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
