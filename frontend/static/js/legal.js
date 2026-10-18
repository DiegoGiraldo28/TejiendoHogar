// Abre páginas legales en un diálogo y mantiene el enlace normal como respaldo.
const dialogoLegal = document.querySelector("#dialogo-legal");

document.querySelectorAll("[data-legal-modal]").forEach((enlace) => {
  enlace.addEventListener("click", async (evento) => {
    if (!dialogoLegal || !dialogoLegal.showModal) return;
    evento.preventDefault();
    const url = new URL(enlace.href);
    url.searchParams.set("modal", "1");
    let respuesta;
    try {
      respuesta = await fetch(url);
    } catch {
      window.location.href = enlace.href;
      return;
    }
    if (!respuesta.ok) {
      window.location.href = enlace.href;
      return;
    }
    const documento = new DOMParser().parseFromString(await respuesta.text(), "text/html");
    const contenido = documento.querySelector(".legal-content");
    if (!contenido) {
      window.location.href = enlace.href;
      return;
    }
    dialogoLegal.querySelector("[data-legal-content]").replaceChildren(document.importNode(contenido, true));
    dialogoLegal.showModal();
    dialogoLegal.querySelector("[data-legal-close]").focus();
  });
});

dialogoLegal?.querySelector("[data-legal-close]")?.addEventListener("click", () => dialogoLegal.close());
