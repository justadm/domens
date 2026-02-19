<template>
  <section class="page-card">
    <div class="header">
      <h2>Домен: {{ item?.fqdn || route.params.id }}</h2>
      <div class="actions">
        <button class="btn" :disabled="loadingAction" @click="recheck">Обновить статус</button>
        <button class="btn btn-ghost" @click="goBack">Назад</button>
      </div>
    </div>

    <p v-if="error" class="error">{{ error }}</p>
    <p v-if="actionMessage" class="ok">{{ actionMessage }}</p>
    <p v-if="loading">Загрузка...</p>

    <div v-if="item && !loading" class="meta-grid">
      <article class="kpi"><p>Текущий статус</p><h3>{{ item.current_status || '-' }}</h3></article>
      <article class="kpi"><p>Score</p><h3>{{ item.score ?? '-' }}</h3></article>
      <article class="kpi"><p>TLD</p><h3>.{{ item.tld || '-' }}</h3></article>
      <article class="kpi"><p>ETA drop</p><h3>{{ item.drop_time_estimated_at || '-' }}</h3></article>
    </div>

    <div class="split" v-if="item && !loading">
      <article class="panel">
        <h3>Свойства</h3>
        <table>
          <tbody>
            <tr><th>id</th><td>{{ item.id }}</td></tr>
            <tr><th>sld</th><td>{{ item.sld }}</td></tr>
            <tr><th>source</th><td>{{ item.source || '-' }}</td></tr>
            <tr><th>status_checked_at</th><td>{{ item.status_checked_at || '-' }}</td></tr>
            <tr><th>created_at</th><td>{{ item.created_at }}</td></tr>
            <tr><th>updated_at</th><td>{{ item.updated_at }}</td></tr>
          </tbody>
        </table>
      </article>

      <article class="panel">
        <h3>Заказы по домену</h3>
        <table>
          <thead><tr><th>order_id</th><th>status</th><th>created</th></tr></thead>
          <tbody>
            <tr v-for="order in item.orders || []" :key="order.id">
              <td><RouterLink :to="`/lk/orders/${order.id}`">{{ order.id }}</RouterLink></td>
              <td>{{ order.status }}</td>
              <td>{{ order.created_at }}</td>
            </tr>
            <tr v-if="(item.orders || []).length === 0"><td colspan="3">Пусто</td></tr>
          </tbody>
        </table>
      </article>
    </div>

    <article class="panel" v-if="item && !loading">
      <h3>История статусов</h3>
      <table>
        <thead><tr><th>observed_at</th><th>status</th><th>provider</th></tr></thead>
        <tbody>
          <tr v-for="h in item.status_history || []" :key="h.id">
            <td>{{ h.observed_at }}</td>
            <td>{{ h.status }}</td>
            <td>{{ h.provider || '-' }}</td>
          </tr>
          <tr v-if="(item.status_history || []).length === 0"><td colspan="3">Пусто</td></tr>
        </tbody>
      </table>
    </article>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { RouterLink, useRoute, useRouter } from 'vue-router';
import { apiRequest } from '@/services/api';

type DomainDetails = {
  id: string;
  fqdn: string;
  sld: string;
  tld: string;
  score: number | null;
  source: string | null;
  current_status: string;
  status_checked_at: string | null;
  drop_time_estimated_at: string | null;
  created_at: string;
  updated_at: string;
  orders: Array<{ id: string; status: string; created_at: string }>;
  status_history: Array<{ id: string; status: string; provider?: string | null; observed_at: string }>;
};

const route = useRoute();
const router = useRouter();

const loading = ref(true);
const loadingAction = ref(false);
const error = ref('');
const actionMessage = ref('');
const item = ref<DomainDetails | null>(null);

async function load() {
  loading.value = true;
  error.value = '';
  actionMessage.value = '';
  try {
    const id = String(route.params.id || '');
    const data = await apiRequest<{ item: DomainDetails }>(`/v1/cabinet/domains/${id}`);
    item.value = data.item;
  } catch (e) {
    error.value = String(e);
  } finally {
    loading.value = false;
  }
}

async function recheck() {
  loadingAction.value = true;
  error.value = '';
  actionMessage.value = '';
  try {
    const id = String(route.params.id || '');
    const result = await apiRequest<{ ok: boolean; status: string; score: number }>(`/v1/cabinet/domains/${id}/recheck`, {
      method: 'POST',
    });
    actionMessage.value = `Обновлено: status=${result.status}, score=${result.score}`;
    await load();
  } catch (e) {
    error.value = String(e);
  } finally {
    loadingAction.value = false;
  }
}

function goBack() {
  router.push('/lk/domens');
}

onMounted(load);
</script>

<style scoped>
.header { display: flex; justify-content: space-between; gap: 10px; align-items: center; margin-bottom: 10px; }
.actions { display: flex; gap: 8px; }
.meta-grid { display: grid; gap: 10px; grid-template-columns: repeat(4, minmax(0, 1fr)); margin-bottom: 12px; }
.kpi { border: 1px solid var(--line); border-radius: 10px; background: var(--surface-2); padding: 10px; }
.kpi p { margin: 0 0 8px; color: var(--muted); }
.kpi h3 { margin: 0; font-size: 26px; }
.split { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 12px; }
.panel { border: 1px solid var(--line); border-radius: 12px; background: var(--surface-2); padding: 12px; }
.panel h3 { margin: 0 0 10px; font-size: 20px; }
table { width: 100%; border-collapse: collapse; }
th, td { border: 1px solid var(--line); padding: 8px; text-align: left; vertical-align: top; }
.error { color: #b42318; margin-bottom: 8px; }
.ok { color: #067647; margin-bottom: 8px; }
.btn-ghost { background: transparent; border: 1px solid var(--line); }
@media (max-width: 1200px) {
  .meta-grid { grid-template-columns: 1fr 1fr; }
  .split { grid-template-columns: 1fr; }
}
</style>
