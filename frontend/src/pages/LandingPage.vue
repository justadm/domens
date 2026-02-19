<template>
  <div class="landing">
    <div class="card">
      <h1>Domens Radar</h1>
      <p>Frontend выделен в отдельный SPA-проект (Vue 3). Страницы LK/Admin работают из единого shell и различаются правами.</p>
      <div class="actions">
        <RouterLink class="btn" to="/lk">Открыть ЛК</RouterLink>
        <RouterLink class="btn" to="/admin">Открыть Admin</RouterLink>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { RouterLink } from 'vue-router';
</script>

<style scoped>
.landing { min-height: 100vh; display: grid; place-items: center; padding: 20px; }
.card { max-width: 760px; border: 1px solid var(--line); background: var(--surface); border-radius: 14px; padding: 24px; }
h1 { margin: 0 0 10px; font-size: 52px; line-height: 0.95; }
p { color: var(--muted); }
.actions { margin-top: 14px; display: flex; gap: 10px; }
</style>
