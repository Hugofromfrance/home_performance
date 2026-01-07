/**
 * Home Performance Card
 * Modern dashboard card for Home Performance integration
 */

const CARD_VERSION = "1.2.0";

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

  // Translations for i18n support
  static _translations = {
    en: {
      // Config & titles
      default_title: "Thermal Performance",
      error_no_zone: "Please specify a zone",
      loading: "Loading...",
      loading_integration: "Loading integration...",

      // Section headers
      isolation: "INSULATION",
      performance: "PERFORMANCE",
      temperatures: "TEMPERATURES",
      technical_details: "TECHNICAL DETAILS",
      history_title: "K HISTORY (7 DAYS)",

      // Insulation ratings
      excellent: "Excellent",
      excellent_desc: "Very well insulated",
      good: "Good",
      good_desc: "Well insulated",
      average: "Average",
      average_desc: "Standard insulation",
      poor: "Poor",
      poor_desc: "Needs improvement",
      very_poor: "Critical",
      very_poor_desc: "Insufficient insulation",
      excellent_inferred: "🏆 Excellent",
      excellent_inferred_desc: "Minimal heating needed",
      summer_mode: "☀️ Summer mode",
      summer_mode_desc: "Measurement not possible",
      off_season: "🌤️ Shoulder season",
      off_season_desc: "ΔT insufficient",
      waiting: "Waiting",
      waiting_desc: "Heating required",
      last_measurement: "Last measurement",
      last_k: "Last K",

      // Performance ratings
      perf_excellent: "Excellent",
      perf_standard: "Standard",
      perf_optimize: "Needs optimization",
      vs_average: "vs average",

      // Metrics
      k_instant: "K instant",
      energy_day: "Energy/day",
      heating_time: "Heating time",
      avg_delta: "Avg delta",
      measured: "measured",
      estimated: "estimated",
      on_24h: "over 24h",
      rolling_24h: "rolling 24h",
      of_time: "of time",
      indoor_outdoor: "In. - Out.",

      // Tooltips
      tooltip_estimated: "estimated",

      // Days
      days: ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"],

      // Loading & analyzing
      integration_starting: "Home Performance is starting. Data will be available in a few seconds.",
      zone_check_hint: "If this message persists, check that the zone",
      exists_in_integration: "exists in the Home Performance integration.",
      expected_entity: "Expected entity",
      analyzing: "Analyzing",
      analysis_in_progress: "Collecting thermal data to calculate room performance. Results available after 12h of analysis.",
      remaining_time: "remaining",
      completed: "Completed",
      ready: "Ready",

      // Editor
      editor_zone: "Zone (e.g.: Living Room, Bedroom)",
      editor_title: "Title",
      editor_card_style: "Card style",
      editor_full: "Full",
      editor_badge: "Badge",
      editor_pill: "Pill",
      editor_demo: "Demo mode (preview)",
      editor_show_graph: "Show history graph",
    },
    fr: {
      // Config & titles
      default_title: "Performance Thermique",
      error_no_zone: "Veuillez spécifier une zone",
      loading: "Chargement...",
      loading_integration: "Chargement de l'intégration...",

      // Section headers
      isolation: "ISOLATION",
      performance: "PERFORMANCE",
      temperatures: "TEMPÉRATURES",
      technical_details: "DÉTAILS TECHNIQUES",
      history_title: "HISTORIQUE K (7 JOURS)",

      // Insulation ratings
      excellent: "Excellent",
      excellent_desc: "Très bien isolé",
      good: "Bon",
      good_desc: "Bien isolé",
      average: "Moyen",
      average_desc: "Isolation standard",
      poor: "Faible",
      poor_desc: "À améliorer",
      very_poor: "Critique",
      very_poor_desc: "Isolation insuffisante",
      excellent_inferred: "🏆 Excellente",
      excellent_inferred_desc: "Chauffe minimale nécessaire",
      summer_mode: "☀️ Mode été",
      summer_mode_desc: "Mesure impossible",
      off_season: "🌤️ Hors saison",
      off_season_desc: "ΔT insuffisant",
      waiting: "En attente",
      waiting_desc: "Chauffe nécessaire",
      last_measurement: "Dernière mesure",
      last_k: "Dernier K",

      // Performance ratings
      perf_excellent: "Excellente",
      perf_standard: "Standard",
      perf_optimize: "À optimiser",
      vs_average: "vs moyenne",

      // Metrics
      k_instant: "K instantané",
      energy_day: "Énergie/jour",
      heating_time: "Temps chauffe",
      avg_delta: "Écart moyen",
      measured: "mesurée",
      estimated: "estimée",
      on_24h: "sur 24h",
      rolling_24h: "sur 24h glissant",
      of_time: "du temps",
      indoor_outdoor: "Int. - Ext.",

      // Tooltips
      tooltip_estimated: "estimé",

      // Days
      days: ["Di", "Lu", "Ma", "Me", "Je", "Ve", "Sa"],

      // Loading & analyzing
      integration_starting: "Home Performance démarre. Les données seront disponibles dans quelques secondes.",
      zone_check_hint: "Si ce message persiste, vérifiez que la zone",
      exists_in_integration: "existe dans l'intégration Home Performance.",
      expected_entity: "Entité attendue",
      analyzing: "Analyse en cours",
      analysis_in_progress: "Collecte des données thermiques pour calculer les performances de la pièce. Résultats disponibles après 12h d'analyse.",
      remaining_time: "restantes",
      completed: "Terminé",
      ready: "Prêt",

      // Editor
      editor_zone: "Zone (ex: Salon, Chambre)",
      editor_title: "Titre",
      editor_card_style: "Style de carte",
      editor_full: "Complète",
      editor_badge: "Badge",
      editor_pill: "Pilule",
      editor_demo: "Mode démo (prévisualisation)",
      editor_show_graph: "Afficher le graphique historique",
    }
  };

  // Get translation for key
  _t(key) {
    const lang = this.hass?.language?.substring(0, 2) || 'en';
    const translations = HomePerformanceCard._translations[lang] || HomePerformanceCard._translations['en'];
    return translations[key] !== undefined ? translations[key] : key;
  }

  static getConfigElement() {
    return document.createElement("home-performance-card-editor");
  }

  static getStubConfig() {
    return {
      zone: "",
      title: "",
      layout: "full",  // "full", "badge", "pill"
      demo: false,
    };
  }

  setConfig(config) {
    if (!config.zone) {
      throw new Error(HomePerformanceCard._translations.en.error_no_zone);
    }
    this.config = {
      title: "",  // Will use _t('default_title') if empty
      layout: "full",
      show_graph: true,
      demo: false,
      ...config,
    };
  }

  getCardSize() {
    // Different sizes for different layouts
    switch (this.config?.layout) {
      case "badge": return 2;
      case "pill": return 1;
      default: return 5;
    }
  }

  // Slugify zone name to match Home Assistant entity_id format
  // Handles special characters like ü, é, ç, etc.
  _slugifyZone(zone) {
    return zone
      .toLowerCase()
      // Normalize Unicode characters (é → e, ü → u, ç → c, etc.)
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      // Replace spaces and special chars with underscores
      .replace(/[^a-z0-9]+/g, '_')
      // Remove leading/trailing underscores
      .replace(/^_+|_+$/g, '');
  }

  // Entity name mappings: French (primary) -> English (fallback)
  // This handles systems where HA generates entity IDs from translated names
  _entityMappings = {
    // Binary sensors
    "donnees_pretes": ["donnees_pretes", "data_ready"],
    "fenetre_ouverte": ["fenetre_ouverte", "window_open"],
    // Sensors
    "coefficient_k": ["coefficient_k", "k_coefficient"],
    "k_par_m3": ["k_par_m3", "k_per_m3"],
    "note_d_isolation": ["note_d_isolation", "insulation_rating", "note_isolation"],
    "performance_energetique": ["performance_energetique", "energy_performance"],
    "energie_mesuree_jour": ["energie_mesuree_jour", "energie_jour_mesuree", "daily_measured_energy"],
    "energie_24h_estimee": ["energie_24h_estimee", "estimated_daily_energy", "daily_estimated_energy"],
    "temps_de_chauffe_24h": ["temps_de_chauffe_24h", "heating_time_24h", "daily_heating_time"],
    "ratio_de_chauffe": ["ratio_de_chauffe", "heating_ratio"],
    "dt_moyen_24h": ["dt_moyen_24h", "average_delta_t", "avg_delta_t_24h", "average_dt_24h"],
    "progression_analyse": ["progression_analyse", "analysis_progress"],
    "temps_restant_analyse": ["temps_restant_analyse", "analysis_time_remaining"],
  };

  _getEntityId(suffix) {
    const zone = this._slugifyZone(this.config.zone);
    const variants = this._entityMappings[suffix] || [suffix];

    // Try each variant and return the first one that exists
    for (const variant of variants) {
      const entityId = `sensor.home_performance_${zone}_${variant}`;
      if (this.hass?.states[entityId] !== undefined) {
        return entityId;
      }
    }
    // Fallback to primary (first) variant
    return `sensor.home_performance_${zone}_${variants[0]}`;
  }

  _getBinaryEntityId(suffix) {
    const zone = this._slugifyZone(this.config.zone);
    const variants = this._entityMappings[suffix] || [suffix];

    // Try each variant and return the first one that exists
    for (const variant of variants) {
      const entityId = `binary_sensor.home_performance_${zone}_${variant}`;
      if (this.hass?.states[entityId] !== undefined) {
        return entityId;
      }
    }
    // Fallback to primary (first) variant
    return `binary_sensor.home_performance_${zone}_${variants[0]}`;
  }

  _getState(entityId) {
    const state = this.hass?.states[entityId];
    return state ? state.state : "unavailable";
  }

  _getAttribute(entityId, attr) {
    const state = this.hass?.states[entityId];
    return state?.attributes?.[attr];
  }

  // Get unit of measurement for a specific entity
  _getEntityUnit(entityId) {
    const state = this.hass?.states[entityId];
    return state?.attributes?.unit_of_measurement;
  }

  // Get user's temperature unit from HA config
  _getTempUnit() {
    return this.hass?.config?.unit_system?.temperature || "°C";
  }

  // Check if user uses Fahrenheit
  _usesFahrenheit() {
    const unit = this._getTempUnit();
    return unit === "°F" || unit === "F";
  }

  // Convert Celsius to Fahrenheit (absolute temperature)
  _celsiusToFahrenheit(celsius) {
    if (celsius === null || celsius === undefined || isNaN(parseFloat(celsius))) {
      return celsius;
    }
    return ((parseFloat(celsius) * 9 / 5) + 32).toFixed(1);
  }

  // Convert temperature DIFFERENCE (delta) to Fahrenheit - NO +32 offset!
  _celsiusDeltaToFahrenheit(celsiusDelta) {
    if (celsiusDelta === null || celsiusDelta === undefined || isNaN(parseFloat(celsiusDelta))) {
      return celsiusDelta;
    }
    return (parseFloat(celsiusDelta) * 9 / 5).toFixed(1);
  }

  // Convert absolute temperature based on user's unit system
  // Our backend always stores in Celsius, this converts for display
  _convertTemp(tempCelsius) {
    if (this._usesFahrenheit()) {
      return this._celsiusToFahrenheit(tempCelsius);
    }
    return tempCelsius;
  }

  // Convert temperature difference (delta) based on user's unit system
  // If sensorUnit is provided and already matches user's unit, skip conversion
  _convertTempDelta(deltaValue, sensorUnit = null) {
    if (deltaValue === null || deltaValue === undefined || isNaN(parseFloat(deltaValue))) {
      return deltaValue;
    }
    const userUnit = this._getTempUnit();
    // If sensor already provides value in user's unit, no conversion needed
    if (sensorUnit && sensorUnit === userUnit) {
      return parseFloat(deltaValue).toFixed(1);
    }
    // Otherwise convert from Celsius
    if (this._usesFahrenheit()) {
      return this._celsiusDeltaToFahrenheit(deltaValue);
    }
    return parseFloat(deltaValue).toFixed(1);
  }

  _entityExists(entityId) {
    return this.hass?.states[entityId] !== undefined;
  }

  // Check if any of the zone's entities exist (integration is loaded)
  _isIntegrationReady() {
    if (this.config.demo) return true;

    // Try to find any entity for this zone to confirm integration is loaded
    const zone = this._slugifyZone(this.config.zone);
    const possibleEntities = [
      `binary_sensor.home_performance_${zone}_donnees_pretes`,
      `binary_sensor.home_performance_${zone}_data_ready`,
      `sensor.home_performance_${zone}_coefficient_k`,
      `sensor.home_performance_${zone}_k_coefficient`,
      `sensor.home_performance_${zone}_progression_analyse`,
      `sensor.home_performance_${zone}_analysis_progress`,
    ];

    return possibleEntities.some(entityId => this.hass?.states[entityId] !== undefined);
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

  // Get data hours from the data_ready sensor
  _getDataHours() {
    if (this.config.demo) return 25;
    const entityId = this._getBinaryEntityId("donnees_pretes");
    return this._getAttribute(entityId, "data_hours") || 0;
  }

  _getProgress() {
    if (this.config.demo) return 100;
    const entityId = this._getEntityId("progression_analyse");
    const value = parseFloat(this._getState(entityId));
    return isNaN(value) ? 0 : Math.min(100, Math.max(0, value));
  }

  _getTimeRemaining() {
    if (this.config.demo) return this._t('ready');
    const entityId = this._getEntityId("temps_restant_analyse");
    return this._getState(entityId);
  }

  _getInsulationData(rating, insulationAttrs = {}) {
    const data = {
      // Calculated ratings
      excellent: { label: this._t('excellent'), color: "#10b981", icon: "mdi:shield-check", desc: this._t('excellent_desc') },
      good: { label: this._t('good'), color: "#22c55e", icon: "mdi:shield-half-full", desc: this._t('good_desc') },
      average: { label: this._t('average'), color: "#eab308", icon: "mdi:shield-outline", desc: this._t('average_desc') },
      poor: { label: this._t('poor'), color: "#f97316", icon: "mdi:shield-alert", desc: this._t('poor_desc') },
      very_poor: { label: this._t('very_poor'), color: "#ef4444", icon: "mdi:shield-off", desc: this._t('very_poor_desc') },
      // Inferred excellent
      excellent_inferred: { label: this._t('excellent_inferred'), color: "#059669", icon: "mdi:trophy", desc: this._t('excellent_inferred_desc') },
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
        label: this._t('summer_mode'),
        color: "#f59e0b",
        icon: "mdi:weather-sunny",
        desc: kValue ? `${this._t('last_measurement')} ${lastK}` : this._t('summer_mode_desc')
      };
    }

    if (season === "off_season") {
      const lastK = kValue ? `(K=${kValue} W/°C)` : "";
      return {
        label: this._t('off_season'),
        color: "#8b5cf6",
        icon: "mdi:weather-partly-cloudy",
        desc: kValue ? `${this._t('last_measurement')} ${lastK}` : this._t('off_season_desc')
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
          label: this._t('waiting'),
          color: "#6b7280",
          icon: "mdi:shield-outline",
          desc: `${this._t('last_k')}: ${kValue} W/°C`
        };
      }
      // Show specific message from status
      if (message) {
        return { label: this._t('waiting'), color: "#6b7280", icon: "mdi:shield-outline", desc: message };
      }
      return { label: this._t('waiting'), color: "#6b7280", icon: "mdi:shield-outline", desc: this._t('waiting_desc') };
    }

    return data[rating] || { label: rating, color: "#6b7280", icon: "mdi:shield-outline", desc: "" };
  }

  _getPerformanceData(level) {
    const data = {
      excellent: { label: this._t('perf_excellent'), color: "#10b981", icon: "mdi:leaf", badge: "−40%" },
      standard: { label: this._t('perf_standard'), color: "#eab308", icon: "mdi:minus", badge: "~" },
      to_optimize: { label: this._t('perf_optimize'), color: "#f97316", icon: "mdi:trending-up", badge: "+20%" },
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
      k_history_7d: [
        { date: "2024-12-18", k: 12.5, estimated: false },  // excellent
        { date: "2024-12-19", k: 18.0, estimated: false },  // good
        { date: "2024-12-20", k: 18.0, estimated: true },   // carry-forward
        { date: "2024-12-21", k: 28.5, estimated: false },  // average
        { date: "2024-12-22", k: 35.0, estimated: false },  // poor
        { date: "2024-12-23", k: 35.0, estimated: true },   // carry-forward
        { date: "2024-12-24", k: 22.0, estimated: false },  // good
      ],
    };
  }

  // Get K history from sensor attributes
  _getKHistory() {
    if (this.config.demo) {
      return this._getDemoData().k_history_7d;
    }
    const kCoefEntityId = this._getEntityId("coefficient_k");
    return this._getAttribute(kCoefEntityId, "k_history_7d") || [];
  }

  // Render sparkline SVG for pill/badge layouts (simple polyline like HA native)
  _renderSparkline(kHistory, width = 80, height = 24, accentColor = "var(--accent)") {
    if (!kHistory || kHistory.length < 2) return '';

    const values = kHistory.map(d => d.k);
    const min = Math.min(...values);
    const max = Math.max(...values);
    const range = max - min || 1;

    // Use integer coordinates for crisp rendering
    const margin = 1;
    const graphWidth = width - margin * 2;
    const graphHeight = height - margin * 2;

    // Calculate points
    const points = values.map((v, i) => {
      const x = margin + (i / (values.length - 1)) * graphWidth;
      const y = margin + (1 - (v - min) / range) * graphHeight;
      return `${x.toFixed(2)},${y.toFixed(2)}`;
    }).join(' ');

    return html`
      <svg
        class="sparkline"
        viewBox="0 0 ${width} ${height}"
        preserveAspectRatio="none"
      >
        <polyline
          points="${points}"
          fill="none"
          stroke="${accentColor}"
          stroke-width="1.5"
          stroke-linecap="round"
          stroke-linejoin="round"
          vector-effect="non-scaling-stroke"
        />
      </svg>
    `;
  }

  // Calculate score (K/m³) - used for both color and height
  _getKScore(k, volume) {
    if (volume && volume > 0) {
      return k / volume;
    }
    // Without volume, use K directly with typical room thresholds (assuming ~30m³)
    return k / 30;
  }

  // Get color based on score (K/m³)
  _getColorFromScore(score) {
    if (score < 0.4) return "#10b981";      // excellent - green
    if (score < 0.7) return "#22c55e";      // good - light green
    if (score < 1.0) return "#eab308";      // average - yellow
    if (score < 1.5) return "#f97316";      // poor - orange
    return "#ef4444";                        // very_poor - red
  }

  // Render bar chart for full layout
  _renderBarChart(kHistory, volume) {
    if (!kHistory || kHistory.length === 0) return '';

    // Calculate scores (K/m³) for each day - this is what determines both color AND height
    const scores = kHistory.map(d => this._getKScore(d.k, volume));
    const minScore = Math.min(...scores);
    const maxScore = Math.max(...scores);
    const range = maxScore - minScore;
    const days = this._t('days');

    // Bar height: 20px minimum (best) to 60px maximum (worst)
    const minHeight = 20;
    const maxHeight = 60;

    return html`
      <div class="k-chart">
        ${kHistory.map((day, index) => {
      const date = new Date(day.date + 'T00:00:00');
      const dayLabel = days[date.getDay()];
      const score = scores[index];
      // Height based on SCORE: higher score (worse) = taller bar
      const heightPx = range > 0.01
        ? minHeight + ((score - minScore) / range) * (maxHeight - minHeight)
        : (minHeight + maxHeight) / 2; // If all nearly same, show at middle height
      const barColor = this._getColorFromScore(score);
      const isEstimated = day.estimated === true;
      const opacity = isEstimated ? 0.5 : 1;
      const tooltip = isEstimated
        ? `${day.date}: ${day.k} W/°C (${this._t('tooltip_estimated')})`
        : `${day.date}: ${day.k} W/°C`;
      return html`
            <div class="bar-wrapper ${isEstimated ? 'estimated' : ''}" title="${tooltip}">
              <div class="bar" style="height: ${heightPx}px; background: ${barColor}; opacity: ${opacity}"></div>
              <span class="bar-label">${dayLabel}</span>
            </div>
          `;
    })}
      </div>
    `;
  }

  render() {
    if (!this.hass || !this.config) {
      return html`<ha-card>${this._t('loading')}</ha-card>`;
    }

    const layout = this.config.layout || "full";

    // Dispatch to appropriate layout renderer
    switch (layout) {
      case "badge":
        return this._renderBadgeLayout();
      case "pill":
        return this._renderPillLayout();
      default:
        return this._renderFullLayout();
    }
  }

  // Full layout (default - original card)
  _renderFullLayout() {
    const integrationReady = this._isIntegrationReady();
    const dataReady = this._isDataReady();
    const progress = this._getProgress();

    return html`
      <ha-card>
        <!-- Header -->
        <div class="header">
          <div class="header-left">
            <div class="header-title">${this.config.zone}</div>
            <div class="header-subtitle">${this.config.title || this._t('default_title')}</div>
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

  // Badge layout (Concept A - compact vertical card)
  _renderBadgeLayout() {
    const integrationReady = this._isIntegrationReady();
    const dataReady = this._isDataReady();
    const progress = this._getProgress();

    if (!integrationReady || !dataReady) {
      // Calculate circle progress (circumference = 2 * PI * radius)
      const radius = 24;
      const circumference = 2 * Math.PI * radius;
      const offset = circumference - (progress / 100) * circumference;

      return html`
        <ha-card class="badge-card badge-analyzing">
          <div class="badge-progress-ring">
            <svg viewBox="0 0 56 56">
              <circle
                class="badge-progress-bg"
                cx="28" cy="28" r="${radius}"
                stroke-width="4"
                fill="none"
              />
              <circle
                class="badge-progress-fill"
                cx="28" cy="28" r="${radius}"
                stroke-width="4"
                fill="none"
                stroke-dasharray="${circumference}"
                stroke-dashoffset="${offset}"
                transform="rotate(-90 28 28)"
              />
            </svg>
            <span class="badge-progress-text">${Math.round(progress)}%</span>
          </div>
          <div class="badge-zone-name">${this.config.zone}</div>
          <div class="badge-status">Analyse en cours</div>
        </ha-card>
      `;
    }

    const demo = this.config.demo ? this._getDemoData() : null;
    const kCoef = demo ? demo.k_coefficient : this._getState(this._getEntityId("coefficient_k"));
    const kPerM3 = demo ? demo.k_per_m3 : this._getState(this._getEntityId("k_par_m3"));
    const insulation = demo ? demo.insulation : this._getState(this._getEntityId("note_d_isolation"));
    const kHistory = this._getKHistory();

    const insulationEntityId = this._getEntityId("note_d_isolation");
    const insulationAttrs = demo ? {} : {
      status: this._getAttribute(insulationEntityId, "status"),
      season: this._getAttribute(insulationEntityId, "season"),
      message: this._getAttribute(insulationEntityId, "message"),
      k_value: this._getAttribute(insulationEntityId, "k_value"),
      k_source: this._getAttribute(insulationEntityId, "k_source"),
    };

    const insulationData = this._getInsulationData(insulation, insulationAttrs);
    const scoreLetter = this._getScoreLetter(insulation);
    const hasHistory = kHistory && kHistory.length >= 2;

    return html`
      <ha-card class="badge-card" style="--accent: ${insulationData.color}">
        <div class="badge-accent-bar"></div>
        <div class="badge-score-circle">
          <span class="badge-score-letter">${scoreLetter}</span>
        </div>
        <div class="badge-rating-label">${insulationData.label}</div>
        ${this.config.show_graph && hasHistory ? html`
          <div class="badge-sparkline-wrapper">
            ${this._renderSparkline(kHistory, 60, 20, insulationData.color)}
          </div>
        ` : html`<div class="badge-separator"></div>`}
        <div class="badge-zone-name">${this.config.zone}</div>
        <div class="badge-k-value">
          ${this._isValidValue(kCoef) ? html`${kCoef}<span class="badge-k-unit">W/°C</span>` : "--"}
        </div>
        ${this._isValidValue(kPerM3) ? html`<div class="badge-k-normalized">${kPerM3} W/m³</div>` : ""}
      </ha-card>
    `;
  }

  // Pill layout (Concept D - horizontal strip)
  _renderPillLayout() {
    const integrationReady = this._isIntegrationReady();
    const dataReady = this._isDataReady();
    const progress = this._getProgress();

    if (!integrationReady || !dataReady) {
      return html`
        <ha-card class="pill-card pill-analyzing">
          <div class="pill-progress-badge">
            <span class="pill-progress-percent">${Math.round(progress)}%</span>
          </div>
          <div class="pill-zone-section">
            <div class="pill-zone-name">${this.config.zone}</div>
            <div class="pill-zone-rating">Analyse en cours</div>
          </div>
          <div class="pill-separator"></div>
          <div class="pill-progress-track-wrapper">
            <div class="pill-progress-track">
              <div class="pill-progress-fill" style="width: ${progress}%"></div>
            </div>
          </div>
        </ha-card>
      `;
    }

    const demo = this.config.demo ? this._getDemoData() : null;
    const kCoef = demo ? demo.k_coefficient : this._getState(this._getEntityId("coefficient_k"));
    const insulation = demo ? demo.insulation : this._getState(this._getEntityId("note_d_isolation"));
    const deltaTRaw = demo ? demo.delta_t : this._getState(this._getEntityId("dt_moyen_24h"));
    const kHistory = this._getKHistory();

    const insulationEntityId = this._getEntityId("note_d_isolation");
    const insulationAttrs = demo ? {} : {
      status: this._getAttribute(insulationEntityId, "status"),
      season: this._getAttribute(insulationEntityId, "season"),
      message: this._getAttribute(insulationEntityId, "message"),
      k_value: this._getAttribute(insulationEntityId, "k_value"),
      k_source: this._getAttribute(insulationEntityId, "k_source"),
    };

    const insulationData = this._getInsulationData(insulation, insulationAttrs);
    const scoreLetter = this._getScoreLetter(insulation);
    const tempUnit = this._getTempUnit();
    const deltaTEntityId = this._getEntityId("dt_moyen_24h");
    const deltaTUnit = this._getEntityUnit(deltaTEntityId);
    const deltaT = this._convertTempDelta(deltaTRaw, deltaTUnit);
    const hasHistory = kHistory && kHistory.length >= 2;

    return html`
      <ha-card class="pill-card" style="--accent: ${insulationData.color}">
        <div class="pill-accent-bar"></div>
        <div class="pill-score-badge">
          <span class="pill-score-letter">${scoreLetter}</span>
        </div>
        <div class="pill-zone-section">
          <div class="pill-zone-name">${this.config.zone}</div>
          <div class="pill-zone-rating">${insulationData.label}</div>
        </div>
        ${this.config.show_graph && hasHistory ? html`
          <div class="pill-sparkline-wrapper">
            ${this._renderSparkline(kHistory, 100, 24, insulationData.color)}
          </div>
        ` : ''}
        <div class="pill-separator"></div>
        <div class="pill-stats-section">
          <div class="pill-stat">
            <div class="pill-stat-value">${this._isValidValue(kCoef) ? kCoef : "--"}</div>
            <div class="pill-stat-label">W/°C</div>
          </div>
          <div class="pill-stat">
            <div class="pill-stat-value">${this._isValidValue(deltaT) ? `${deltaT}°` : "--"}</div>
            <div class="pill-stat-label">ΔT</div>
          </div>
        </div>
      </ha-card>
    `;
  }

  // Get score letter from insulation rating
  _getScoreLetter(rating) {
    const letters = {
      excellent: "A+",
      excellent_inferred: "A+",
      good: "A",
      average: "B",
      poor: "C",
      very_poor: "D",
    };
    return letters[rating] || "?";
  }

  _renderLoading() {
    const zone = this._slugifyZone(this.config.zone);
    const expectedEntity = `binary_sensor.home_performance_${zone}_donnees_pretes`;

    return html`
      <div class="analyzing">
        <div class="loading-spinner">
          <div class="spinner"></div>
        </div>
        <div class="analyzing-title" style="margin-top: 12px;">${this._t('loading_integration')}</div>
        <div class="analyzing-info" style="margin-top: 8px;">
          ${this._t('integration_starting')}
        </div>
        <div class="analyzing-hint" style="margin-top: 16px; font-size: 0.75em; color: var(--text-secondary); opacity: 0.7;">
          ${this._t('zone_check_hint')} "<strong>${this.config.zone}</strong>"
          ${this._t('exists_in_integration')}
          <br/>${this._t('expected_entity')}: <code>${expectedEntity}</code>
        </div>
      </div>
    `;
  }

  _renderAnalyzing(progress) {
    const timeRemaining = this._getTimeRemaining();
    const isReady = timeRemaining === "Prêt" || timeRemaining === "Ready" || timeRemaining === this._t('ready');

    return html`
      <div class="analyzing">
        <div class="analyzing-header">
          <span class="analyzing-title">${this._t('analyzing')}</span>
          <span class="analyzing-percent">${Math.round(progress)}%</span>
        </div>
        <div class="progress-track">
          <div class="progress-fill" style="width: ${progress}%"></div>
        </div>
        <div class="analyzing-footer">
          <ha-icon icon="mdi:clock-outline"></ha-icon>
          <span>${!isReady ? `${timeRemaining} ${this._t('remaining_time')}` : this._t('completed')}</span>
        </div>
        <div class="analyzing-info">
          ${this._t('analysis_in_progress')}
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
    const kPerM3EntityId = this._getEntityId("k_par_m3");
    const volume = demo ? 35 : this._getAttribute(kPerM3EntityId, "volume_m3");
    const insulation = demo ? demo.insulation : this._getState(this._getEntityId("note_d_isolation"));
    const performance = demo ? demo.performance : this._getState(this._getEntityId("performance_energetique"));
    const kHistory = this._getKHistory();

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
    const deltaTRaw = demo ? demo.delta_t : this._getState(this._getEntityId("dt_moyen_24h"));

    // Get temperatures from DeltaT sensor attributes (stored in Celsius)
    const deltaTEntityId = this._getEntityId("dt_moyen_24h");
    const indoorTempRaw = demo ? demo.indoor_temp : this._getAttribute(deltaTEntityId, "indoor_temp");
    const outdoorTempRaw = demo ? demo.outdoor_temp : this._getAttribute(deltaTEntityId, "outdoor_temp");

    // Convert temperatures based on user's unit system (backend stores in Celsius)
    const tempUnit = this._getTempUnit();
    const indoorTemp = this._convertTemp(indoorTempRaw);
    const outdoorTemp = this._convertTemp(outdoorTempRaw);
    const deltaTUnit = this._getEntityUnit(deltaTEntityId);
    const deltaT = this._convertTempDelta(deltaTRaw, deltaTUnit);  // Skip conversion if already in user's unit

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
            <div class="score-label">${this._t('isolation')}</div>
            <div class="score-value">${insulationData.label}</div>
            <div class="score-desc">${insulationData.desc}</div>
          </div>
        </div>

        <div class="score-card" style="--accent: ${perfData.color}">
          <div class="score-icon">
            <ha-icon icon="${perfData.icon}"></ha-icon>
          </div>
          <div class="score-content">
            <div class="score-label">${this._t('performance')}</div>
            <div class="score-value">${perfData.label}</div>
            <div class="score-badge">${perfData.badge} ${this._t('vs_average')}</div>
          </div>
        </div>

        <div class="score-card temp-card" style="--accent: #6366f1">
          <div class="score-icon">
            <ha-icon icon="mdi:thermometer"></ha-icon>
          </div>
          <div class="score-content">
            <div class="score-label">${this._t('temperatures')}</div>
            <div class="temp-values">
              <div class="temp-row">
                <ha-icon icon="mdi:home"></ha-icon>
                <span class="temp-value">${indoorTemp ?? "--"}${tempUnit}</span>
              </div>
              <div class="temp-row">
                <ha-icon icon="mdi:tree"></ha-icon>
                <span class="temp-value">${outdoorTemp ?? "--"}${tempUnit}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Metrics Grid -->
      <div class="metrics-section">
        <div class="section-title">${this._t('technical_details')}</div>

        <div class="metrics-grid">
          <div class="metric">
            <div class="metric-header">
              <ha-icon icon="mdi:heat-wave"></ha-icon>
              <span>${this._t('k_instant')}</span>
            </div>
            <div class="metric-value">${this._isValidValue(kCoef24h) ? `${kCoef24h} W/°C` : "--"}</div>
            ${this._isValidValue(kPerM3_24h)
        ? html`<div class="metric-sub">${kPerM3_24h} W/(°C·m³)</div>`
        : html`<div class="metric-sub">${this._t('rolling_24h')}</div>`}
          </div>

          <div class="metric">
            <div class="metric-header">
              <ha-icon icon="mdi:lightning-bolt"></ha-icon>
              <span>${this._t('energy_day')}</span>
            </div>
            <div class="metric-value">${this._isValidValue(dailyEnergy) ? `${dailyEnergy} kWh` : "--"}</div>
            <div class="metric-unit"><span class="metric-type">(${energyType === "mesurée" ? this._t('measured') : this._t('estimated')})</span></div>
          </div>

          <div class="metric">
            <div class="metric-header">
              <ha-icon icon="mdi:radiator"></ha-icon>
              <span>${this._t('heating_time')}</span>
            </div>
            <div class="metric-value">${this._isValidValue(heatingTime) ? heatingTime : "0min"}</div>
            <div class="metric-unit">${this._t('on_24h')}</div>
            ${this._isValidValue(heatingRatio)
        ? html`<div class="metric-sub">${heatingRatio}% ${this._t('of_time')}</div>`
        : ""}
          </div>

          <div class="metric">
            <div class="metric-header">
              <ha-icon icon="mdi:thermometer"></ha-icon>
              <span>${this._t('avg_delta')}</span>
            </div>
            <div class="metric-value">${this._isValidValue(deltaT) ? `${deltaT}${tempUnit}` : "--"}</div>
            <div class="metric-sub">${this._t('indoor_outdoor')}</div>
          </div>
        </div>
      </div>

      <!-- K History Chart (7 days) -->
      ${this.config.show_graph && kHistory && kHistory.length >= 2 ? html`
        <div class="history-section">
          <div class="section-title">${this._t('history_title')}</div>
          ${this._renderBarChart(kHistory, volume)}
        </div>
      ` : ''}
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

      .spinner {
        width: 40px;
        height: 40px;
        border: 3px solid var(--border-color);
        border-top-color: #6366f1;
        border-radius: 50%;
        animation: spin 1s linear infinite;
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

      /* ========================================
         K HISTORY - FULL LAYOUT (Bar Chart)
         ======================================== */
      .history-section {
        background: var(--bg-secondary);
        border-radius: 10px;
        padding: 8px 10px;
        margin-top: 8px;
      }

      .k-chart {
        display: flex;
        align-items: flex-end;
        justify-content: space-between;
        height: 80px;
        gap: 4px;
        padding: 4px 0;
      }

      .bar-wrapper {
        flex: 1;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: flex-end;
        height: 100%;
        cursor: pointer;
      }

      .bar-wrapper .bar {
        width: 100%;
        border-radius: 3px 3px 0 0;
        transition: all 0.2s ease;
        min-height: 4px;
        /* height is set via inline style */
      }

      .bar-wrapper:hover .bar {
        filter: brightness(1.2);
      }

      .bar-wrapper.estimated .bar {
        background-image: repeating-linear-gradient(
          45deg,
          transparent,
          transparent 2px,
          rgba(255,255,255,0.1) 2px,
          rgba(255,255,255,0.1) 4px
        );
      }

      .bar-label {
        font-size: 9px;
        color: var(--text-secondary);
        margin-top: 4px;
        text-transform: uppercase;
        letter-spacing: 0.2px;
      }

      /* Sparkline (shared for pill & badge) */
      .sparkline {
        display: block;
        width: 100%;
        height: 100%;
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

        .pill-sparkline-wrapper {
          display: none;
        }

        .k-chart {
          height: 60px;
        }

        .k-chart .bar {
          max-height: 40px;
        }

        .bar-label {
          font-size: 7px;
        }
      }

      /* ========================================
         BADGE LAYOUT (Concept A)
         ======================================== */
      .badge-card {
        background: var(--bg-primary);
        border-radius: 14px;
        border: 1px solid var(--border-color);
        padding: 20px 16px;
        min-width: 120px;
        flex: 1 1 140px;
        min-height: 223px;
        text-align: center;
        position: relative;
        overflow: hidden;
        display: flex;
        flex-direction: column;
      }

      .badge-accent-bar {
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 3px;
        background: var(--accent);
      }

      .badge-score-circle {
        width: 56px;
        height: 56px;
        border-radius: 12px;
        background: color-mix(in srgb, var(--accent) 20%, transparent);
        display: flex;
        align-items: center;
        justify-content: center;
        margin: 0 auto 12px;
      }

      .badge-score-letter {
        font-size: 26px;
        font-weight: 800;
        color: var(--accent);
        letter-spacing: -1px;
      }

      .badge-rating-label {
        font-size: 13px;
        font-weight: 700;
        color: var(--accent);
        text-transform: uppercase;
        letter-spacing: 0.8px;
        margin-bottom: 8px;
      }

      .badge-separator {
        width: 40px;
        height: 2px;
        background: var(--border-color);
        margin: 0 auto 10px;
        border-radius: 1px;
      }

      .badge-sparkline-wrapper {
        width: 80%;
        height: 24px;
        margin: 8px auto 12px;
      }

      .badge-zone-name {
        font-size: 14px;
        font-weight: 600;
        color: var(--text-primary);
        margin-bottom: 6px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }

      .badge-k-value {
        font-size: 15px;
        font-weight: 700;
        color: var(--text-primary);
        font-variant-numeric: tabular-nums;
      }

      .badge-k-unit {
        font-size: 11px;
        font-weight: 500;
        color: var(--text-secondary);
        margin-left: 2px;
      }

      .badge-k-normalized {
        font-size: 11px;
        color: var(--text-secondary);
        margin-top: 2px;
        opacity: 0.8;
      }

      /* Badge Analyzing State */
      .badge-analyzing {
        --accent: #6366f1;
        justify-content: center;
        align-items: center;
      }

      .badge-progress-ring {
        width: 56px;
        height: 56px;
        margin: 0 auto 12px;
        position: relative;
      }

      .badge-progress-ring svg {
        width: 100%;
        height: 100%;
      }

      .badge-progress-bg {
        stroke: var(--border-color);
      }

      .badge-progress-fill {
        stroke: #6366f1;
        stroke-linecap: round;
        transition: stroke-dashoffset 0.5s ease;
      }

      .badge-progress-text {
        position: absolute;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        font-size: 14px;
        font-weight: 700;
        color: #6366f1;
      }

      .badge-status {
        font-size: 11px;
        color: var(--text-secondary);
        margin-top: 4px;
        text-transform: uppercase;
        letter-spacing: 0.3px;
      }

      /* ========================================
         PILL LAYOUT (Concept D)
         ======================================== */
      .pill-card {
        background: var(--bg-primary);
        border-radius: 14px;
        border: 1px solid var(--border-color);
        padding: 8px 16px 8px 8px;
        display: flex;
        align-items: center;
        gap: 12px;
        width: 100%;
        height: 58px;
        position: relative;
        overflow: hidden;
      }

      .pill-accent-bar {
        position: absolute;
        left: 0;
        top: 0;
        bottom: 0;
        width: 4px;
        background: var(--accent);
        border-radius: 14px 0 0 14px;
      }

      .pill-score-badge {
        width: 42px;
        height: 42px;
        background: color-mix(in srgb, var(--accent) 20%, transparent);
        border-radius: 10px;
        display: flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
        margin-left: 8px;
      }

      .pill-score-letter {
        font-size: 18px;
        font-weight: 800;
        color: var(--accent);
      }

      .pill-zone-section {
        flex-shrink: 0;
        min-width: 0;
      }

      .pill-zone-name {
        font-size: 14px;
        font-weight: 600;
        color: var(--text-primary);
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }

      .pill-zone-rating {
        font-size: 11px;
        color: var(--accent);
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.3px;
      }

      .pill-sparkline-wrapper {
        flex: 1;
        min-width: 50px;
        height: 24px;
        margin: 0 12px;
      }

      .pill-separator {
        width: 1px;
        height: 28px;
        background: var(--border-color);
      }

      .pill-stats-section {
        display: flex;
        gap: 16px;
        flex-shrink: 0;
      }

      .pill-stat {
        text-align: center;
      }

      .pill-stat-value {
        font-size: 14px;
        font-weight: 700;
        color: var(--text-primary);
        font-variant-numeric: tabular-nums;
      }

      .pill-stat-label {
        font-size: 9px;
        color: var(--text-secondary);
        text-transform: uppercase;
        letter-spacing: 0.3px;
      }

      /* Pill Analyzing State */
      .pill-analyzing {
        --accent: #6366f1;
      }

      .pill-analyzing .pill-accent-bar {
        background: #6366f1;
      }

      .pill-progress-badge {
        width: 42px;
        height: 42px;
        background: color-mix(in srgb, #6366f1 20%, transparent);
        border-radius: 10px;
        display: flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
        margin-left: 8px;
      }

      .pill-progress-percent {
        font-size: 13px;
        font-weight: 800;
        color: #6366f1;
      }

      .pill-progress-track-wrapper {
        flex: 1;
        min-width: 60px;
        max-width: 120px;
      }

      .pill-progress-track {
        width: 100%;
        height: 4px;
        background: var(--border-color);
        border-radius: 2px;
        overflow: hidden;
      }

      .pill-progress-fill {
        height: 100%;
        background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
        border-radius: 2px;
        transition: width 0.5s ease;
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

  // Get translation for key (reuse HomePerformanceCard translations)
  _t(key) {
    const lang = this.hass?.language?.substring(0, 2) || 'en';
    const translations = HomePerformanceCard._translations[lang] || HomePerformanceCard._translations['en'];
    return translations[key] !== undefined ? translations[key] : key;
  }

  setConfig(config) {
    this.config = config;
  }

  configChanged(ev) {
    const target = ev.target;
    const newConfig = { ...this.config };

    if (target.configValue) {
      // ha-checkbox uses 'checked' property, not 'value'
      if (target.tagName === "HA-CHECKBOX" || target.type === "checkbox") {
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

  _setLayout(layout) {
    const newConfig = { ...this.config, layout };
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
          label="${this._t('editor_zone')}"
          .value=${this.config.zone || ""}
          .configValue=${"zone"}
          @input=${this.configChanged}
        ></ha-textfield>

        <ha-textfield
          label="${this._t('editor_title')}"
          .value=${this.config.title || ""}
          .configValue=${"title"}
          @input=${this.configChanged}
        ></ha-textfield>

        <div class="layout-selector">
          <label>${this._t('editor_card_style')}</label>
          <div class="layout-options">
            <div
              class="layout-option ${this.config.layout === "full" || !this.config.layout ? "selected" : ""}"
              @click=${() => this._setLayout("full")}
            >
              <div class="layout-preview layout-full">
                <div class="lp-header"></div>
                <div class="lp-content"></div>
              </div>
              <span>${this._t('editor_full')}</span>
            </div>
            <div
              class="layout-option ${this.config.layout === "badge" ? "selected" : ""}"
              @click=${() => this._setLayout("badge")}
            >
              <div class="layout-preview layout-badge">
                <div class="lp-circle"></div>
                <div class="lp-text"></div>
              </div>
              <span>${this._t('editor_badge')}</span>
            </div>
            <div
              class="layout-option ${this.config.layout === "pill" ? "selected" : ""}"
              @click=${() => this._setLayout("pill")}
            >
              <div class="layout-preview layout-pill">
                <div class="lp-dot"></div>
                <div class="lp-bar"></div>
              </div>
              <span>${this._t('editor_pill')}</span>
            </div>
          </div>
        </div>

        <ha-formfield label="${this._t('editor_show_graph')}">
          <ha-checkbox
            .checked=${this.config.show_graph !== false}
            .configValue=${"show_graph"}
            @change=${this.configChanged}
          ></ha-checkbox>
        </ha-formfield>

        <ha-formfield label="${this._t('editor_demo')}">
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

      .layout-selector label {
        display: block;
        font-size: 12px;
        color: var(--secondary-text-color);
        margin-bottom: 8px;
        text-transform: uppercase;
        letter-spacing: 0.5px;
      }

      .layout-options {
        display: flex;
        gap: 12px;
      }

      .layout-option {
        flex: 1;
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 8px;
        padding: 12px;
        border: 2px solid var(--divider-color);
        border-radius: 12px;
        cursor: pointer;
        transition: all 0.2s ease;
      }

      .layout-option:hover {
        border-color: var(--primary-color);
        background: rgba(var(--rgb-primary-color), 0.05);
      }

      .layout-option.selected {
        border-color: var(--primary-color);
        background: rgba(var(--rgb-primary-color), 0.1);
      }

      .layout-option span {
        font-size: 11px;
        font-weight: 600;
        color: var(--primary-text-color);
      }

      .layout-preview {
        width: 50px;
        height: 40px;
        background: var(--card-background-color);
        border-radius: 6px;
        display: flex;
        flex-direction: column;
        padding: 4px;
        gap: 3px;
      }

      .layout-full .lp-header {
        height: 8px;
        background: var(--divider-color);
        border-radius: 2px;
      }

      .layout-full .lp-content {
        flex: 1;
        background: var(--divider-color);
        border-radius: 2px;
        opacity: 0.5;
      }

      .layout-badge {
        align-items: center;
        justify-content: center;
        gap: 4px;
      }

      .layout-badge .lp-circle {
        width: 16px;
        height: 16px;
        background: var(--primary-color);
        border-radius: 4px;
        opacity: 0.6;
      }

      .layout-badge .lp-text {
        width: 24px;
        height: 4px;
        background: var(--divider-color);
        border-radius: 2px;
      }

      .layout-pill {
        flex-direction: row;
        align-items: center;
        justify-content: flex-start;
        padding: 8px;
        gap: 6px;
      }

      .layout-pill .lp-dot {
        width: 12px;
        height: 12px;
        background: var(--primary-color);
        border-radius: 3px;
        opacity: 0.6;
      }

      .layout-pill .lp-bar {
        flex: 1;
        height: 6px;
        background: var(--divider-color);
        border-radius: 2px;
      }
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
  `%c HOME-PERFORMANCE %c v${CARD_VERSION} `,
  "color: white; background: #6366f1; font-weight: bold; border-radius: 4px 0 0 4px; padding: 2px 6px;",
  "color: #6366f1; background: #1a1a2e; font-weight: bold; border-radius: 0 4px 4px 0; padding: 2px 6px;"
);
