document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("table.tabla-interactiva").forEach((tabla) => {
    const cuerpo = tabla.tBodies[0];
    if (!cuerpo) return;
    const filasFijas = [...cuerpo.rows].filter((fila) => fila.classList.contains("fila-total"));
    let filas = [...cuerpo.rows].filter((fila) => !fila.classList.contains("fila-total"));
    let filtradas = [...filas];
    let pagina = 1;
    let porPagina = Number(tabla.dataset.pageSize || 10);
    let ordenColumna = -1;
    let ordenAscendente = true;

    const controles = document.createElement("div");
    controles.className = "controles-tabla";
    controles.innerHTML = `<label class="busqueda-tabla">Buscar en la tabla<input type="search" placeholder="${tabla.dataset.searchPlaceholder || "Filtrar..."}"></label><label class="filas-pagina">Mostrar<select><option>5</option><option selected>10</option><option>25</option><option>50</option></select> filas</label>`;
    tabla.parentNode.insertBefore(controles, tabla);

    const pie = document.createElement("div");
    pie.className = "paginacion-tabla";
    tabla.parentNode.appendChild(pie);
    const buscador = controles.querySelector("input");
    const selector = controles.querySelector("select");
    selector.value = String(porPagina);

    const valorOrden = (fila, indice) => {
      const texto = fila.cells[indice]?.innerText.trim() || "";
      if (/^\d{4}-\d{2}-\d{2}/.test(texto)) return new Date(texto.replace(" ", "T")).getTime();
      const numero = Number(texto.replace(/[^0-9,.-]/g, "").replace(",", "."));
      return texto && Number.isFinite(numero) ? numero : texto.toLocaleLowerCase("es");
    };

    const renderizar = () => {
      const paginas = Math.max(1, Math.ceil(filtradas.length / porPagina));
      pagina = Math.min(pagina, paginas);
      filas.forEach((fila) => fila.hidden = true);
      filtradas.slice((pagina - 1) * porPagina, pagina * porPagina).forEach((fila) => fila.hidden = false);
      filasFijas.forEach((fila) => fila.hidden = pagina !== paginas);
      const inicio = filtradas.length ? (pagina - 1) * porPagina + 1 : 0;
      const fin = Math.min(pagina * porPagina, filtradas.length);
      pie.innerHTML = `<span>Mostrando ${inicio}–${fin} de ${filtradas.length}</span><div><button type="button" ${pagina === 1 ? "disabled" : ""}>Anterior</button><strong>Página ${pagina} de ${paginas}</strong><button type="button" ${pagina === paginas ? "disabled" : ""}>Siguiente</button></div>`;
      const botones = pie.querySelectorAll("button");
      botones[0].onclick = () => { pagina--; renderizar(); };
      botones[1].onclick = () => { pagina++; renderizar(); };
    };

    buscador.addEventListener("input", () => {
      const consulta = buscador.value.trim().toLocaleLowerCase("es");
      filtradas = filas.filter((fila) => fila.innerText.toLocaleLowerCase("es").includes(consulta));
      pagina = 1;
      renderizar();
    });
    selector.addEventListener("change", () => { porPagina = Number(selector.value); pagina = 1; renderizar(); });

    [...tabla.tHead.rows[0].cells].forEach((cabecera, indice) => {
      if (cabecera.hasAttribute("data-no-sort")) return;
      cabecera.classList.add("ordenable");
      cabecera.tabIndex = 0;
      const ordenar = () => {
        ordenAscendente = ordenColumna === indice ? !ordenAscendente : true;
        ordenColumna = indice;
        tabla.querySelectorAll("th").forEach((th) => th.removeAttribute("data-orden"));
        cabecera.dataset.orden = ordenAscendente ? "asc" : "desc";
        filas.sort((a, b) => {
          const x = valorOrden(a, indice), y = valorOrden(b, indice);
          const comparacion = typeof x === "number" && typeof y === "number" ? x - y : String(x).localeCompare(String(y), "es", { numeric: true });
          return ordenAscendente ? comparacion : -comparacion;
        });
        filas.forEach((fila) => cuerpo.insertBefore(fila, filasFijas[0] || null));
        const consulta = buscador.value.trim().toLocaleLowerCase("es");
        filtradas = filas.filter((fila) => fila.innerText.toLocaleLowerCase("es").includes(consulta));
        pagina = 1; renderizar();
      };
      cabecera.addEventListener("click", ordenar);
      cabecera.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") ordenar(); });
    });
    renderizar();
  });
});
