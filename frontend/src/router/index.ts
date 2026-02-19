import { createRouter, createWebHistory } from 'vue-router';
import { useAuthStore } from '@/stores/auth';
import AppShell from '@/layouts/AppShell.vue';
import LandingPage from '@/pages/LandingPage.vue';
import LkDashboardPage from '@/pages/LkDashboardPage.vue';
import LkWatchPage from '@/pages/LkWatchPage.vue';
import LkAlertsPage from '@/pages/LkAlertsPage.vue';
import LkRegistrationsPage from '@/pages/LkRegistrationsPage.vue';
import LkHistoryPage from '@/pages/LkHistoryPage.vue';
import LkDomainsPage from '@/pages/LkDomainsPage.vue';
import LkOrdersPage from '@/pages/LkOrdersPage.vue';
import AdminDashboardPage from '@/pages/AdminDashboardPage.vue';
import AdminUsersPage from '@/pages/AdminUsersPage.vue';
import AdminEventsPage from '@/pages/AdminEventsPage.vue';

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'landing', component: LandingPage },
    {
      path: '/lk',
      component: AppShell,
      meta: { requiresAuth: true },
      children: [
        { path: '', name: 'lk-dashboard', component: LkDashboardPage },
        { path: 'domens', name: 'lk-domens', component: LkDomainsPage, meta: { capability: 'cabinet.read' } },
        { path: 'orders', name: 'lk-orders', component: LkOrdersPage, meta: { capability: 'cabinet.read' } },
        { path: 'watch', name: 'lk-watch', component: LkWatchPage, meta: { capability: 'watch.manage' } },
        { path: 'alerts', name: 'lk-alerts', component: LkAlertsPage, meta: { capability: 'alerts.manage' } },
        {
          path: 'registrations',
          name: 'lk-registrations',
          component: LkRegistrationsPage,
          meta: { capability: 'copilot.register_domain' },
        },
        { path: 'history', name: 'lk-history', component: LkHistoryPage, meta: { capability: 'cabinet.read' } },
      ],
    },
    {
      path: '/admin',
      component: AppShell,
      meta: { requiresAuth: true, capability: 'admin.panel.read' },
      children: [
        { path: '', name: 'admin-dashboard', component: AdminDashboardPage },
        { path: 'users', name: 'admin-users', component: AdminUsersPage },
        { path: 'events', name: 'admin-events', component: AdminEventsPage },
      ],
    },
  ],
});

router.beforeEach(async (to) => {
  const auth = useAuthStore();
  if (!auth.user && !auth.loading) {
    try {
      await auth.fetchMe();
    } catch {
      // no-op
    }
  }

  if (to.meta.requiresAuth && !auth.authenticated) {
    return { name: 'landing' };
  }

  const capability = to.meta.capability as string | undefined;
  if (capability && !auth.hasCapability(capability)) {
    return { name: 'lk-dashboard' };
  }

  return true;
});
