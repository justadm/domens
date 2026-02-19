<template>
  <section class="page-card">
    <h2>События</h2>

    <div class="status-chips">
      <button class="status-chip" :class="{ 'is-active': !filters.event_type }" @click="setEventType('')">
        Все ({{ page.items.length }})
      </button>
      <button
        v-for="chip in eventTypeChips"
        :key="chip.value"
        class="status-chip"
        :class="{ 'is-active': filters.event_type === chip.value }"
        @click="setEventType(chip.value)"
      >
        {{ chip.value }} ({{ chip.count }})
      </button>
    </div>

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

    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th class="col-date">
              <button class="th-sort" @click="toggleSort('created_at')">
                created_at <span class="sort-indicator">{{ sortMark('created_at') }}</span>
              </button>
            </th>
            <th class="col-short">
              <button class="th-sort" @click="toggleSort('event_type')">
                event_type <span class="sort-indicator">{{ sortMark('event_type') }}</span>
              </button>
            </th>
            <th class="col-short">
              <button class="th-sort" @click="toggleSort('telegram_user_id')">
                user_id <span class="sort-indicator">{{ sortMark('telegram_user_id') }}</span>
              </button>
            </th>
            <th class="col-short">
              <button class="th-sort" @click="toggleSort('username')">
                username <span class="sort-indicator">{{ sortMark('username') }}</span>
              </button>
            </th>
            <th class="col-short">
              <button class="th-sort" @click="toggleSort('telegram_chat_id')">
                chat_id <span class="sort-indicator">{{ sortMark('telegram_chat_id') }}</span>
              </button>
            </th>
            <th>payload</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in page.items" :key="item.id">
            <td class="nowrap">{{ item.created_at }}</td>
            <td class="nowrap">{{ item.event_type }}</td>
            <td class="nowrap">{{ item.telegram_user_id || '-' }}</td>
            <td class="nowrap">{{ item.username ? `@${item.username}` : '-' }}</td>
            <td class="nowrap">{{ item.telegram_chat_id || '-' }}</td>
            <td><pre>{{ JSON.stringify(item.payload || {}, null, 2) }}</pre></td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { apiRequest } from '@/services/api';

type EventItem = {
  id: string;
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
const route = useRoute();
const router = useRouter();

const filters = reactive({
  event_type: '',
  telegram_user_id: '',
  telegram_chat_id: '',
  search: '',
  limit: 50,
  sort_by: 'created_at',
  sort_dir: 'desc',
});

const eventTypeChips = computed(() => {
  const counts = new Map<string, number>();
  for (const item of page.value.items) {
    const key = String(item.event_type || '').toLowerCase();
    if (!key) continue;
    counts.set(key, (counts.get(key) || 0) + 1);
  }
  return Array.from(counts.entries())
    .sort((a, b) => b[1] - a[1])
    .slice(0, 8)
    .map(([value, count]) => ({ value, count }));
});

function buildParams(offset = 0): URLSearchParams {
  const p = new URLSearchParams({
    limit: String(Math.max(1, Math.min(300, Number(filters.limit) || 50))),
    offset: String(offset),
    sort_by: filters.sort_by,
    sort_dir: filters.sort_dir,
  });
  if (filters.event_type) p.set('event_type', filters.event_type);
  if (filters.telegram_user_id) p.set('telegram_user_id', filters.telegram_user_id);
  if (filters.telegram_chat_id) p.set('telegram_chat_id', filters.telegram_chat_id);
  if (filters.search) p.set('search', filters.search);
  return p;
}

function syncUrl(offset = 0) {
  const query: Record<string, string> = {};
  if (filters.event_type) query.event_type = filters.event_type;
  if (filters.telegram_user_id) query.telegram_user_id = filters.telegram_user_id;
  if (filters.telegram_chat_id) query.telegram_chat_id = filters.telegram_chat_id;
  if (filters.search) query.search = filters.search;
  if (filters.limit !== 50) query.limit = String(filters.limit);
  if (filters.sort_by !== 'created_at') query.sort_by = filters.sort_by;
  if (filters.sort_dir !== 'desc') query.sort_dir = filters.sort_dir;
  if (offset > 0) query.offset = String(offset);
  router.replace({ query });
}

async function load(offset = 0) {
  error.value = '';
  try {
    const params = buildParams(offset);
    syncUrl(offset);
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

function toggleSort(sortBy: string) {
  if (filters.sort_by === sortBy) {
    filters.sort_dir = filters.sort_dir === 'asc' ? 'desc' : 'asc';
  } else {
    filters.sort_by = sortBy;
    filters.sort_dir = 'asc';
  }
  load(0);
}

function sortMark(sortBy: string) {
  if (filters.sort_by !== sortBy) return '↕';
  return filters.sort_dir === 'asc' ? '↑' : '↓';
}

function setEventType(value: string) {
  filters.event_type = value;
  load(0);
}

function exportCsv() {
  const params = buildParams(page.value.offset);
  window.open(`/v1/admin/bot-events.csv?${params.toString()}`, '_blank');
}

function initFromQuery() {
  filters.event_type = typeof route.query.event_type === 'string' ? route.query.event_type : '';
  filters.telegram_user_id = typeof route.query.telegram_user_id === 'string' ? route.query.telegram_user_id : '';
  filters.telegram_chat_id = typeof route.query.telegram_chat_id === 'string' ? route.query.telegram_chat_id : '';
  filters.search = typeof route.query.search === 'string' ? route.query.search : '';
  const limitRaw = Number(route.query.limit);
  if (Number.isFinite(limitRaw) && limitRaw > 0) {
    filters.limit = Math.max(1, Math.min(300, limitRaw));
  }
  const sortBy = typeof route.query.sort_by === 'string' ? route.query.sort_by : '';
  const sortDir = typeof route.query.sort_dir === 'string' ? route.query.sort_dir : '';
  if (['created_at', 'event_type', 'telegram_user_id', 'username', 'telegram_chat_id'].includes(sortBy)) {
    filters.sort_by = sortBy;
  }
  if (sortDir === 'asc' || sortDir === 'desc') {
    filters.sort_dir = sortDir;
  }
}

function offsetFromQuery() {
  const raw = Number(route.query.offset);
  if (!Number.isFinite(raw) || raw < 0) return 0;
  return Math.floor(raw);
}

const pageLabel = computed(() => {
  const total = Number(page.value.total || 0);
  const from = total ? Number(page.value.offset || 0) + 1 : 0;
  const to = Math.min(Number(page.value.offset || 0) + Number(page.value.limit || 0), total);
  return `${from}-${to} из ${total}`;
});

onMounted(() => {
  initFromQuery();
  load(offsetFromQuery());
});
</script>

<style scoped>
.row { display: grid; grid-template-columns: repeat(7, minmax(0, 1fr)); gap: 8px; margin-bottom: 10px; }
pre { margin: 0; max-width: 420px; overflow: auto; }
.error { color: #b42318; }
@media (max-width: 1400px) { .row { grid-template-columns: 1fr 1fr; } }
</style>
