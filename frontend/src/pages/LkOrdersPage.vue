<template>
  <section class="page-card">
    <h2>Мои заказы</h2>

    <div class="row">
      <input v-model.trim="filters.search" placeholder="Поиск по домену/requested_by/error" />
      <select v-model="filters.status">
        <option value="">Все статусы</option>
        <option value="created">created</option>
        <option value="queued">queued</option>
        <option value="sent_to_registrar">sent_to_registrar</option>
        <option value="registered">registered</option>
        <option value="failed">failed</option>
        <option value="canceled">canceled</option>
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
          <th>order_id</th>
          <th>domain</th>
          <th>status</th>
          <th>requested_by</th>
          <th>created</th>
          <th>updated</th>
          <th>error</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="item in page.items" :key="item.id">
          <td>{{ item.id }}</td>
          <td>{{ item.domain }}</td>
          <td>{{ item.status }}</td>
          <td>{{ item.requested_by || '-' }}</td>
          <td>{{ item.created_at || '-' }}</td>
          <td>{{ item.updated_at || '-' }}</td>
          <td>{{ item.error_message || '-' }}</td>
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
import { apiRequest } from '@/services/api';

type OrderItem = {
  id: string;
  domain: string;
  status: string;
  requested_by?: string | null;
  error_message?: string | null;
  created_at?: string;
  updated_at?: string;
  completed_at?: string | null;
};

type OrdersPage = {
  total: number;
  limit: number;
  offset: number;
  next_offset: number | null;
  prev_offset: number | null;
  items: OrderItem[];
};

const error = ref('');
const page = ref<OrdersPage>({ total: 0, limit: 50, offset: 0, next_offset: null, prev_offset: null, items: [] });
const filters = reactive({
  search: '',
  status: '',
  limit: 50,
});

function buildParams(offset = 0): URLSearchParams {
  const p = new URLSearchParams({
    limit: String(Math.max(1, Math.min(200, Number(filters.limit) || 50))),
    offset: String(offset),
  });
  if (filters.search) p.set('search', filters.search);
  if (filters.status) p.set('status', filters.status);
  return p;
}

async function load(offset = 0) {
  error.value = '';
  try {
    page.value = await apiRequest<OrdersPage>(`/v1/cabinet/orders?${buildParams(offset).toString()}`);
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
.row { display: grid; grid-template-columns: 1fr 260px 120px auto; gap: 8px; margin-bottom: 10px; }
.pager { display: flex; gap: 8px; align-items: center; margin-bottom: 10px; }
table { width: 100%; border-collapse: collapse; }
th, td { border: 1px solid var(--line); padding: 8px; text-align: left; vertical-align: top; }
input, select { border: 1px solid var(--line); border-radius: 8px; padding: 8px; }
.error { color: #b42318; }
@media (max-width: 1300px) { .row { grid-template-columns: 1fr 1fr; } }
</style>
