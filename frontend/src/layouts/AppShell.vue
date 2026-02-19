<template>
  <div class="spark-shell">
    <aside class="spark-sidebar">
      <a class="spark-brand" href="/lk">
        <span class="spark-brand-icon"></span>
        <span>Domens Portal</span>
      </a>

      <div class="spark-user">
        <div class="spark-avatar">{{ initials }}</div>
        <div class="spark-user-meta">
          <div class="spark-user-name">{{ displayName }}</div>
          <small>{{ auth.authenticated ? 'Авторизован' : 'Гость' }}</small>
        </div>
      </div>

      <nav class="spark-nav">
        <p class="spark-nav-caption">Main</p>
        <RouterLink
          v-for="item in lkItems"
          :key="item.key"
          :to="item.to"
          class="spark-nav-item"
          active-class="active"
        >
          {{ item.label }}
        </RouterLink>

        <template v-if="adminVisible">
          <p class="spark-nav-caption">Admin</p>
          <RouterLink to="/admin" class="spark-nav-item" active-class="active">Админ</RouterLink>
          <RouterLink to="/admin/users" class="spark-nav-sub" active-class="active-sub">Пользователи</RouterLink>
          <RouterLink to="/admin/events" class="spark-nav-sub" active-class="active-sub">События</RouterLink>
        </template>

        <p class="spark-nav-caption">System</p>
        <a class="spark-nav-sub" href="/docs" target="_blank" rel="noreferrer">API Docs</a>
        <a class="spark-nav-sub" href="/v1/auth/me" target="_blank" rel="noreferrer">Session JSON</a>
      </nav>
    </aside>

    <div class="spark-main">
      <header class="spark-topbar">
        <div class="spark-left">
          <button class="spark-icon-btn" aria-label="menu">☰</button>
          <input class="spark-search" placeholder="Search domains, users, events..." />
        </div>
        <div class="spark-right">
          <span class="spark-mode">{{ route.path.startsWith('/admin') ? 'ADMIN' : 'LK' }}</span>
          <button class="btn" @click="onLogout">Выйти</button>
        </div>
      </header>

      <section class="spark-hero">
        <h1>{{ title }}</h1>
        <p>{{ subtitle }}</p>
        <small>{{ breadcrumb }}</small>
      </section>

      <main class="spark-content">
        <div class="spark-content-inner">
          <RouterView />
        </div>
      </main>

      <footer class="spark-footer">
        <span>Domens Radar</span>
        <span>Powered by Spark-like Layout</span>
      </footer>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue';
import { useRoute, useRouter, RouterView, RouterLink } from 'vue-router';
import { useAuthStore } from '@/stores/auth';

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();

onMounted(async () => {
  if (!auth.user) {
    await auth.fetchMe();
  }
});

const displayName = computed(() => {
  const u = auth.user;
  if (!u) return 'Гость';
  return u.username ? `@${u.username}` : u.first_name || u.telegram_user_id;
});

const initials = computed(() => displayName.value.replace('@', '').slice(0, 1).toUpperCase() || 'U');

const title = computed(() => (route.path.startsWith('/admin') ? 'Админ-панель' : 'Личный кабинет'));
const subtitle = computed(() =>
  route.path.startsWith('/admin')
    ? 'Управление пользователями, событиями и доступами.'
    : 'Домены, watch-правила, алерты и заказы в одном интерфейсе.',
);

const breadcrumb = computed(() => {
  if (route.path.startsWith('/admin/users')) return 'Dashboard / Admin / Users';
  if (route.path.startsWith('/admin/events')) return 'Dashboard / Admin / Events';
  if (route.path.startsWith('/admin')) return 'Dashboard / Admin';
  if (route.path.startsWith('/lk/domens/')) return 'Dashboard / LK / Domains / Details';
  if (route.path.startsWith('/lk/orders/')) return 'Dashboard / LK / Orders / Details';
  if (route.path.startsWith('/lk/domens')) return 'Dashboard / LK / Domains';
  if (route.path.startsWith('/lk/orders')) return 'Dashboard / LK / Orders';
  if (route.path.startsWith('/lk/watch')) return 'Dashboard / LK / Watch';
  if (route.path.startsWith('/lk/alerts')) return 'Dashboard / LK / Alerts';
  if (route.path.startsWith('/lk/history')) return 'Dashboard / LK / History';
  return 'Dashboard / LK';
});

const lkItems = computed(() =>
  auth.menu.filter((item) => item.to.startsWith('/lk') && item.key !== 'dashboard').length
    ? auth.menu.filter((item) => item.to.startsWith('/lk'))
    : [{ key: 'dashboard', label: 'Дашборд', to: '/lk' }],
);

const adminVisible = computed(() => auth.hasCapability('admin.panel.read'));

async function onLogout() {
  await auth.logout();
  await router.push('/');
}
</script>

<style scoped>
.spark-shell {
  min-height: 100vh;
  display: grid;
  grid-template-columns: 320px 1fr;
}

.spark-sidebar {
  background: #f6f8fc;
  border-right: 1px solid #dfe5f2;
  padding: 14px;
}

.spark-brand {
  display: flex;
  align-items: center;
  gap: 12px;
  height: 76px;
  border: 1px solid #d6dff1;
  border-radius: 16px;
  background: #fff;
  padding: 0 18px;
  font-size: 22px;
  font-weight: 800;
  color: #1d335a;
}

.spark-brand-icon {
  width: 22px;
  height: 22px;
  border-radius: 7px;
  background: linear-gradient(135deg, #6fb5ff 0%, #2f79f6 100%);
}

.spark-user {
  margin-top: 14px;
  border: 1px solid #d6dff1;
  border-radius: 16px;
  background: #f3f6fc;
  padding: 16px;
  display: grid;
  grid-template-columns: 56px 1fr;
  gap: 14px;
  align-items: center;
}

.spark-avatar {
  width: 56px;
  height: 56px;
  border-radius: 999px;
  display: grid;
  place-items: center;
  color: #fff;
  font-weight: 800;
  font-size: 22px;
  background: linear-gradient(135deg, #5b8fe2, #3f78d8);
}

.spark-user-name {
  font-weight: 700;
  font-size: 18px;
  color: #233a62;
}

.spark-user small {
  color: #7184a2;
  font-size: 16px;
}

.spark-nav {
  margin-top: 14px;
  display: grid;
  gap: 10px;
}

.spark-nav-caption {
  margin: 10px 6px 2px;
  font-size: 14px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: #8da0bf;
  font-weight: 700;
}

.spark-nav-item {
  border: 1px solid #d6dff1;
  border-radius: 14px;
  background: #fff;
  min-height: 56px;
  padding: 0 18px;
  font-weight: 600;
  color: #243a5f;
  display: flex;
  align-items: center;
  font-size: 18px;
}

.spark-nav-sub {
  min-height: 40px;
  border-radius: 10px;
  padding: 0 18px 0 26px;
  color: #536b91;
  display: flex;
  align-items: center;
  font-weight: 600;
  font-size: 16px;
  border: 1px dashed transparent;
}

.spark-nav-item.active {
  color: #255eb1;
  background: rgba(58, 120, 220, 0.12);
  border-color: rgba(58, 120, 220, 0.45);
}

.spark-nav-sub.active-sub {
  border-color: #c9d5ee;
  background: #eef3ff;
}

.spark-main {
  min-width: 0;
  background: #eef2f8;
}

.spark-topbar {
  height: 66px;
  padding: 0 22px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  color: #e8f0ff;
  background: #214889;
}

.spark-left, .spark-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.spark-icon-btn {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.3);
  background: rgba(255, 255, 255, 0.08);
  color: #fff;
  cursor: pointer;
}

.spark-search {
  width: min(520px, 52vw);
  height: 38px;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.22);
  background: rgba(255, 255, 255, 0.1);
  color: #fff;
  padding: 0 12px;
}

.spark-search::placeholder {
  color: rgba(235, 245, 255, 0.7);
}

.spark-mode {
  font-size: 12px;
  letter-spacing: 0.08em;
  font-weight: 700;
  color: #adc5ea;
}

.spark-hero {
  min-height: 118px;
  color: #fff;
  background: #214889;
  padding: 20px 26px;
}

.spark-hero h1 {
  margin: 0;
  font-size: 48px;
  line-height: 1.1;
}

.spark-hero p {
  margin: 8px 0 4px;
  font-size: 18px;
  opacity: 0.95;
}

.spark-hero small {
  color: #aec6ea;
}

.spark-content {
  padding: 16px;
}

.spark-content-inner {
  min-height: calc(100vh - 250px);
  border: 1px solid #d8e1f0;
  border-radius: 18px;
  background: #f7faff;
  padding: 14px;
  overflow: auto;
}

.spark-footer {
  height: 50px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  color: #6f84a7;
  border-top: 1px solid #d8e1f0;
  padding: 0 16px;
  background: #fff;
}

@media (max-width: 1200px) {
  .spark-shell {
    grid-template-columns: 1fr;
  }
  .spark-sidebar {
    border-right: none;
    border-bottom: 1px solid #dfe5f2;
  }
  .spark-brand { font-size: 21px; }
  .spark-user-name { font-size: 18px; }
  .spark-hero h1 {
    font-size: 42px;
  }
}
</style>
