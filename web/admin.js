let clientsOffset = 0;
let eventsOffset = 0;
let clientsPage = { total: 0, limit: 50, offset: 0, next_offset: null, prev_offset: null, items: [] };
let eventsPage = { total: 0, limit: 50, offset: 0, next_offset: null, prev_offset: null, items: [] };

async function api(path) {
  const res = await fetch(path, {
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
  });
  const text = await res.text();
  let body = {};
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

function esc(v) {
  return String(v ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function dt(v) {
  if (!v) return "-";
  try {
    return new Date(v).toLocaleString("ru-RU");
  } catch {
    return String(v);
  }
}

function setPage(page) {
  document.querySelectorAll(".page").forEach((el) => el.classList.add("hidden"));
  const target = document.getElementById(`page-${page}`);
  if (target) target.classList.remove("hidden");
  document.querySelectorAll(".nav-btn").forEach((el) => {
    el.classList.toggle("active", el.dataset.page === page);
  });
}

async function loadAuth() {
  const line = document.getElementById("auth-line");
  const me = await api("/v1/auth/me");
  if (!me.authenticated || !me.user) {
    line.textContent = "Нет авторизации. Войди через основной интерфейс.";
    throw new Error("unauthorized");
  }
  const canAdmin = Boolean(me.user?.capabilities?.admin_panel_read || me.user?.is_admin);
  if (!canAdmin) {
    line.textContent = `Недостаточно прав: ${me.user.telegram_user_id}`;
    throw new Error("forbidden");
  }
  line.textContent = `Админ: @${me.user.username || me.user.telegram_user_id}`;
}

async function loadDashboard() {
  const out = document.getElementById("dashboard-stats");
  const raw = document.getElementById("dashboard-raw");
  const data = await api("/v1/admin/dashboard");
  const stats = data.stats || {};
  const cards = [
    ["Всего пользователей", stats.users_total],
    ["Зарегистрированные", stats.users_registered],
    ["Активные", stats.users_active],
    ["С watch-правилами", stats.users_with_watch_rules],
    ["Watch-правил всего", stats.watch_rules_total],
    ["Watch-правил активных", stats.watch_rules_active],
    ["Доменов", stats.domains_total],
    ["Алертов", stats.alerts_total],
    ["Заказов регистрации", stats.registration_orders_total],
    ["Bot events", stats.bot_events_total],
    ["Access events", stats.access_events_total],
    ["Copilot events", stats.copilot_events_total],
    ["Conversations", stats.conversations_total],
    ["Магазинов", stats.stores_total ?? "N/A"],
    ["Товаров", stats.products_total ?? "N/A"],
    ["Ecom-заказов", stats.ecommerce_orders_total ?? "N/A"],
  ];
  out.innerHTML = cards
    .map(([k, v]) => `<article class="card"><div class="k">${esc(k)}</div><div class="v">${esc(v)}</div></article>`)
    .join("");
  raw.textContent = JSON.stringify(stats, null, 2);
}

function renderClients() {
  const root = document.getElementById("clients-table");
  const page = document.getElementById("clients-page");
  const prev = document.getElementById("clients-prev");
  const next = document.getElementById("clients-next");
  prev.disabled = clientsPage.prev_offset === null || clientsPage.prev_offset === undefined;
  next.disabled = clientsPage.next_offset === null || clientsPage.next_offset === undefined;
  const from = clientsPage.total ? clientsPage.offset + 1 : 0;
  const to = Math.min(clientsPage.offset + clientsPage.limit, clientsPage.total);
  page.textContent = `${from}-${to} из ${clientsPage.total}`;
  root.innerHTML = `
    <table>
      <thead><tr><th>user_id</th><th>username</th><th>registered</th><th>roles</th><th>permissions</th><th>events</th><th>last_event</th></tr></thead>
      <tbody>
        ${(clientsPage.items || [])
          .map(
            (x) => `
              <tr>
                <td>${esc(x.telegram_user_id)}</td>
                <td>${esc(x.username ? `@${x.username}` : "-")}</td>
                <td>${esc(x.is_registered ? "yes" : "no")}</td>
                <td>${esc((x.roles || []).join(", "))}</td>
                <td>${esc((x.permissions || []).join(", "))}</td>
                <td>${esc(x.events_total)}</td>
                <td>${esc(dt(x.last_event_at))}</td>
              </tr>
            `
          )
          .join("")}
      </tbody>
    </table>
  `;
}

async function loadClients() {
  const params = new URLSearchParams();
  const search = document.getElementById("clients-search").value.trim();
  const perm = document.getElementById("clients-permission").value.trim();
  const regOnly = document.getElementById("clients-registered").value === "true";
  const limit = Math.max(1, Math.min(200, Number(document.getElementById("clients-limit").value || 50)));
  params.set("limit", String(limit));
  params.set("offset", String(clientsOffset));
  if (search) params.set("search", search);
  if (perm) params.set("permission_contains", perm);
  if (regOnly) params.set("registered_only", "true");
  clientsPage = await api(`/v1/admin/users-activity?${params.toString()}`);
  clientsOffset = Number(clientsPage.offset || 0);
  renderClients();
}

function renderEvents() {
  const root = document.getElementById("events-table");
  const page = document.getElementById("events-page");
  const prev = document.getElementById("events-prev");
  const next = document.getElementById("events-next");
  prev.disabled = eventsPage.prev_offset === null || eventsPage.prev_offset === undefined;
  next.disabled = eventsPage.next_offset === null || eventsPage.next_offset === undefined;
  const from = eventsPage.total ? eventsPage.offset + 1 : 0;
  const to = Math.min(eventsPage.offset + eventsPage.limit, eventsPage.total);
  page.textContent = `${from}-${to} из ${eventsPage.total}`;
  root.innerHTML = `
    <table>
      <thead><tr><th>created_at</th><th>event_type</th><th>user_id</th><th>username</th><th>chat_id</th><th>payload</th></tr></thead>
      <tbody>
        ${(eventsPage.items || [])
          .map(
            (x) => `
              <tr>
                <td>${esc(dt(x.created_at))}</td>
                <td>${esc(x.event_type)}</td>
                <td>${esc(x.telegram_user_id || "-")}</td>
                <td>${esc(x.username ? `@${x.username}` : "-")}</td>
                <td>${esc(x.telegram_chat_id || "-")}</td>
                <td><pre>${esc(JSON.stringify(x.payload || {}, null, 2))}</pre></td>
              </tr>
            `
          )
          .join("")}
      </tbody>
    </table>
  `;
}

async function loadEvents() {
  const params = new URLSearchParams();
  const type = document.getElementById("events-type").value.trim();
  const uid = document.getElementById("events-user").value.trim();
  const chat = document.getElementById("events-chat").value.trim();
  const search = document.getElementById("events-search").value.trim();
  const limit = Math.max(1, Math.min(300, Number(document.getElementById("events-limit").value || 50)));
  params.set("limit", String(limit));
  params.set("offset", String(eventsOffset));
  if (type) params.set("event_type", type);
  if (uid) params.set("telegram_user_id", uid);
  if (chat) params.set("telegram_chat_id", chat);
  if (search) params.set("search", search);
  eventsPage = await api(`/v1/admin/bot-events?${params.toString()}`);
  eventsOffset = Number(eventsPage.offset || 0);
  renderEvents();
}

function bind() {
  document.querySelectorAll(".nav-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      setPage(btn.dataset.page);
      if (btn.dataset.page === "dashboard") await loadDashboard();
      if (btn.dataset.page === "clients") await loadClients();
      if (btn.dataset.page === "events") await loadEvents();
    });
  });
  document.getElementById("clients-apply").addEventListener("click", async () => {
    clientsOffset = 0;
    await loadClients();
  });
  document.getElementById("clients-prev").addEventListener("click", async () => {
    if (clientsPage.prev_offset === null || clientsPage.prev_offset === undefined) return;
    clientsOffset = Number(clientsPage.prev_offset) || 0;
    await loadClients();
  });
  document.getElementById("clients-next").addEventListener("click", async () => {
    if (clientsPage.next_offset === null || clientsPage.next_offset === undefined) return;
    clientsOffset = Number(clientsPage.next_offset) || 0;
    await loadClients();
  });
  document.getElementById("events-apply").addEventListener("click", async () => {
    eventsOffset = 0;
    await loadEvents();
  });
  document.getElementById("events-prev").addEventListener("click", async () => {
    if (eventsPage.prev_offset === null || eventsPage.prev_offset === undefined) return;
    eventsOffset = Number(eventsPage.prev_offset) || 0;
    await loadEvents();
  });
  document.getElementById("events-next").addEventListener("click", async () => {
    if (eventsPage.next_offset === null || eventsPage.next_offset === undefined) return;
    eventsOffset = Number(eventsPage.next_offset) || 0;
    await loadEvents();
  });
  document.getElementById("link-clients").addEventListener("click", async (e) => {
    e.preventDefault();
    setPage("clients");
    await loadClients();
  });
  document.getElementById("link-events").addEventListener("click", async (e) => {
    e.preventDefault();
    setPage("events");
    await loadEvents();
  });
}

async function init() {
  try {
    bind();
    await loadAuth();
    await loadDashboard();
  } catch (err) {
    document.getElementById("auth-line").textContent = `Ошибка: ${String(err)}`;
  }
}

init();
