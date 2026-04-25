import * as THREE from "./assets/vendor/three.module.js";

const BACKEND_BASE =
  window.location.port === "8000" ? window.location.origin : "http://127.0.0.1:8000";
const textureLoader = new THREE.TextureLoader();
const earthTexture = textureLoader.load("./assets/textures/earth_atmos_2048.jpg");
const cloudTexture = textureLoader.load("./assets/textures/earth_clouds_1024.png");
earthTexture.colorSpace = THREE.SRGBColorSpace;
cloudTexture.colorSpace = THREE.SRGBColorSpace;

const state = {
  mode: "civilian",
  analysisDate: todayIsoDate(),
  location: {
    city: "Basking Ridge, NJ",
    lat: 40.7062,
    lon: -74.5493,
  },
  status: null,
  visibility: null,
  infrastructure: null,
  model: null,
  briefing: null,
  replay: [],
};

const els = {
  modeSwitch: document.getElementById("mode-switch"),
  locationChip: document.getElementById("location-chip"),
  statusUpdated: document.getElementById("status-updated"),
  openModelModal: document.getElementById("open-model-modal"),
  stormPill: document.getElementById("storm-pill"),
  statusEyebrow: document.getElementById("status-eyebrow"),
  stormTitle: document.getElementById("storm-title"),
  stormSummary: document.getElementById("storm-summary"),
  modelLadder: document.getElementById("model-ladder"),
  forecastVisual: document.getElementById("forecast-visual"),
  globeModel: document.getElementById("globe-model"),
  currentKp: document.getElementById("current-kp"),
  bzValue: document.getElementById("bz-value"),
  windSpeed: document.getElementById("wind-speed"),
  briefingSource: document.getElementById("briefing-source"),
  briefingHeadline: document.getElementById("briefing-headline"),
  briefingSummary: document.getElementById("briefing-summary"),
  briefingPoints: document.getElementById("briefing-points"),
  impactCopy: document.getElementById("impact-copy"),
  probabilityMeta: document.getElementById("probability-meta"),
  probabilityRing: document.getElementById("probability-ring"),
  probabilityValue: document.getElementById("probability-value"),
  visibilityMessage: document.getElementById("visibility-message"),
  lookWindow: document.getElementById("look-window"),
  cloudCover: document.getElementById("cloud-cover"),
  viewlineLat: document.getElementById("viewline-lat"),
  skyCopy: document.getElementById("sky-copy"),
  analysisDate: document.getElementById("analysis-date"),
  analysisLive: document.getElementById("analysis-live"),
  analysisNote: document.getElementById("analysis-note"),
  mapAnalysisLabel: document.getElementById("map-analysis-label"),
  loadReplay: document.getElementById("load-replay"),
  replayList: document.getElementById("replay-list"),
  eventSource: document.getElementById("event-source"),
  btValue: document.getElementById("bt-value"),
  gScale: document.getElementById("g-scale"),
  infraLevel: document.getElementById("infra-level"),
  riskList: document.getElementById("risk-list"),
  companyCopy: document.getElementById("company-copy"),
  openAlertModal: document.getElementById("open-alert-modal"),
  alertModal: document.getElementById("alert-modal"),
  closeAlertModal: document.getElementById("close-alert-modal"),
  alertForm: document.getElementById("alert-form"),
  alertPhone: document.getElementById("alert-phone"),
  alertThreshold: document.getElementById("alert-threshold"),
  thresholdValue: document.getElementById("threshold-value"),
  alertMessage: document.getElementById("alert-message"),
  modelModal: document.getElementById("model-modal"),
  closeModelModal: document.getElementById("close-model-modal"),
  modelModalTitle: document.getElementById("model-modal-title"),
  modelModalSummary: document.getElementById("model-modal-summary"),
  modelScaleList: document.getElementById("model-scale-list"),
  modelOrbit: document.getElementById("model-orbit"),
  modelBars: document.getElementById("model-bars"),
  modelFactorChips: document.getElementById("model-factor-chips"),
  heroCity: document.getElementById("hero-city"),
  heroSubcopy: document.getElementById("hero-subcopy"),
  globeSeverity: document.getElementById("globe-severity"),
  mapLocationLabel: document.getElementById("map-location-label"),
  countdown: document.getElementById("countdown"),
  countdownCopy: document.getElementById("countdown-copy"),
  heartbeatCopy: document.getElementById("heartbeat-copy"),
  heartbeatPath: document.getElementById("heartbeat-path"),
  eventHeadline: document.getElementById("event-headline"),
  eventTiming: document.getElementById("event-timing"),
  eventImpactList: document.getElementById("event-impact-list"),
  globeShell: document.getElementById("globe-shell"),
  globeCanvas: document.getElementById("globe-canvas"),
};

const globe = createGlobeScene(els.globeShell, els.globeCanvas);
const debug = true;

function logDebug(message, payload) {
  if (!debug) return;
  if (payload === undefined) {
    console.log(`[SolarSentinel] ${message}`);
    return;
  }
  console.log(`[SolarSentinel] ${message}`, payload);
}

function logError(message, error) {
  console.error(`[SolarSentinel] ${message}`, error);
}

function todayIsoDate() {
  return new Date().toISOString().slice(0, 10);
}

function isToday(value) {
  return value === todayIsoDate();
}

function formatLocalDate(value) {
  if (!value) return "waiting for feed";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "waiting for feed" : date.toLocaleString();
}

function prettyDate(value) {
  if (!value) return "Live now";
  const date = new Date(`${value}T00:00:00`);
  return Number.isNaN(date.getTime())
    ? value
    : date.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

function safeNumber(value, digits = 0) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "--";
  return Number(value).toFixed(digits);
}

function formatPercent(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "--";
  return `${Math.round(Number(value))}%`;
}

function formatCountdown(seconds) {
  if (!seconds || seconds <= 0) return "No impact expected";
  const total = Math.max(0, Math.floor(seconds));
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const remainingSeconds = total % 60;
  return `${String(hours).padStart(2, "0")}h ${String(minutes).padStart(2, "0")}m ${String(remainingSeconds).padStart(2, "0")}s`;
}

function severityClass(level) {
  return (level || "quiet").toLowerCase();
}

function severityLabel(level) {
  const key = (level || "quiet").toLowerCase();
  return {
    quiet: "Quiet",
    watch: "Watch",
    moderate: "Elevated",
    high: "High",
    severe: "Severe",
  }[key] || "Quiet";
}

function plainEnglish(level) {
  const key = (level || "quiet").toLowerCase();
  return {
    quiet: "No meaningful storm risk right now.",
    watch: "Conditions are worth watching.",
    moderate: "A visible storm may be building.",
    high: "Storm conditions look strong.",
    severe: "A major storm is likely.",
  }[key] || "No meaningful storm risk right now.";
}

function getSeverityScale(model) {
  return Array.isArray(model?.severity_scale) && model.severity_scale.length ? model.severity_scale : [
    { key: "quiet", label: "Quiet", summary: "Low storm risk.", rank: 0, tone: "calm" },
    { key: "watch", label: "Watch", summary: "Worth monitoring.", rank: 1, tone: "watch" },
    { key: "moderate", label: "Moderate", summary: "Some visible effects are possible.", rank: 2, tone: "moderate" },
    { key: "high", label: "High", summary: "Strong storm conditions are plausible.", rank: 3, tone: "high" },
    { key: "severe", label: "Severe", summary: "Major storm conditions are likely.", rank: 4, tone: "severe" },
  ];
}

function setMode(mode) {
  state.mode = mode;
  document.body.dataset.mode = mode;
  els.heroSubcopy.textContent =
    mode === "company"
      ? "Operational context on the left, live globe on the right."
      : "Global storm context with your location pinned on the globe.";
}

function setConnectionState(connected, detail) {
  logDebug(connected ? "backend connected" : "backend offline", detail);
}

async function fetchJson(path, options) {
  const response = await fetch(`${BACKEND_BASE}${path}`, options);
  const contentType = response.headers.get("content-type") || "";
  const body = contentType.includes("application/json") ? await response.json() : await response.text();
  if (!response.ok) {
    const error = new Error(`${path} failed with ${response.status}`);
    error.details = body;
    throw error;
  }
  return body;
}

async function reverseGeocode(lat, lon) {
  const response = await fetch(
    `https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat=${lat}&lon=${lon}`,
    { headers: { Accept: "application/json" } },
  );
  if (!response.ok) throw new Error("reverse geocode failed");
  const data = await response.json();
  const address = data.address || {};
  const city = address.city || address.town || address.village || address.hamlet || address.county || "Your location";
  const region = address.state || address.country_code?.toUpperCase() || address.country || "";
  return {
    city: region ? `${city}, ${region}` : city,
    lat,
    lon,
  };
}

async function initLocation() {
  applyLocation(state.location);
  if (!navigator.geolocation) return;
  return new Promise((resolve) => {
    navigator.geolocation.getCurrentPosition(
      async ({ coords }) => {
        try {
          const place = await reverseGeocode(coords.latitude, coords.longitude);
          applyLocation(place);
        } catch (error) {
          logError("reverse geocode failed", error);
          applyLocation({
            city: "Approximate location",
            lat: coords.latitude,
            lon: coords.longitude,
          });
        }
        resolve();
      },
      () => resolve(),
      { enableHighAccuracy: false, timeout: 5000, maximumAge: 600000 },
    );
  });
}

function applyLocation(location) {
  state.location = location;
  els.heroCity.textContent = location.city;
  els.locationChip.textContent = `Location: ${location.city}`;
  els.mapLocationLabel.textContent = location.city;
  globe.setLocation(location.lat, location.lon);
}

async function fetchForecastModel(latitude) {
  if (isToday(state.analysisDate)) {
    return fetchJson(`/model/predict/current?latitude=${latitude}`);
  }
  return fetchJson("/model/predict", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ date: state.analysisDate, latitude }),
  });
}

async function fetchCivilianBrief(latitude, longitude) {
  const query = new URLSearchParams({
    latitude: String(latitude),
    longitude: String(longitude),
    analysis_date: state.analysisDate,
  });
  return fetchJson(`/api/civilian-brief?${query.toString()}`);
}

function renderRiskList(regions) {
  els.riskList.innerHTML = "";
  if (!regions?.length) {
    els.riskList.innerHTML = '<p class="empty-copy">No regional warning clusters right now.</p>';
    return;
  }

  for (const region of regions.slice(0, 3)) {
    const row = document.createElement("div");
    row.className = "risk-row";
    row.innerHTML = `
      <div>
        <strong>${region.region_id}</strong>
        <div class="mono-meta">${region.name}</div>
      </div>
      <span class="risk-level ${region.threat_level}">${region.threat_level}</span>
    `;
    els.riskList.append(row);
  }
}

function renderReplay(items) {
  els.replayList.innerHTML = "";
  if (!items?.length) {
    els.replayList.innerHTML = '<p class="empty-copy">Replay unavailable.</p>';
    return;
  }

  for (const item of items) {
    const node = document.createElement("div");
    node.className = "replay-item";
    node.innerHTML = `
      <strong>${item.date} · ${severityLabel(item.prediction)}</strong>
      <div class="mono-meta">${formatPercent((item.confidence || 0) * 100)} confidence</div>
      <p>${item.explanation}</p>
    `;
    els.replayList.append(node);
  }
}

function renderModelLadder(model) {
  els.modelLadder.innerHTML = "";
  for (const item of getSeverityScale(model)) {
    const row = document.createElement("div");
    row.className = `model-ladder-row${item.key === model?.prediction ? " is-active" : ""}`;
    row.innerHTML = `
      <div class="model-ladder-rank">${Number(item.rank) + 1}</div>
      <div class="model-ladder-copy">
        <strong>${item.label}</strong>
        <span>${item.summary}</span>
      </div>
      <div class="model-ladder-tag">${item.key === model?.prediction ? "current" : ""}</div>
    `;
    els.modelLadder.append(row);
  }
}

function renderModelModal(model) {
  els.modelModalTitle.textContent = model?.prediction_label
    ? `${model.prediction_label} forecast`
    : "Model forecast";
  els.modelModalSummary.textContent = model?.prediction_summary || "The model is preparing a severity estimate.";

  els.modelScaleList.innerHTML = "";
  for (const item of getSeverityScale(model)) {
    const row = document.createElement("div");
    row.className = `model-scale-item${item.key === model?.prediction ? " is-active" : ""}`;
    row.innerHTML = `
      <div class="model-scale-rank">${Number(item.rank) + 1}</div>
      <div class="model-scale-copy">
        <strong>${item.label}</strong>
        <span>${item.summary}</span>
      </div>
      <div class="model-ladder-tag">${item.key === model?.prediction ? formatPercent((model.confidence || 0) * 100) : ""}</div>
    `;
    els.modelScaleList.append(row);
  }

  els.modelOrbit.innerHTML = renderModelOrbit(model?.prediction_orbit || []);

  els.modelBars.innerHTML = "";
  for (const item of (model?.prediction_chart || [])) {
    const bar = document.createElement("div");
    bar.className = "model-bar";
    bar.innerHTML = `
      <div class="model-bar-head">
        <strong>${item.label}</strong>
        <span class="mono-meta">${formatPercent(Number(item.value) * 100)}</span>
      </div>
      <div class="model-bar-track">
        <div class="model-bar-fill" style="width:${Math.max(2, Number(item.value) * 100)}%;background:${item.color}"></div>
      </div>
    `;
    els.modelBars.append(bar);
  }

  els.modelFactorChips.innerHTML = "";
  for (const factor of (model?.top_factors || []).slice(0, 3)) {
    const chip = document.createElement("div");
    chip.className = "factor-chip";
    chip.innerHTML = `
      <strong>${factor.feature}</strong>
      <span>${Number(factor.value).toFixed(1)}</span>
    `;
    els.modelFactorChips.append(chip);
  }
}

function renderModelOrbit(orbit) {
  if (!Array.isArray(orbit) || !orbit.length) return "";
  const cx = 120;
  const cy = 120;
  const baseRadius = 28;
  const rings = [34, 54, 74, 94];
  const polar = orbit.map((item) => {
    const angle = ((Number(item.angle) || 0) - 90) * (Math.PI / 180);
    const radius = baseRadius + (Number(item.radius) || 0.5) * 78;
    return {
      ...item,
      x: cx + Math.cos(angle) * radius,
      y: cy + Math.sin(angle) * radius,
      size: 5 + (Number(item.value) || 0) * 12,
    };
  });
  return `
    <svg class="model-orbit-svg" viewBox="0 0 240 240" role="img" aria-label="Model orbit visualization">
      ${rings.map((ring) => `<circle cx="${cx}" cy="${cy}" r="${ring}" class="model-orbit-ring"/>`).join("")}
      <circle cx="${cx}" cy="${cy}" r="16" class="model-orbit-core"/>
      ${polar.map((item) => `
        <g class="model-orbit-node${item.active ? " is-active" : ""}">
          <line x1="${cx}" y1="${cy}" x2="${item.x}" y2="${item.y}" class="model-orbit-ray"/>
          <circle cx="${item.x}" cy="${item.y}" r="${item.size}" fill="${item.color}" class="model-orbit-dot"/>
          <text x="${item.x}" y="${item.y - item.size - 8}" text-anchor="middle" class="model-orbit-value">${formatPercent(Number(item.value) * 100)}</text>
          <text x="${item.x}" y="${item.y + item.size + 16}" text-anchor="middle" class="model-orbit-label">${item.label}</text>
        </g>
      `).join("")}
    </svg>
  `;
}

function formatAlertTiming(alert) {
  if (!alert) return "Waiting for live status.";
  const parts = [];
  if (alert.issue_datetime) parts.push(`Issued ${formatLocalDate(alert.issue_datetime)}`);
  if (alert.valid_from) parts.push(`From ${formatLocalDate(alert.valid_from)}`);
  if (alert.valid_to) parts.push(`Until ${formatLocalDate(alert.valid_to)}`);
  if (alert.warning_condition) parts.push(alert.warning_condition);
  return parts.join(" · ") || "Live NOAA alert timing unavailable.";
}

function buildStatusSummary(status, model) {
  if (status?.summary) return status.summary;
  const alert = status?.primary_alert;
  if (alert?.summary) return alert.summary;
  if (model?.prediction_summary) return model.prediction_summary;
  return `${plainEnglish(model?.prediction)} Solar wind ${safeNumber(status?.wind_speed)} km/s, Bz ${safeNumber(status?.bz, 1)} nT.`;
}

function renderForecastVisual(model) {
  const chart = Array.isArray(model?.prediction_chart) ? model.prediction_chart : [];
  if (!chart.length) {
    els.forecastVisual.innerHTML = "";
    return;
  }

  const width = 560;
  const height = 220;
  const left = 28;
  const right = 28;
  const top = 24;
  const bottom = 54;
  const innerWidth = width - left - right;
  const innerHeight = height - top - bottom;
  const step = chart.length > 1 ? innerWidth / (chart.length - 1) : innerWidth;
  const points = chart.map((item, index) => {
    const value = Math.max(0, Math.min(1, Number(item.value) || 0));
    return {
      ...item,
      percent: formatPercent(value * 100),
      x: left + index * step,
      y: top + (1 - value) * innerHeight,
    };
  });
  const line = points.map((point, index) => `${index === 0 ? "M" : "L"} ${point.x} ${point.y}`).join(" ");
  const area = `${line} L ${points.at(-1).x} ${top + innerHeight} L ${points[0].x} ${top + innerHeight} Z`;
  const gridLevels = [0.25, 0.5, 0.75];

  els.forecastVisual.innerHTML = `
    <div class="forecast-header">
      <div>
        <strong>Forecast spread</strong>
        <span class="mono-meta">Model confidence across all severity bands</span>
      </div>
      <div class="forecast-active-pill" style="--active-color:${points.find((item) => item.active)?.color || "#48b8ff"}">
        ${model?.prediction_label || "Forecast"}
      </div>
    </div>
    <svg class="forecast-svg" viewBox="0 0 ${width} ${height}" role="img" aria-label="Forecast probability graph">
      <defs>
        <linearGradient id="forecast-line-gradient" x1="0%" y1="0%" x2="100%" y2="0%">
          ${points.map((point, index) => `<stop offset="${(index / Math.max(1, points.length - 1)) * 100}%" stop-color="${point.color}"/>`).join("")}
        </linearGradient>
        <linearGradient id="forecast-area-gradient" x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stop-color="rgba(72,184,255,0.36)"/>
          <stop offset="100%" stop-color="rgba(72,184,255,0.02)"/>
        </linearGradient>
      </defs>
      ${gridLevels.map((level) => {
        const y = top + (1 - level) * innerHeight;
        return `<line x1="${left}" y1="${y}" x2="${width - right}" y2="${y}" class="forecast-grid-line"/>`;
      }).join("")}
      <path d="${area}" class="forecast-area"></path>
      <path d="${line}" class="forecast-line"></path>
      ${points.map((point) => `
        <g class="forecast-point${point.active ? " is-active" : ""}">
          <line x1="${point.x}" y1="${point.y}" x2="${point.x}" y2="${top + innerHeight}" class="forecast-stem"/>
          <circle cx="${point.x}" cy="${point.y}" r="${point.active ? 8 : 5.5}" fill="${point.color}" class="forecast-node"/>
          <text x="${point.x}" y="${point.y - 14}" text-anchor="middle" class="forecast-value">${point.percent}</text>
          <text x="${point.x}" y="${height - 18}" text-anchor="middle" class="forecast-label">${point.label}</text>
        </g>
      `).join("")}
    </svg>
  `;
}

function renderEventStrip(status) {
  const alert = status?.primary_alert;
  els.eventHeadline.textContent = alert?.summary || "No active NOAA alert right now.";
  els.eventTiming.textContent = formatAlertTiming(alert);
  els.eventImpactList.innerHTML = "";

  const details = [];
  if (alert?.product_id) details.push({ title: "Product", body: alert.product_id });
  if (alert?.warning_condition) details.push({ title: "Condition", body: alert.warning_condition });
  if (alert?.valid_from || alert?.valid_to) {
    details.push({
      title: "Window",
      body: `${alert.valid_from ? formatLocalDate(alert.valid_from) : "Now"} to ${alert.valid_to ? formatLocalDate(alert.valid_to) : "ongoing"}`,
    });
  }
  const impacts = Array.isArray(alert?.impacts) ? alert.impacts.filter(Boolean).slice(0, 3) : [];
  for (const detail of details) {
    const card = document.createElement("div");
    card.className = "event-impact-card";
    card.innerHTML = `
      <strong>${detail.title}</strong>
      <span>${detail.body}</span>
    `;
    els.eventImpactList.append(card);
  }

  for (const impact of impacts) {
    const card = document.createElement("div");
    card.className = "event-impact-card";
    const [title, ...rest] = impact.split(" - ");
    card.innerHTML = `
      <strong>${title || "Impact"}</strong>
      <span>${rest.join(" - ") || impact}</span>
    `;
    els.eventImpactList.append(card);
  }

  if (!details.length && !impacts.length) {
    els.eventImpactList.innerHTML = `
      <div class="event-impact-card">
        <strong>Conditions stable</strong>
        <span>Fresh impacts will appear here when NOAA publishes an active alert.</span>
      </div>
    `;
  }
}

function updateHeartbeat(status) {
  const bz = Number(status?.bz ?? 0);
  const points = [];
  const baseY = 62;
  const amplitude = Math.min(38, Math.max(8, Math.abs(bz) * 2));
  for (let index = 0; index <= 24; index += 1) {
    const x = index * 50;
    const y =
      index % 6 === 3
        ? baseY - amplitude
        : index % 6 === 4
          ? baseY + amplitude * 0.9
          : baseY + Math.sin(index / 2) * Math.max(4, amplitude * 0.15);
    points.push(`${index === 0 ? "M" : "L"}${x},${y.toFixed(1)}`);
  }
  els.heartbeatPath.setAttribute("d", points.join(" "));
  els.heartbeatPath.style.stroke = bz < -10 ? "#f05a63" : bz < 0 ? "#f3ab58" : "#7ec0ff";
  els.heartbeatCopy.textContent =
    bz < -15
      ? "Solar wind is pressing hard into Earth."
      : bz < -5
        ? "Negative Bz is coupling with Earth. Watch for intensification."
        : "Bz is calm or northward. Earth is resisting the storm for now.";
}

function updateUI() {
  const status = state.status || {};
  const visibility = state.visibility || {};
  const model = state.model || {};
  const briefing = state.briefing || {};
  const infrastructure = state.infrastructure || {};
  const level = model.prediction || status.storm_severity?.level || "quiet";

  els.statusUpdated.textContent = formatLocalDate(status.last_updated);
  els.statusEyebrow.textContent = isToday(state.analysisDate) ? "Current global conditions" : `Historical forecast for ${prettyDate(state.analysisDate)}`;
  els.stormPill.textContent = status.g_scale || status.storm_severity?.level || "G0";
  els.stormPill.className = `severity-pill ${severityClass(level)}`;
  els.stormTitle.textContent = `${severityLabel(level)} conditions`;
  els.stormSummary.textContent = buildStatusSummary(status, model);
  els.globeModel.textContent = `${severityLabel(model.prediction)} · ${formatPercent((model.confidence || 0) * 100)}`;
  els.currentKp.textContent = safeNumber(status.kp, 1);
  els.bzValue.textContent = `${safeNumber(status.bz, 1)} nT`;
  els.windSpeed.textContent = `${safeNumber(status.wind_speed)} km/s`;

  els.briefingSource.textContent = briefing.source || "auto";
  els.briefingHeadline.textContent = briefing.headline || "Loading briefing...";
  els.briefingSummary.textContent = briefing.summary || "Preparing a short, plain-language explanation.";
  els.briefingPoints.innerHTML = "";
  for (const point of (briefing.takeaways || []).slice(0, 3)) {
    const item = document.createElement("li");
    item.textContent = point;
    els.briefingPoints.append(item);
  }
  els.impactCopy.textContent = briefing.what_to_do || model.explanation || plainEnglish(level);

  const probability = visibility.adjusted_probability ?? visibility.probability ?? 0;
  els.probabilityMeta.textContent = `Kp need: ${safeNumber(visibility.kp_required, 1)}`;
  els.probabilityValue.textContent = formatPercent(probability);
  els.probabilityRing.style.background =
    `radial-gradient(circle closest-side, rgba(6, 13, 24, 1) 75%, transparent 76% 100%), ` +
    `conic-gradient(#7be6be 0 ${probability}%, rgba(255,255,255,0.08) ${probability}% 100%)`;
  els.visibilityMessage.textContent = visibility.message || "Waiting for local forecast.";
  els.lookWindow.textContent = visibility.look_window || "Waiting for local forecast.";
  els.cloudCover.textContent = visibility.cloud_cover_label || "N/A";
  els.viewlineLat.textContent = `${safeNumber(visibility.viewline_latitude, 1)}°`;
  els.skyCopy.textContent = visibility.sky_copy || "Waiting for local sky guidance.";

  els.analysisNote.textContent = isToday(state.analysisDate)
    ? "Live forecast by default."
    : `Historical analysis for ${prettyDate(state.analysisDate)}.`;
  els.mapAnalysisLabel.textContent = isToday(state.analysisDate) ? "Live now" : prettyDate(state.analysisDate);

  els.eventSource.textContent = status.kp_source || "NOAA 1-minute Kp";
  els.btValue.textContent = `${safeNumber(status.bt, 1)} nT`;
  els.gScale.textContent = status.g_scale || "--";
  els.infraLevel.textContent = infrastructure.recommended_warning_level || "QUIET";
  els.companyCopy.textContent = infrastructure.summary || "Waiting for live event data.";
  renderRiskList(infrastructure.region_risks);

  els.globeSeverity.textContent = status.storm_severity?.label || `${severityLabel(level)} Conditions`;
  els.countdown.textContent = formatCountdown(status.cme_countdown_seconds);
  els.countdownCopy.textContent = status.countdown_copy || "When NASA predicts the next CME impact, the timer appears here.";

  renderModelLadder(model);
  renderModelModal(model);
  renderForecastVisual(model);
  renderEventStrip(status);
  updateHeartbeat(status);
  globe.setSeverity(level, status.kp || 0, status.bz || 0);
  globe.setLocation(state.location.lat, state.location.lon);
  globe.setAuroraBand(visibility.viewline_latitude || 67, status.kp || 0);
}

async function refreshData() {
  const { lat, lon } = state.location;
  logDebug("refresh start", { lat, lon, analysisDate: state.analysisDate });
  const [status, visibility, infrastructure, model] = await Promise.all([
    fetchJson("/api/status"),
    fetchJson(`/api/visibility?lat=${lat}&lon=${lon}`),
    fetchJson("/api/infrastructure"),
    fetchForecastModel(lat),
  ]);

  let briefing = null;
  try {
    briefing = await fetchCivilianBrief(lat, lon);
  } catch (error) {
    logError("briefing fetch failed", error);
  }

  state.status = status;
  state.visibility = visibility;
  state.infrastructure = infrastructure;
  state.model = model;
  state.briefing = briefing;
  updateUI();
}

async function loadReplay() {
  const replay = await fetchJson(`/model/replay?start_date=2024-05-09&end_date=2024-05-12&latitude=${state.location.lat}`);
  state.replay = replay.items || [];
  renderReplay(state.replay);
}

async function saveAlert(event) {
  event.preventDefault();
  const payload = {
    phone: els.alertPhone.value.trim(),
    lat: state.location.lat,
    lon: state.location.lon,
    kp_threshold: Number(els.alertThreshold.value),
  };

  try {
    const result = await fetchJson("/api/alerts/subscribe", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    els.alertMessage.textContent = `Saved. Alerts will go to ${result.phone_masked}.`;
  } catch (error) {
    els.alertMessage.textContent = "Could not save the alert right now.";
    logError("alert subscribe failed", error);
  }
}

function createGlobeScene(shell, canvas) {
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  earthTexture.anisotropy = renderer.capabilities.getMaxAnisotropy();
  cloudTexture.anisotropy = renderer.capabilities.getMaxAnisotropy();

  const scene = new THREE.Scene();
  scene.fog = new THREE.Fog(0x060d18, 12, 24);

  const camera = new THREE.PerspectiveCamera(38, 1, 0.1, 100);
  camera.position.set(0, 0.2, 7.5);

  const root = new THREE.Group();
  scene.add(root);

  const stars = createStars();
  scene.add(stars);

  const lights = new THREE.Group();
  lights.add(new THREE.AmbientLight(0xb9d5ff, 1.05));
  const key = new THREE.DirectionalLight(0xffffff, 1.35);
  key.position.set(4, 2, 6);
  lights.add(key);
  const rim = new THREE.DirectionalLight(0x48b8ff, 1.0);
  rim.position.set(-5, 3, -4);
  lights.add(rim);
  scene.add(lights);

  const earth = createEarthMesh();
  const clouds = createCloudMesh();
  const atmosphere = createAtmosphereMesh();
  const auroraBand = createAuroraBand();
  const marker = createLocationMarker();
  root.add(earth, clouds, atmosphere, auroraBand, marker);

  let dragging = false;
  let lastX = 0;
  let lastY = 0;
  let rotationX = 0.25;
  let rotationY = -0.7;
  root.rotation.x = rotationX;
  root.rotation.y = rotationY;

  function onResize() {
    const rect = shell.getBoundingClientRect();
    renderer.setSize(rect.width, rect.height, false);
    camera.aspect = rect.width / rect.height;
    camera.updateProjectionMatrix();
  }

  function animate() {
    requestAnimationFrame(animate);
    if (!dragging) {
      root.rotation.y += 0.0018;
      clouds.rotation.y += 0.0012;
    }
    renderer.render(scene, camera);
  }

  canvas.addEventListener("pointerdown", (event) => {
    dragging = true;
    lastX = event.clientX;
    lastY = event.clientY;
    canvas.setPointerCapture(event.pointerId);
  });

  canvas.addEventListener("pointermove", (event) => {
    if (!dragging) return;
    const dx = event.clientX - lastX;
    const dy = event.clientY - lastY;
    lastX = event.clientX;
    lastY = event.clientY;
    rotationY += dx * 0.005;
    rotationX = Math.max(-0.85, Math.min(0.85, rotationX + dy * 0.004));
    root.rotation.y = rotationY;
    root.rotation.x = rotationX;
  });

  function endDrag() {
    dragging = false;
  }

  canvas.addEventListener("pointerup", endDrag);
  canvas.addEventListener("pointerleave", endDrag);
  window.addEventListener("resize", onResize);
  onResize();
  animate();

  return {
    setLocation(lat, lon) {
      const pos = latLonToVector(lat, lon, 2.1);
      marker.position.copy(pos);
      marker.lookAt(pos.clone().multiplyScalar(2));
    },
    setAuroraBand(viewlineLat, kp) {
      const latitude = Math.max(38, Math.min(76, Number(viewlineLat) || 67));
      const radius = Math.max(0.5, Math.cos((latitude * Math.PI) / 180) * 2.08);
      auroraBand.geometry.dispose();
      auroraBand.geometry = new THREE.TorusGeometry(radius, 0.08 + Math.min(0.18, kp * 0.012), 18, 120);
      auroraBand.position.set(0, Math.sin((latitude * Math.PI) / 180) * 2.08, 0);
      auroraBand.material.opacity = 0.22 + Math.min(0.45, kp * 0.05);
    },
    setSeverity(level, kp, bz) {
      const severe = level === "severe" || kp >= 8 || bz < -15;
      const elevated = level === "high" || level === "moderate" || kp >= 6 || bz < -8;
      atmosphere.material.color.set(severe ? 0xf05a63 : elevated ? 0xf3ab58 : 0x48b8ff);
      atmosphere.material.opacity = severe ? 0.22 : elevated ? 0.18 : 0.14;
      auroraBand.material.color.set(severe ? 0xff6d7f : elevated ? 0x7be6be : 0x48b8ff);
    },
  };
}

function createEarthMesh() {
  const geometry = new THREE.SphereGeometry(2, 96, 96);
  const material = new THREE.MeshStandardMaterial({
    map: earthTexture,
    roughness: 0.95,
    metalness: 0.01,
  });
  return new THREE.Mesh(geometry, material);
}

function createCloudMesh() {
  const geometry = new THREE.SphereGeometry(2.04, 72, 72);
  const material = new THREE.MeshStandardMaterial({
    map: cloudTexture,
    transparent: true,
    opacity: 0.4,
    depthWrite: false,
  });
  return new THREE.Mesh(geometry, material);
}

function createAtmosphereMesh() {
  const geometry = new THREE.SphereGeometry(2.18, 64, 64);
  const material = new THREE.MeshBasicMaterial({
    color: 0x48b8ff,
    transparent: true,
    opacity: 0.14,
    side: THREE.BackSide,
    blending: THREE.AdditiveBlending,
  });
  return new THREE.Mesh(geometry, material);
}

function createAuroraBand() {
  const geometry = new THREE.TorusGeometry(0.9, 0.12, 18, 120);
  const material = new THREE.MeshBasicMaterial({
    color: 0x7be6be,
    transparent: true,
    opacity: 0.3,
    blending: THREE.AdditiveBlending,
  });
  const mesh = new THREE.Mesh(geometry, material);
  mesh.rotation.x = Math.PI / 2;
  return mesh;
}

function createLocationMarker() {
  const group = new THREE.Group();
  const core = new THREE.Mesh(
    new THREE.SphereGeometry(0.045, 16, 16),
    new THREE.MeshBasicMaterial({ color: 0xffffff }),
  );
  const ring = new THREE.Mesh(
    new THREE.RingGeometry(0.08, 0.12, 32),
    new THREE.MeshBasicMaterial({ color: 0x7be6be, transparent: true, opacity: 0.8, side: THREE.DoubleSide }),
  );
  ring.lookAt(new THREE.Vector3(0, 0, 1));
  group.add(core, ring);
  return group;
}

function createStars() {
  const geometry = new THREE.BufferGeometry();
  const positions = [];
  for (let index = 0; index < 1600; index += 1) {
    const radius = 14 + Math.random() * 10;
    const theta = Math.random() * Math.PI * 2;
    const phi = Math.acos(2 * Math.random() - 1);
    positions.push(
      radius * Math.sin(phi) * Math.cos(theta),
      radius * Math.sin(phi) * Math.sin(theta),
      radius * Math.cos(phi),
    );
  }
  geometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
  const material = new THREE.PointsMaterial({
    color: 0xffffff,
    size: 0.035,
    transparent: true,
    opacity: 0.75,
    sizeAttenuation: true,
  });
  return new THREE.Points(geometry, material);
}

function latLonToVector(lat, lon, radius) {
  const phi = (90 - lat) * (Math.PI / 180);
  const theta = (lon + 180) * (Math.PI / 180);
  return new THREE.Vector3(
    -(radius * Math.sin(phi) * Math.cos(theta)),
    radius * Math.cos(phi),
    radius * Math.sin(phi) * Math.sin(theta),
  );
}

async function init() {
  setMode(state.mode);
  els.analysisDate.value = state.analysisDate;
  els.thresholdValue.textContent = els.alertThreshold.value;
  els.mapAnalysisLabel.textContent = "Live now";
  setConnectionState(false, "Checking backend connection...");
  applyLocation(state.location);

  try {
    const health = await fetchJson("/health");
    setConnectionState(true, `Backend connected at ${BACKEND_BASE}`);
    logDebug("health ok", health);
  } catch (error) {
    setConnectionState(false, `Backend offline. Expected at ${BACKEND_BASE}`);
    logError("health failed", error);
  }

  await initLocation();

  try {
    await refreshData();
  } catch (error) {
    logError("initial refresh failed", error);
    els.stormTitle.textContent = "Backend unavailable";
    els.stormSummary.textContent = `Start the API at ${BACKEND_BASE} to load live data.`;
  }

  setInterval(() => {
    refreshData().catch((error) => logError("scheduled refresh failed", error));
  }, 60000);
}

els.modeSwitch.addEventListener("click", () => {
  setMode(state.mode === "civilian" ? "company" : "civilian");
});

els.locationChip.addEventListener("click", async () => {
  await initLocation();
  await refreshData().catch((error) => logError("manual location refresh failed", error));
});

els.analysisDate.addEventListener("change", async () => {
  state.analysisDate = els.analysisDate.value || todayIsoDate();
  await refreshData().catch((error) => logError("analysis refresh failed", error));
});

els.analysisLive.addEventListener("click", async () => {
  state.analysisDate = todayIsoDate();
  els.analysisDate.value = state.analysisDate;
  await refreshData().catch((error) => logError("live analysis refresh failed", error));
});

els.loadReplay.addEventListener("click", () => {
  loadReplay().catch((error) => logError("replay load failed", error));
});

els.openAlertModal?.addEventListener("click", () => els.alertModal.showModal());
els.closeAlertModal?.addEventListener("click", () => els.alertModal.close());
els.openModelModal?.addEventListener("click", () => els.modelModal.showModal());
els.closeModelModal?.addEventListener("click", () => els.modelModal.close());
els.alertThreshold.addEventListener("input", () => {
  els.thresholdValue.textContent = els.alertThreshold.value;
});
els.alertForm.addEventListener("submit", saveAlert);

init();
