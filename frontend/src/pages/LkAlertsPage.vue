<template>
  <section class="page-card">
    <div class="page-head">
      <div>
        <h2>Алерты</h2>
        <p>История отправок, причины попадания в радар и настройки каналов.</p>
      </div>
      <button class="btn" @click="refreshAll" :disabled="loading">Обновить</button>
    </div>

    <section class="settings-band">
      <div class="settings-head">
        <h3>Каналы</h3>
        <span>{{ activeChannels }} active</span>
      </div>
      <div class="channel-row">
        <input v-model.trim="telegramChatId" placeholder="Telegram chat_id" />
        <button class="btn" @click="toggleTelegram(true)">Telegram ON</button>
        <button class="btn" @click="toggleTelegram(false)">Telegram OFF</button>
        <input v-model.trim="maxTarget" placeholder="MAX target/chat" />
        <button class="btn" @click="toggleMax(true)">MAX ON</button>
        <button class="btn" @click="toggleMax(false)">MAX OFF</button>
      </div>
      <div class="subscription-list">
        <span v-for="item in subs" :key="`${item.channel_type}:${item.channel_target || '-'}`" class="subscription-chip">
          {{ item.channel_type }}: {{ item.channel_target || '-' }} / {{ item.status }}
        </span>
        <span v-if="subs.length === 0" class="muted">Каналы еще не настроены</span>
      </div>
    </section>

    <section class="alerts-band">
      <div class="view-tabs" aria-label="Alert history view">
        <button class="tab-button" :class="{ active: activeView === 'alerts' }" @click="switchView('alerts')">
          Алерты
        </button>
        <button class="tab-button" :class="{ active: activeView === 'digests' }" @click="switchView('digests')">
          Дайджесты
        </button>
      </div>

      <div class="toolbar">
        <input v-model.trim="filters.search" :placeholder="searchPlaceholder" @keyup.enter="loadCurrent(0)" />
        <select v-if="activeView === 'alerts'" v-model="filters.feedback" @change="loadAlerts(0)">
          <option value="">feedback: all</option>
          <option value="more">Больше таких</option>
          <option value="less">Меньше таких</option>
          <option value="never">Не повторять</option>
          <option value="why">Почему прислали</option>
        </select>
        <input v-model.number="filters.limit" type="number" min="1" max="100" />
        <button class="btn" @click="loadCurrent(0)">Применить</button>
      </div>

      <div v-if="activeView === 'alerts' && activeDigestDomains.length > 0" class="active-filter">
        <span>Алерты из дайджеста: {{ activeDigestDomains.join(', ') }}</span>
        <button class="btn" @click="clearDigestFilter">Сбросить</button>
      </div>

      <p v-if="error" class="error">{{ error }}</p>
      <p v-if="loading" class="muted">Загрузка...</p>

      <div class="alerts-meta" v-if="!loading">
        <strong>{{ activeTotal }}</strong>
        <span>{{ activeView === 'alerts' ? 'алертов найдено' : 'дайджестов найдено' }}</span>
      </div>

      <div v-if="activeView === 'alerts'" class="alert-list">
        <article class="alert-item" v-for="item in alerts" :key="item.id">
          <div class="alert-main">
            <div>
              <div class="alert-title">
                <strong>{{ item.domain }}</strong>
                <span class="badge">{{ item.channel }}</span>
                <span class="badge muted-badge">{{ shortAlertType(item.alert_type) }}</span>
              </div>
              <div class="chips">
                <span>score {{ displayValue(item.explanation.score) }}</span>
                <span>{{ item.explanation.status || 'status unknown' }}</span>
                <span>.{{ item.explanation.tld || domainTld(item.domain) }}</span>
                <span>{{ riskLabel(item.explanation.risk) }}</span>
              </div>
            </div>
            <time>{{ formatDate(item.created_at) }}</time>
          </div>

          <div class="reason-grid">
            <div>
              <small>Почему прислали</small>
              <p>{{ reasonText(item) }}</p>
            </div>
            <div>
              <small>Источник проверки</small>
              <p>{{ providerSourceText(item) }}</p>
              <p class="state-note">
                Проверено: {{ formatDate(item.provider_checked_at) }}
              </p>
              <p class="state-note">
                Уверенность: {{ providerConfidenceLabel(item.provider_confidence) }}
              </p>
            </div>
            <div>
              <small>Feedback</small>
              <p>{{ feedbackLabel(item.latest_feedback?.type) }}</p>
              <p v-if="item.suppression_state?.active" class="state-note">
                {{ suppressionLabel(item.suppression_state.reason) }}
              </p>
            </div>
          </div>

          <div class="actions">
            <button class="btn" @click="sendFeedback(item, 'more')" :disabled="item.savingFeedback === 'more'">
              Больше таких
            </button>
            <button
              class="btn"
              @click="sendFeedback(item, 'less')"
              :disabled="item.savingFeedback === 'less' || suppressionActive(item, 'user_less') || suppressionActive(item, 'user_never')"
            >
              Меньше таких
            </button>
            <button
              class="btn danger"
              @click="sendFeedback(item, 'never')"
              :disabled="item.savingFeedback === 'never' || suppressionActive(item, 'user_never')"
            >
              Не повторять
            </button>
          </div>
        </article>
        <p v-if="!loading && alerts.length === 0" class="empty">Пока нет алертов под выбранные фильтры</p>
      </div>

      <div v-else class="digest-list">
        <article class="digest-item" v-for="item in digests" :key="item.id">
          <div class="alert-main">
            <div>
              <div class="alert-title">
                <strong>{{ item.items_count }} домен{{ pluralDomainSuffix(item.items_count) }}</strong>
                <span class="badge">{{ item.channel }}</span>
                <span class="badge muted-badge">message {{ item.message_id || '-' }}</span>
              </div>
              <div class="chips">
                <span v-for="domain in item.domains" :key="`${item.id}:${domain}`">{{ domain }}</span>
              </div>
            </div>
            <time>{{ formatDate(item.created_at) }}</time>
          </div>

          <div class="reason-grid digest-grid">
            <div>
              <small>Куда отправлено</small>
              <p>{{ item.channel_target || '-' }}</p>
            </div>
            <div>
              <small>Delivery</small>
              <p>{{ item.delivery?.mode || item.channel }} / {{ item.message_id || '-' }}</p>
            </div>
            <div>
              <small>Состав</small>
              <p>{{ item.domains.join(', ') || 'без доменов' }}</p>
            </div>
          </div>

          <div class="actions">
            <button class="btn" @click="showDigestAlerts(item)" :disabled="item.domains.length === 0">
              Показать связанные алерты
            </button>
          </div>
        </article>
        <p v-if="!loading && digests.length === 0" class="empty">Пока нет дайджестов под выбранные фильтры</p>
      </div>

      <div class="pager" v-if="!loading && activeTotal > 0">
        <button class="btn" @click="loadCurrent(activePrevOffset || 0)" :disabled="activePrevOffset === null">
          Назад
        </button>
        <span>offset {{ activeOffset }}</span>
        <button class="btn" @click="loadCurrent(activeNextOffset || activeOffset)" :disabled="activeNextOffset === null">
          Вперед
        </button>
      </div>
    </section>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue';
import { apiRequest } from '@/services/api';

type Subscription = {
  channel_type: string;
  channel_target: string | null;
  status: string;
  updated_at?: string;
};

type AlertExplanation = {
  score?: number | string | null;
  status?: string | null;
  provider?: string | null;
  matched_query?: string | null;
  tld?: string | null;
  length?: number | null;
  risk?: string | null;
  checked_at?: string | null;
};

type AlertFeedback = {
  type: 'more' | 'less' | 'never' | string;
  created_at: string;
  payload?: Record<string, unknown>;
};

type SuppressionState = {
  active: boolean;
  reason: 'user_less' | 'user_never' | string;
  created_at?: string | null;
  expires_at?: string | null;
};

type AlertItem = {
  id: string;
  domain: string;
  alert_type: string;
  channel: string;
  channel_target: string;
  acknowledged: boolean;
  created_at: string;
  acknowledged_at?: string | null;
  explanation: AlertExplanation;
  provider: string;
  provider_status: string;
  provider_checked_at?: string | null;
  provider_confidence: string;
  latest_feedback?: AlertFeedback | null;
  feedback_counts?: Record<string, number>;
  suppression_state?: SuppressionState | null;
  savingFeedback?: string;
};

type DigestItem = {
  id: string;
  channel: string;
  channel_target: string;
  created_at: string;
  domains: string[];
  items_count: number;
  message_id?: string | null;
  delivery?: Record<string, unknown>;
};

const subs = ref<Subscription[]>([]);
const alerts = ref<AlertItem[]>([]);
const digests = ref<DigestItem[]>([]);
const telegramChatId = ref('');
const maxTarget = ref('');
const error = ref('');
const loading = ref(false);
const total = ref(0);
const offset = ref(0);
const nextOffset = ref<number | null>(null);
const prevOffset = ref<number | null>(null);
const digestTotal = ref(0);
const digestOffset = ref(0);
const digestNextOffset = ref<number | null>(null);
const digestPrevOffset = ref<number | null>(null);
const activeView = ref<'alerts' | 'digests'>('alerts');
const activeDigestDomains = ref<string[]>([]);

const filters = reactive({
  search: '',
  feedback: '',
  limit: 30,
});

const activeChannels = computed(
  () => subs.value.filter((x) => String(x.status || '').toLowerCase() === 'active').length,
);
const activeTotal = computed(() => (activeView.value === 'alerts' ? total.value : digestTotal.value));
const activeOffset = computed(() => (activeView.value === 'alerts' ? offset.value : digestOffset.value));
const activeNextOffset = computed(() => (activeView.value === 'alerts' ? nextOffset.value : digestNextOffset.value));
const activePrevOffset = computed(() => (activeView.value === 'alerts' ? prevOffset.value : digestPrevOffset.value));
const searchPlaceholder = computed(() =>
  activeView.value === 'alerts' ? 'Поиск по домену, причине, типу' : 'Поиск по домену или каналу digest',
);

async function loadSettings() {
  const profile = await apiRequest<{ chat_id?: string | null }>('/v1/cabinet/profile');
  telegramChatId.value = profile.chat_id || '';

  const data = await apiRequest<{ items: Subscription[] }>('/v1/cabinet/subscriptions');
  subs.value = data.items || [];

  const max = subs.value.find((x) => String(x.channel_type || '').toLowerCase() === 'max');
  if (max?.channel_target) {
    maxTarget.value = max.channel_target;
  }
}

async function loadAlerts(targetOffset = offset.value) {
  loading.value = true;
  error.value = '';
  try {
    const params = new URLSearchParams({
      limit: String(Math.max(1, Math.min(100, Number(filters.limit) || 30))),
      offset: String(Math.max(0, targetOffset)),
    });
    if (filters.search) params.set('search', filters.search);
    if (filters.feedback) params.set('feedback', filters.feedback);
    if (activeDigestDomains.value.length > 0) {
      params.set('domains', activeDigestDomains.value.join(','));
    }
    const data = await apiRequest<{
      total: number;
      limit: number;
      offset: number;
      next_offset: number | null;
      prev_offset: number | null;
      items: AlertItem[];
    }>(`/v1/cabinet/alerts?${params.toString()}`);
    alerts.value = (data.items || []).map((item) => ({ ...item, explanation: item.explanation || {} }));
    total.value = data.total || 0;
    offset.value = data.offset || 0;
    nextOffset.value = data.next_offset;
    prevOffset.value = data.prev_offset;
  } catch (e) {
    error.value = String(e);
  } finally {
    loading.value = false;
  }
}

async function loadDigests(targetOffset = digestOffset.value) {
  loading.value = true;
  error.value = '';
  try {
    const params = new URLSearchParams({
      limit: String(Math.max(1, Math.min(100, Number(filters.limit) || 30))),
      offset: String(Math.max(0, targetOffset)),
    });
    if (filters.search) params.set('search', filters.search);
    const data = await apiRequest<{
      total: number;
      limit: number;
      offset: number;
      next_offset: number | null;
      prev_offset: number | null;
      items: DigestItem[];
    }>(`/v1/cabinet/digests?${params.toString()}`);
    digests.value = (data.items || []).map((item) => ({
      ...item,
      domains: item.domains || [],
      delivery: item.delivery || {},
    }));
    digestTotal.value = data.total || 0;
    digestOffset.value = data.offset || 0;
    digestNextOffset.value = data.next_offset;
    digestPrevOffset.value = data.prev_offset;
  } catch (e) {
    error.value = String(e);
  } finally {
    loading.value = false;
  }
}

async function loadCurrent(targetOffset = activeOffset.value) {
  if (activeView.value === 'digests') {
    await loadDigests(targetOffset);
    return;
  }
  await loadAlerts(targetOffset);
}

async function refreshAll() {
  error.value = '';
  try {
    await Promise.all([loadSettings(), loadAlerts(0), loadDigests(0)]);
  } catch (e) {
    error.value = String(e);
  }
}

async function switchView(view: 'alerts' | 'digests') {
  activeView.value = view;
  error.value = '';
  if (view === 'digests' && digests.value.length === 0 && digestTotal.value === 0) {
    await loadDigests(0);
  }
}

async function clearDigestFilter() {
  activeDigestDomains.value = [];
  await loadAlerts(0);
}

async function toggleTelegram(enabled: boolean) {
  error.value = '';
  try {
    const data = await apiRequest<{ items: Subscription[] }>('/v1/cabinet/subscriptions/telegram', {
      method: 'POST',
      body: JSON.stringify({ enabled, chat_id: telegramChatId.value || null }),
    });
    subs.value = data.items || [];
    await Promise.all([loadAlerts(0), loadDigests(0)]);
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
    await Promise.all([loadAlerts(0), loadDigests(0)]);
  } catch (e) {
    error.value = String(e);
  }
}

async function sendFeedback(item: AlertItem, feedbackType: 'more' | 'less' | 'never') {
  error.value = '';
  item.savingFeedback = feedbackType;
  try {
    const data = await apiRequest<{ feedback: AlertFeedback }>(`/v1/cabinet/alerts/${item.id}/feedback`, {
      method: 'POST',
      body: JSON.stringify({ feedback_type: feedbackType }),
    });
    item.latest_feedback = data.feedback;
    item.feedback_counts = {
      ...(item.feedback_counts || {}),
      [feedbackType]: (item.feedback_counts?.[feedbackType] || 0) + 1,
    };
    if (feedbackType === 'less' || feedbackType === 'never') {
      item.suppression_state = {
        active: true,
        reason: feedbackType === 'less' ? 'user_less' : 'user_never',
        created_at: data.feedback.created_at,
        expires_at: null,
      };
    }
  } catch (e) {
    error.value = String(e);
  } finally {
    item.savingFeedback = '';
  }
}

function formatDate(value?: string | null): string {
  if (!value) return '-';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function displayValue(value: unknown): string {
  if (value === null || value === undefined || value === '') return '-';
  return String(value);
}

function domainTld(domain: string): string {
  const parts = domain.split('.');
  return parts.length > 1 ? parts[parts.length - 1] : '-';
}

function shortAlertType(value: string): string {
  if (value.startsWith('watch_rule_match')) return 'watch';
  if (value.startsWith('monitor_match')) return 'monitor';
  if (value.startsWith('admin_fanout')) return 'admin';
  return value || 'alert';
}

function riskLabel(value?: string | null): string {
  if (value === 'provider_checked') return 'provider checked';
  if (value === 'provider_check_required') return 'needs provider check';
  return value || 'risk unknown';
}

function providerSourceText(item: AlertItem): string {
  const provider = item.provider || item.explanation.provider || 'heuristic';
  const status = item.provider_status || item.explanation.status || 'unknown';
  return `${provider} / ${status}`;
}

function providerConfidenceLabel(value?: string | null): string {
  if (value === 'provider_checked') return 'проверено провайдером';
  if (value === 'heuristic') return 'эвристика';
  if (value === 'stale') return 'устаревшая проверка';
  if (value === 'rate_limited') return 'провайдер ограничил запросы';
  return 'unknown';
}

function feedbackLabel(value?: string | null): string {
  if (value === 'more') return 'Больше таких';
  if (value === 'less') return 'Меньше таких';
  if (value === 'never') return 'Не повторять';
  if (value === 'why') return 'Открыто объяснение';
  return 'Еще нет';
}

function suppressionLabel(value?: string | null): string {
  if (value === 'user_less') return 'Скрыто: меньше таких';
  if (value === 'user_never') return 'Скрыто: не повторять домен';
  return 'Скрытие активно';
}

function suppressionActive(item: AlertItem, reason: string): boolean {
  const state = item.suppression_state;
  return Boolean(state?.active && state.reason === reason);
}

function pluralDomainSuffix(count: number): string {
  const value = Math.abs(Number(count) || 0);
  if (value % 10 === 1 && value % 100 !== 11) return '';
  if ([2, 3, 4].includes(value % 10) && ![12, 13, 14].includes(value % 100)) return 'а';
  return 'ов';
}

async function showDigestAlerts(item: DigestItem) {
  activeView.value = 'alerts';
  filters.feedback = '';
  filters.search = '';
  activeDigestDomains.value = [...item.domains];
  await loadAlerts(0);
}

function reasonText(item: AlertItem): string {
  const parts: string[] = [];
  const matchedQuery = item.explanation.matched_query;
  if (matchedQuery) parts.push(`совпало с watch-запросом "${matchedQuery}"`);
  if (item.explanation.score !== undefined && item.explanation.score !== null) {
    parts.push(`score ${item.explanation.score}`);
  }
  if (item.explanation.status) parts.push(`статус ${item.explanation.status}`);
  if (item.explanation.length) parts.push(`длина ${item.explanation.length}`);
  return parts.length ? parts.join(', ') : 'подходит под текущие правила мониторинга';
}

onMounted(refreshAll);
</script>

<style scoped>
.page-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}
.page-head h2 {
  margin: 0;
}
.page-head p {
  margin: 4px 0 0;
  color: var(--muted);
}
.settings-band,
.alerts-band {
  border-top: 1px solid var(--line);
  padding-top: 14px;
  margin-top: 14px;
}
.view-tabs {
  display: inline-flex;
  border: 1px solid var(--line);
  border-radius: 8px;
  overflow: hidden;
  margin-bottom: 10px;
  background: var(--surface-2);
}
.tab-button {
  border: 0;
  border-right: 1px solid var(--line);
  border-radius: 0;
  padding: 8px 14px;
  background: transparent;
  color: var(--muted);
  font-weight: 800;
}
.tab-button:last-child {
  border-right: 0;
}
.tab-button.active {
  background: #ffffff;
  color: #0f172a;
}
.settings-head,
.alert-main,
.alerts-meta,
.pager {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}
.settings-head h3 {
  margin: 0;
}
.settings-head span,
.muted {
  color: var(--muted);
}
.channel-row {
  display: grid;
  grid-template-columns: minmax(160px, 1fr) auto auto minmax(160px, 1fr) auto auto;
  gap: 8px;
  margin: 10px 0;
}
.subscription-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.subscription-chip,
.badge,
.chips span {
  border: 1px solid var(--line);
  background: var(--surface-2);
  border-radius: 8px;
  padding: 5px 8px;
  font-size: 13px;
  color: #334155;
}
.toolbar {
  display: grid;
  grid-template-columns: minmax(220px, 1fr) 180px 90px auto;
  gap: 8px;
  margin-bottom: 10px;
}
.active-filter {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: #fff8ed;
  color: #7c3d12;
  padding: 8px 10px;
  margin-bottom: 10px;
}
.active-filter span {
  overflow-wrap: anywhere;
}
.alerts-meta {
  justify-content: flex-start;
  margin-bottom: 10px;
  color: var(--muted);
}
.alert-list {
  display: grid;
  gap: 10px;
}
.alert-item,
.digest-item {
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--surface-2);
  padding: 12px;
}
.alert-title {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.alert-title strong {
  font-size: 18px;
}
.muted-badge {
  color: var(--muted);
}
.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}
.reason-grid {
  display: grid;
  grid-template-columns: 1.6fr 1fr 1fr;
  gap: 10px;
  margin-top: 12px;
}
.digest-grid {
  grid-template-columns: 1fr 1fr 1.6fr;
}
.reason-grid small {
  display: block;
  color: var(--muted);
  margin-bottom: 3px;
}
.reason-grid p {
  margin: 0;
}
.state-note {
  color: #8a4b12;
  font-size: 13px;
  margin-top: 5px !important;
}
.actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 12px;
}
.danger {
  border-color: #f3b7b7;
  color: #b42318;
}
.empty {
  color: var(--muted);
  margin: 8px 0;
}
.pager {
  justify-content: flex-end;
  margin-top: 12px;
}
.error {
  color: #b42318;
}
input,
select {
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 8px;
  min-width: 0;
}
button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
@media (max-width: 1200px) {
  .channel-row,
  .toolbar,
  .reason-grid {
    grid-template-columns: 1fr 1fr;
  }
}
@media (max-width: 720px) {
  .page-head,
  .alert-main,
  .settings-head,
  .pager {
    align-items: stretch;
    flex-direction: column;
  }
  .channel-row,
  .toolbar,
  .reason-grid {
    grid-template-columns: 1fr;
  }
}
</style>
