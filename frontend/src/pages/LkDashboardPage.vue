<template>
  <section class="page-card">
    <h2>Дашборд доменов</h2>

    <p v-if="error" class="error">{{ error }}</p>
    <p v-if="loading">Загрузка...</p>

    <div class="kpi-grid" v-if="!loading">
      <article class="kpi"><p>watch-правил активных</p><h3>{{ watchActive }}</h3></article>
      <article class="kpi"><p>каналов алертов ON</p><h3>{{ alertsChannels }}</h3></article>
      <article class="kpi"><p>событий в истории</p><h3>{{ historyItems.length }}</h3></article>
      <article class="kpi"><p>режим admin</p><h3>{{ isAdmin ? 'ON' : 'OFF' }}</h3></article>
    </div>

    <div class="split" v-if="!loading">
      <article class="panel">
        <h3>Статусы watch-правил</h3>
        <div class="status-list">
          <div class="status-row">
            <span>active</span>
            <strong>{{ statusCounts.active }}</strong>
          </div>
          <div class="status-row">
            <span>paused</span>
            <strong>{{ statusCounts.paused }}</strong>
          </div>
          <div class="status-row">
            <span>deleted</span>
            <strong>{{ statusCounts.deleted }}</strong>
          </div>
        </div>
      </article>

      <article class="panel">
        <h3>Последние события</h3>
        <table>
          <thead>
            <tr><th>event_type</th><th>created_at</th></tr>
          </thead>
          <tbody>
            <tr v-for="item in historyItems.slice(0, 8)" :key="`${item.created_at}_${item.event_type}`">
              <td>{{ item.event_type }}</td>
              <td>{{ item.created_at }}</td>
            </tr>
            <tr v-if="historyItems.length === 0">
              <td colspan="2">Пусто</td>
            </tr>
          </tbody>
        </table>
      </article>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { apiRequest } from '@/services/api';

type Profile = {
  watch_rules_active?: number;
  capabilities?: Record<string, boolean>;
  is_admin?: boolean;
};
type WatchRule = { status?: string };
type SubItem = { status?: string };
type HistoryItem = { event_type: string; created_at: string };

const loading = ref(true);
const error = ref('');
const profile = ref<Profile>({});
const watchRules = ref<WatchRule[]>([]);
const subscriptions = ref<SubItem[]>([]);
const historyItems = ref<HistoryItem[]>([]);

const watchActive = computed(() => profile.value.watch_rules_active || 0);
const isAdmin = computed(() => Boolean(profile.value.capabilities?.admin_panel_read || profile.value.is_admin));
const alertsChannels = computed(
  () => subscriptions.value.filter((x) => String(x.status || '').toLowerCase() === 'active').length,
);

const statusCounts = computed(() => {
  const acc = { active: 0, paused: 0, deleted: 0 };
  for (const item of watchRules.value) {
    const status = String(item.status || '').toLowerCase();
    if (status === 'active' || status === 'paused' || status === 'deleted') {
      acc[status] += 1;
    }
  }
  return acc;
});

onMounted(async () => {
  try {
    const [profileData, subscriptionsData, watchRulesData, historyData] = await Promise.all([
      apiRequest<Profile>('/v1/cabinet/profile'),
      apiRequest<{ items: SubItem[] }>('/v1/cabinet/subscriptions'),
      apiRequest<{ items: WatchRule[] }>('/v1/cabinet/watch-rules'),
      apiRequest<{ items: HistoryItem[] }>('/v1/cabinet/history?limit=20'),
    ]);
    profile.value = profileData;
    subscriptions.value = subscriptionsData.items || [];
    watchRules.value = watchRulesData.items || [];
    historyItems.value = historyData.items || [];
  } catch (e) {
    error.value = String(e);
  } finally {
    loading.value = false;
  }
});
</script>

<style scoped>
.error { color: #b42318; margin-bottom: 8px; }
.split { display: grid; grid-template-columns: 1fr 1.5fr; gap: 12px; margin-top: 12px; }
.panel { border: 1px solid var(--line); border-radius: 12px; padding: 12px; background: var(--surface-2); }
.panel h3 { margin: 0 0 10px; font-size: 20px; }
.status-list { display: grid; gap: 8px; }
.status-row { display: flex; justify-content: space-between; border: 1px solid var(--line); border-radius: 8px; padding: 8px; }
table { width: 100%; border-collapse: collapse; }
th, td { border: 1px solid var(--line); padding: 8px; text-align: left; }
@media (max-width: 1200px) { .split { grid-template-columns: 1fr; } }
</style>
