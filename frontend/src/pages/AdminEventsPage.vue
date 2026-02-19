<template>
  <section class="page-card">
    <h2>События</h2>

    <div class="row">
      <input v-model.trim="filters.event_type" placeholder="event_type" />
      <input v-model.trim="filters.telegram_user_id" placeholder="telegram_user_id" />
      <input v-model.trim="filters.telegram_chat_id" placeholder="telegram_chat_id" />
      <input v-model.trim="filters.search" placeholder="Поиск по payload" />
      <input v-model.number="filters.limit" type="number" min="1" max="300" />
      <button class="btn" @click="apply">Применить</button>
      <button class="btn" @click="exportCsv">Экспорт CSV</button>
    </div>

    <p v-if="error" class="error">{{ error }}</p>

    <div class="pager">
      <button class="btn" :disabled="page.prev_offset == null" @click="go(page.prev_offset)">Назад</button>
      <button class="btn" :disabled="page.next_offset == null" @click="go(page.next_offset)">Вперёд</button>
      <span>{{ pageLabel }}</span>
    </div>

    <table>
      <thead>
        <tr>
          <th>created_at</th>
          <th>event_type</th>
          <th>user_id</th>
          <th>username</th>
          <th>chat_id</th>
          <th>payload</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="item in page.items" :key="`${item.created_at}_${item.event_type}_${item.telegram_user_id || '-'}`">
          <td>{{ item.created_at }}</td>
          <td>{{ item.event_type }}</td>
          <td>{{ item.telegram_user_id || '-' }}</td>
          <td>{{ item.username ? `@${item.username}` : '-' }}</td>
          <td>{{ item.telegram_chat_id || '-' }}</td>
          <td><pre>{{ JSON.stringify(item.payload || {}, null, 2) }}</pre></td>
        </tr>
      </tbody>
    </table>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue';
import { apiRequest } from '@/services/api';

type EventItem = {
  created_at: string;
  event_type: string;
  telegram_user_id?: string | null;
  username?: string | null;
  telegram_chat_id?: string | null;
  payload?: Record<string, unknown>;
};

type EventsPage = {
  total: number;
  limit: number;
  offset: number;
  next_offset: number | null;
  prev_offset: number | null;
  items: EventItem[];
};

const error = ref('');
const page = ref<EventsPage>({ total: 0, limit: 50, offset: 0, next_offset: null, prev_offset: null, items: [] });

const filters = reactive({
  event_type: '',
  telegram_user_id: '',
  telegram_chat_id: '',
  search: '',
  limit: 50,
});

function buildParams(offset = 0): URLSearchParams {
  const p = new URLSearchParams({
    limit: String(Math.max(1, Math.min(300, Number(filters.limit) || 50))),
    offset: String(offset),
  });
  if (filters.event_type) p.set('event_type', filters.event_type);
  if (filters.telegram_user_id) p.set('telegram_user_id', filters.telegram_user_id);
  if (filters.telegram_chat_id) p.set('telegram_chat_id', filters.telegram_chat_id);
  if (filters.search) p.set('search', filters.search);
  return p;
}

async function load(offset = 0) {
  error.value = '';
  try {
    const params = buildParams(offset);
    page.value = await apiRequest<EventsPage>(`/v1/admin/bot-events?${params.toString()}`);
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

function exportCsv() {
  const params = buildParams(page.value.offset);
  window.open(`/v1/admin/bot-events.csv?${params.toString()}`, '_blank');
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
.row { display: grid; grid-template-columns: repeat(7, minmax(0, 1fr)); gap: 8px; margin-bottom: 10px; }
pre { margin: 0; max-width: 420px; overflow: auto; }
.error { color: #b42318; }
@media (max-width: 1400px) { .row { grid-template-columns: 1fr 1fr; } }
</style>
