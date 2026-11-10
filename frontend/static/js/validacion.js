// Presenta en español los errores nativos mientras se completa el formulario.
const mensajeValidacion = (campo) => {
  const validez = campo.validity;
  if (validez.customError) return campo.validationMessage;
  if (validez.valueMissing) return "Completa este campo.";
  if (validez.typeMismatch) return "Ingresa un valor con el formato correcto.";
  if (validez.tooShort) return `Usa al menos ${campo.minLength} caracteres.`;
  if (validez.tooLong) return `Usa como máximo ${campo.maxLength} caracteres.`;
  if (validez.rangeUnderflow) return `El valor mínimo es ${campo.min}.`;
  if (validez.rangeOverflow) return `El valor máximo es ${campo.max}.`;
  if (validez.stepMismatch) return "Usa un valor dentro del rango permitido.";
  if (validez.patternMismatch) return "Revisa el formato indicado para este campo.";
  return campo.validationMessage;
};

document.querySelectorAll(".auth-form, .data-form, .content-card form").forEach((formulario) => {
  const confirmar = formulario.querySelector("[data-password-confirm]");
  const contrasena = formulario.querySelector("#id_password, #id_new_password1");
  const indicador = formulario.querySelector("[data-password-match]");

  const validarCoincidencia = () => {
    if (!confirmar || !contrasena) return;
    const coincide = !confirmar.value || confirmar.value === contrasena.value;
    confirmar.setCustomValidity(coincide ? "" : "Las contraseñas no coinciden.");
    if (indicador) {
      indicador.textContent = confirmar.value
        ? (coincide ? "Las contraseñas coinciden" : "Las contraseñas no coinciden")
        : "";
    }
  };

  const validarCampo = (campo) => {
    validarCoincidencia();
    const lista = document.getElementById(`${campo.id}_errors`);
    if (campo.checkValidity()) {
      campo.removeAttribute("aria-invalid");
      if (lista) lista.replaceChildren();
      return;
    }
    campo.setAttribute("aria-invalid", "true");
    if (lista) {
      const error = document.createElement("li");
      error.textContent = mensajeValidacion(campo);
      lista.replaceChildren(error);
    }
  };

  formulario.querySelectorAll("input, select, textarea").forEach((campo) => {
    campo.addEventListener("blur", () => validarCampo(campo));
    campo.addEventListener("input", () => validarCampo(campo));
  });
  contrasena?.addEventListener("input", () => confirmar && validarCampo(confirmar));
});
