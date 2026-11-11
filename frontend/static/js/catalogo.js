// Ajusta campos de existencias y vista previa sin sustituir la validación del servidor.
// Stock solo aplica a Disponible; los días de confección solo a Sobre pedido (el servidor guarda 1 en Disponible).
const tipoProducto = document.querySelector("#id_tipo");
const camposStock = document.querySelector("[data-stock-fields]");
const camposSobrePedido = document.querySelector("[data-sobre-pedido-fields]");

function mostrarCampos(contenedor, visible, tieneErrores) {
  if (!contenedor) return;
  const activo = visible || tieneErrores;
  contenedor.hidden = !activo;
  contenedor.querySelectorAll("input").forEach((campo) => {
    campo.disabled = !activo;
  });
}

function actualizarCamposPorTipo() {
  if (!tipoProducto) return;
  const disponible = tipoProducto.value === tipoProducto.dataset.tipoDisponible;
  mostrarCampos(camposStock, disponible, camposStock?.dataset.stockErrors === "true");
  mostrarCampos(camposSobrePedido, !disponible, camposSobrePedido?.dataset.sobrePedidoErrors === "true");
}

tipoProducto?.addEventListener("change", actualizarCamposPorTipo);
actualizarCamposPorTipo();

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
