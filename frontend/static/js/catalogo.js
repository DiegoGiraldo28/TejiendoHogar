// Ajusta campos de existencias y vista previa sin sustituir la validación del servidor.
const tipoProducto = document.querySelector("#id_tipo");
const camposStock = document.querySelector("[data-stock-fields]");

function actualizarCamposStock() {
  if (!tipoProducto || !camposStock) return;
  const disponible = tipoProducto.value === "Disponible";
  camposStock.hidden = !disponible;
  camposStock.querySelectorAll("input").forEach((campo) => { campo.disabled = !disponible; });
}

tipoProducto?.addEventListener("change", actualizarCamposStock);
actualizarCamposStock();

const campoImagen = document.querySelector("#id_imagen");
const vistaPrevia = document.querySelector("#vista-previa");
campoImagen?.addEventListener("change", () => {
  const archivo = campoImagen.files[0];
  if (!archivo || !vistaPrevia) return;
  vistaPrevia.src = URL.createObjectURL(archivo);
  vistaPrevia.hidden = false;
});

// Añade filas vacías al formset de receta cuando esta plantilla está presente.
const agregarLinea = document.querySelector("[data-agregar-linea]");
if (agregarLinea) {
  agregarLinea.addEventListener("click", () => {
    const plantilla = document.querySelector("#linea-receta-vacia");
    const total = document.querySelector("#id_receta-TOTAL_FORMS");
    if (!plantilla || !total) return;
    const indice = Number(total.value);
    const fila = document.createElement("div");
    fila.className = "recipe-row";
    fila.innerHTML = plantilla.innerHTML.replaceAll("__prefix__", String(indice));
    document.querySelector("[data-lineas-receta]").append(fila);
    total.value = String(indice + 1);
  });
}
