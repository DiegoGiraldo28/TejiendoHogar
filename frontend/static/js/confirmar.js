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
