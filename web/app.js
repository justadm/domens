const I18N = {
  ru: {
    lang: "Язык",
    theme: "Тема",
    metric_checked: "Проверено",
    metric_available: "Доступны",
    metric_pending: "Pending Delete",
    metric_score: "Средний Score",
    scanner_title: "Сканер доменов",
    scanner_domains: "Домены (по одному в строке)",
    scanner_run: "Проверить",
    monitor_run: "Запустить мониторинг",
    th_domain: "Домен",
    th_status: "Статус",
    th_score: "Score",
    th_eta: "ETA освобождения",
    alert_title: "Алерт в Telegram",
    alert_domain: "Домен",
    alert_chat: "Chat ID",
    alert_send: "Отправить алерт",
    reg_title: "Регистрация",
    reg_token: "Confirmation token",
    reg_confirm: "Подтвердить",
    reg_order: "Order ID",
    reg_execute: "Execute",
    activity_title: "Последние события",
    api_online: "API: online",
    api_offline: "API: offline",
    feed_empty: "Событий пока нет",
    auth_guest: "Гость",
    auth_logged_as: "Вход:",
    auth_logout: "Выйти",
    auth_login_hint: "Вход через Telegram/MAX",
    auth_max_login: "Войти через MAX",
    cabinet_title: "Кабинет",
    cabinet_refresh: "Обновить",
    cabinet_profile: "Профиль",
    cabinet_subscriptions: "Подписки",
    cabinet_chat_id: "Telegram Chat ID",
    cabinet_alerts_on: "Алерты ON",
    cabinet_alerts_off: "Алерты OFF",
    cabinet_max_target: "MAX target/chat",
    cabinet_max_on: "MAX ON",
    cabinet_max_off: "MAX OFF",
    cabinet_watch: "Watch-правила",
    cabinet_watch_query: "Запрос",
    cabinet_watch_add: "Добавить правило",
    cabinet_watch_tlds: "TLDs CSV",
    cabinet_watch_min_score: "Min score",
    cabinet_watch_max_price: "Max price USD",
    cabinet_watch_search: "Поиск rules",
    cabinet_watch_status_filter: "Статус",
    cabinet_history: "История",
    cabinet_history_type: "Тип события",
    cabinet_history_search: "Поиск по payload",
    cabinet_history_limit: "Лимит",
    cabinet_history_apply: "Применить",
    cabinet_login_required: "Войдите через Telegram, чтобы открыть кабинет",
    cabinet_empty: "Пусто",
    cabinet_pause: "Пауза",
    cabinet_resume: "Возобновить",
    cabinet_delete: "Удалить",
    cabinet_save: "Сохранить",
  },
  en: {
    lang: "Language",
    theme: "Theme",
    metric_checked: "Checked",
    metric_available: "Available",
    metric_pending: "Pending Delete",
    metric_score: "Average Score",
    scanner_title: "Domain Scanner",
    scanner_domains: "Domains (one per line)",
    scanner_run: "Run Scan",
    monitor_run: "Run monitoring once",
    th_domain: "Domain",
    th_status: "Status",
    th_score: "Score",
    th_eta: "Drop ETA",
    alert_title: "Telegram Alert",
    alert_domain: "Domain",
    alert_chat: "Chat ID",
    alert_send: "Send Alert",
    reg_title: "Registration Pipeline",
    reg_token: "Confirmation token",
    reg_confirm: "Confirm",
    reg_order: "Order ID",
    reg_execute: "Execute",
    activity_title: "Recent activity",
    api_online: "API: online",
    api_offline: "API: offline",
    feed_empty: "No events yet",
    auth_guest: "Guest",
    auth_logged_as: "Signed in:",
    auth_logout: "Logout",
    auth_login_hint: "Sign in with Telegram/MAX",
    auth_max_login: "Sign in with MAX",
    cabinet_title: "Cabinet",
    cabinet_refresh: "Refresh",
    cabinet_profile: "Profile",
    cabinet_subscriptions: "Subscriptions",
    cabinet_chat_id: "Telegram Chat ID",
    cabinet_alerts_on: "Alerts ON",
    cabinet_alerts_off: "Alerts OFF",
    cabinet_max_target: "MAX target/chat",
    cabinet_max_on: "MAX ON",
    cabinet_max_off: "MAX OFF",
    cabinet_watch: "Watch Rules",
    cabinet_watch_query: "Query",
    cabinet_watch_add: "Add Rule",
    cabinet_watch_tlds: "TLDs CSV",
    cabinet_watch_min_score: "Min score",
    cabinet_watch_max_price: "Max price USD",
    cabinet_watch_search: "Search rules",
    cabinet_watch_status_filter: "Status",
    cabinet_history: "History",
    cabinet_history_type: "Event Type",
    cabinet_history_search: "Search payload",
    cabinet_history_limit: "Limit",
    cabinet_history_apply: "Apply",
    cabinet_login_required: "Sign in with Telegram to open cabinet",
    cabinet_empty: "Empty",
    cabinet_pause: "Pause",
    cabinet_resume: "Resume",
    cabinet_delete: "Delete",
    cabinet_save: "Save",
  },
};

let currentLang = localStorage.getItem("domens_lang") || "ru";
let currentTheme = localStorage.getItem("domens_theme") || "dark";
let lastResults = [];
let sortState = { key: "domain", dir: "asc" };
let authState = { authenticated: false, user: null };
let cabinetState = { profile: null, subscriptions: [], watchRules: [], history: [] };
let cabinetRefreshTimer = null;

async function api(path, options = {}) {
  const res = await fetch(path, {
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    ...options,
  });

  const text = await res.text();
  let body;
  try {
    body = JSON.parse(text);
  } catch {
    body = { raw: text };
  }

  if (!res.ok) {
    throw new Error(JSON.stringify(body));
  }
  return body;
}

function linesToDomains(value) {
  return value
    .split("\n")
    .map((s) => s.trim())
    .filter(Boolean);
}

function csvToList(value) {
  return String(value || "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function put(el, data) {
  el.textContent = JSON.stringify(data, null, 2);
}

function escapeHtml(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function formatDate(value) {
  if (!value) return "-";
  try {
    return new Date(value).toLocaleString(currentLang === "ru" ? "ru-RU" : "en-US");
  } catch {
    return String(value);
  }
}

function compare(a, b) {
  const { key, dir } = sortState;
  const mul = dir === "asc" ? 1 : -1;

  if (key === "score") {
    return (Number(a.score || 0) - Number(b.score || 0)) * mul;
  }
  if (key === "eta") {
    const av = a.drop_time_estimated_at ? Date.parse(a.drop_time_estimated_at) : 0;
    const bv = b.drop_time_estimated_at ? Date.parse(b.drop_time_estimated_at) : 0;
    return (av - bv) * mul;
  }

  const av = String(a[key] || "").toLowerCase();
  const bv = String(b[key] || "").toLowerCase();
  return av.localeCompare(bv) * mul;
}

function renderResults() {
  const tbody = document.getElementById("results-body");
  tbody.innerHTML = "";

  const results = [...lastResults].sort(compare);
  for (const item of results) {
    const tr = document.createElement("tr");
    const safeStatus = String(item.status || "unknown");
    tr.innerHTML = `
      <td>${item.domain || "-"}</td>
      <td><span class="status-chip status-${safeStatus}">${safeStatus}</span></td>
      <td>${item.score ?? "-"}</td>
      <td>${formatDate(item.drop_time_estimated_at)}</td>
    `;
    tbody.appendChild(tr);
  }
}

function updateMetrics(results) {
  const checked = results.length;
  const available = results.filter((r) => r.status === "available").length;
  const pending = results.filter((r) => r.status === "pending_delete").length;
  const avgScore = checked ? (results.reduce((s, r) => s + Number(r.score || 0), 0) / checked).toFixed(1) : "0";

  document.getElementById("metric-checked").textContent = String(checked);
  document.getElementById("metric-available").textContent = String(available);
  document.getElementById("metric-pending").textContent = String(pending);
  document.getElementById("metric-score").textContent = String(avgScore);
}

function applyLanguage(lang) {
  currentLang = lang in I18N ? lang : "ru";
  localStorage.setItem("domens_lang", currentLang);
  document.documentElement.lang = currentLang;

  const dict = I18N[currentLang];
  document.querySelectorAll("[data-i18n]").forEach((el) => {
    const key = el.getAttribute("data-i18n");
    if (key && dict[key]) {
      el.textContent = dict[key];
    }
  });

  document.getElementById("lang-select").value = currentLang;
  const logoutBtn = document.getElementById("logout-btn");
  if (logoutBtn) {
    logoutBtn.textContent = dict.auth_logout;
  }
  const maxLoginBtn = document.getElementById("max-login-btn");
  if (maxLoginBtn) {
    maxLoginBtn.textContent = dict.auth_max_login;
  }
}

function applyTheme(theme) {
  currentTheme = theme === "light" ? "light" : "dark";
  localStorage.setItem("domens_theme", currentTheme);
  document.documentElement.setAttribute("data-theme", currentTheme);
  document.getElementById("theme-select").value = currentTheme;
}

function setupMenu() {
  const menuLinks = document.querySelectorAll(".js-menu-link");
  menuLinks.forEach((link) => {
    link.addEventListener("click", (e) => {
      const href = link.getAttribute("href") || "";
      if (!href.startsWith("#")) return;
      e.preventDefault();
      const target = document.querySelector(href);
      if (!target) return;
      target.scrollIntoView({ behavior: "smooth", block: "start" });
      menuLinks.forEach((item) => item.classList.remove("active"));
      link.classList.add("active");
    });
  });

  const groups = document.querySelectorAll("details.nav-group[data-group]");
  groups.forEach((group) => {
    const key = `menu_group_${group.dataset.group}`;
    const saved = localStorage.getItem(key);
    if (saved === "open") group.open = true;
    if (saved === "closed") group.open = false;

    group.addEventListener("toggle", () => {
      localStorage.setItem(key, group.open ? "open" : "closed");
    });
  });
}

function setupSorting() {
  document.querySelectorAll("#results-table th[data-sort]").forEach((th) => {
    th.addEventListener("click", () => {
      const key = th.dataset.sort;
      if (!key) return;

      if (sortState.key === key) {
        sortState.dir = sortState.dir === "asc" ? "desc" : "asc";
      } else {
        sortState.key = key;
        sortState.dir = "asc";
      }
      renderResults();
    });
  });
}

async function refreshHealth() {
  const badge = document.getElementById("api-health");
  const dict = I18N[currentLang];
  try {
    await api("/health");
    badge.textContent = dict.api_online;
  } catch {
    badge.textContent = dict.api_offline;
  }
}

async function refreshActivity() {
  const feed = document.getElementById("activity-feed");
  const dict = I18N[currentLang];
  try {
    const data = await api("/v1/activity/recent?limit=20");
    const items = data.items || [];
    if (!items.length) {
      feed.innerHTML = `<p class=\"feed-empty\">${dict.feed_empty}</p>`;
      return;
    }

    feed.innerHTML = items
      .map(
        (item) => `
        <article class="feed-item">
          <div class="feed-row">
            <strong>${item.domain}</strong>
            <span class="feed-kind">${item.kind}</span>
          </div>
          <div class="feed-row">
            <span class="feed-status">${item.status}</span>
            <time>${formatDate(item.created_at)}</time>
          </div>
        </article>
      `,
      )
      .join("");
  } catch (err) {
    feed.innerHTML = `<p class=\"feed-empty\">${String(err)}</p>`;
  }
}

function setCabinetMessage(message) {
  const profileEl = document.getElementById("cabinet-profile");
  const subsEl = document.getElementById("cabinet-subs");
  const watchEl = document.getElementById("cabinet-watch-list");
  const historyEl = document.getElementById("cabinet-history");
  if (profileEl) profileEl.innerHTML = `<p class="feed-empty">${escapeHtml(message)}</p>`;
  if (subsEl) subsEl.innerHTML = `<p class="feed-empty">${escapeHtml(message)}</p>`;
  if (watchEl) watchEl.innerHTML = `<p class="feed-empty">${escapeHtml(message)}</p>`;
  if (historyEl) historyEl.innerHTML = `<p class="feed-empty">${escapeHtml(message)}</p>`;
}

function renderCabinetProfile(data) {
  const root = document.getElementById("cabinet-profile");
  if (!root) return;
  const rows = [
    ["telegram_user_id", data.telegram_user_id || "-"],
    ["username", data.username ? `@${data.username}` : "-"],
    ["first_name", data.first_name || "-"],
    ["locale", data.locale || "-"],
    ["chat_id", data.chat_id || "-"],
    ["disclaimer_version", data.disclaimer_version || "-"],
    ["disclaimer_accepted_at", formatDate(data.disclaimer_accepted_at)],
    ["alerts_enabled", data.alerts_enabled ? "true" : "false"],
    ["max_alerts_enabled", data.max_alerts_enabled ? "true" : "false"],
    ["watch_rules_active", String(data.watch_rules_active || 0)],
  ];
  root.innerHTML = rows
    .map(
      ([key, value]) =>
        `<div class="kv-row"><span class="kv-key">${escapeHtml(key)}</span><span class="kv-value">${escapeHtml(value)}</span></div>`,
    )
    .join("");
  const chatInput = document.getElementById("cabinet-chat-id");
  if (chatInput && data.chat_id) {
    chatInput.value = data.chat_id;
  }
}

function renderCabinetSubscriptions(items) {
  const root = document.getElementById("cabinet-subs");
  const dict = I18N[currentLang];
  if (!root) return;
  if (!items || !items.length) {
    root.innerHTML = `<p class="feed-empty">${dict.cabinet_empty}</p>`;
    return;
  }
  root.innerHTML = items
    .map(
      (item) => `
      <article class="list-row">
        <div class="feed-row">
          <strong>${escapeHtml(item.channel_type)}</strong>
          <span class="feed-status">${escapeHtml(item.status)}</span>
        </div>
        <div class="feed-row">
          <span>${escapeHtml(item.channel_target || "-")}</span>
          <time>${formatDate(item.updated_at)}</time>
        </div>
      </article>`,
    )
    .join("");

  const maxSub = items.find((item) => String(item.channel_type || "").toLowerCase() === "max");
  const maxInput = document.getElementById("cabinet-max-target");
  if (maxSub && maxInput && !maxInput.value.trim()) {
    maxInput.value = String(maxSub.channel_target || "");
  }
}

function renderCabinetWatchRules(items) {
  const root = document.getElementById("cabinet-watch-list");
  const dict = I18N[currentLang];
  if (!root) return;
  if (!items || !items.length) {
    root.innerHTML = `<p class="feed-empty">${dict.cabinet_empty}</p>`;
    return;
  }
  root.innerHTML = items
    .map(
      (item) => `
      <article class="list-row">
        <div class="feed-row">
          <strong>${escapeHtml(item.query)}</strong>
          <span class="feed-status">${escapeHtml(item.status)}</span>
        </div>
        <div class="feed-row">
          <span>${escapeHtml(item.id)}</span>
          <span>score >= ${item.min_score ?? "-"} | max $${item.max_price_usd ?? "-"}</span>
        </div>
        <div class="rule-edit-grid">
          <input class="rule-edit-input" data-rule-field="query" data-rule-id="${escapeHtml(item.id)}" value="${escapeHtml(item.query || "")}" />
          <input class="rule-edit-input" data-rule-field="tlds" data-rule-id="${escapeHtml(item.id)}" value="${escapeHtml((item.tlds || []).join(","))}" placeholder=".com,.io" />
          <input class="rule-edit-input" data-rule-field="min_score" data-rule-id="${escapeHtml(item.id)}" value="${item.min_score ?? ""}" type="number" min="0" max="100" step="0.1" placeholder="70" />
          <input class="rule-edit-input" data-rule-field="max_price_usd" data-rule-id="${escapeHtml(item.id)}" value="${item.max_price_usd ?? ""}" type="number" min="0" step="0.01" placeholder="20" />
        </div>
        <div class="list-row-actions">
          <button type="button" class="mini-btn js-watch-action" data-action="paused" data-rule-id="${escapeHtml(item.id)}">${dict.cabinet_pause}</button>
          <button type="button" class="mini-btn js-watch-action" data-action="active" data-rule-id="${escapeHtml(item.id)}">${dict.cabinet_resume}</button>
          <button type="button" class="mini-btn js-watch-action" data-action="deleted" data-rule-id="${escapeHtml(item.id)}">${dict.cabinet_delete}</button>
          <button type="button" class="mini-btn js-watch-save" data-rule-id="${escapeHtml(item.id)}">${dict.cabinet_save}</button>
        </div>
      </article>`,
    )
    .join("");
}

function renderCabinetHistory(items) {
  const root = document.getElementById("cabinet-history");
  const dict = I18N[currentLang];
  if (!root) return;
  if (!items || !items.length) {
    root.innerHTML = `<p class="feed-empty">${dict.cabinet_empty}</p>`;
    return;
  }
  root.innerHTML = items
    .map(
      (item) => `
      <article class="list-row">
        <div class="feed-row">
          <strong>${escapeHtml(item.event_type)}</strong>
          <time>${formatDate(item.created_at)}</time>
        </div>
        <pre class="output">${escapeHtml(JSON.stringify(item.payload || {}, null, 2))}</pre>
      </article>`,
    )
    .join("");
}

async function refreshCabinet() {
  const dict = I18N[currentLang];
  if (!authState.authenticated || !authState.user) {
    setCabinetMessage(dict.cabinet_login_required);
    return;
  }

  try {
    const watchSearch = document.getElementById("cabinet-watch-search").value.trim();
    const watchStatus = document.getElementById("cabinet-watch-status-filter").value.trim();
    const historyType = document.getElementById("cabinet-history-type").value.trim();
    const historySearch = document.getElementById("cabinet-history-search").value.trim();
    const historyLimitRaw = Number(document.getElementById("cabinet-history-limit").value || 40);
    const historyLimit = Number.isFinite(historyLimitRaw) ? Math.max(1, Math.min(200, historyLimitRaw)) : 40;

    const watchParams = new URLSearchParams();
    if (watchStatus) watchParams.set("status", watchStatus);
    if (watchSearch) watchParams.set("search", watchSearch);
    const watchUrl = watchParams.size ? `/v1/cabinet/watch-rules?${watchParams.toString()}` : "/v1/cabinet/watch-rules";

    const historyParams = new URLSearchParams({ limit: String(historyLimit) });
    if (historyType) historyParams.set("event_type", historyType);
    if (historySearch) historyParams.set("search", historySearch);
    const historyUrl = `/v1/cabinet/history?${historyParams.toString()}`;

    const [profile, subs, watchRules, history] = await Promise.all([
      api("/v1/cabinet/profile"),
      api("/v1/cabinet/subscriptions"),
      api(watchUrl),
      api(historyUrl),
    ]);
    cabinetState = {
      profile,
      subscriptions: subs.items || [],
      watchRules: watchRules.items || [],
      history: history.items || [],
    };
    renderCabinetProfile(profile);
    renderCabinetSubscriptions(cabinetState.subscriptions);
    renderCabinetWatchRules(cabinetState.watchRules);
    renderCabinetHistory(cabinetState.history);
  } catch (err) {
    setCabinetMessage(String(err));
  }
}

function renderAuthState(authenticated, user) {
  const dict = I18N[currentLang];
  const userLine = document.getElementById("auth-user-line");
  const logoutBtn = document.getElementById("logout-btn");
  const widgetRoot = document.getElementById("tg-auth-widget");
  const maxLoginBtn = document.getElementById("max-login-btn");

  if (!userLine || !logoutBtn || !widgetRoot || !maxLoginBtn) {
    return;
  }

  if (authenticated && user) {
    const username = user.username ? `@${user.username}` : user.first_name || user.telegram_user_id;
    userLine.textContent = `${dict.auth_logged_as} ${username}`;
    logoutBtn.classList.remove("hidden");
    widgetRoot.classList.add("hidden");
    maxLoginBtn.classList.add("hidden");
    authState = { authenticated: true, user };
    return;
  }

  userLine.textContent = `${dict.auth_guest}. ${dict.auth_login_hint}`;
  logoutBtn.classList.add("hidden");
  widgetRoot.classList.remove("hidden");
  if (!maxLoginBtn.dataset.enabled || maxLoginBtn.dataset.enabled !== "true") {
    maxLoginBtn.classList.add("hidden");
  } else {
    maxLoginBtn.classList.remove("hidden");
  }
  authState = { authenticated: false, user: null };
}

async function refreshAuth() {
  try {
    const data = await api("/v1/auth/me");
    renderAuthState(Boolean(data.authenticated), data.user || null);
    await refreshCabinet();
  } catch {
    renderAuthState(false, null);
    await refreshCabinet();
  }
}

async function initTelegramAuthWidget() {
  const widgetRoot = document.getElementById("tg-auth-widget");
  if (!widgetRoot) return;

  try {
    const config = await api("/v1/auth/telegram/widget-config");
    if (!config.enabled || !config.bot_username) {
      widgetRoot.textContent = "Telegram auth disabled";
      return;
    }

    window.DomensTelegramAuth = async (user) => {
      try {
        await api("/v1/auth/telegram/login", {
          method: "POST",
          body: JSON.stringify(user),
        });
        await refreshAuth();
      } catch (err) {
        const errorText = String(err);
        document.getElementById("auth-user-line").textContent = errorText;
      }
    };

    widgetRoot.innerHTML = "";
    const script = document.createElement("script");
    script.async = true;
    script.src = "https://telegram.org/js/telegram-widget.js?22";
    script.setAttribute("data-telegram-login", config.bot_username);
    script.setAttribute("data-size", "medium");
    script.setAttribute("data-userpic", "false");
    script.setAttribute("data-request-access", "write");
    script.setAttribute("data-radius", "8");
    script.setAttribute("data-onauth", "DomensTelegramAuth(user)");
    widgetRoot.appendChild(script);
  } catch {
    widgetRoot.textContent = "Telegram auth unavailable";
  }
}

async function initMaxAuth() {
  const maxLoginBtn = document.getElementById("max-login-btn");
  if (!maxLoginBtn) return;

  maxLoginBtn.dataset.enabled = "false";
  maxLoginBtn.classList.add("hidden");

  try {
    const config = await api("/v1/auth/max/config");
    if (!config.enabled) {
      return;
    }
    maxLoginBtn.dataset.enabled = "true";
    if (!authState.authenticated) {
      maxLoginBtn.classList.remove("hidden");
    }
  } catch {
    maxLoginBtn.dataset.enabled = "false";
  }
}

document.getElementById("check-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const output = document.getElementById("check-output");

  try {
    const domains = linesToDomains(document.getElementById("domains-input").value);
    const data = await api("/v1/domains/check", {
      method: "POST",
      body: JSON.stringify({ domains, source: "web" }),
    });

    lastResults = data.results || [];
    renderResults();
    updateMetrics(lastResults);
    put(output, data);
    await refreshActivity();
  } catch (err) {
    put(output, { error: String(err) });
  }
});

document.getElementById("run-monitor-btn").addEventListener("click", async () => {
  const output = document.getElementById("monitor-output");
  output.classList.remove("hidden");
  try {
    const data = await api("/v1/monitoring/run-once", { method: "POST" });
    put(output, data);
    await refreshActivity();
  } catch (err) {
    put(output, { error: String(err) });
  }
});

document.getElementById("alert-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const output = document.getElementById("alert-output");

  try {
    const domain = document.getElementById("alert-domain").value.trim();
    const chatId = document.getElementById("alert-chat-id").value.trim();
    const data = await api("/v1/alerts/trigger", {
      method: "POST",
      body: JSON.stringify({ domain, telegram_chat_id: chatId }),
    });

    document.getElementById("confirm-token").value = data.confirmation_token || "";
    put(output, data);
    await refreshActivity();
  } catch (err) {
    put(output, { error: String(err) });
  }
});

document.getElementById("confirm-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const output = document.getElementById("registration-output");

  try {
    const confirmationToken = document.getElementById("confirm-token").value.trim();
    const data = await api("/v1/registrations/confirm", {
      method: "POST",
      body: JSON.stringify({ confirmation_token: confirmationToken, confirmed_by: "web:manual" }),
    });
    document.getElementById("execute-order-id").value = data.order_id || "";
    put(output, data);
    await refreshActivity();
  } catch (err) {
    put(output, { error: String(err) });
  }
});

document.getElementById("execute-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const output = document.getElementById("registration-output");

  try {
    const orderId = document.getElementById("execute-order-id").value.trim();
    const data = await api(`/v1/registrations/${orderId}/execute`, {
      method: "POST",
    });
    put(output, data);
    await refreshActivity();
  } catch (err) {
    put(output, { error: String(err) });
  }
});

document.getElementById("lang-select").addEventListener("change", (e) => {
  applyLanguage(e.target.value);
  refreshHealth();
  refreshActivity();
});

document.getElementById("theme-select").addEventListener("change", (e) => {
  applyTheme(e.target.value);
});

document.getElementById("logout-btn").addEventListener("click", async () => {
  try {
    await api("/v1/auth/logout", { method: "POST" });
  } catch {
    // keep UI state change even if server already dropped session
  }
  await refreshAuth();
});

document.getElementById("max-login-btn").addEventListener("click", async () => {
  try {
    const data = await api("/v1/auth/max/login-url");
    if (!data.enabled || !data.url) {
      document.getElementById("auth-user-line").textContent = "MAX OAuth is not configured";
      return;
    }
    window.location.href = data.url;
  } catch (err) {
    document.getElementById("auth-user-line").textContent = String(err);
  }
});

document.getElementById("cabinet-refresh-btn").addEventListener("click", async () => {
  await refreshCabinet();
});

document.getElementById("cabinet-alerts-on-btn").addEventListener("click", async () => {
  try {
    await api("/v1/cabinet/subscriptions/telegram", {
      method: "POST",
      body: JSON.stringify({
        enabled: true,
        chat_id: document.getElementById("cabinet-chat-id").value.trim() || null,
      }),
    });
    await refreshCabinet();
  } catch (err) {
    setCabinetMessage(String(err));
  }
});

document.getElementById("cabinet-alerts-off-btn").addEventListener("click", async () => {
  try {
    await api("/v1/cabinet/subscriptions/telegram", {
      method: "POST",
      body: JSON.stringify({
        enabled: false,
        chat_id: document.getElementById("cabinet-chat-id").value.trim() || null,
      }),
    });
    await refreshCabinet();
  } catch (err) {
    setCabinetMessage(String(err));
  }
});

document.getElementById("cabinet-max-on-btn").addEventListener("click", async () => {
  try {
    await api("/v1/cabinet/subscriptions/channel", {
      method: "POST",
      body: JSON.stringify({
        channel_type: "max",
        enabled: true,
        target: document.getElementById("cabinet-max-target").value.trim() || null,
      }),
    });
    await refreshCabinet();
  } catch (err) {
    setCabinetMessage(String(err));
  }
});

document.getElementById("cabinet-max-off-btn").addEventListener("click", async () => {
  try {
    await api("/v1/cabinet/subscriptions/channel", {
      method: "POST",
      body: JSON.stringify({
        channel_type: "max",
        enabled: false,
        target: document.getElementById("cabinet-max-target").value.trim() || null,
      }),
    });
    await refreshCabinet();
  } catch (err) {
    setCabinetMessage(String(err));
  }
});

document.getElementById("cabinet-watch-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    const minScoreRaw = document.getElementById("cabinet-watch-min-score").value.trim();
    const maxPriceRaw = document.getElementById("cabinet-watch-max-price").value.trim();
    await api("/v1/cabinet/watch-rules", {
      method: "POST",
      body: JSON.stringify({
        query: document.getElementById("cabinet-watch-query").value.trim(),
        tlds: csvToList(document.getElementById("cabinet-watch-tlds").value),
        min_score: minScoreRaw ? Number(minScoreRaw) : null,
        max_price_usd: maxPriceRaw ? Number(maxPriceRaw) : null,
      }),
    });
    document.getElementById("cabinet-watch-query").value = "";
    document.getElementById("cabinet-watch-tlds").value = "";
    document.getElementById("cabinet-watch-min-score").value = "";
    document.getElementById("cabinet-watch-max-price").value = "";
    await refreshCabinet();
  } catch (err) {
    setCabinetMessage(String(err));
  }
});

document.getElementById("cabinet-watch-list").addEventListener("click", async (e) => {
  const target = e.target;
  if (!(target instanceof HTMLElement)) return;
  if (!target.classList.contains("js-watch-action")) return;

  const ruleId = target.dataset.ruleId;
  const status = target.dataset.action;
  if (!ruleId || !status) return;

  try {
    await api(`/v1/cabinet/watch-rules/${ruleId}/status`, {
      method: "POST",
      body: JSON.stringify({ status }),
    });
    await refreshCabinet();
  } catch (err) {
    setCabinetMessage(String(err));
  }
});

document.getElementById("cabinet-watch-list").addEventListener("click", async (e) => {
  const target = e.target;
  if (!(target instanceof HTMLElement)) return;
  if (!target.classList.contains("js-watch-save")) return;

  const ruleId = target.dataset.ruleId;
  if (!ruleId) return;

  const queryEl = document.querySelector(`input[data-rule-field="query"][data-rule-id="${ruleId}"]`);
  const tldsEl = document.querySelector(`input[data-rule-field="tlds"][data-rule-id="${ruleId}"]`);
  const minScoreEl = document.querySelector(`input[data-rule-field="min_score"][data-rule-id="${ruleId}"]`);
  const maxPriceEl = document.querySelector(`input[data-rule-field="max_price_usd"][data-rule-id="${ruleId}"]`);
  if (!(queryEl instanceof HTMLInputElement)) return;
  if (!(tldsEl instanceof HTMLInputElement)) return;
  if (!(minScoreEl instanceof HTMLInputElement)) return;
  if (!(maxPriceEl instanceof HTMLInputElement)) return;

  const payload = {
    query: queryEl.value.trim(),
    tlds: csvToList(tldsEl.value),
    min_score: minScoreEl.value.trim() ? Number(minScoreEl.value.trim()) : null,
    max_price_usd: maxPriceEl.value.trim() ? Number(maxPriceEl.value.trim()) : null,
  };

  try {
    await api(`/v1/cabinet/watch-rules/${ruleId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
    await refreshCabinet();
  } catch (err) {
    setCabinetMessage(String(err));
  }
});

document.getElementById("cabinet-watch-search").addEventListener("input", () => {
  if (cabinetRefreshTimer) clearTimeout(cabinetRefreshTimer);
  cabinetRefreshTimer = setTimeout(() => {
    refreshCabinet();
  }, 250);
});

document.getElementById("cabinet-watch-status-filter").addEventListener("change", () => {
  refreshCabinet();
});

document.getElementById("cabinet-history-apply-btn").addEventListener("click", () => {
  refreshCabinet();
});

applyTheme(currentTheme);
applyLanguage(currentLang);
setupMenu();
setupSorting();
initTelegramAuthWidget();
initMaxAuth();
refreshAuth();
refreshHealth();
refreshActivity();
refreshCabinet();
setInterval(refreshHealth, 30000);
setInterval(refreshActivity, 45000);
