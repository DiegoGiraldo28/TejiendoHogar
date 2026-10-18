// Alterna la visibilidad del campo de contraseña sin afectar el formulario.
document.querySelectorAll("[data-toggle-password]").forEach((boton) => {
  boton.addEventListener("click", () => {
    const campo = document.getElementById(boton.dataset.passwordTarget);
    if (!campo) return;
    const mostrar = campo.type === "password";
    campo.type = mostrar ? "text" : "password";
    boton.setAttribute("aria-pressed", String(mostrar));
    boton.setAttribute("aria-label", mostrar ? "Ocultar contraseña" : "Mostrar contraseña");
    boton.querySelector("[data-eye-open]").classList.toggle("is-hidden", !mostrar);
    boton.querySelector("[data-eye-closed]").classList.toggle("is-hidden", mostrar);
  });
});
