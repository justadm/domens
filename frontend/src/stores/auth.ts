import { computed, ref } from 'vue';
import { defineStore } from 'pinia';
import type { AuthMeResponse, AuthUser, NavItem } from '@/types/auth';
import { apiRequest } from '@/services/api';

const BASE_MENU: NavItem[] = [
  { key: 'dashboard', label: 'Дашборд', to: '/lk' },
  { key: 'domains', label: 'Домены', to: '/lk/domens', requires: 'cabinet.read' },
  { key: 'orders', label: 'Заказы', to: '/lk/orders', requires: 'cabinet.read' },
  { key: 'watch', label: 'Watch-правила', to: '/lk/watch', requires: 'watch.manage' },
  { key: 'alerts', label: 'Алерты', to: '/lk/alerts', requires: 'alerts.manage' },
  { key: 'preferences', label: 'Настройки радара', to: '/lk/preferences', requires: 'alerts.manage' },
  { key: 'history', label: 'История', to: '/lk/history', requires: 'cabinet.read' },
  { key: 'admin', label: 'Админ', to: '/admin', requires: 'admin.panel.read' },
];

export const useAuthStore = defineStore('auth', () => {
  const loading = ref(false);
  const authenticated = ref(false);
  const user = ref<AuthUser | null>(null);

  const capabilities = computed(() => user.value?.capabilities || {});
  const permissions = computed(() => user.value?.permissions || []);

  function toCapabilityKey(code: string): string {
    return code.replace(/\./g, '_').replace(/-/g, '_').trim().toLowerCase();
  }

  function hasCapability(code: string | undefined): boolean {
    if (!code) return true;
    const raw = code.trim();
    const snake = toCapabilityKey(raw);
    return Boolean(
      capabilities.value[raw] ||
        capabilities.value[snake] ||
        permissions.value.includes(raw) ||
        permissions.value.includes(snake) ||
        (raw === 'admin.panel.read' && user.value?.is_admin),
    );
  }

  const menu = computed(() => BASE_MENU.filter((item) => hasCapability(item.requires)));

  async function fetchMe(): Promise<void> {
    loading.value = true;
    try {
      const me = await apiRequest<AuthMeResponse>('/v1/auth/me');
      authenticated.value = Boolean(me.authenticated && me.user);
      user.value = me.user;
    } finally {
      loading.value = false;
    }
  }

  async function logout(): Promise<void> {
    await apiRequest('/v1/auth/logout', { method: 'POST' });
    authenticated.value = false;
    user.value = null;
  }

  return {
    loading,
    authenticated,
    user,
    capabilities,
    menu,
    hasCapability,
    fetchMe,
    logout,
  };
});
