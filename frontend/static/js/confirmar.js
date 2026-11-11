// Mejora el enlace de confirmación con el diálogo nativo; mantiene el respaldo GET.
document.querySelectorAll("[data-open-confirm]").forEach((boton) => {
  const contenedor = boton.closest("[data-confirm-container]");
  const dialogo = contenedor?.querySelector("dialog");
  if (!dialogo) return;
  boton.hidden = false;
  contenedor.querySelector("[data-fallback-delete]").hidden = true;
  boton.addEventListener("click", () => dialogo.showModal());
  dialogo.querySelector("[data-close-confirm]").addEventListener("click", () => dialogo.close());
});

// Variante de un solo control: el enlace a la página de confirmación abre el diálogo si hay JavaScript.
document.querySelectorAll("[data-confirm-link]").forEach((enlace) => {
  const dialogo = enlace.closest("[data-confirm-container]")?.querySelector("dialog");
  if (!dialogo || typeof dialogo.showModal !== "function") return;
  enlace.setAttribute("aria-haspopup", "dialog");
  enlace.addEventListener("click", (evento) => {
    evento.preventDefault();
    dialogo.showModal();
  });
  dialogo.querySelector("[data-close-confirm]")?.addEventListener("click", () => dialogo.close());
});
