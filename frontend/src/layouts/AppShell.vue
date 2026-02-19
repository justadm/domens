<template>
  <div class="shell">
    <aside class="sidebar">
      <a class="brand" href="/lk">
        <span class="brand-mark"></span>
        <span>Domens Portal</span>
      </a>
      <div class="user-card">
        <div class="avatar">{{ initials }}</div>
        <div>
          <div class="name">{{ displayName }}</div>
          <small>{{ auth.authenticated ? 'Авторизован' : 'Гость' }}</small>
        </div>
      </div>
      <nav class="menu">
        <RouterLink v-for="item in auth.menu" :key="item.key" :to="item.to" class="menu-item" active-class="active">
          {{ item.label }}
        </RouterLink>
      </nav>
    </aside>

    <div class="main">
      <header class="topbar">
        <div>
          <h1>{{ title }}</h1>
          <p>Единый интерфейс. Отличия только в правах и наполнении.</p>
        </div>
        <button class="btn" @click="onLogout">Выйти</button>
      </header>
      <main class="content">
        <RouterView />
      </main>
      <footer class="footer">
        <span>Domens Radar</span>
        <span>Unified Frontend</span>
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

async function onLogout() {
  await auth.logout();
  await router.push('/');
}
</script>

<style scoped>
.shell {
  min-height: 100vh;
  display: grid;
  grid-template-columns: 280px 1fr;
}

.sidebar {
  border-right: 1px solid var(--line);
  background: var(--surface);
  padding: 12px;
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  border: 1px solid var(--line);
  border-radius: 10px;
  padding: 10px;
  font-size: 26px;
  font-weight: 800;
}

.brand-mark {
  width: 12px;
  height: 12px;
  border-radius: 4px;
  background: linear-gradient(135deg, #66a9ff 0%, #2f78f4 100%);
}

.user-card {
  margin-top: 10px;
  border: 1px solid var(--line);
  border-radius: 10px;
  background: var(--surface-2);
  padding: 10px;
  display: grid;
  grid-template-columns: 40px 1fr;
  gap: 10px;
  align-items: center;
}

.avatar {
  width: 40px;
  height: 40px;
  border-radius: 999px;
  display: grid;
  place-items: center;
  color: #fff;
  font-weight: 800;
  background: linear-gradient(135deg, var(--brand-2), #73a6f3);
}

.name {
  font-weight: 700;
}

.user-card small {
  color: var(--muted);
}

.menu {
  margin-top: 10px;
  display: grid;
  gap: 8px;
}

.menu-item {
  border: 1px solid var(--line);
  border-radius: 10px;
  background: #fff;
  padding: 10px;
  font-weight: 600;
}

.menu-item.active {
  color: #1d4f9a;
  background: rgba(58, 120, 220, 0.12);
  border-color: rgba(58, 120, 220, 0.45);
}

.topbar {
  padding: 18px;
  color: #fff;
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: start;
  background: linear-gradient(110deg, var(--brand) 0%, #2b5ca8 50%, #3365b0 100%);
}

.topbar h1 {
  margin: 0;
  font-size: 36px;
  letter-spacing: -0.02em;
}

.topbar p {
  margin: 8px 0 0;
  opacity: 0.9;
}

.content {
  padding: 16px;
}

.footer {
  border-top: 1px solid var(--line);
  height: 42px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  color: var(--muted);
  padding: 0 14px;
  background: var(--surface);
}

@media (max-width: 1000px) {
  .shell {
    grid-template-columns: 1fr;
  }
}
</style>
