<template>
  <section class="page-card">
    <h2>Общая статистика</h2>
    <div class="kpi-grid" v-if="stats">
      <article class="kpi"><p>пользователей всего</p><h3>{{ stats.users_total ?? 0 }}</h3></article>
      <article class="kpi"><p>зарегистрированных</p><h3>{{ stats.users_registered ?? 0 }}</h3></article>
      <article class="kpi"><p>watch-правил</p><h3>{{ stats.watch_rules_total ?? 0 }}</h3></article>
      <article class="kpi"><p>bot events</p><h3>{{ stats.bot_events_total ?? 0 }}</h3></article>
    </div>
    <p v-else>Загрузка...</p>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { apiRequest } from '@/services/api';

type DashboardResp = { stats: Record<string, number | null> };

const stats = ref<Record<string, number | null> | null>(null);

onMounted(async () => {
  const data = await apiRequest<DashboardResp>('/v1/admin/dashboard');
  stats.value = data.stats;
});
</script>
