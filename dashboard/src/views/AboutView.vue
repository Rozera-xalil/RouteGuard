<script setup>
import { computed, onActivated, ref } from 'vue'
import { api } from '../api'
import { featureLabel, lang, pct, t } from '../i18n'
import BarList from '../components/BarList.vue'

const info = ref(null)
const error = ref('')

onActivated(async () => {
  if (info.value) return
  try {
    info.value = await api.info()
    error.value = ''
  } catch (e) {
    error.value = e.code === 'network' ? t('errNetwork') : e.code === 503 ? t('errModel') : e.message
  }
})

const m = computed(() => info.value?.metrics ?? {})
const caught = computed(() => Math.round((m.value.recall_at_threshold ?? 0) * 10))
const times = computed(() =>
  m.value['recall_at_naive_0.5'] > 0 ? (m.value.recall_at_threshold / m.value['recall_at_naive_0.5']).toFixed(1) : null,
)
const trained = computed(() =>
  info.value?.trained_at
    ? new Date(info.value.trained_at).toLocaleDateString(lang.value === 'ar' ? 'ar' : undefined, {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
      })
    : '',
)
const tiles = computed(() => [
  { k: 'm_pr_auc', v: m.value.pr_auc?.toFixed(3), n: t('m_pr_auc_n', { b: m.value.base_rate?.toFixed(3) }) },
  { k: 'm_roc_auc', v: m.value.roc_auc?.toFixed(3), n: t('m_roc_auc_n') },
  {
    k: 'm_brier',
    v: m.value.brier_calibrated?.toFixed(3),
    n: t('m_brier_n', { r: m.value.brier_raw?.toFixed(3) }),
  },
  { k: 'm_base', v: pct(m.value.base_rate, 1), n: t('m_base_n') },
])
const drivers = computed(() =>
  (info.value?.top_drivers ?? []).slice(0, 8).map((d) => ({
    key: d.feature,
    label: featureLabel(d.feature, d.label),
    size: d.share,
    tone: 'plain',
    valueText: pct(d.share, 1),
  })),
)
</script>

<template>
  <p v-if="error" class="card error" role="alert">{{ error }}</p>
  <p v-else-if="!info" class="muted">{{ t('loading') }}</p>

  <div v-else class="stack">
    <section class="card lead">
      <h2>{{ t('aboutTitle') }}</h2>
      <p class="big">{{ t('catchLine', { n: caught }) }}</p>
      <p v-if="times">{{ t('catchMore', { x: times }) }}</p>
      <p>{{ t('flagShare', { p: pct(m.flagged_share) }) }}</p>
      <p>{{ t('liftLine', { x: m.lift_at_10pct?.toFixed(1) }) }}</p>
      <p class="hint">
        {{ t('version', { v: info.model_version }) }} · {{ t('trained', { d: trained }) }}
      </p>
    </section>

    <div class="tiles">
      <section v-for="x in tiles" :key="x.k" class="card tile">
        <span class="label">{{ t(x.k) }}</span>
        <strong>{{ x.v }}</strong>
        <span class="hint">{{ x.n }}</span>
      </section>
    </div>

    <section class="card">
      <h2>{{ t('driversTitle') }}</h2>
      <BarList :rows="drivers" />
      <p class="hint note">{{ t('costNote', { a: info.decision_costs.cost_missed_late / info.decision_costs.cost_false_alarm }) }}</p>
    </section>
  </div>
</template>

<style scoped>
.stack {
  display: grid;
  gap: 1.75rem;
  max-width: 880px;
}
.lead p {
  margin: 0.35rem 0;
}
.big {
  font-family: var(--font-display);
  font-size: 1.6rem;
  line-height: 1.3;
}
.tiles {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
  gap: 1.5rem;
}
.tile {
  display: grid;
  gap: 0.2rem;
  align-content: start;
}
.tile strong {
  font-family: var(--font-display);
  font-size: 2.3rem;
  font-weight: 500;
  line-height: 1.1;
}
.label {
  font-weight: 700;
}
.note {
  margin-top: 1.1rem;
}
.error {
  border-color: var(--berry);
  font-weight: 600;
}
</style>
