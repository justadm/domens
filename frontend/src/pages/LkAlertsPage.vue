<template>
  <section class="page-card">
    <h2>Алерты и каналы</h2>

    <div class="row">
      <input v-model.trim="telegramChatId" placeholder="Telegram chat_id" />
      <button class="btn" @click="toggleTelegram(true)">Telegram ON</button>
      <button class="btn" @click="toggleTelegram(false)">Telegram OFF</button>
      <input v-model.trim="maxTarget" placeholder="MAX target/chat" />
      <button class="btn" @click="toggleMax(true)">MAX ON</button>
      <button class="btn" @click="toggleMax(false)">MAX OFF</button>
    </div>

    <p v-if="error" class="error">{{ error }}</p>

    <table>
      <thead>
        <tr><th>channel</th><th>target</th><th>status</th><th>updated</th></tr>
      </thead>
      <tbody>
        <tr v-for="item in subs" :key="`${item.channel_type}:${item.channel_target || '-'}`">
          <td>{{ item.channel_type }}</td>
          <td>{{ item.channel_target || '-' }}</td>
          <td>{{ item.status }}</td>
          <td>{{ item.updated_at || '-' }}</td>
        </tr>
      </tbody>
    </table>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { apiRequest } from '@/services/api';

type Subscription = {
  channel_type: string;
  channel_target: string | null;
  status: string;
  updated_at?: string;
};

const subs = ref<Subscription[]>([]);
const telegramChatId = ref('');
const maxTarget = ref('');
const error = ref('');

async function load() {
  error.value = '';
  try {
    const profile = await apiRequest<{ chat_id?: string | null }>('/v1/cabinet/profile');
    telegramChatId.value = profile.chat_id || '';

    const data = await apiRequest<{ items: Subscription[] }>('/v1/cabinet/subscriptions');
    subs.value = data.items || [];

    const max = subs.value.find((x) => String(x.channel_type || '').toLowerCase() === 'max');
    if (max?.channel_target) {
      maxTarget.value = max.channel_target;
    }
  } catch (e) {
    error.value = String(e);
  }
}

async function toggleTelegram(enabled: boolean) {
  error.value = '';
  try {
    const data = await apiRequest<{ items: Subscription[] }>('/v1/cabinet/subscriptions/telegram', {
      method: 'POST',
      body: JSON.stringify({ enabled, chat_id: telegramChatId.value || null }),
    });
    subs.value = data.items || [];
  } catch (e) {
    error.value = String(e);
  }
}

async function toggleMax(enabled: boolean) {
  error.value = '';
  try {
    const data = await apiRequest<{ items: Subscription[] }>('/v1/cabinet/subscriptions/channel', {
      method: 'POST',
      body: JSON.stringify({
        channel_type: 'max',
        enabled,
        target: maxTarget.value || null,
      }),
    });
    subs.value = data.items || [];
  } catch (e) {
    error.value = String(e);
  }
}

onMounted(load);
</script>

<style scoped>
.row { display: grid; grid-template-columns: 1fr auto auto 1fr auto auto; gap: 8px; margin-bottom: 10px; }
.error { color: #b42318; }
@media (max-width: 1100px) {
  .row { grid-template-columns: 1fr 1fr; }
}
</style>
