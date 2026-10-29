"use strict";
const examples = [
  ["Notebook de prueba", "Laboratorio A", "Pendiente", "El equipo de demostración no enciende. Se registra el caso para su evaluación."],
  ["Monitor de prueba", "Sala de pruebas B", "En revisión", "La pantalla de ejemplo presenta una imagen intermitente. Se está revisando la conexión."],
  ["Tablet de prueba", "Oficina de ejemplo C", "Archivado", "Se completó la revisión simulada del dispositivo y se archivó el informe."],
  ["Impresora de prueba", "Taller de pruebas D", "Pendiente", "Incidente simulado de impresión. Pendiente de revisión del equipo."],
  ["Notebook de prueba", "Sala de pruebas B", "En revisión", "Se simula una revisión de rendimiento del equipo y sus componentes."],
  ["Monitor de prueba", "Laboratorio A", "Archivado", "Se finalizó la comprobación simulada de la pantalla."],
  ["Tablet de prueba", "Taller de pruebas D", "Pendiente", "Caso ficticio de carga de batería. Pendiente de evaluación."],
  ["Impresora de prueba", "Oficina de ejemplo C", "En revisión", "Se revisa un atasco de papel simulado en la impresora de ejemplo."]
];
const states = {"Pendiente":"pending", "En revisión":"review", "Archivado":"archived"};
const $ = (id) => document.getElementById(id);
let reports, selected, notification;
function resetData() {
  reports = examples.map(([equipment, sector, state, description], i) => ({
    id: `DEMO-${String(i + 1).padStart(4, "0")}`, equipment, sector, state, description,
    date: `2026-01-${String(10 + i * 2).padStart(2, "0")}`,
    history: ["Registro de ejemplo creado · Responsable TI"]
  }));
}
function element(tag, value, className) {
  const node = document.createElement(tag);
  if (value !== undefined) node.textContent = value;
  if (className) node.className = className;
  return node;
}
function render() {
  $("total").textContent = reports.length;
  for (const [state, id] of Object.entries(states)) $(id).textContent = reports.filter(r => r.state === state).length;
  const query = $("search").value.trim().toLocaleLowerCase("es");
  const state = $("status").value;
  const visible = reports.filter(r => (!state || r.state === state) && [r.id,r.equipment,r.sector,r.description].join(" ").toLocaleLowerCase("es").includes(query));
  $("rows").replaceChildren();
  visible.forEach(report => {
    const row = element("tr"), heading = element("td");
    heading.append(element("strong", report.id), element("small", report.equipment));
    row.append(heading, element("td", report.sector), element("td", report.date.split("-").reverse().join("/")));
    const status = element("td"); status.append(element("span", report.state, `badge ${states[report.state]}`));
    const action = element("td"), button = element("button", "Ver detalle →", "detail-button");
    button.type = "button"; button.setAttribute("aria-label", `Ver detalle de ${report.id}`);
    button.addEventListener("click", () => openDetail(report.id)); action.append(button); row.append(status, action); $("rows").append(row);
  });
  $("result-count").textContent = `${visible.length} de ${reports.length} informes`;
  $("empty").hidden = visible.length > 0;
}
function renderHistory() {
  $("history").replaceChildren(...selected.history.map(item => element("li", item)));
}
function openDetail(id) {
  selected = reports.find(r => r.id === id);
  $("detail-title").textContent = selected.id;
  $("detail-description").textContent = selected.description;
  $("detail-fields").replaceChildren();
  for (const [key, value] of [["Equipo",selected.equipment],["Sector",selected.sector],["Responsable","Responsable TI"],["Identificador",`DEMO-EQ-${id.slice(-4)}`],["Fecha",selected.date],["Documento","PDF disponible en la aplicación completa"]]) {
    $("detail-fields").append(element("dt",key),element("dd",value));
  }
  $("detail-status").value = selected.state; renderHistory(); $("detail").showModal();
}
function announce(text) {
  clearTimeout(notification); $("message").textContent = text;
  notification = setTimeout(() => { $("message").textContent = ""; }, 3500);
}
$("search").addEventListener("input", render);
$("status").addEventListener("change", render);
$("close").addEventListener("click", () => $("detail").close());
$("detail-status").addEventListener("change", (event) => {
  const next = event.target.value;
  if (!Object.hasOwn(states, next) || !selected) return;
  selected.history.unshift(`${selected.state} → ${next} · Cambio simulado`);
  selected.state = next; renderHistory(); render(); announce("Estado actualizado en la demostración.");
});
$("reset").addEventListener("click", () => {
  resetData(); $("search").value = ""; $("status").value = ""; render(); announce("La demo volvió a sus datos iniciales.");
});
resetData(); render();
