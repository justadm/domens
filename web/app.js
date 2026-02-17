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
    auth_login_hint: "Вход через Telegram",
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
    auth_login_hint: "Sign in with Telegram",
  },
};

let currentLang = localStorage.getItem("domens_lang") || "ru";
let currentTheme = localStorage.getItem("domens_theme") || "dark";
let lastResults = [];
let sortState = { key: "domain", dir: "asc" };

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

function put(el, data) {
  el.textContent = JSON.stringify(data, null, 2);
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

function renderAuthState(authenticated, user) {
  const dict = I18N[currentLang];
  const userLine = document.getElementById("auth-user-line");
  const logoutBtn = document.getElementById("logout-btn");
  const widgetRoot = document.getElementById("tg-auth-widget");

  if (!userLine || !logoutBtn || !widgetRoot) {
    return;
  }

  if (authenticated && user) {
    const username = user.username ? `@${user.username}` : user.first_name || user.telegram_user_id;
    userLine.textContent = `${dict.auth_logged_as} ${username}`;
    logoutBtn.classList.remove("hidden");
    widgetRoot.classList.add("hidden");
    return;
  }

  userLine.textContent = `${dict.auth_guest}. ${dict.auth_login_hint}`;
  logoutBtn.classList.add("hidden");
  widgetRoot.classList.remove("hidden");
}

async function refreshAuth() {
  try {
    const data = await api("/v1/auth/me");
    renderAuthState(Boolean(data.authenticated), data.user || null);
  } catch {
    renderAuthState(false, null);
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

applyTheme(currentTheme);
applyLanguage(currentLang);
setupMenu();
setupSorting();
initTelegramAuthWidget();
refreshAuth();
refreshHealth();
refreshActivity();
setInterval(refreshHealth, 30000);
setInterval(refreshActivity, 45000);
