<template>
  <section class="page-card">
    <div class="page-head">
      <div>
        <h2>Настройки радара</h2>
        <p>Watch-правила и скрытые домены, которые влияют на будущие алерты.</p>
      </div>
      <button class="btn" @click="loadPreferences" :disabled="loading">Обновить</button>
    </div>

    <p v-if="error" class="error">{{ error }}</p>
    <p v-if="loading" class="muted">Загрузка...</p>

    <div class="split" v-if="!loading">
      <article class="panel">
        <h3>Watch-правила</h3>
        <table>
          <thead>
            <tr><th>query</th><th>status</th><th>limit</th></tr>
          </thead>
          <tbody>
            <tr v-for="rule in watchRules" :key="rule.id">
              <td>{{ rule.query }}</td>
              <td>{{ rule.status }}</td>
              <td>{{ rule.daily_alert_limit ?? '-' }}</td>
            </tr>
            <tr v-if="watchRules.length === 0"><td colspan="3">Пусто</td></tr>
          </tbody>
        </table>
      </article>

      <article class="panel">
        <h3>Скрытые домены</h3>
        <table>
          <thead>
            <tr><th>domain</th><th>reason</th><th>expires</th><th></th></tr>
          </thead>
          <tbody>
            <tr v-for="item in suppressions" :key="item.id">
              <td>{{ item.fqdn }}</td>
              <td>{{ suppressionLabel(item.reason) }}</td>
              <td>{{ formatDate(item.expires_at) }}</td>
              <td><button class="btn" @click="deleteSuppression(item.id)">Вернуть</button></td>
            </tr>
            <tr v-if="suppressions.length === 0"><td colspan="4">Пусто</td></tr>
          </tbody>
        </table>
      </article>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { apiRequest } from '@/services/api';

type WatchRule = {
  id: string;
  query: string;
  status: string;
  daily_alert_limit?: number | null;
};

type Suppression = {
  id: string;
  fqdn: string;
  reason: string;
  expires_at?: string | null;
};

const loading = ref(false);
const error = ref('');
const watchRules = ref<WatchRule[]>([]);
const suppressions = ref<Suppression[]>([]);

async function loadPreferences() {
  loading.value = true;
  error.value = '';
  try {
    const data = await apiRequest<{ watch_rules: WatchRule[]; suppressions: Suppression[] }>('/v1/cabinet/preferences');
    watchRules.value = data.watch_rules || [];
    suppressions.value = data.suppressions || [];
  } catch (e) {
    error.value = String(e);
  } finally {
    loading.value = false;
  }
}

async function deleteSuppression(id: string) {
  error.value = '';
  try {
    await apiRequest(`/v1/cabinet/preferences/suppressions/${id}`, { method: 'DELETE' });
    suppressions.value = suppressions.value.filter((item) => item.id !== id);
  } catch (e) {
    error.value = String(e);
  }
}

function suppressionLabel(reason: string): string {
  if (reason === 'user_less') return 'меньше таких';
  if (reason === 'user_never') return 'не повторять';
  return reason || '-';
}

function formatDate(value?: string | null): string {
  if (!value) return '-';
  return new Date(value).toLocaleString();
}

onMounted(loadPreferences);
</script>

<style scoped>
.error { color: #b42318; margin-bottom: 8px; }
.muted { color: var(--muted); }
.page-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
}
.page-head p { margin: 0; color: var(--muted); }
.split {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin-top: 12px;
}
.panel {
  border: 1px solid var(--line);
  border-radius: 12px;
  padding: 12px;
  background: var(--surface-2);
  overflow-x: auto;
}
.panel h3 { margin: 0 0 10px; font-size: 20px; }
@media (max-width: 1200px) {
  .page-head { display: grid; }
  .split { grid-template-columns: 1fr; }
}
</style>
