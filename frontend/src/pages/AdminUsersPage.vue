<template>
  <section class="page-card">
    <h2>Пользователи</h2>

    <div class="row">
      <input v-model.trim="filters.search" placeholder="@username / user_id / chat_id" />
      <input v-model.trim="filters.permission_contains" placeholder="permission contains" />
      <select v-model="filters.registered_only">
        <option :value="false">Все</option>
        <option :value="true">Только зарегистрированные</option>
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

    <table>
      <thead>
        <tr>
          <th>user_id</th>
          <th>username</th>
          <th>registered</th>
          <th>roles</th>
          <th>permissions</th>
          <th>events</th>
          <th>last_event</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="u in page.items" :key="u.telegram_user_id">
          <td>{{ u.telegram_user_id }}</td>
          <td>{{ u.username ? `@${u.username}` : '-' }}</td>
          <td>{{ u.is_registered ? 'yes' : 'no' }}</td>
          <td>{{ (u.roles || []).join(', ') || '-' }}</td>
          <td>{{ (u.permissions || []).join(', ') || '-' }}</td>
          <td>{{ u.events_total }}</td>
          <td>{{ u.last_event_at || '-' }}</td>
        </tr>
      </tbody>
    </table>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue';
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

const filters = reactive({
  search: '',
  permission_contains: '',
  registered_only: false,
  limit: 50,
});

function buildParams(offset = 0): URLSearchParams {
  const p = new URLSearchParams({
    limit: String(Math.max(1, Math.min(200, Number(filters.limit) || 50))),
    offset: String(offset),
  });
  if (filters.search) p.set('search', filters.search);
  if (filters.permission_contains) p.set('permission_contains', filters.permission_contains);
  if (filters.registered_only) p.set('registered_only', 'true');
  return p;
}

async function load(offset = 0) {
  error.value = '';
  try {
    const params = buildParams(offset);
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

function exportCsv() {
  const params = buildParams(page.value.offset);
  window.open(`/v1/admin/users-activity.csv?${params.toString()}`, '_blank');
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
.row { display: grid; grid-template-columns: 1.2fr 1fr 220px 120px auto auto; gap: 8px; margin-bottom: 10px; }
.pager { display: flex; gap: 8px; align-items: center; margin-bottom: 10px; }
table { width: 100%; border-collapse: collapse; }
th, td { border: 1px solid var(--line); padding: 8px; vertical-align: top; text-align: left; }
input, select { border: 1px solid var(--line); border-radius: 8px; padding: 8px; }
.error { color: #b42318; }
@media (max-width: 1300px) { .row { grid-template-columns: 1fr 1fr; } }
</style>
