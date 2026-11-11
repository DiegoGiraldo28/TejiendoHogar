// Mejoras opcionales del proceso de compra; sin JavaScript todo funciona con el servidor.

// Cantidad del detalle de producto: − y + cambian el campo sin recargar la página.
document.querySelectorAll("[data-cantidad]").forEach((control) => {
  const campo = control.querySelector("input[type='number']");
  if (!campo) return;
  control.querySelectorAll("[data-paso]").forEach((boton) => {
    boton.addEventListener("click", (evento) => {
      evento.preventDefault();
      const minimo = Number(campo.min) || 1;
      const maximo = Number(campo.max) || minimo;
      const actual = Number(campo.value) || minimo;
      campo.value = Math.min(maximo, Math.max(minimo, actual + Number(boton.dataset.paso)));
      campo.dispatchEvent(new Event("input", { bubbles: true }));
    });
  });
});

// Formularios de pago: deshabilita los botones al enviar para evitar el doble clic.
// El servidor también protege el doble envío.
document.querySelectorAll("form[data-un-envio]").forEach((formulario) => {
  formulario.addEventListener("submit", (evento) => {
    if (formulario.dataset.enviado) {
      evento.preventDefault();
      return;
    }
    formulario.dataset.enviado = "true";
    const boton = evento.submitter;
    if (boton && boton.name) {
      const oculto = document.createElement("input");
      oculto.type = "hidden";
      oculto.name = boton.name;
      oculto.value = boton.value;
      formulario.append(oculto);
    }
    formulario.querySelectorAll("button[type='submit']").forEach((otro) => {
      otro.disabled = true;
      otro.setAttribute("aria-disabled", "true");
    });
  });
});
