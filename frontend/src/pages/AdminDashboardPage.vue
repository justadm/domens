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

    <div class="kpi-grid quality-grid" v-if="!loading && quality">
      <article class="kpi"><p>Alerts 7d</p><h3>{{ quality.alerts_total }}</h3></article>
      <article class="kpi"><p>Feedback 7d</p><h3>{{ quality.feedback_total }}</h3></article>
      <article class="kpi"><p>Positive feedback 7d</p><h3>{{ formatRate(quality.feedback_ratios.positive_rate) }}</h3></article>
      <article class="kpi"><p>Negative feedback 7d</p><h3>{{ formatRate(quality.feedback_ratios.negative_rate) }}</h3></article>
      <article class="kpi"><p>Why clicked 7d</p><h3>{{ quality.feedback_ratios.why }}</h3></article>
      <article class="kpi"><p>Suppressed 7d</p><h3>{{ quality.suppressed_total }}</h3></article>
      <article class="kpi"><p>Monitor runs 7d</p><h3>{{ quality.monitor_runs_total }}</h3></article>
      <article class="kpi"><p>Checked 7d</p><h3>{{ quality.monitor_checked_total }}</h3></article>
      <article class="kpi"><p>Monitor alerts 7d</p><h3>{{ quality.monitor_alerts_sent }}</h3></article>
      <article class="kpi"><p>Digests 7d</p><h3>{{ quality.monitor_digests_sent }}</h3></article>
      <article class="kpi"><p>Duplicate groups 7d</p><h3>{{ quality.monitor_duplicate_alert_groups_total }}</h3></article>
      <article class="kpi"><p>Telegram errors 7d</p><h3>{{ quality.telegram_errors_total }}</h3></article>
      <article class="kpi"><p>Registration</p><h3>{{ quality.registration_enabled ? 'ON' : 'OFF' }}</h3></article>
      <article class="kpi"><p>Radar mode</p><h3>{{ radarMode }}</h3></article>
      <article class="kpi"><p>Target cooldown</p><h3>{{ quality.monitor_alert_target_cooldown_minutes }}m</h3></article>
    </div>

    <article class="panel quality-panel" v-if="!loading && quality">
      <h3>Feedback distribution</h3>
      <table>
        <thead>
          <tr><th>signal</th><th>count</th><th>share</th></tr>
        </thead>
        <tbody>
          <tr v-for="item in feedbackDistribution" :key="item.key">
            <td>{{ item.label }}</td>
            <td>{{ item.count }}</td>
            <td>{{ item.share }}</td>
          </tr>
          <tr v-if="quality.feedback_ratios.total === 0"><td colspan="3">Пусто</td></tr>
        </tbody>
      </table>
    </article>

    <article class="panel quality-panel" v-if="!loading && quality">
      <h3>Canary skip reasons</h3>
      <table>
        <thead>
          <tr><th>reason</th><th>count</th></tr>
        </thead>
        <tbody>
          <tr v-for="[reason, count] in skipReasons" :key="reason">
            <td>{{ reason }}</td>
            <td>{{ count }}</td>
          </tr>
          <tr v-if="skipReasons.length === 0"><td colspan="2">Пусто</td></tr>
        </tbody>
      </table>
    </article>

    <article class="panel quality-panel" v-if="!loading && quality">
      <h3>Same-domain duplicate groups</h3>
      <table>
        <thead>
          <tr><th>destination</th><th>fqdn</th><th>count</th><th>first</th><th>last</th></tr>
        </thead>
        <tbody>
          <tr v-for="item in quality.monitor_duplicate_alert_groups" :key="`${item.destination}:${item.fqdn}`">
            <td>{{ item.destination }}</td>
            <td>{{ item.fqdn }}</td>
            <td>{{ item.count }}</td>
            <td>{{ item.first_sent_at || '-' }}</td>
            <td>{{ item.last_sent_at || '-' }}</td>
          </tr>
          <tr v-if="quality.monitor_duplicate_alert_groups.length === 0"><td colspan="5">Пусто</td></tr>
        </tbody>
      </table>
    </article>

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
import { computed, onMounted, ref } from 'vue';
import { apiRequest } from '@/services/api';

type DashboardResp = { stats: Record<string, number | null> };
type QualityResp = {
  days: number;
  alerts_total: number;
  feedback_total: number;
  feedback_ratios: {
    more: number;
    less: number;
    never: number;
    why: number;
    positive_rate: number;
    negative_rate: number;
    total: number;
  };
  suppressed_total: number;
  monitor_runs_total: number;
  monitor_alerts_sent: number;
  monitor_digests_sent: number;
  monitor_checked_total: number;
  monitor_skip_reasons: Record<string, number>;
  monitor_duplicate_alert_groups: Array<{
    destination: string;
    fqdn: string;
    count: number;
    first_sent_at?: string | null;
    last_sent_at?: string | null;
  }>;
  monitor_duplicate_alert_groups_total: number;
  telegram_errors_total: number;
  registration_enabled: boolean;
  monitor_enabled: boolean;
  monitor_watchlist_only: boolean;
  monitor_admin_fanout_enabled: boolean;
  monitor_alert_target_cooldown_minutes: number;
};
type UsersPage = {
  items: Array<{ telegram_user_id: string; username?: string | null; events_total?: number }>;
};
type EventsPage = {
  items: Array<{ created_at: string; event_type: string; telegram_user_id?: string | null }>;
};

const loading = ref(true);
const error = ref('');
const stats = ref<Record<string, number | null> | null>(null);
const quality = ref<QualityResp | null>(null);
const users = ref<UsersPage>({ items: [] });
const events = ref<EventsPage>({ items: [] });
const skipReasons = computed(() =>
  Object.entries(quality.value?.monitor_skip_reasons || {}).sort((a, b) => b[1] - a[1]),
);
const formatRate = (value: number) => `${Math.round(Number(value || 0) * 100)}%`;
const feedbackDistribution = computed(() => {
  const ratios = quality.value?.feedback_ratios;
  const total = ratios?.total || 0;
  if (!ratios || total === 0) return [];
  return [
    { key: 'more', label: 'More like this', count: ratios.more },
    { key: 'less', label: 'Less like this', count: ratios.less },
    { key: 'never', label: 'Never repeat', count: ratios.never },
    { key: 'why', label: 'Why clicked', count: ratios.why },
  ].map((item) => ({
    ...item,
    share: formatRate(item.count / total),
  }));
});
const radarMode = computed(() => {
  if (!quality.value?.monitor_enabled) return 'OFF';
  if (quality.value.monitor_watchlist_only && !quality.value.monitor_admin_fanout_enabled) return 'canary';
  return 'wide';
});

onMounted(async () => {
  try {
    const [dashboardData, qualityData, usersData, eventsData] = await Promise.all([
      apiRequest<DashboardResp>('/v1/admin/dashboard'),
      apiRequest<QualityResp>('/v1/admin/quality?days=7'),
      apiRequest<UsersPage>('/v1/admin/users-activity?limit=8&offset=0'),
      apiRequest<EventsPage>('/v1/admin/bot-events?limit=8&offset=0'),
    ]);
    stats.value = dashboardData.stats;
    quality.value = qualityData;
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
.quality-grid { margin-top: 12px; }
.quality-panel { margin-top: 12px; }
.split { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-top: 12px; }
.panel { border: 1px solid var(--line); border-radius: 12px; padding: 12px; background: var(--surface-2); }
.panel h3 { margin: 0 0 10px; font-size: 20px; }
table { width: 100%; border-collapse: collapse; }
th, td { border: 1px solid var(--line); padding: 8px; text-align: left; }
@media (max-width: 1200px) { .split { grid-template-columns: 1fr; } }
</style>
