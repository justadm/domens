<template>
  <section class="page-card">
    <h2>Дашборд доменов</h2>
    <div class="kpi-grid" v-if="!loading">
      <article class="kpi"><p>watch-правил активных</p><h3>{{ watchActive }}</h3></article>
      <article class="kpi"><p>каналов алертов ON</p><h3>{{ alertsChannels }}</h3></article>
      <article class="kpi"><p>доступов cabinet</p><h3>{{ cabinetRead ? 1 : 0 }}</h3></article>
      <article class="kpi"><p>режим admin</p><h3>{{ isAdmin ? 'ON' : 'OFF' }}</h3></article>
    </div>
    <p v-else>Загрузка...</p>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { apiRequest } from '@/services/api';

type Profile = { watch_rules_active?: number; capabilities?: Record<string, boolean>; is_admin?: boolean };

const loading = ref(true);
const profile = ref<Profile>({});

const watchActive = computed(() => profile.value.watch_rules_active || 0);
const cabinetRead = computed(() => Boolean(profile.value.capabilities?.cabinet_read));
const isAdmin = computed(() => Boolean(profile.value.capabilities?.admin_panel_read || profile.value.is_admin));
const alertsChannels = computed(() => Number(profile.value.capabilities?.alerts_manage ? 1 : 0));

onMounted(async () => {
  try {
    profile.value = await apiRequest<Profile>('/v1/cabinet/profile');
  } finally {
    loading.value = false;
  }
});
</script>
