<template>
  <section class="page-card">
    <h2>Мои домены</h2>

    <div class="row">
      <input v-model.trim="filters.search" placeholder="Поиск по домену/source" />
      <input v-model.trim="filters.tld" placeholder="TLD (.ru/.com/.ai)" />
      <select v-model="filters.status">
        <option value="">Все статусы</option>
        <option value="available">available</option>
        <option value="registered">registered</option>
        <option value="pending_delete">pending_delete</option>
        <option value="redemption">redemption</option>
        <option value="client_hold">client_hold</option>
        <option value="inactive">inactive</option>
        <option value="unknown">unknown</option>
      </select>
      <input v-model.number="filters.limit" type="number" min="1" max="200" />
      <button class="btn" @click="apply">Применить</button>
    </div>

    <p v-if="error" class="error">{{ error }}</p>

    <div class="pager">
      <button class="btn" :disabled="page.prev_offset == null" @click="go(page.prev_offset)">Назад</button>
      <button class="btn" :disabled="page.next_offset == null" @click="go(page.next_offset)">Вперед</button>
      <span>{{ pageLabel }}</span>
    </div>

    <table>
      <thead>
        <tr>
          <th>fqdn</th>
          <th>status</th>
          <th>score</th>
          <th>tld</th>
          <th>latest order</th>
          <th>drop eta</th>
          <th>updated</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="item in page.items" :key="item.id">
          <td><RouterLink :to="`/lk/domens/${item.id}`">{{ item.fqdn }}</RouterLink></td>
          <td>{{ item.current_status || '-' }}</td>
          <td>{{ item.score ?? '-' }}</td>
          <td>{{ item.tld || '-' }}</td>
          <td>{{ item.latest_order_status || '-' }}</td>
          <td>{{ item.drop_time_estimated_at || '-' }}</td>
          <td>{{ item.updated_at || '-' }}</td>
        </tr>
        <tr v-if="page.items.length === 0">
          <td colspan="7">Пусто</td>
        </tr>
      </tbody>
    </table>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue';
import { RouterLink } from 'vue-router';
import { apiRequest } from '@/services/api';

type DomainItem = {
  id: string;
  fqdn: string;
  tld?: string | null;
  score?: number | null;
  current_status?: string | null;
  latest_order_status?: string | null;
  drop_time_estimated_at?: string | null;
  updated_at?: string | null;
};

type DomainsPage = {
  total: number;
  limit: number;
  offset: number;
  next_offset: number | null;
  prev_offset: number | null;
  items: DomainItem[];
};

const error = ref('');
const page = ref<DomainsPage>({ total: 0, limit: 50, offset: 0, next_offset: null, prev_offset: null, items: [] });
const filters = reactive({
  search: '',
  tld: '',
  status: '',
  limit: 50,
});

function buildParams(offset = 0): URLSearchParams {
  const p = new URLSearchParams({
    limit: String(Math.max(1, Math.min(200, Number(filters.limit) || 50))),
    offset: String(offset),
  });
  if (filters.search) p.set('search', filters.search);
  if (filters.tld) p.set('tld', filters.tld);
  if (filters.status) p.set('status', filters.status);
  return p;
}

async function load(offset = 0) {
  error.value = '';
  try {
    page.value = await apiRequest<DomainsPage>(`/v1/cabinet/domains?${buildParams(offset).toString()}`);
  } catch (e) {
    error.value = String(e);
  }
}

function apply() {
  load(0);
}

function go(offset: number | null) {
  if (offset == null) return;
  load(offset);
}

const pageLabel = computed(() => {
  const total = Number(page.value.total || 0);
  const from = total ? Number(page.value.offset || 0) + 1 : 0;
  const to = Math.min(Number(page.value.offset || 0) + Number(page.value.limit || 0), total);
  return `${from}-${to} из ${total}`;
});

onMounted(() => load(0));
</script>

<style scoped>
.row { display: grid; grid-template-columns: 1.4fr 160px 220px 120px auto; gap: 8px; margin-bottom: 10px; }
.pager { display: flex; gap: 8px; align-items: center; margin-bottom: 10px; }
table { width: 100%; border-collapse: collapse; }
th, td { border: 1px solid var(--line); padding: 8px; text-align: left; vertical-align: top; }
input, select { border: 1px solid var(--line); border-radius: 8px; padding: 8px; }
.error { color: #b42318; }
@media (max-width: 1300px) { .row { grid-template-columns: 1fr 1fr; } }
</style>
