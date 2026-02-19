<template>
  <section class="page-card">
    <h2>Пользователи</h2>

    <div class="status-chips">
      <button class="status-chip" :class="{ 'is-active': !filters.registered_only }" @click="setRegistered(false)">
        Все ({{ page.items.length }})
      </button>
      <button class="status-chip" :class="{ 'is-active': filters.registered_only }" @click="setRegistered(true)">
        Зарегистрированы ({{ registeredCount }})
      </button>
      <button class="status-chip" :class="{ 'is-active': adminOnly }" @click="toggleAdminOnly">
        С admin.panel.read ({{ adminPermCount }})
      </button>
    </div>

    <div class="row">
      <input v-model.trim="filters.search" placeholder="@username / user_id / chat_id" />
      <input v-model.trim="filters.permission_contains" placeholder="permission contains" />
      <select v-model="registeredSelect">
        <option value="all">Все</option>
        <option value="registered">Только зарегистрированные</option>
      </select>
      <input v-model.number="filters.limit" type="number" min="1" max="200" />
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
            <th class="col-short">
              <button class="th-sort" @click="toggleSort('telegram_user_id')">
                user_id <span class="sort-indicator">{{ sortMark('telegram_user_id') }}</span>
              </button>
            </th>
            <th>
              <button class="th-sort" @click="toggleSort('username')">
                username <span class="sort-indicator">{{ sortMark('username') }}</span>
              </button>
            </th>
            <th class="col-short nowrap">registered</th>
            <th class="col-short nowrap">roles</th>
            <th>permissions</th>
            <th class="col-short nowrap">events</th>
            <th class="col-date">
              <button class="th-sort" @click="toggleSort('updated_at')">
                last_event <span class="sort-indicator">{{ sortMark('updated_at') }}</span>
              </button>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="u in page.items" :key="u.telegram_user_id">
            <td class="nowrap">{{ u.telegram_user_id }}</td>
            <td>{{ u.username ? `@${u.username}` : '-' }}</td>
            <td class="nowrap">{{ u.is_registered ? 'yes' : 'no' }}</td>
            <td>{{ (u.roles || []).join(', ') || '-' }}</td>
            <td>{{ (u.permissions || []).join(', ') || '-' }}</td>
            <td class="nowrap">{{ u.events_total }}</td>
            <td class="nowrap">{{ u.last_event_at || '-' }}</td>
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

type UserItem = {
  telegram_user_id: string;
  username?: string | null;
  is_registered?: boolean;
  roles?: string[];
  permissions?: string[];
  events_total?: number;
  last_event_at?: string | null;
};

type UsersPage = {
  total: number;
  limit: number;
  offset: number;
  next_offset: number | null;
  prev_offset: number | null;
  items: UserItem[];
};

const error = ref('');
const page = ref<UsersPage>({ total: 0, limit: 50, offset: 0, next_offset: null, prev_offset: null, items: [] });
const route = useRoute();
const router = useRouter();

const filters = reactive({
  search: '',
  permission_contains: '',
  registered_only: false,
  limit: 50,
  sort_by: 'updated_at',
  sort_dir: 'desc',
});

const adminOnly = computed(() => filters.permission_contains === 'admin.panel.read');
const registeredSelect = computed({
  get: () => (filters.registered_only ? 'registered' : 'all'),
  set: (value: string) => {
    filters.registered_only = value === 'registered';
  },
});

const registeredCount = computed(() => page.value.items.filter((x) => !!x.is_registered).length);
const adminPermCount = computed(() =>
  page.value.items.filter((x) => (x.permissions || []).some((p) => String(p).toLowerCase() === 'admin.panel.read')).length,
);

function buildParams(offset = 0): URLSearchParams {
  const p = new URLSearchParams({
    limit: String(Math.max(1, Math.min(200, Number(filters.limit) || 50))),
    offset: String(offset),
    sort_by: filters.sort_by,
    sort_dir: filters.sort_dir,
  });
  if (filters.search) p.set('search', filters.search);
  if (filters.permission_contains) p.set('permission_contains', filters.permission_contains);
  if (filters.registered_only) p.set('registered_only', 'true');
  return p;
}

function syncUrl(offset = 0) {
  const query: Record<string, string> = {};
  if (filters.search) query.search = filters.search;
  if (filters.permission_contains) query.permission_contains = filters.permission_contains;
  if (filters.registered_only) query.registered_only = 'true';
  if (filters.limit !== 50) query.limit = String(filters.limit);
  if (filters.sort_by !== 'updated_at') query.sort_by = filters.sort_by;
  if (filters.sort_dir !== 'desc') query.sort_dir = filters.sort_dir;
  if (offset > 0) query.offset = String(offset);
  router.replace({ query });
}

async function load(offset = 0) {
  error.value = '';
  try {
    const params = buildParams(offset);
    syncUrl(offset);
    page.value = await apiRequest<UsersPage>(`/v1/admin/users-activity?${params.toString()}`);
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

function setRegistered(registeredOnly: boolean) {
  filters.registered_only = registeredOnly;
  load(0);
}

function toggleAdminOnly() {
  filters.permission_contains = adminOnly.value ? '' : 'admin.panel.read';
  load(0);
}

function exportCsv() {
  const params = buildParams(page.value.offset);
  window.open(`/v1/admin/users-activity.csv?${params.toString()}`, '_blank');
}

function initFromQuery() {
  filters.search = typeof route.query.search === 'string' ? route.query.search : '';
  filters.permission_contains = typeof route.query.permission_contains === 'string' ? route.query.permission_contains : '';
  filters.registered_only = String(route.query.registered_only || '').toLowerCase() === 'true';
  const limitRaw = Number(route.query.limit);
  if (Number.isFinite(limitRaw) && limitRaw > 0) {
    filters.limit = Math.max(1, Math.min(200, limitRaw));
  }
  const sortBy = typeof route.query.sort_by === 'string' ? route.query.sort_by : '';
  const sortDir = typeof route.query.sort_dir === 'string' ? route.query.sort_dir : '';
  if (['telegram_user_id', 'username', 'updated_at'].includes(sortBy)) {
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
.row { display: grid; grid-template-columns: 1.2fr 1fr 220px 120px auto auto; gap: 8px; margin-bottom: 10px; }
.error { color: #b42318; }
@media (max-width: 1300px) { .row { grid-template-columns: 1fr 1fr; } }
</style>
