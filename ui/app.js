const DEFAULT_STATE = {
  theme: "dark",
  solar_kw: 100,
  grid_kw: 120,
  num_dg: 2,
  dg_ratings: [250, 250],
  num_outputs: 3,
  outgoing_ratings: [400, 400, 250],
  busbar_material: "Aluminium",
  num_poles: 4,
};

const state = {
  ...DEFAULT_STATE,
  lastDesign: null,
};

const elements = {};

function $(id) {
  return document.getElementById(id);
}

function waitForApi() {
  return new Promise((resolve) => {
    const tick = () => {
      if (window.pywebview?.api) {
        resolve(window.pywebview.api);
        return;
      }
      setTimeout(tick, 50);
    };
    tick();
  });
}

function svgToDataUri(svg) {
  return `data:image/svg+xml;base64,${btoa(unescape(encodeURIComponent(svg)))}`;
}

function numberValue(id, fallback = 0) {
  const value = Number($(id).value);
  return Number.isFinite(value) ? value : fallback;
}

function renderDynamicFields() {
  const dgCount = Math.max(0, Math.floor(numberValue("numDg", 0)));
  const outputCount = Math.max(1, Math.floor(numberValue("numOutputs", 1)));
  const dgContainer = $("dgInputs");
  const outputContainer = $("outgoingInputs");

  const dgValues = Array.from(dgContainer.querySelectorAll("input")).map((input) => Number(input.value) || 0);
  const outgoingValues = Array.from(outputContainer.querySelectorAll("input")).map((input) => Number(input.value) || 0);

  dgContainer.innerHTML = "";
  outputContainer.innerHTML = "";

  for (let index = 0; index < dgCount; index += 1) {
    const wrapper = document.createElement("label");
    wrapper.className = "row";
    wrapper.innerHTML = `
      <span>DG ${index + 1}</span>
      <input type="number" min="0" step="1" value="${dgValues[index] ?? state.dg_ratings[index] ?? 250}" data-dg-index="${index}" />
    `;
    dgContainer.appendChild(wrapper);
  }

  for (let index = 0; index < outputCount; index += 1) {
    const wrapper = document.createElement("label");
    wrapper.className = "row";
    wrapper.innerHTML = `
      <span>O/G ${index + 1}</span>
      <input type="number" min="0" step="1" value="${outgoingValues[index] ?? state.outgoing_ratings[index] ?? (index < 2 ? 400 : 250)}" data-output-index="${index}" />
    `;
    outputContainer.appendChild(wrapper);
  }
}

function collectInputs() {
  const dgInputs = Array.from($("dgInputs").querySelectorAll("input")).map((input) => Number(input.value) || 0);
  const outputInputs = Array.from($("outgoingInputs").querySelectorAll("input")).map((input) => Number(input.value) || 0);

  return {
    theme: state.theme,
    solar_kw: numberValue("solarKw", 0),
    grid_kw: numberValue("gridKw", 0),
    num_dg: Math.max(0, Math.floor(numberValue("numDg", 0))),
    dg_ratings: dgInputs,
    num_outputs: Math.max(1, Math.floor(numberValue("numOutputs", 1))),
    outgoing_ratings: outputInputs,
    busbar_material: $("busbarMaterial").value,
    num_poles: Number($("numPoles").value) || 4,
  };
}

function setLoading(isLoading) {
  document.body.classList.toggle("loading", isLoading);
}

function setStatus(message, kind = "ok") {
  const statusCard = $("statusCard");
  const statusText = $("statusText");
  statusCard.classList.remove("ok", "warn");
  statusCard.classList.add(kind === "warn" ? "warn" : "ok");
  statusText.textContent = message;
}

function renderMetrics(design) {
  const summary = design.summary;
  const items = [
    ["Busbar Current", `${summary.total_busbar_current.toFixed(2)} A`],
    ["Outgoing Capacity", `${summary.total_outgoing_rating.toFixed(0)} A`],
    ["Busbar Spec", summary.busbar_spec],
    ["Panel Size", `${design.ga.panel_w} × ${design.ga.panel_h} × ${design.ga.panel_d} mm`],
  ];

  $("summaryGrid").innerHTML = items
    .map(([label, value]) => `
      <article class="metric-card">
        <div class="metric-label">${label}</div>
        <div class="metric-value">${value}</div>
      </article>
    `)
    .join("");
}

function renderTable(containerId, rows, headers) {
  if (!rows?.length) {
    $(containerId).innerHTML = `<li class="list-empty">No data available.</li>`;
    return;
  }
  const listItems = rows.map((row) => {
    const primary = headers.map((header) => row[header]).filter(Boolean).join(" | ");
    return `<li>${primary}</li>`;
  });
  $(containerId).innerHTML = listItems.join("");
}

function renderFromDesign(design) {
  state.lastDesign = design;
  renderMetrics(design);

  $("sldImage").src = svgToDataUri(design.sld.svg);
  $("gaImage").src = svgToDataUri(design.ga.svg);

  const warning = design.summary.warning_flag;
  setStatus(
    warning
      ? `Warning: total busbar current ${design.summary.total_busbar_current.toFixed(2)} A exceeds outgoing capacity ${design.summary.total_outgoing_rating.toFixed(0)} A.`
      : `System is properly sized. Total busbar current ${design.summary.total_busbar_current.toFixed(2)} A.`,
    warning ? "warn" : "ok",
  );

  $("bomCount").textContent = `${design.bom_rows.length} items`;

  renderTable("bomTable", design.bom_rows, ["Sr No", "Description", "Rating", "Qty", "UOM"]);
}

async function generateDesign() {
  const api = await waitForApi();
  const payload = collectInputs();
  state.theme = payload.theme;
  document.body.dataset.theme = state.theme;
  setLoading(true);

  try {
    const design = await api.generate(payload);
    if (!design.ok) {
      throw new Error(design.error || "Design generation failed");
    }
    state.solar_kw = payload.solar_kw;
    state.grid_kw = payload.grid_kw;
    state.num_dg = payload.num_dg;
    state.dg_ratings = payload.dg_ratings;
    state.num_outputs = payload.num_outputs;
    state.outgoing_ratings = payload.outgoing_ratings;
    state.busbar_material = payload.busbar_material;
    state.num_poles = payload.num_poles;
    renderFromDesign(design);
  } catch (error) {
    setStatus(error.message, "warn");
  } finally {
    setLoading(false);
  }
}

async function exportFile(methodName, suggestedName) {
  const api = await waitForApi();
  const payload = collectInputs();
  setLoading(true);

  try {
    const response = await api[methodName](payload);
    if (!response || response.ok === false) {
      throw new Error(response?.error || "Export failed");
    }
    setStatus(`Saved ${response.filename || suggestedName}${response.path ? ` to ${response.path}` : ""}.`, "ok");
  } catch (error) {
    setStatus(error.message, "warn");
  } finally {
    setLoading(false);
  }
}

async function loadInitialState() {
  const api = await waitForApi();
  const initial = await api.get_state();

  state.theme = initial.theme || DEFAULT_STATE.theme;
  state.solar_kw = initial.solar_kw ?? DEFAULT_STATE.solar_kw;
  state.grid_kw = initial.grid_kw ?? DEFAULT_STATE.grid_kw;
  state.num_dg = initial.num_dg ?? DEFAULT_STATE.num_dg;
  state.dg_ratings = initial.dg_ratings ?? DEFAULT_STATE.dg_ratings;
  state.num_outputs = initial.num_outputs ?? DEFAULT_STATE.num_outputs;
  state.outgoing_ratings = initial.outgoing_ratings ?? DEFAULT_STATE.outgoing_ratings;
  state.busbar_material = initial.busbar_material ?? DEFAULT_STATE.busbar_material;
  state.num_poles = initial.num_poles ?? DEFAULT_STATE.num_poles;

  $("solarKw").value = state.solar_kw;
  $("gridKw").value = state.grid_kw;
  $("numDg").value = state.num_dg;
  $("numOutputs").value = state.num_outputs;
  $("busbarMaterial").value = state.busbar_material;
  $("numPoles").value = state.num_poles;

  document.body.dataset.theme = state.theme;
  $("themeToggle").textContent = state.theme === "dark" ? "Light mode" : "Dark mode";

  renderDynamicFields();
  await generateDesign();
}

function bindEvents() {
  $("themeToggle").addEventListener("click", async () => {
    state.theme = state.theme === "dark" ? "light" : "dark";
    document.body.dataset.theme = state.theme;
    $("themeToggle").textContent = state.theme === "dark" ? "Light mode" : "Dark mode";
    const api = await waitForApi();
    await api.set_theme(state.theme);
    await generateDesign();
  });

  ["generateButton", "generateButtonAlt"].forEach((id) => {
    $(id).addEventListener("click", generateDesign);
  });

  $("downloadPdfButton").addEventListener("click", () => exportFile("export_pdf", "microgrid_panel_report.pdf"));
  $("downloadGaButton").addEventListener("click", () => exportFile("export_ga_pdf", "microgrid_panel_ga.pdf"));
  $("downloadExcelButton").addEventListener("click", () => exportFile("export_excel", "microgrid_panel_bom.xlsx"));

  ["solarKw", "gridKw", "numDg", "numOutputs", "busbarMaterial", "numPoles"].forEach((id) => {
    $(id).addEventListener("change", () => {
      renderDynamicFields();
    });
  });

  ["solarKw", "gridKw", "numDg", "numOutputs"].forEach((id) => {
    $(id).addEventListener("input", () => {
      renderDynamicFields();
    });
  });

  document.addEventListener("input", (event) => {
    if (event.target.matches("#dgInputs input, #outgoingInputs input")) {
      state.dg_ratings = Array.from($("dgInputs").querySelectorAll("input")).map((input) => Number(input.value) || 0);
      state.outgoing_ratings = Array.from($("outgoingInputs").querySelectorAll("input")).map((input) => Number(input.value) || 0);
    }
  });
}

document.addEventListener("DOMContentLoaded", async () => {
  elements.body = document.body;
  bindEvents();
  renderDynamicFields();
  await loadInitialState();
});
