<template>
  <section class="page-card">
    <h2>Watch-правила</h2>

    <form class="row" @submit.prevent="createRule">
      <input v-model.trim="createForm.query" placeholder="Запрос (например: ai fintech)" required minlength="2" />
      <input v-model.trim="createForm.tlds" placeholder="TLDs CSV (.com,.io,.ai,.ru)" />
      <input v-model.trim="createForm.min_score" type="number" min="0" max="100" step="0.1" placeholder="Min score" />
      <input v-model.trim="createForm.max_price_usd" type="number" min="0" step="0.01" placeholder="Max price USD" />
      <input v-model.trim="createForm.max_length" type="number" min="3" max="30" placeholder="Max length" />
      <input v-model.trim="createForm.daily_alert_limit" type="number" min="1" max="10" placeholder="Daily alerts" />
      <button class="btn" type="submit">Добавить</button>
    </form>

    <div class="row">
      <input v-model.trim="filters.search" placeholder="Поиск" @input="loadRules" />
      <select v-model="filters.status" @change="loadRules">
        <option value="">all</option>
        <option value="active">active</option>
        <option value="paused">paused</option>
        <option value="deleted">deleted</option>
      </select>
      <button class="btn" @click="loadRules">Обновить</button>
    </div>

    <p v-if="error" class="error">{{ error }}</p>

    <div class="list">
      <article class="item" v-for="item in items" :key="item.id">
        <div class="item-head">
          <strong>{{ item.query }}</strong>
          <span class="status">{{ item.status }}</span>
        </div>
        <div class="item-grid">
          <input v-model.trim="item.query" />
          <input v-model.trim="item.tldsCsv" placeholder=".com,.io" />
          <input v-model.trim="item.minScore" type="number" min="0" max="100" step="0.1" placeholder="Min score" />
          <input v-model.trim="item.maxPrice" type="number" min="0" step="0.01" placeholder="Max price" />
          <input v-model.trim="item.maxLength" type="number" min="3" max="30" placeholder="Max length" />
          <input v-model.trim="item.dailyAlertLimit" type="number" min="1" max="10" placeholder="Daily alerts" />
        </div>
        <div class="actions">
          <button class="btn" @click="setStatus(item.id, 'active')">active</button>
          <button class="btn" @click="setStatus(item.id, 'paused')">paused</button>
          <button class="btn" @click="setStatus(item.id, 'deleted')">deleted</button>
          <button class="btn" @click="saveRule(item)">Сохранить</button>
        </div>
      </article>
      <p v-if="!loading && items.length === 0">Пусто</p>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue';
import { apiRequest } from '@/services/api';

type RuleApi = {
  id: string;
  query: string;
  status: string;
  tlds: string[];
  min_score: number | null;
  max_price_usd: number | null;
  max_length: number | null;
  daily_alert_limit: number;
};

type RuleUi = {
  id: string;
  query: string;
  status: string;
  tldsCsv: string;
  minScore: string;
  maxPrice: string;
  maxLength: string;
  dailyAlertLimit: string;
};

const loading = ref(false);
const error = ref('');
const items = ref<RuleUi[]>([]);

const filters = reactive({
  search: '',
  status: '',
});

const createForm = reactive({
  query: '',
  tlds: '',
  min_score: '',
  max_price_usd: '',
  max_length: '',
  daily_alert_limit: '3',
});

function toUi(item: RuleApi): RuleUi {
  return {
    id: item.id,
    query: item.query,
    status: item.status,
    tldsCsv: (item.tlds || []).join(','),
    minScore: item.min_score == null ? '' : String(item.min_score),
    maxPrice: item.max_price_usd == null ? '' : String(item.max_price_usd),
    maxLength: item.max_length == null ? '' : String(item.max_length),
    dailyAlertLimit: String(item.daily_alert_limit || 3),
  };
}

async function loadRules() {
  loading.value = true;
  error.value = '';
  try {
    const params = new URLSearchParams();
    if (filters.search) params.set('search', filters.search);
    if (filters.status) params.set('status', filters.status);
    const qs = params.toString();
    const data = await apiRequest<{ items: RuleApi[] }>(`/v1/cabinet/watch-rules${qs ? `?${qs}` : ''}`);
    items.value = (data.items || []).map(toUi);
  } catch (e) {
    error.value = String(e);
  } finally {
    loading.value = false;
  }
}

async function createRule() {
  error.value = '';
  try {
    await apiRequest('/v1/cabinet/watch-rules', {
      method: 'POST',
      body: JSON.stringify({
        query: createForm.query,
        tlds: createForm.tlds.split(',').map((s) => s.trim()).filter(Boolean),
        min_score: createForm.min_score ? Number(createForm.min_score) : null,
        max_price_usd: createForm.max_price_usd ? Number(createForm.max_price_usd) : null,
        max_length: createForm.max_length ? Number(createForm.max_length) : null,
        daily_alert_limit: createForm.daily_alert_limit ? Number(createForm.daily_alert_limit) : 3,
      }),
    });
    createForm.query = '';
    createForm.tlds = '';
    createForm.min_score = '';
    createForm.max_price_usd = '';
    createForm.max_length = '';
    createForm.daily_alert_limit = '3';
    await loadRules();
  } catch (e) {
    error.value = String(e);
  }
}

async function setStatus(ruleId: string, status: 'active' | 'paused' | 'deleted') {
  error.value = '';
  try {
    await apiRequest(`/v1/cabinet/watch-rules/${ruleId}/status`, {
      method: 'POST',
      body: JSON.stringify({ status }),
    });
    await loadRules();
  } catch (e) {
    error.value = String(e);
  }
}

async function saveRule(item: RuleUi) {
  error.value = '';
  try {
    await apiRequest(`/v1/cabinet/watch-rules/${item.id}`, {
      method: 'PATCH',
      body: JSON.stringify({
        query: item.query,
        tlds: item.tldsCsv.split(',').map((s) => s.trim()).filter(Boolean),
        min_score: item.minScore ? Number(item.minScore) : null,
        max_price_usd: item.maxPrice ? Number(item.maxPrice) : null,
        max_length: item.maxLength ? Number(item.maxLength) : null,
        daily_alert_limit: item.dailyAlertLimit ? Number(item.dailyAlertLimit) : 3,
      }),
    });
    await loadRules();
  } catch (e) {
    error.value = String(e);
  }
}

onMounted(loadRules);
</script>

<style scoped>
.row { display: grid; grid-template-columns: repeat(7, minmax(0, 1fr)); gap: 8px; margin-bottom: 10px; }
.list { display: grid; gap: 8px; }
.item { border: 1px solid var(--line); border-radius: 10px; background: var(--surface-2); padding: 10px; }
.item-head { display: flex; justify-content: space-between; margin-bottom: 8px; }
.item-grid { display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 8px; margin-bottom: 8px; }
.actions { display: flex; gap: 8px; flex-wrap: wrap; }
.error { color: #b42318; }
input, select { border: 1px solid var(--line); border-radius: 8px; padding: 8px; }
@media (max-width: 1200px) {
  .row { grid-template-columns: 1fr 1fr; }
  .item-grid { grid-template-columns: 1fr 1fr; }
}
</style>
