/**
 * Home Performance Card
 * Modern dashboard card for Home Performance integration
 * Version is managed in manifest.json
 */

const LitElement = customElements.get("hui-masonry-view")
  ? Object.getPrototypeOf(customElements.get("hui-masonry-view"))
  : Object.getPrototypeOf(customElements.get("hui-view"));
const html = LitElement.prototype.html;
const css = LitElement.prototype.css;

class HomePerformanceCard extends LitElement {
  static get properties() {
    return {
      hass: { type: Object },
      config: { type: Object },
    };
  }

  static getConfigElement() {
    return document.createElement("home-performance-card-editor");
  }

  static getStubConfig() {
    return {
      zone: "",
      title: "Performance Thermique",
      demo: false,
    };
  }

  setConfig(config) {
    if (!config.zone) {
      throw new Error("Veuillez spécifier une zone");
    }
    this.config = {
      title: "Performance Thermique",
      demo: false,
      ...config,
    };
  }

  getCardSize() {
    return 5;
  }

  _getEntityId(suffix) {
    const zone = this.config.zone.toLowerCase().replace(/\s+/g, "_");
    return `sensor.home_performance_${zone}_${suffix}`;
  }

  _getBinaryEntityId(suffix) {
    const zone = this.config.zone.toLowerCase().replace(/\s+/g, "_");
    return `binary_sensor.home_performance_${zone}_${suffix}`;
  }

  _getState(entityId) {
    const state = this.hass?.states[entityId];
    return state ? state.state : "unavailable";
  }

  _getAttribute(entityId, attr) {
    const state = this.hass?.states[entityId];
    return state?.attributes?.[attr];
  }

  _entityExists(entityId) {
    return this.hass?.states[entityId] !== undefined;
  }

  _isIntegrationReady() {
    if (this.config.demo) return true;
    // Check if the main sensor exists in HA
    const entityId = this._getBinaryEntityId("donnees_pretes");
    return this._entityExists(entityId);
  }

  _isDataReady() {
    if (this.config.demo) return true;
    const entityId = this._getBinaryEntityId("donnees_pretes");
    return this._getState(entityId) === "on";
  }

  _isStorageLoaded() {
    if (this.config.demo) return true;
    const entityId = this._getBinaryEntityId("donnees_pretes");
    const storageLoaded = this._getAttribute(entityId, "storage_loaded");
    return storageLoaded === true;
  }

  _getProgress() {
    if (this.config.demo) return 100;
    const entityId = this._getEntityId("progression_analyse");
    const value = parseFloat(this._getState(entityId));
    return isNaN(value) ? 0 : Math.min(100, Math.max(0, value));
  }

  _getTimeRemaining() {
    if (this.config.demo) return "Prêt";
    const entityId = this._getEntityId("temps_restant_analyse");
    return this._getState(entityId);
  }

  _getInsulationData(rating, insulationAttrs = {}) {
    const data = {
      // Calculated ratings
      excellent: { label: "Excellent", color: "#10b981", icon: "mdi:shield-check", desc: "Très bien isolé" },
      good: { label: "Bon", color: "#22c55e", icon: "mdi:shield-half-full", desc: "Bien isolé" },
      average: { label: "Moyen", color: "#eab308", icon: "mdi:shield-outline", desc: "Isolation standard" },
      poor: { label: "Faible", color: "#f97316", icon: "mdi:shield-alert", desc: "À améliorer" },
      very_poor: { label: "Critique", color: "#ef4444", icon: "mdi:shield-off", desc: "Isolation insuffisante" },
      // Inferred excellent
      excellent_inferred: { label: "🏆 Excellente", color: "#059669", icon: "mdi:trophy", desc: "Chauffe minimale nécessaire" },
    };

    // Get season and status from attributes
    const season = insulationAttrs.season;
    const status = insulationAttrs.status;
    const message = insulationAttrs.message;
    const kValue = insulationAttrs.k_value;
    const kSource = insulationAttrs.k_source;

    // Handle season-specific messages
    if (season === "summer") {
      const lastK = kValue ? `(K=${kValue} W/°C)` : "";
      return {
        label: "☀️ Mode été",
        color: "#f59e0b",
        icon: "mdi:weather-sunny",
        desc: kValue ? `Dernière mesure ${lastK}` : "Mesure impossible"
      };
    }

    if (season === "off_season") {
      const lastK = kValue ? `(K=${kValue} W/°C)` : "";
      return {
        label: "🌤️ Hors saison",
        color: "#8b5cf6",
        icon: "mdi:weather-partly-cloudy",
        desc: kValue ? `Dernière mesure ${lastK}` : "ΔT insuffisant"
      };
    }

    // Handle excellent inferred
    if (rating === "excellent_inferred" || status === "excellent_inferred") {
      return data.excellent_inferred;
    }

    // Handle waiting states
    if (!rating || rating === "unknown" || rating === "unavailable") {
      // Check if we have a last valid K to show
      if (kValue && kSource === "last_valid") {
        return {
          label: "En attente",
          color: "#6b7280",
          icon: "mdi:shield-outline",
          desc: `Dernier K: ${kValue} W/°C`
        };
      }
      // Show specific message from status
      if (message) {
        return { label: "En attente", color: "#6b7280", icon: "mdi:shield-outline", desc: message };
      }
      return { label: "En attente", color: "#6b7280", icon: "mdi:shield-outline", desc: "Chauffe nécessaire" };
    }

    return data[rating] || { label: rating, color: "#6b7280", icon: "mdi:shield-outline", desc: "" };
  }

  _getPerformanceData(level) {
    const data = {
      excellent: { label: "Excellente", color: "#10b981", icon: "mdi:leaf", badge: "−40%" },
      standard: { label: "Standard", color: "#eab308", icon: "mdi:minus", badge: "~" },
      to_optimize: { label: "À optimiser", color: "#f97316", icon: "mdi:trending-up", badge: "+20%" },
    };
    return data[level] || { label: level, color: "#6b7280", icon: "mdi:help", badge: "?" };
  }

  // Check if value is valid (not null, undefined, unavailable, unknown)
  _isValidValue(value) {
    return value !== null && value !== undefined && value !== "unavailable" && value !== "unknown";
  }

  // Format energy values to 3 decimals
  _formatEnergy(value) {
    if (value === "unavailable" || value === "unknown" || value === null) {
      return value;
    }
    const num = parseFloat(value);
    return isNaN(num) ? value : num.toFixed(3);
  }

  // Demo data
  _getDemoData() {
    return {
      k_coefficient: "45.2",
      k_per_m3: "1.28",
      daily_energy: "3.421",
      heating_time: "6h 23min",
      heating_ratio: "27",
      delta_t: "12.5",
      indoor_temp: "21.3",
      outdoor_temp: "8.8",
      insulation: "good",
      performance: "excellent",
    };
  }

  render() {
    if (!this.hass || !this.config) {
      return html`<ha-card>Chargement...</ha-card>`;
    }

    const integrationReady = this._isIntegrationReady();
    const dataReady = this._isDataReady();
    const progress = this._getProgress();

    return html`
      <ha-card>
        <!-- Header -->
        <div class="header">
          <div class="header-left">
            <div class="header-title">${this.config.zone}</div>
            <div class="header-subtitle">${this.config.title}</div>
          </div>
          <div class="header-right">
            ${dataReady
        ? html``
        : html`<div class="status-loading"><span class="dot"></span></div>`
      }
          </div>
        </div>

        <!-- Content -->
        <div class="content">
          ${!integrationReady
        ? this._renderLoading()
        : (!dataReady ? this._renderAnalyzing(progress) : this._renderData())}
        </div>
      </ha-card>
    `;
  }

  _renderLoading() {
    return html`
      <div class="analyzing">
        <div class="loading-spinner">
          <ha-icon icon="mdi:home-thermometer"></ha-icon>
        </div>
        <div class="analyzing-title" style="margin-top: 12px;">Chargement de l'intégration...</div>
        <div class="analyzing-info" style="margin-top: 8px;">
          Home Performance démarre. Les données seront disponibles dans quelques secondes.
        </div>
      </div>
    `;
  }

  _renderAnalyzing(progress) {
    const timeRemaining = this._getTimeRemaining();

    return html`
      <div class="analyzing">
        <div class="analyzing-header">
          <span class="analyzing-title">Analyse en cours</span>
          <span class="analyzing-percent">${Math.round(progress)}%</span>
        </div>
        <div class="progress-track">
          <div class="progress-fill" style="width: ${progress}%"></div>
        </div>
        <div class="analyzing-footer">
          <ha-icon icon="mdi:clock-outline"></ha-icon>
          <span>${timeRemaining !== "Prêt" ? `Reste ${timeRemaining}` : "Terminé"}</span>
        </div>
        <div class="analyzing-info">
          Collecte des données thermiques pour calculer les performances de la pièce.
          Résultats disponibles après 12h d'analyse.
        </div>
      </div>
    `;
  }

  _renderData() {
    const demo = this.config.demo ? this._getDemoData() : null;

    // Get values - use French slugified names matching _attr_name
    const kCoef = demo ? demo.k_coefficient : this._getState(this._getEntityId("coefficient_k"));
    const kCoefEntityId = this._getEntityId("coefficient_k");
    const kCoef24h = demo ? demo.k_coefficient_24h : this._getAttribute(kCoefEntityId, "k_24h");
    const kPerM3_24h = demo ? demo.k_per_m3_24h : this._getAttribute(kCoefEntityId, "k_per_m3_24h");
    const kPerM3 = demo ? demo.k_per_m3 : this._getState(this._getEntityId("k_par_m3"));
    const insulation = demo ? demo.insulation : this._getState(this._getEntityId("note_d_isolation"));
    const performance = demo ? demo.performance : this._getState(this._getEntityId("performance_energetique"));

    // Get insulation attributes for season/inference support
    const insulationEntityId = this._getEntityId("note_d_isolation");
    const insulationAttrs = demo ? {} : {
      status: this._getAttribute(insulationEntityId, "status"),
      season: this._getAttribute(insulationEntityId, "season"),
      message: this._getAttribute(insulationEntityId, "message"),
      k_value: this._getAttribute(insulationEntityId, "k_value"),
      k_source: this._getAttribute(insulationEntityId, "k_source"),
      temp_stable: this._getAttribute(insulationEntityId, "temp_stable"),
    };

    // Priority: measured energy (if available) > estimated energy
    // Try both possible entity_id formats (HA slugification varies)
    let dailyEnergy = demo ? demo.daily_energy : this._getState(this._getEntityId("energie_mesuree_jour"));
    if (!demo && (dailyEnergy === "unavailable" || dailyEnergy === "unknown" || dailyEnergy === null)) {
      // Fallback to alternative slugification
      dailyEnergy = this._getState(this._getEntityId("energie_jour_mesuree"));
    }
    let energyType = "mesurée";
    if (!demo && (dailyEnergy === "unavailable" || dailyEnergy === "unknown" || dailyEnergy === null)) {
      dailyEnergy = this._getState(this._getEntityId("energie_24h_estimee"));
      energyType = "estimée";
    }
    // Format energy to 3 decimals
    dailyEnergy = this._formatEnergy(dailyEnergy);

    const heatingTime = demo ? demo.heating_time : this._getState(this._getEntityId("temps_de_chauffe_24h"));
    const heatingRatio = demo ? demo.heating_ratio : this._getState(this._getEntityId("ratio_de_chauffe"));
    const deltaT = demo ? demo.delta_t : this._getState(this._getEntityId("dt_moyen_24h"));

    // Get temperatures from DeltaT sensor attributes
    const deltaTEntityId = this._getEntityId("dt_moyen_24h");
    const indoorTemp = demo ? demo.indoor_temp : this._getAttribute(deltaTEntityId, "indoor_temp");
    const outdoorTemp = demo ? demo.outdoor_temp : this._getAttribute(deltaTEntityId, "outdoor_temp");

    const insulationData = this._getInsulationData(insulation, insulationAttrs);
    const perfData = this._getPerformanceData(performance);

    return html`
      <!-- Main Score - 3 columns -->
      <div class="score-section">
        <div class="score-card" style="--accent: ${insulationData.color}">
          <div class="score-header">
            <div class="score-icon">
              <ha-icon icon="${insulationData.icon}"></ha-icon>
            </div>
            ${this._isValidValue(kCoef) ? html`
              <div class="k-badge">
                <span class="k-value">${kCoef}</span>
                <span class="k-unit">W/°C</span>
                ${this._isValidValue(kPerM3) ? html`<span class="k-sub">${kPerM3} W/m³</span>` : ""}
              </div>
            ` : ""}
          </div>
          <div class="score-content">
            <div class="score-label">Isolation</div>
            <div class="score-value">${insulationData.label}</div>
            <div class="score-desc">${insulationData.desc}</div>
          </div>
        </div>

        <div class="score-card" style="--accent: ${perfData.color}">
          <div class="score-icon">
            <ha-icon icon="${perfData.icon}"></ha-icon>
          </div>
          <div class="score-content">
            <div class="score-label">Performance</div>
            <div class="score-value">${perfData.label}</div>
            <div class="score-badge">${perfData.badge} vs moyenne</div>
          </div>
        </div>

        <div class="score-card temp-card" style="--accent: #6366f1">
          <div class="score-icon">
            <ha-icon icon="mdi:thermometer"></ha-icon>
          </div>
          <div class="score-content">
            <div class="score-label">Températures</div>
            <div class="temp-values">
              <div class="temp-row">
                <ha-icon icon="mdi:home"></ha-icon>
                <span class="temp-value">${indoorTemp ?? "--"}°C</span>
              </div>
              <div class="temp-row">
                <ha-icon icon="mdi:tree"></ha-icon>
                <span class="temp-value">${outdoorTemp ?? "--"}°C</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Metrics Grid -->
      <div class="metrics-section">
        <div class="section-title">Détails techniques</div>

        <div class="metrics-grid">
          <div class="metric">
            <div class="metric-header">
              <ha-icon icon="mdi:heat-wave"></ha-icon>
              <span>K instantané</span>
            </div>
            <div class="metric-value">${this._isValidValue(kCoef24h) ? `${kCoef24h} W/°C` : "--"}</div>
            ${this._isValidValue(kPerM3_24h)
        ? html`<div class="metric-sub">${kPerM3_24h} W/(°C·m³)</div>`
        : html`<div class="metric-sub">sur 24h glissant</div>`}
          </div>

          <div class="metric">
            <div class="metric-header">
              <ha-icon icon="mdi:lightning-bolt"></ha-icon>
              <span>Énergie/jour</span>
            </div>
            <div class="metric-value">${this._isValidValue(dailyEnergy) ? `${dailyEnergy} kWh` : "--"}</div>
            <div class="metric-unit"><span class="metric-type">(${energyType})</span></div>
          </div>

          <div class="metric">
            <div class="metric-header">
              <ha-icon icon="mdi:radiator"></ha-icon>
              <span>Temps chauffe</span>
            </div>
            <div class="metric-value">${this._isValidValue(heatingTime) ? heatingTime : "0min"}</div>
            <div class="metric-unit">sur 24h</div>
            ${this._isValidValue(heatingRatio)
        ? html`<div class="metric-sub">${heatingRatio}% du temps</div>`
        : ""}
          </div>

          <div class="metric">
            <div class="metric-header">
              <ha-icon icon="mdi:thermometer"></ha-icon>
              <span>Écart moyen</span>
            </div>
            <div class="metric-value">${this._isValidValue(deltaT) ? `${deltaT}°C` : "--"}</div>
            <div class="metric-sub">Int. - Ext.</div>
          </div>
        </div>
      </div>
    `;
  }

  static get styles() {
    return css`
      :host {
        --bg-primary: var(--card-background-color, #1a1a2e);
        --bg-secondary: var(--secondary-background-color, #16213e);
        --text-primary: var(--primary-text-color, #e4e4e7);
        --text-secondary: var(--secondary-text-color, #a1a1aa);
        --border-color: var(--divider-color, rgba(255,255,255,0.08));
        --accent-gradient: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
      }

      ha-card {
        background: var(--bg-primary);
        border-radius: 14px;
        overflow: hidden;
        border: 1px solid var(--border-color);
      }

      /* Header - Compact */
      .header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 12px 14px;
        background: #1C1C1C;
      }

      .header-title {
        font-size: 1.15em;
        font-weight: 700;
        color: var(--text-primary);
        letter-spacing: -0.02em;
      }

      .header-subtitle {
        font-size: 0.85em;
        color: var(--text-secondary);
        margin-top: 1px;
      }

      .status-ready {
        width: 28px;
        height: 28px;
        background: rgba(16, 185, 129, 0.15);
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
      }

      .status-ready ha-icon {
        --mdc-icon-size: 16px;
        color: #10b981;
      }

      .status-loading {
        width: 28px;
        height: 28px;
        display: flex;
        align-items: center;
        justify-content: center;
      }

      .dot {
        width: 8px;
        height: 8px;
        background: #6366f1;
        border-radius: 50%;
        animation: pulse 2s ease-in-out infinite;
      }

      @keyframes pulse {
        0%, 100% { opacity: 0.4; transform: scale(1); }
        50% { opacity: 1; transform: scale(1.1); }
      }

      @keyframes spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
      }

      .loading-spinner {
        display: flex;
        justify-content: center;
        align-items: center;
        padding: 20px;
      }

      .loading-spinner ha-icon {
        --mdc-icon-size: 48px;
        color: #6366f1;
        animation: spin 2s linear infinite;
      }

      /* Content - Compact */
      .content {
        padding: 10px;
      }

      /* Analyzing State */
      .analyzing {
        text-align: center;
      }

      .analyzing-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 6px;
      }

      .analyzing-title {
        font-size: 0.82em;
        color: var(--text-secondary);
      }

      .analyzing-percent {
        font-size: 1em;
        font-weight: 700;
        color: var(--text-primary);
      }

      .progress-track {
        height: 4px;
        background: var(--border-color);
        border-radius: 2px;
        overflow: hidden;
      }

      .progress-fill {
        height: 100%;
        background: var(--accent-gradient);
        border-radius: 2px;
        transition: width 0.5s ease;
      }

      .analyzing-footer {
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 4px;
        margin-top: 6px;
        font-size: 0.78em;
        color: var(--text-secondary);
      }

      .analyzing-footer ha-icon {
        --mdc-icon-size: 13px;
      }

      .analyzing-info {
        margin-top: 10px;
        padding: 10px;
        background: var(--bg-secondary);
        border-radius: 8px;
        font-size: 0.85em;
        color: var(--text-secondary);
        line-height: 1.4;
        text-align: left;
      }

      /* Score Section - 3 columns */
      .score-section {
        display: grid;
        grid-template-columns: 1fr 1fr 1fr;
        gap: 6px;
        margin-bottom: 8px;
      }

      .score-card {
        background: var(--bg-secondary);
        border-radius: 10px;
        padding: 8px 10px;
        border-left: 3px solid var(--accent);
      }

      .score-header {
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        margin-bottom: 6px;
      }

      .score-icon {
        width: 28px;
        height: 28px;
        background: color-mix(in srgb, var(--accent) 20%, transparent);
        border-radius: 7px;
        display: flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
        margin-bottom: 6px;
      }

      .score-header .score-icon {
        margin-bottom: 0;
      }

      .k-badge {
        display: flex;
        flex-direction: column;
        align-items: flex-end;
        text-align: right;
        line-height: 1.1;
      }

      .k-badge .k-value {
        font-size: 1.1em;
        font-weight: 700;
        color: var(--accent);
      }

      .k-badge .k-unit {
        font-size: 0.7em;
        color: var(--text-secondary);
        margin-left: 2px;
      }

      .k-badge .k-sub {
        font-size: 0.65em;
        color: var(--text-secondary);
        opacity: 0.8;
      }

      .score-icon ha-icon {
        --mdc-icon-size: 15px;
        color: var(--accent);
      }

      .score-label {
        font-size: 0.75em;
        color: var(--text-secondary);
        text-transform: uppercase;
        letter-spacing: 0.04em;
        margin-bottom: 1px;
      }

      .score-value {
        font-size: 1.1em;
        font-weight: 700;
        color: var(--accent);
      }

      .score-desc, .score-badge {
        font-size: 0.85em;
        color: var(--text-secondary);
        margin-top: 2px;
      }

      /* Temperature Card */
      .temp-card .temp-values {
        display: flex;
        flex-direction: column;
        gap: 2px;
      }

      .temp-card .temp-row {
        display: flex;
        align-items: center;
        gap: 4px;
      }

      .temp-card .temp-row ha-icon {
        --mdc-icon-size: 12px;
        color: var(--text-secondary);
        opacity: 0.7;
      }

      .temp-card .temp-value {
        font-size: 0.95em;
        font-weight: 600;
        color: var(--text-primary);
      }

      /* Metrics Section - Compact */
      .metrics-section {
        background: var(--bg-secondary);
        border-radius: 10px;
        padding: 8px 10px;
      }

      .section-title {
        font-size: 0.78em;
        color: var(--text-secondary);
        text-transform: uppercase;
        letter-spacing: 0.06em;
        margin-bottom: 8px;
        padding-bottom: 6px;
        border-bottom: 1px solid var(--border-color);
      }

      .metrics-grid {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 4px;
      }

      .metric {
        text-align: center;
        padding: 4px 2px;
      }

      .metric-header {
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 3px;
        margin-bottom: 3px;
        color: var(--text-secondary);
        font-size: 0.75em;
      }

      .metric-header ha-icon {
        --mdc-icon-size: 12px;
      }

      .metric-value {
        font-size: 1.1em;
        font-weight: 700;
        color: var(--text-primary);
        line-height: 1;
      }

      .metric-unit {
        font-size: 0.8em;
        color: var(--text-secondary);
        margin-top: 1px;
      }

      .metric-type {
        opacity: 0.7;
      }

      .metric-sub {
        font-size: 0.78em;
        color: var(--text-secondary);
        opacity: 0.7;
        margin-top: 2px;
      }

      .metric-sub.waiting {
        font-style: italic;
        opacity: 0.5;
      }

      /* Responsive */
      @media (max-width: 400px) {
        .score-section {
          grid-template-columns: 1fr 1fr;
        }

        .temp-card {
          grid-column: span 2;
        }

        .metrics-grid {
          grid-template-columns: 1fr 1fr;
        }
      }

      @media (max-width: 280px) {
        .score-section {
          grid-template-columns: 1fr;
        }

        .temp-card {
          grid-column: span 1;
        }

        .metrics-grid {
          grid-template-columns: 1fr;
        }
      }
    `;
  }
}

// Card Editor
class HomePerformanceCardEditor extends LitElement {
  static get properties() {
    return {
      hass: { type: Object },
      config: { type: Object },
    };
  }

  setConfig(config) {
    this.config = config;
  }

  configChanged(ev) {
    const target = ev.target;
    const newConfig = { ...this.config };

    if (target.configValue) {
      if (target.type === "checkbox") {
        newConfig[target.configValue] = target.checked;
      } else {
        newConfig[target.configValue] = target.value;
      }
    }

    const event = new CustomEvent("config-changed", {
      detail: { config: newConfig },
      bubbles: true,
      composed: true,
    });
    this.dispatchEvent(event);
  }

  render() {
    if (!this.hass || !this.config) {
      return html``;
    }

    return html`
      <div class="editor">
        <ha-textfield
          label="Zone (ex: Salon, Chambre)"
          .value=${this.config.zone || ""}
          .configValue=${"zone"}
          @input=${this.configChanged}
        ></ha-textfield>

        <ha-textfield
          label="Titre"
          .value=${this.config.title || "Performance Thermique"}
          .configValue=${"title"}
          @input=${this.configChanged}
        ></ha-textfield>

        <ha-formfield label="Mode démo (prévisualisation)">
          <ha-checkbox
            .checked=${this.config.demo === true}
            .configValue=${"demo"}
            @change=${this.configChanged}
          ></ha-checkbox>
        </ha-formfield>
      </div>
    `;
  }

  static get styles() {
    return css`
      .editor {
        display: flex;
        flex-direction: column;
        gap: 16px;
        padding: 16px;
      }
      ha-textfield { width: 100%; }
    `;
  }
}

// Register
customElements.define("home-performance-card", HomePerformanceCard);
customElements.define("home-performance-card-editor", HomePerformanceCardEditor);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "home-performance-card",
  name: "Home Performance",
  description: "Carte performance thermique",
  preview: true,
});

console.info(
  `%c HOME-PERFORMANCE %c Loaded `,
  "color: white; background: #6366f1; font-weight: bold; border-radius: 4px 0 0 4px; padding: 2px 6px;",
  "color: #6366f1; background: #1a1a2e; font-weight: bold; border-radius: 0 4px 4px 0; padding: 2px 6px;"
);
