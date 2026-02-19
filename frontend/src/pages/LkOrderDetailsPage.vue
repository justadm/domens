<template>
  <section class="page-card">
    <div class="header">
      <h2>Заказ: {{ item?.id || route.params.id }}</h2>
      <div class="actions">
        <button class="btn" :disabled="loadingAction || isTerminal" @click="executeOrder">Execute</button>
        <button class="btn btn-danger" :disabled="loadingAction || isTerminal" @click="cancelOrder">Cancel</button>
        <button class="btn btn-ghost" @click="goBack">Назад</button>
      </div>
    </div>

    <p v-if="error" class="error">{{ error }}</p>
    <p v-if="actionMessage" class="ok">{{ actionMessage }}</p>
    <p v-if="loading">Загрузка...</p>

    <div v-if="item && !loading" class="meta-grid">
      <article class="kpi"><p>Статус</p><h3>{{ item.status }}</h3></article>
      <article class="kpi"><p>Домен</p><h3>{{ item.domain }}</h3></article>
      <article class="kpi"><p>Requested by</p><h3>{{ item.requested_by || '-' }}</h3></article>
      <article class="kpi"><p>Completed</p><h3>{{ item.completed_at || '-' }}</h3></article>
    </div>

    <div class="split" v-if="item && !loading">
      <article class="panel">
        <h3>Детали заказа</h3>
        <table>
          <tbody>
            <tr><th>id</th><td>{{ item.id }}</td></tr>
            <tr><th>domain</th><td><RouterLink :to="`/lk/domens/${item.domain_id}`">{{ item.domain }}</RouterLink></td></tr>
            <tr><th>status</th><td>{{ item.status }}</td></tr>
            <tr><th>error_message</th><td>{{ item.error_message || '-' }}</td></tr>
            <tr><th>created_at</th><td>{{ item.created_at }}</td></tr>
            <tr><th>updated_at</th><td>{{ item.updated_at }}</td></tr>
          </tbody>
        </table>
      </article>

      <article class="panel">
        <h3>Снимок домена</h3>
        <table>
          <tbody>
            <tr><th>status</th><td>{{ item.domain_snapshot?.current_status || '-' }}</td></tr>
            <tr><th>score</th><td>{{ item.domain_snapshot?.score ?? '-' }}</td></tr>
            <tr><th>eta_drop</th><td>{{ item.domain_snapshot?.drop_time_estimated_at || '-' }}</td></tr>
            <tr><th>updated_at</th><td>{{ item.domain_snapshot?.updated_at || '-' }}</td></tr>
          </tbody>
        </table>
      </article>
    </div>

    <article class="panel" v-if="item && !loading">
      <h3>История событий по заказу</h3>
      <table>
        <thead><tr><th>created_at</th><th>event_type</th><th>payload</th></tr></thead>
        <tbody>
          <tr v-for="event in item.events || []" :key="event.id">
            <td>{{ event.created_at }}</td>
            <td>{{ event.event_type }}</td>
            <td><pre>{{ JSON.stringify(event.payload || {}, null, 2) }}</pre></td>
          </tr>
          <tr v-if="(item.events || []).length === 0"><td colspan="3">Пусто</td></tr>
        </tbody>
      </table>
    </article>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { RouterLink, useRoute, useRouter } from 'vue-router';
import { apiRequest } from '@/services/api';

type OrderDetails = {
  id: string;
  domain_id: string;
  domain: string;
  status: string;
  requested_by?: string | null;
  error_message?: string | null;
  created_at: string;
  updated_at: string;
  completed_at?: string | null;
  domain_snapshot?: {
    current_status?: string;
    score?: number | null;
    drop_time_estimated_at?: string | null;
    updated_at?: string | null;
  };
  events?: Array<{ id: string; event_type: string; payload?: Record<string, unknown>; created_at: string }>;
};

const route = useRoute();
const router = useRouter();

const loading = ref(true);
const loadingAction = ref(false);
const error = ref('');
const actionMessage = ref('');
const item = ref<OrderDetails | null>(null);

const isTerminal = computed(() => {
  const status = String(item.value?.status || '').toLowerCase();
  return status === 'registered' || status === 'failed' || status === 'canceled';
});

async function load() {
  loading.value = true;
  error.value = '';
  try {
    const id = String(route.params.id || '');
    const data = await apiRequest<{ item: OrderDetails }>(`/v1/cabinet/orders/${id}`);
    item.value = data.item;
  } catch (e) {
    error.value = String(e);
  } finally {
    loading.value = false;
  }
}

async function executeOrder() {
  loadingAction.value = true;
  error.value = '';
  actionMessage.value = '';
  try {
    const id = String(route.params.id || '');
    const res = await apiRequest<{ status: string }>(`/v1/cabinet/orders/${id}/execute`, { method: 'POST' });
    actionMessage.value = `Execute: ${res.status}`;
    await load();
  } catch (e) {
    error.value = String(e);
  } finally {
    loadingAction.value = false;
  }
}

async function cancelOrder() {
  loadingAction.value = true;
  error.value = '';
  actionMessage.value = '';
  try {
    const id = String(route.params.id || '');
    const res = await apiRequest<{ status: string }>(`/v1/cabinet/orders/${id}/cancel`, { method: 'POST' });
    actionMessage.value = `Cancel: ${res.status}`;
    await load();
  } catch (e) {
    error.value = String(e);
  } finally {
    loadingAction.value = false;
  }
}

function goBack() {
  router.push('/lk/orders');
}

onMounted(load);
</script>

<style scoped>
.header { display: flex; justify-content: space-between; gap: 10px; align-items: center; margin-bottom: 10px; }
.actions { display: flex; gap: 8px; }
.meta-grid { display: grid; gap: 10px; grid-template-columns: repeat(4, minmax(0, 1fr)); margin-bottom: 12px; }
.kpi { border: 1px solid var(--line); border-radius: 10px; background: var(--surface-2); padding: 10px; }
.kpi p { margin: 0 0 8px; color: var(--muted); }
.kpi h3 { margin: 0; font-size: 24px; }
.split { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 12px; }
.panel { border: 1px solid var(--line); border-radius: 12px; background: var(--surface-2); padding: 12px; }
.panel h3 { margin: 0 0 10px; font-size: 20px; }
table { width: 100%; border-collapse: collapse; }
th, td { border: 1px solid var(--line); padding: 8px; text-align: left; vertical-align: top; }
pre { margin: 0; max-width: 800px; overflow: auto; }
.error { color: #b42318; margin-bottom: 8px; }
.ok { color: #067647; margin-bottom: 8px; }
.btn-ghost { background: transparent; border: 1px solid var(--line); }
.btn-danger { background: #b42318; color: #fff; }
@media (max-width: 1200px) {
  .meta-grid { grid-template-columns: 1fr 1fr; }
  .split { grid-template-columns: 1fr; }
}
</style>
