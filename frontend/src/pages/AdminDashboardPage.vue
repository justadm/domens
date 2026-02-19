<template>
  <section class="page-card">
    <h2>Общая статистика</h2>
    <p v-if="error" class="error">{{ error }}</p>

    <div class="kpi-grid" v-if="!loading && stats">
      <article class="kpi"><p>пользователей всего</p><h3>{{ stats.users_total ?? 0 }}</h3></article>
      <article class="kpi"><p>зарегистрированных</p><h3>{{ stats.users_registered ?? 0 }}</h3></article>
      <article class="kpi"><p>watch-правил</p><h3>{{ stats.watch_rules_total ?? 0 }}</h3></article>
      <article class="kpi"><p>bot events</p><h3>{{ stats.bot_events_total ?? 0 }}</h3></article>
      <article class="kpi"><p>регистраций доменов</p><h3>{{ stats.registration_orders_total ?? 0 }}</h3></article>
      <article class="kpi"><p>успешных регистраций</p><h3>{{ stats.registration_orders_completed ?? 0 }}</h3></article>
      <article class="kpi"><p>магазинов (external)</p><h3>{{ stats.stores_total ?? 0 }}</h3></article>
      <article class="kpi"><p>товаров (external)</p><h3>{{ stats.products_total ?? 0 }}</h3></article>
    </div>

    <p v-else-if="loading">Загрузка...</p>

    <div class="split" v-if="!loading">
      <article class="panel">
        <h3>Последние пользователи</h3>
        <table>
          <thead>
            <tr><th>user_id</th><th>username</th><th>events</th></tr>
          </thead>
          <tbody>
            <tr v-for="u in users.items" :key="u.telegram_user_id">
              <td>{{ u.telegram_user_id }}</td>
              <td>{{ u.username ? `@${u.username}` : '-' }}</td>
              <td>{{ u.events_total ?? 0 }}</td>
            </tr>
            <tr v-if="users.items.length === 0"><td colspan="3">Пусто</td></tr>
          </tbody>
        </table>
      </article>

      <article class="panel">
        <h3>Последние события</h3>
        <table>
          <thead>
            <tr><th>created_at</th><th>event_type</th><th>user_id</th></tr>
          </thead>
          <tbody>
            <tr v-for="e in events.items" :key="`${e.created_at}_${e.event_type}_${e.telegram_user_id || '-'}`">
              <td>{{ e.created_at }}</td>
              <td>{{ e.event_type }}</td>
              <td>{{ e.telegram_user_id || '-' }}</td>
            </tr>
            <tr v-if="events.items.length === 0"><td colspan="3">Пусто</td></tr>
          </tbody>
        </table>
      </article>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { apiRequest } from '@/services/api';

type DashboardResp = { stats: Record<string, number | null> };
type UsersPage = {
  items: Array<{ telegram_user_id: string; username?: string | null; events_total?: number }>;
};
type EventsPage = {
  items: Array<{ created_at: string; event_type: string; telegram_user_id?: string | null }>;
};

const loading = ref(true);
const error = ref('');
const stats = ref<Record<string, number | null> | null>(null);
const users = ref<UsersPage>({ items: [] });
const events = ref<EventsPage>({ items: [] });

onMounted(async () => {
  try {
    const [dashboardData, usersData, eventsData] = await Promise.all([
      apiRequest<DashboardResp>('/v1/admin/dashboard'),
      apiRequest<UsersPage>('/v1/admin/users-activity?limit=8&offset=0'),
      apiRequest<EventsPage>('/v1/admin/bot-events?limit=8&offset=0'),
    ]);
    stats.value = dashboardData.stats;
    users.value = usersData;
    events.value = eventsData;
  } catch (e) {
    error.value = String(e);
  } finally {
    loading.value = false;
  }
});
</script>

<style scoped>
.error { color: #b42318; margin-bottom: 8px; }
.split { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-top: 12px; }
.panel { border: 1px solid var(--line); border-radius: 12px; padding: 12px; background: var(--surface-2); }
.panel h3 { margin: 0 0 10px; font-size: 20px; }
table { width: 100%; border-collapse: collapse; }
th, td { border: 1px solid var(--line); padding: 8px; text-align: left; }
@media (max-width: 1200px) { .split { grid-template-columns: 1fr; } }
</style>
