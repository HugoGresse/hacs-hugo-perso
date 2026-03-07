/**
 * AI Usage Monitor Card
 * A custom Lovelace card for Home Assistant that displays
 * Cursor and Claude Code usage, refreshing on page focus.
 */

class AIUsageMonitorCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._boundVisibilityHandler = this._onVisibilityChange.bind(this);
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  setConfig(config) {
    this._config = {
      title: config.title || "AI Usage",
      cursor_auto_entity: config.cursor_auto_entity || "",
      cursor_api_entity: config.cursor_api_entity || "",
      cursor_total_entity: config.cursor_total_entity || "",
      cursor_spend_entity: config.cursor_spend_entity || "",
      claude_entity: config.claude_entity || "",
      show_cursor: config.show_cursor !== false,
      show_claude: config.show_claude !== false,
      ...config,
    };
  }

  connectedCallback() {
    document.addEventListener("visibilitychange", this._boundVisibilityHandler);
    window.addEventListener("focus", () => this._refreshEntities());
  }

  disconnectedCallback() {
    document.removeEventListener("visibilitychange", this._boundVisibilityHandler);
  }

  _onVisibilityChange() {
    if (document.visibilityState === "visible") {
      this._refreshEntities();
    }
  }

  _refreshEntities() {
    if (!this._hass) return;

    const entities = [
      this._config.cursor_auto_entity,
      this._config.cursor_api_entity,
      this._config.cursor_total_entity,
      this._config.cursor_spend_entity,
      this._config.claude_entity,
    ].filter(Boolean);

    for (const entityId of entities) {
      this._hass.callService("homeassistant", "update_entity", {
        entity_id: entityId,
      });
    }
  }

  _getBarColor(percent) {
    if (percent < 50) return "#4caf50";
    if (percent < 75) return "#ff9800";
    return "#f44336";
  }

  _render() {
    if (!this._hass || !this._config) return;

    const c = this._config;
    const h = this._hass;

    let cursorHtml = "";
    let claudeHtml = "";

    // --- Cursor section ---
    if (c.show_cursor) {
      const autoState = c.cursor_auto_entity ? h.states[c.cursor_auto_entity] : null;
      const apiState = c.cursor_api_entity ? h.states[c.cursor_api_entity] : null;
      const totalState = c.cursor_total_entity ? h.states[c.cursor_total_entity] : null;
      const spendState = c.cursor_spend_entity ? h.states[c.cursor_spend_entity] : null;

      const bars = [];

      if (autoState && autoState.state !== "unavailable" && autoState.state !== "unknown") {
        const v = parseFloat(autoState.state);
        bars.push({ label: "Auto (Agent)", value: v });
      }
      if (apiState && apiState.state !== "unavailable" && apiState.state !== "unknown") {
        const v = parseFloat(apiState.state);
        bars.push({ label: "API (Named)", value: v });
      }
      if (totalState && totalState.state !== "unavailable" && totalState.state !== "unknown") {
        const v = parseFloat(totalState.state);
        bars.push({ label: "Total", value: v });
      }

      let spendLine = "";
      if (spendState && spendState.state !== "unavailable") {
        spendLine = `<div class="spend">Spend: $${spendState.state}</div>`;
      }

      const barsHtml = bars
        .map(
          (b) => `
        <div class="bar-row">
          <div class="bar-label">${b.label}</div>
          <div class="bar-track">
            <div class="bar-fill" style="width: ${Math.min(b.value, 100)}%; background: ${this._getBarColor(b.value)}"></div>
          </div>
          <div class="bar-value">${b.value.toFixed(1)}%</div>
        </div>`
        )
        .join("");

      cursorHtml = `
        <div class="service">
          <div class="service-header">
            <span class="service-icon">⌨️</span>
            <span class="service-name">Cursor</span>
          </div>
          ${barsHtml}
          ${spendLine}
        </div>`;
    }

    // --- Claude section ---
    if (c.show_claude && c.claude_entity) {
      const claudeState = h.states[c.claude_entity];
      if (claudeState && claudeState.state !== "unavailable" && claudeState.state !== "unknown") {
        const v = parseFloat(claudeState.state);
        claudeHtml = `
          <div class="service">
            <div class="service-header">
              <span class="service-icon">🤖</span>
              <span class="service-name">Claude Code</span>
            </div>
            <div class="bar-row">
              <div class="bar-label">Usage</div>
              <div class="bar-track">
                <div class="bar-fill" style="width: ${Math.min(v, 100)}%; background: ${this._getBarColor(v)}"></div>
              </div>
              <div class="bar-value">${v.toFixed(1)}%</div>
            </div>
          </div>`;
      } else {
        claudeHtml = `
          <div class="service">
            <div class="service-header">
              <span class="service-icon">🤖</span>
              <span class="service-name">Claude Code</span>
            </div>
            <div class="unavailable">No data available — check cookie configuration</div>
          </div>`;
      }
    }

    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
        }
        ha-card {
          padding: 16px;
        }
        .title {
          font-size: 1.1em;
          font-weight: 500;
          margin-bottom: 12px;
          color: var(--primary-text-color);
        }
        .service {
          margin-bottom: 16px;
        }
        .service:last-child {
          margin-bottom: 0;
        }
        .service-header {
          display: flex;
          align-items: center;
          gap: 8px;
          margin-bottom: 8px;
          font-weight: 500;
          font-size: 0.95em;
        }
        .service-icon {
          font-size: 1.2em;
        }
        .bar-row {
          display: flex;
          align-items: center;
          gap: 8px;
          margin-bottom: 6px;
        }
        .bar-label {
          width: 80px;
          font-size: 0.85em;
          color: var(--secondary-text-color);
          flex-shrink: 0;
        }
        .bar-track {
          flex: 1;
          height: 8px;
          background: var(--divider-color, #e0e0e0);
          border-radius: 4px;
          overflow: hidden;
        }
        .bar-fill {
          height: 100%;
          border-radius: 4px;
          transition: width 0.5s ease;
        }
        .bar-value {
          width: 55px;
          text-align: right;
          font-size: 0.85em;
          font-weight: 500;
          flex-shrink: 0;
        }
        .spend {
          font-size: 0.8em;
          color: var(--secondary-text-color);
          margin-top: 4px;
        }
        .unavailable {
          font-size: 0.85em;
          color: var(--secondary-text-color);
          font-style: italic;
        }
      </style>
      <ha-card>
        <div class="title">${c.title}</div>
        ${cursorHtml}
        ${claudeHtml}
      </ha-card>
    `;
  }

  getCardSize() {
    return 3;
  }

  static getStubConfig() {
    return {
      title: "AI Usage",
      cursor_auto_entity: "sensor.cursor_auto_usage",
      cursor_api_entity: "sensor.cursor_api_usage",
      cursor_total_entity: "sensor.cursor_total_usage",
      cursor_spend_entity: "sensor.cursor_total_spend",
      claude_entity: "sensor.claude_usage",
    };
  }
}

customElements.define("ai-usage-monitor-card", AIUsageMonitorCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "ai-usage-monitor-card",
  name: "AI Usage Monitor",
  description: "Display Cursor and Claude Code usage with auto-refresh on focus",
});
