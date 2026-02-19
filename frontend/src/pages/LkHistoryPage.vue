<template>
  <section class="page-card">
    <h2>История действий</h2>
    <div class="row">
      <input v-model.trim="eventType" placeholder="event_type" />
      <input v-model.trim="search" placeholder="Поиск по payload" />
      <input v-model.number="limit" type="number" min="1" max="200" />
      <button class="btn" @click="load">Применить</button>
    </div>
    <p v-if="error" class="error">{{ error }}</p>
    <div class="list">
      <article class="item" v-for="item in items" :key="item.id || `${item.event_type}_${item.created_at}`">
        <div class="head">
          <strong>{{ item.event_type }}</strong>
          <time>{{ item.created_at }}</time>
        </div>
        <pre>{{ JSON.stringify(item.payload || {}, null, 2) }}</pre>
      </article>
      <p v-if="!items.length">Пусто</p>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { apiRequest } from '@/services/api';

type HistoryItem = {
  id?: string;
  event_type: string;
  created_at: string;
  payload?: Record<string, unknown>;
};

const eventType = ref('');
const search = ref('');
const limit = ref(40);
const items = ref<HistoryItem[]>([]);
const error = ref('');

async function load() {
  error.value = '';
  try {
    const params = new URLSearchParams({ limit: String(Math.max(1, Math.min(200, Number(limit.value) || 40))) });
    if (eventType.value) params.set('event_type', eventType.value);
    if (search.value) params.set('search', search.value);
    const data = await apiRequest<{ items: HistoryItem[] }>(`/v1/cabinet/history?${params.toString()}`);
    items.value = data.items || [];
  } catch (e) {
    error.value = String(e);
  }
}

onMounted(load);
</script>

<style scoped>
.row { display: grid; grid-template-columns: 1fr 1fr 120px auto; gap: 8px; margin-bottom: 10px; }
.list { display: grid; gap: 8px; }
.item { border: 1px solid var(--line); border-radius: 10px; background: var(--surface-2); padding: 10px; }
.head { display: flex; justify-content: space-between; margin-bottom: 8px; }
pre { margin: 0; overflow: auto; }
.error { color: #b42318; }
@media (max-width: 1000px) { .row { grid-template-columns: 1fr 1fr; } }
</style>
