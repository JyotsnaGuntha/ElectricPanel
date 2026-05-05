const DEFAULT_STATE = {
  theme: "dark",
  solar_kw: null,
  grid_kw: null,
  num_dg: null,
  dg_ratings: [],
  num_outputs: null,
  outgoing_ratings: [],
  busbar_material: "",
  num_poles: null,
};

const state = {
  ...DEFAULT_STATE,
  lastDesign: null,
  hasPendingChanges: false,
  solarRecommendation: null,
  solarInputMode: "upload",
  uploadedBills: [],
};

const FULLSCREEN_MIN_ZOOM = 1;
const FULLSCREEN_MAX_ZOOM = 4;
const FULLSCREEN_ZOOM_STEP = 0.12;
const FULLSCREEN_PAN_WHEEL_STEP = 0.75;
let fullscreenZoom = 1;
let fullscreenPanX = 0;
let fullscreenPanY = 0;
let fullscreenDragging = false;
let fullscreenDragStartX = 0;
let fullscreenDragStartY = 0;
let fullscreenDragBasePanX = 0;
let fullscreenDragBasePanY = 0;

const elements = {};

const MAX_BILL_UPLOADS = 20;

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

function placeholderSvg(title, subtitle, theme = "dark") {
  const isLight = theme === "light";
  const bgStart = isLight ? "#f5f9ff" : "#0b1626";
  const bgEnd = isLight ? "#e7f0fb" : "#15253d";
  const frame = isLight ? "#94a3b8" : "#334155";
  const accent = isLight ? "#1ba6a1" : "#56d5d2";
  const titleColor = isLight ? "#10203a" : "#e7eef9";
  const subtitleColor = isLight ? "#59708f" : "#9bb0cf";

  return `
    <svg xmlns="http://www.w3.org/2000/svg" width="1200" height="720" viewBox="0 0 1200 720">
      <defs>
        <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stop-color="${bgStart}"/>
          <stop offset="100%" stop-color="${bgEnd}"/>
        </linearGradient>
      </defs>
      <rect x="0" y="0" width="1200" height="720" fill="url(#bg)"/>
      <rect x="70" y="70" width="1060" height="580" rx="20" fill="none" stroke="${frame}" stroke-width="2" stroke-dasharray="10 8"/>
      <circle cx="600" cy="280" r="50" fill="none" stroke="${accent}" stroke-width="4"/>
      <line x1="600" y1="230" x2="600" y2="330" stroke="${accent}" stroke-width="4"/>
      <line x1="550" y1="280" x2="650" y2="280" stroke="${accent}" stroke-width="4"/>
      <text x="600" y="390" text-anchor="middle" fill="${titleColor}" font-size="38" font-family="Segoe UI, Arial, sans-serif" font-weight="700">${title}</text>
      <text x="600" y="435" text-anchor="middle" fill="${subtitleColor}" font-size="24" font-family="Segoe UI, Arial, sans-serif">${subtitle}</text>
      <text x="600" y="515" text-anchor="middle" fill="${accent}" font-size="22" font-family="Segoe UI, Arial, sans-serif">Click Generate to build live preview</text>
    </svg>
  `;
}

function setPreviewPlaceholders() {
  $("sldImage").src = svgToDataUri(placeholderSvg("SLD Preview", "Diagram will appear after generation", state.theme));
  $("gaImage").src = svgToDataUri(placeholderSvg("GA Preview", "Layout will appear after generation", state.theme));
}

function getThemeIconSVG(theme) {
  // Use Lucide-style outline SVGs (no fill, stroke=currentColor)
  const common = 'width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"';
  if (theme === 'dark') {
    // Show Sun when Dark mode is active
    return `
      <svg ${common} aria-hidden="true"><circle cx="12" cy="12" r="4"></circle>
        <line x1="12" y1="2" x2="12" y2="4"></line>
        <line x1="12" y1="20" x2="12" y2="22"></line>
        <line x1="4.93" y1="4.93" x2="6.34" y2="6.34"></line>
        <line x1="17.66" y1="17.66" x2="19.07" y2="19.07"></line>
        <line x1="2" y1="12" x2="4" y2="12"></line>
        <line x1="20" y1="12" x2="22" y2="12"></line>
        <line x1="4.93" y1="19.07" x2="6.34" y2="17.66"></line>
        <line x1="17.66" y1="6.34" x2="19.07" y2="4.93"></line>
      </svg>`;
  }
  // Show Moon when Light mode is active
  return `
    <svg ${common} aria-hidden="true"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path></svg>`;
}

function numberValue(id, fallback = 0) {
  const value = Number($(id).value);
  return Number.isFinite(value) ? value : fallback;
}

function parseOptionalNumber(rawValue) {
  if (rawValue === null || rawValue === undefined || rawValue === "") {
    return null;
  }
  const value = Number(rawValue);
  return Number.isFinite(value) ? value : null;
}

function formatInputValue(value) {
  return Number.isFinite(value) ? String(value) : "";
}

function collectDynamicInputValues(containerId) {
  return Array.from($(containerId).querySelectorAll("input")).map((input) => parseOptionalNumber(input.value));
}

function formatFileSize(bytes) {
  if (!Number.isFinite(bytes) || bytes < 1024) {
    return `${Math.max(0, Math.round(bytes || 0))} B`;
  }
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  }
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function setSolarInputMode(mode, recommendation = null) {
  state.solarInputMode = mode;
  state.solarRecommendation = recommendation;
  const solarField = $("solarKwField");
  const solarInput = $("solarKw");
  const recommendationChip = $("solarRecommendationChip");
  const recommendedInline = $("recommendedInline");
  const uploadAgainButton = $("uploadBillsAgainButton");
  const uploadStatus = $("solarUploadStatus");

  if (mode === "upload") {
    if (solarField) solarField.classList.add("hidden");
    if (recommendationChip) recommendationChip.classList.add("hidden");
    if (recommendedInline) recommendedInline.classList.add("hidden");
    if (uploadAgainButton) uploadAgainButton.classList.add("hidden");
    if (uploadStatus) uploadStatus.textContent = "Upload multiple PDF bills and let the app recommend a solar value.";
    return;
  }

  if (solarField) solarField.classList.remove("hidden");
  if (uploadAgainButton) uploadAgainButton.classList.remove("hidden");

  if (mode === "recommended" && recommendation !== null) {
    if (solarInput) solarInput.value = formatInputValue(Number(recommendation));
    if (recommendationChip) recommendationChip.classList.remove("hidden");
    if (recommendedInline) {
      recommendedInline.textContent = `Recommended: ${Number(recommendation)} kW`;
      recommendedInline.classList.remove("hidden");
    }
    if (uploadStatus) uploadStatus.textContent = "Recommended value applied from your uploaded energy bills.";
  } else {
    if (mode === "manual" && solarInput) {
      solarInput.value = "";
    }
    if (recommendationChip) recommendationChip.classList.add("hidden");
    if (recommendedInline) recommendedInline.classList.add("hidden");
    if (uploadStatus) uploadStatus.textContent = "Enter solar capacity manually or upload bills for a recommendation.";
  }
}

function renderBillFileList() {
  const list = $("billFilesList");
  if (!state.uploadedBills.length) {
    list.innerHTML = "<p class='card-note'>No files selected yet.</p>";
    return;
  }

  list.innerHTML = state.uploadedBills
    .map((file, index) => `
      <div class="upload-file-item">
        <div class="upload-file-meta">
          <div class="upload-file-name">${file.name}</div>
          <div class="upload-file-size">${formatFileSize(file.size)}</div>
        </div>
        <button class="ghost-button upload-file-remove" type="button" data-remove-bill-index="${index}">Remove</button>
      </div>
    `)
    .join("");
}

function openUploadModal() {
  $("uploadModal").classList.remove("hidden");
  $("uploadAnalysisResult").classList.add("hidden");
  $("billFilesInput").value = "";
  $("analyzeBillsButton").disabled = false;
  renderBillFileList();
}

function closeUploadModal() {
  $("uploadModal").classList.add("hidden");
  $("uploadDropzone").classList.remove("is-dragover");
}

async function fileToUploadPayload(file) {
  return {
    name: file.name,
    type: file.type || "application/pdf",
    size: file.size,
    content: await new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result);
      reader.onerror = () => reject(new Error(`Failed to read ${file.name}`));
      reader.readAsDataURL(file);
    }),
  };
}

async function addUploadedBills(files) {
  const pdfFiles = Array.from(files || []).filter((file) => {
    const fileName = String(file?.name || "").toLowerCase();
    const fileType = String(file?.type || "");
    return fileType === "application/pdf" || fileName.endsWith(".pdf") || Boolean(file?.content);
  });
  if (!pdfFiles.length) {
    window.alert("Please select PDF files only.");
    return;
  }

  const remainingSlots = Math.max(0, MAX_BILL_UPLOADS - state.uploadedBills.length);
  const nextFiles = await Promise.all(
    pdfFiles.slice(0, remainingSlots).map((file) => {
      if (file?.content) {
        return {
          name: file.name,
          type: file.type || "application/pdf",
          size: file.size || 0,
          content: file.content,
        };
      }
      return fileToUploadPayload(file);
    }),
  );
  state.uploadedBills = [...state.uploadedBills, ...nextFiles];
  renderBillFileList();
}

function handleBillDrop(event) {
  event.preventDefault();
  event.stopPropagation();
  $("uploadDropzone").classList.remove("is-dragover");
  if (event.dataTransfer?.files?.length) {
    addUploadedBills(event.dataTransfer.files);
  }
}

async function filesToPayload(files) {
  return files;
}

function enhanceNumberSteppers(scope = document) {
  const numericInputs = scope.querySelectorAll('input[type="number"]:not([data-stepperized="true"])');

  numericInputs.forEach((input) => {
    const wrapper = document.createElement("div");
    wrapper.className = "number-stepper";

    const controls = document.createElement("div");
    controls.className = "stepper-controls";

    const incrementButton = document.createElement("button");
    incrementButton.type = "button";
    incrementButton.className = "stepper-btn";
    incrementButton.textContent = "+";
    incrementButton.setAttribute("aria-label", "Increase value");

    const decrementButton = document.createElement("button");
    decrementButton.type = "button";
    decrementButton.className = "stepper-btn";
    decrementButton.textContent = "-";
    decrementButton.setAttribute("aria-label", "Decrease value");

    input.dataset.stepperized = "true";
    const parent = input.parentNode;
    parent.insertBefore(wrapper, input);
    wrapper.appendChild(input);
    controls.appendChild(decrementButton);
    controls.appendChild(incrementButton);
    wrapper.appendChild(controls);

    incrementButton.addEventListener("click", () => {
      input.stepUp();
      input.dispatchEvent(new Event("input", { bubbles: true }));
      input.dispatchEvent(new Event("change", { bubbles: true }));
    });

    decrementButton.addEventListener("click", () => {
      input.stepDown();
      input.dispatchEvent(new Event("input", { bubbles: true }));
      input.dispatchEvent(new Event("change", { bubbles: true }));
    });
  });
}

function renderDynamicFields() {
  const dgCount = Math.max(0, Math.floor(numberValue("numDg", 0)));
  const outputCount = Math.max(0, Math.floor(numberValue("numOutputs", 0)));
  const dgContainer = $("dgInputs");
  const outputContainer = $("outgoingInputs");

  const dgValues = collectDynamicInputValues("dgInputs");
  const outgoingValues = collectDynamicInputValues("outgoingInputs");

  dgContainer.innerHTML = "";
  outputContainer.innerHTML = "";

  for (let index = 0; index < dgCount; index += 1) {
    const value = dgValues[index] ?? parseOptionalNumber(state.dg_ratings[index]);
    const wrapper = document.createElement("label");
    wrapper.className = "row";
    wrapper.innerHTML = `
      <span>DG ${index + 1}</span>
      <input type="number" min="0" step="1" value="${formatInputValue(value)}" placeholder="Enter" data-dg-index="${index}" />
    `;
    dgContainer.appendChild(wrapper);
  }

  for (let index = 0; index < outputCount; index += 1) {
    const value = outgoingValues[index] ?? parseOptionalNumber(state.outgoing_ratings[index]);
    const wrapper = document.createElement("label");
    wrapper.className = "row";
    wrapper.innerHTML = `
      <span>O/G ${index + 1}</span>
      <input type="number" min="0" step="1" value="${formatInputValue(value)}" placeholder="Enter" data-output-index="${index}" />
    `;
    outputContainer.appendChild(wrapper);
  }

  enhanceNumberSteppers(dgContainer);
  enhanceNumberSteppers(outputContainer);
}

function collectInputs() {
  const dgInputs = collectDynamicInputValues("dgInputs");
  const outputInputs = collectDynamicInputValues("outgoingInputs");

  const solarKwRaw = $("solarKw").value;
  const gridKwRaw = $("gridKw").value;
  const numDgRaw = $("numDg").value;
  const numOutputsRaw = $("numOutputs").value;
  const busbarMaterial = $("busbarMaterial").value;
  const numPolesRaw = $("numPoles").value;

  if (solarKwRaw === "") {
    throw new Error("Please enter solar capacity.");
  }
  if (gridKwRaw === "") {
    throw new Error("Please enter grid capacity.");
  }
  if (numDgRaw === "") {
    throw new Error("Please enter number of DGs.");
  }
  if (numOutputsRaw === "") {
    throw new Error("Please enter outgoing feeders.");
  }
  if (!busbarMaterial) {
    throw new Error("Please select busbar material.");
  }
  if (!numPolesRaw) {
    throw new Error("Please select system phases / poles.");
  }

  const solarKwNum = Number(solarKwRaw);
  const gridKwNum = Number(gridKwRaw);

  const numDg = Math.max(0, Math.floor(Number(numDgRaw)));
  const numOutputs = Math.max(0, Math.floor(Number(numOutputsRaw)));
  if (numOutputs < 1) {
    throw new Error("Outgoing feeders must be at least 1.");
  }

  if (numDg > dgInputs.length || dgInputs.some((value) => value === null)) {
    throw new Error("Please enter all DG ratings.");
  }
  if (numOutputs > outputInputs.length || outputInputs.some((value) => value === null)) {
    throw new Error("Please enter all outgoing feeder ratings.");
  }

  return {
    theme: state.theme,
    solar_kw: solarKwNum,
    grid_kw: gridKwNum,
    num_dg: numDg,
    dg_ratings: dgInputs,
    num_outputs: numOutputs,
    outgoing_ratings: outputInputs,
    busbar_material: busbarMaterial,
    num_poles: Number(numPolesRaw),
  };
}

function setLoading(isLoading) {
  document.body.classList.toggle("loading", isLoading);
}

function setFullscreenZoom(nextZoom) {
  fullscreenZoom = Math.max(FULLSCREEN_MIN_ZOOM, Math.min(FULLSCREEN_MAX_ZOOM, nextZoom));
  if (fullscreenZoom <= FULLSCREEN_MIN_ZOOM) {
    fullscreenPanX = 0;
    fullscreenPanY = 0;
  }
  applyFullscreenTransform();
}

function setFullscreenPan(nextPanX, nextPanY) {
  if (fullscreenZoom <= FULLSCREEN_MIN_ZOOM) {
    fullscreenPanX = 0;
    fullscreenPanY = 0;
  } else {
    fullscreenPanX = nextPanX;
    fullscreenPanY = nextPanY;
  }
  applyFullscreenTransform();
}

function applyFullscreenTransform() {
  const fullscreenImage = $("fullscreenImage");
  fullscreenImage.style.transform = `translate(${fullscreenPanX}px, ${fullscreenPanY}px) scale(${fullscreenZoom})`;
  fullscreenImage.classList.toggle("is-pannable", fullscreenZoom > FULLSCREEN_MIN_ZOOM);
}

function resetFullscreenZoom() {
  setFullscreenZoom(1);
}

function openFullscreenFromImage(imageElement) {
  if (!imageElement?.src) {
    return;
  }
  const overlay = $("fullscreenOverlay");
  const fullscreenImage = $("fullscreenImage");
  fullscreenImage.src = imageElement.src;
  fullscreenImage.classList.remove("is-dragging");
  fullscreenDragging = false;
  resetFullscreenZoom();
  overlay.classList.remove("hidden");
}

function closeFullscreen() {
  fullscreenDragging = false;
  $("fullscreenImage").classList.remove("is-dragging");
  resetFullscreenZoom();
  $("fullscreenOverlay").classList.add("hidden");
}

function setStatus(message, kind = "ok") {
  const statusCard = $("statusCard");
  const statusText = $("statusText");
  if (kind !== "warn") {
    statusCard.classList.add("hidden");
    statusCard.classList.remove("ok", "warn");
    statusText.textContent = "";
    return;
  }

  statusCard.classList.remove("hidden");
  statusCard.classList.remove("ok", "warn");
  statusCard.classList.add("warn");
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

function renderFromDesign(design) {
  state.lastDesign = design;
  renderMetrics(design);

  $("sldImage").src = svgToDataUri(design.sld.svg);
  $("gaImage").src = svgToDataUri(design.ga.svg);

  const warning = design.summary.warning_flag;
  if (warning) {
    setStatus(
      `Incoming current ${design.summary.total_busbar_current.toFixed(2)} A is less than outgoing capacity ${design.summary.total_outgoing_rating.toFixed(0)} A.`,
      "warn",
    );
  } else {
    setStatus("", "ok");
  }
}

async function generateDesign() {
  const api = await waitForApi();
  let payload;
  try {
    payload = collectInputs();
  } catch (error) {
    window.alert(error.message);
    return;
  }
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
    state.hasPendingChanges = false;
  } catch (error) {
    state.lastDesign = null;
    setPreviewPlaceholders();
    $("summaryGrid").innerHTML = "";
    window.alert(error.message);
    setStatus(error.message, "warn");
  } finally {
    setLoading(false);
  }
}

async function analyzeBillUploads() {
  if (!state.uploadedBills.length) {
    window.alert("Add at least one PDF bill before analyzing.");
    return;
  }

  const api = await waitForApi();
  setLoading(true);
  try {
    const files = await filesToPayload(state.uploadedBills);
    const response = await api.analyze_bills({ files });
    if (!response || response.ok === false) {
      throw new Error(response?.error || "Bill analysis failed");
    }

      $("recommendedSolarLabel").textContent = `Recommended Solar Capacity: ${response.recommended_kw} kW`;
      $("uploadAnalysisResult").classList.remove("hidden");
      $("analyzeBillsButton").disabled = true;
      state.solarRecommendation = response.recommended_kw;
      const recommendedInline = $("recommendedInline");
      if (recommendedInline) {
        recommendedInline.textContent = `Recommended: ${response.recommended_kw} kW`;
        recommendedInline.classList.remove("hidden");
      }
  } catch (error) {
    window.alert(error.message);
  } finally {
    setLoading(false);
  }
}

async function chooseBillFiles() {
  const api = await waitForApi();
  if (window.pywebview?.api?.pick_bill_files) {
    const response = await api.pick_bill_files();
    if (!response || response.ok === false) {
      return;
    }
    await addUploadedBills(response.files || []);
    return;
  }

  $("billFilesInput").click();
}

async function refreshThemeForLastDesign() {
  if (!state.lastDesign?.inputs) {
    return;
  }

  const api = await waitForApi();
  const payload = {
    ...state.lastDesign.inputs,
    theme: state.theme,
  };

  setLoading(true);
  try {
    const design = await api.generate(payload);
    if (!design.ok) {
      throw new Error(design.error || "Design generation failed");
    }
    renderFromDesign(design);
  } catch (error) {
    setStatus(error.message, "warn");
  } finally {
    setLoading(false);
  }
}

async function exportFile(methodName, suggestedName) {
  const api = await waitForApi();
  let payload;
  try {
    payload = collectInputs();
  } catch (error) {
    window.alert(error.message);
    return;
  }
  setLoading(true);

  try {
    const response = await api[methodName](payload);
    if (!response || response.ok === false) {
      return;
    }
  } catch (error) {
    return;
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
  state.solarRecommendation = state.solar_kw;
  state.solarInputMode = state.solar_kw ? "recommended" : "upload";
  state.uploadedBills = [];

  $("solarKw").value = formatInputValue(parseOptionalNumber(state.solar_kw));
  $("gridKw").value = formatInputValue(parseOptionalNumber(state.grid_kw));
  $("numDg").value = formatInputValue(parseOptionalNumber(state.num_dg));
  $("numOutputs").value = formatInputValue(parseOptionalNumber(state.num_outputs));
  $("busbarMaterial").value = state.busbar_material || "";
  $("numPoles").value = state.num_poles ? String(state.num_poles) : "";

  document.body.dataset.theme = state.theme;
  $("themeToggle").innerHTML = getThemeIconSVG(state.theme);
  $("themeToggle").setAttribute("aria-label", state.theme === "dark" ? "Switch to light theme" : "Switch to dark theme");
  $("themeToggle").setAttribute("title", state.theme === "dark" ? "Switch to light theme" : "Switch to dark theme");

  setPreviewPlaceholders();
  renderDynamicFields();
  setSolarInputMode(state.solarInputMode, state.solarRecommendation);
}

function bindEvents() {
  $("uploadBillsButton").addEventListener("click", openUploadModal);
  const uploadAgainEl = $("uploadBillsAgainButton");
  if (uploadAgainEl) uploadAgainEl.addEventListener("click", openUploadModal);
  $("uploadModalClose").addEventListener("click", closeUploadModal);
  $("uploadModalBackdrop").addEventListener("click", closeUploadModal);
  $("cancelUploadButton").addEventListener("click", closeUploadModal);
  $("selectFilesButton").addEventListener("click", chooseBillFiles);
  $("billFilesInput").addEventListener("change", async (event) => addUploadedBills(event.target.files));
  $("analyzeBillsButton").addEventListener("click", analyzeBillUploads);
  $("uploadDropzone").addEventListener("dragenter", (event) => {
    event.preventDefault();
    $("uploadDropzone").classList.add("is-dragover");
  });
  $("uploadDropzone").addEventListener("dragover", (event) => {
    event.preventDefault();
    $("uploadDropzone").classList.add("is-dragover");
  });
  $("uploadDropzone").addEventListener("dragleave", () => {
    $("uploadDropzone").classList.remove("is-dragover");
  });
  $("uploadDropzone").addEventListener("drop", handleBillDrop);
  $("proceedRecommendedButton").addEventListener("click", () => {
    if (state.solarRecommendation !== null) {
      setSolarInputMode("recommended", state.solarRecommendation);
    }
    closeUploadModal();
  });
  $("enterManuallyButton").addEventListener("click", () => {
    setSolarInputMode("manual");
    closeUploadModal();
    const solarInput = $("solarKw");
    if (solarInput) solarInput.focus();
  });
  $("billFilesList").addEventListener("click", (event) => {
    const removeIndex = event.target.getAttribute("data-remove-bill-index");
    if (removeIndex === null || removeIndex === undefined) {
      return;
    }
    state.uploadedBills.splice(Number(removeIndex), 1);
    renderBillFileList();
  });

  $("themeToggle").addEventListener("click", async () => {
    state.theme = state.theme === "dark" ? "light" : "dark";
    document.body.dataset.theme = state.theme;
    $("themeToggle").innerHTML = getThemeIconSVG(state.theme);
    $("themeToggle").setAttribute("aria-label", state.theme === "dark" ? "Switch to light theme" : "Switch to dark theme");
    $("themeToggle").setAttribute("title", state.theme === "dark" ? "Switch to light theme" : "Switch to dark theme");
    const api = await waitForApi();
    await api.set_theme(state.theme);
    if (!state.lastDesign) {
      setPreviewPlaceholders();
      return;
    }

    if (state.hasPendingChanges) {
      await refreshThemeForLastDesign();
      return;
    }

    await generateDesign();
  });

  ["generateButtonOutput"].forEach((id) => {
    $(id).addEventListener("click", generateDesign);
  });

  $("downloadPdfButton").addEventListener("click", () => exportFile("export_pdf", "microgrid_panel_report.pdf"));
  $("downloadGaButton").addEventListener("click", () => exportFile("export_ga_pdf", "microgrid_panel_ga.pdf"));
  $("downloadExcelButton").addEventListener("click", () => exportFile("export_excel", "microgrid_panel_bom.xlsx"));
  $("fullscreenSldButton").addEventListener("click", () => openFullscreenFromImage($("sldImage")));
  $("fullscreenGaButton").addEventListener("click", () => openFullscreenFromImage($("gaImage")));
  $("fullscreenClose").addEventListener("click", closeFullscreen);
  $("fullscreenOverlay").addEventListener("click", (event) => {
    if (event.target.id === "fullscreenOverlay") {
      closeFullscreen();
    }
  });

  $("fullscreenOverlay").addEventListener(
    "wheel",
    (event) => {
      if ($("fullscreenOverlay").classList.contains("hidden")) {
        return;
      }

      // Use Ctrl+Wheel (or wheel at 1x) to zoom; otherwise pan while zoomed in.
      if (event.ctrlKey || event.metaKey || fullscreenZoom <= FULLSCREEN_MIN_ZOOM) {
        event.preventDefault();
        const direction = event.deltaY < 0 ? 1 : -1;
        const nextZoom = fullscreenZoom + (direction * FULLSCREEN_ZOOM_STEP);
        setFullscreenZoom(nextZoom);
        return;
      }

      event.preventDefault();
      setFullscreenPan(
        fullscreenPanX - (event.deltaX * FULLSCREEN_PAN_WHEEL_STEP),
        fullscreenPanY - (event.deltaY * FULLSCREEN_PAN_WHEEL_STEP),
      );
    },
    { passive: false },
  );

  $("fullscreenImage").addEventListener("mousedown", (event) => {
    if (fullscreenZoom <= FULLSCREEN_MIN_ZOOM || event.button !== 0) {
      return;
    }
    fullscreenDragging = true;
    fullscreenDragStartX = event.clientX;
    fullscreenDragStartY = event.clientY;
    fullscreenDragBasePanX = fullscreenPanX;
    fullscreenDragBasePanY = fullscreenPanY;
    $("fullscreenImage").classList.add("is-dragging");
    event.preventDefault();
  });

  document.addEventListener("mousemove", (event) => {
    if (!fullscreenDragging) {
      return;
    }
    const dx = event.clientX - fullscreenDragStartX;
    const dy = event.clientY - fullscreenDragStartY;
    setFullscreenPan(fullscreenDragBasePanX + dx, fullscreenDragBasePanY + dy);
  });

  document.addEventListener("mouseup", () => {
    if (!fullscreenDragging) {
      return;
    }
    fullscreenDragging = false;
    $("fullscreenImage").classList.remove("is-dragging");
  });

  $("fullscreenImage").addEventListener("dblclick", () => {
    resetFullscreenZoom();
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      closeFullscreen();
      closeUploadModal();
    }
  });

  ["solarKw", "gridKw", "numDg", "numOutputs", "busbarMaterial", "numPoles"].forEach((id) => {
    $(id).addEventListener("change", () => {
      state.hasPendingChanges = true;
      renderDynamicFields();
    });
  });

  ["solarKw", "gridKw", "numDg", "numOutputs"].forEach((id) => {
    $(id).addEventListener("input", () => {
      state.hasPendingChanges = true;
      renderDynamicFields();
    });
  });

  $("solarKw").addEventListener("input", () => {
    state.solarInputMode = "manual";
    $("solarRecommendationChip").classList.add("hidden");
  });

  document.addEventListener("input", (event) => {
    if (event.target.matches("#dgInputs input, #outgoingInputs input")) {
      state.hasPendingChanges = true;
      state.dg_ratings = collectDynamicInputValues("dgInputs");
      state.outgoing_ratings = collectDynamicInputValues("outgoingInputs");
    }
  });
}

document.addEventListener("DOMContentLoaded", async () => {
  elements.body = document.body;
  bindEvents();
  enhanceNumberSteppers(document);
  renderDynamicFields();
  await loadInitialState();
});
