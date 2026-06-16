<template>
  <main class="legal-page">
    <section class="legal-hero">
      <RouterLink class="back-link" to="/">← На главную</RouterLink>
      <p class="eyebrow">Закрытый пилот</p>
      <h1>Юридическая информация</h1>
      <p class="lead">
        Рабочий пакет для пилота Domens Radar. Перед публичным продвижением документы должны пройти
        юридическое ревью и получить финальные реквизиты оператора.
      </p>
    </section>

    <section class="legal-grid" aria-label="Legal documents">
      <article v-for="section in sections" :key="section.title" class="legal-section">
        <h2>{{ section.title }}</h2>
        <p class="section-note">{{ section.note }}</p>
        <ul>
          <li v-for="item in section.items" :key="item">{{ item }}</li>
        </ul>
      </article>
    </section>

    <section class="launch-gate">
      <h2>До публичного запуска нужно закрыть</h2>
      <div class="gate-list">
        <span v-for="item in gates" :key="item">{{ item }}</span>
      </div>
    </section>
  </main>
</template>

<script setup lang="ts">
import { RouterLink } from 'vue-router';

const sections = [
  {
    title: 'Privacy Policy',
    note: 'Какие данные обрабатываются в пилоте.',
    items: [
      'Telegram ID, chat ID, username, роли и настройки алертов.',
      'Watch-правила, alert history, feedback и suppressions.',
      'Audit logs для безопасности, delivery и monitoring events.',
      'Сроки хранения и список провайдеров нужно финализировать до публичного запуска.',
    ],
  },
  {
    title: 'Offer / Agreement',
    note: 'Правила использования сервиса.',
    items: [
      'Сервис дает подсказки и объяснимые алерты, но не гарантирует доступность домена.',
      'Регистрация только после явного подтверждения пользователя.',
      'DNS reserve или DNS-зона не считаются регистрацией домена.',
      'Платежные, refund и dispute-условия пока не финализированы.',
    ],
  },
  {
    title: 'Support & Disclaimer',
    note: 'Контакты и ограничения ответственности.',
    items: [
      'Support Telegram/email нужно заполнить перед публичным запуском.',
      'Пользователь сам проверяет trademark, бренд-риски, цену и правила TLD.',
      'Provider checks могут быть устаревшими или недоступными.',
      'В closed pilot возможны изменения scoring, limits и feedback behavior.',
    ],
  },
];

const gates = [
  'legal review',
  'operator details',
  'production support contacts',
  'retention periods',
  'provider/processor list',
  'registration launch approval',
];
</script>

<style scoped>
.legal-page {
  min-height: 100vh;
  padding: 32px;
}

.legal-hero {
  max-width: 980px;
  margin: 0 auto 24px;
}

.back-link {
  display: inline-flex;
  margin-bottom: 20px;
  color: var(--brand);
  font-weight: 800;
}

.eyebrow {
  margin: 0 0 8px;
  color: var(--brand);
  font-weight: 900;
  text-transform: uppercase;
  font-size: 13px;
}

h1 {
  margin: 0;
  font-size: 48px;
  line-height: 1;
}

.lead {
  max-width: 760px;
  color: var(--muted);
  font-size: 18px;
  line-height: 1.55;
}

.legal-grid {
  max-width: 980px;
  margin: 0 auto;
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}

.legal-section {
  border: 1px solid var(--line);
  background: var(--surface);
  border-radius: 10px;
  padding: 18px;
}

.legal-section h2 {
  margin: 0 0 8px;
  font-size: 22px;
}

.section-note {
  color: var(--muted);
  min-height: 48px;
}

.legal-section ul {
  padding-left: 18px;
  line-height: 1.55;
}

.legal-section li + li {
  margin-top: 8px;
}

.launch-gate {
  max-width: 980px;
  margin: 18px auto 0;
  border: 1px solid var(--line);
  background: var(--surface-2);
  border-radius: 10px;
  padding: 18px;
}

.launch-gate h2 {
  margin: 0 0 12px;
  font-size: 22px;
}

.gate-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.gate-list span {
  border: 1px solid #c9d5ea;
  background: #fff;
  border-radius: 999px;
  padding: 7px 10px;
  color: #2a4065;
  font-weight: 800;
}

@media (max-width: 860px) {
  .legal-page {
    padding: 20px;
  }

  h1 {
    font-size: 36px;
  }

  .legal-grid {
    grid-template-columns: 1fr;
  }

  .section-note {
    min-height: 0;
  }
}
</style>
