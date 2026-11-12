<script setup>
import { computed, onActivated, onDeactivated, ref } from 'vue'
import { api } from '../api'
import { featureLabel, lang, pct, t } from '../i18n'
import BarList from '../components/BarList.vue'

const summary = ref(null)
const recent = ref([])
const error = ref('')
const saving = ref('')
let timer = null

async function load() {
  try {
    const [s, r] = await Promise.all([api.summary(), api.recent(8)])
    summary.value = s
    recent.value = r
    error.value = ''
  } catch (e) {
    error.value = e.code === 'network' ? t('errNetwork') : e.code === 503 ? t('errModel') : e.message
  }
}

onActivated(() => {
  load()
  timer = setInterval(load, 15000)
})
onDeactivated(() => clearInterval(timer))

async function report(row, actualLate) {
  saving.value = row.id
  try {
    await api.feedback(row.id, actualLate)
    await load()
  } catch (e) {
    error.value = e.message
  } finally {
    saving.value = ''
  }
}

const drift = computed(() => summary.value?.drift ?? null)
const perf = computed(() => summary.value?.live_performance ?? { n_labeled: 0 })
const volume = computed(() => summary.value?.volume ?? { total: 0, last_24h: 0, last_24h_by_risk: {} })

const driftRows = computed(() =>
  (drift.value?.features ?? []).slice(0, 8).map((f) => ({
    key: f.feature,
    label: featureLabel(f.feature, f.feature),
    size: f.psi,
    tone: 'plain',
    valueText: f.psi.toFixed(2),
  })),
)

const riskParts = computed(() => {
  const by = volume.value.last_24h_by_risk
  const total = Object.values(by).reduce((a, b) => a + b, 0)
  return ['low', 'medium', 'high']
    .filter((k) => by[k])
    .map((k) => ({ k, n: by[k], w: (by[k] / total) * 100 }))
})

const perfTiles = computed(() => [
  ['precision', perf.value.precision],
  ['recall', perf.value.recall],
  ['lateRate', perf.value.late_rate],
])

const when = (iso) =>
  new Date(iso).toLocaleString(lang.value === 'ar' ? 'ar' : undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
</script>

<template>
  <p v-if="error" class="error card" role="alert">{{ error }}</p>
  <p v-if="!summary && !error" class="muted">{{ t('loading') }}</p>

  <div v-if="summary" class="wall">
    <section class="card">
      <h2>{{ t('trafficTitle') }}</h2>
      <template v-if="volume.total">
        <div class="nums">
          <div>
            <strong>{{ volume.total }}</strong>
            <span class="muted">{{ t('total') }}</span>
          </div>
          <div>
            <strong>{{ volume.last_24h }}</strong>
            <span class="muted">{{ t('last24') }}</span>
          </div>
        </div>
        <div v-if="riskParts.length" class="stack" role="img" :aria-label="riskParts.map((p) => `${t('level_' + p.k)}: ${p.n}`).join(', ')">
          <span v-for="p in riskParts" :key="p.k" :class="p.k" :style="{ width: p.w + '%' }" />
        </div>
        <ul v-if="riskParts.length" class="legend">
          <li v-for="p in riskParts" :key="p.k">
            <span class="chip" :class="p.k">{{ t('level_' + p.k) }}</span> {{ p.n }}
          </li>
        </ul>
      </template>
      <p v-else class="muted">{{ t('noTraffic') }}</p>
    </section>

    <section class="card">
      <h2>{{ t('driftTitle') }}</h2>
      <span class="chip" :class="drift.status">{{ t('drift_' + drift.status) }}</span>
      <p class="hint help">{{ t('driftHelp') }}</p>
      <p v-if="drift.status === 'insufficient_data'" class="muted">
        {{ t('driftNeed', { n: drift.rows ?? 0, m: drift.min_rows }) }}
      </p>
      <BarList v-else :rows="driftRows" />
    </section>

    <section class="card">
      <h2>{{ t('perfTitle') }}</h2>
      <p v-if="!perf.n_labeled" class="muted">{{ t('perfEmpty') }}</p>
      <template v-else>
        <div class="tiles">
          <div v-for="[k, v] in perfTiles" :key="k" class="tile">
            <strong>{{ v === null || v === undefined ? '-' : pct(v) }}</strong>
            <span>{{ t(k) }}</span>
          </div>
          <div class="tile">
            <strong>{{ perf.brier }}</strong>
            <span>{{ t('brier') }}</span>
          </div>
        </div>
        <p class="hint">{{ t('perfN', { n: perf.n_labeled }) }}</p>
      </template>
    </section>

    <section class="card recent">
      <h2>{{ t('recentTitle') }}</h2>
      <p v-if="!recent.length" class="muted">{{ t('recentEmpty') }}</p>
      <ul v-else class="rows">
        <li v-for="r in recent" :key="r.id">
          <span class="route">{{ r.seller_state }} → {{ r.customer_state }}</span>
          <span class="muted time">{{ when(r.ts) }}</span>
          <span class="chip" :class="r.risk_level">{{ pct(r.probability) }}</span>
          <span class="actions">
            <span v-if="r.actual_late !== null" class="chip" :class="r.actual_late ? 'high' : 'low'">
              {{ r.actual_late ? t('wasLate') : t('wasOnTime') }}
            </span>
            <template v-else>
              <button class="chip-btn" :disabled="saving === r.id" @click="report(r, false)">{{ t('onTime') }}</button>
              <button class="chip-btn" :disabled="saving === r.id" @click="report(r, true)">{{ t('late') }}</button>
            </template>
          </span>
        </li>
      </ul>
      <p class="hint">{{ t('refreshed') }}</p>
    </section>
  </div>
</template>

<style scoped>
.wall {
  display: grid;
  gap: 1.75rem;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 340px), 1fr));
  align-items: start;
}
.recent {
  grid-column: 1 / -1;
}
.nums {
  display: flex;
  gap: 2rem;
  margin-bottom: 1rem;
}
.nums strong,
.tile strong {
  display: block;
  font-family: var(--font-display);
  font-size: 2.2rem;
  font-weight: 500;
  line-height: 1.1;
}
.stack {
  display: flex;
  height: 16px;
  border-radius: 999px;
  overflow: hidden;
  background: var(--petal);
}
.stack .low {
  background: #4fbf9a;
}
.stack .medium {
  background: #ff9f5a;
}
.stack .high {
  background: var(--berry);
}
.legend {
  list-style: none;
  display: flex;
  flex-wrap: wrap;
  gap: 0.6rem 1.2rem;
  padding: 0;
  margin: 0.8rem 0 0;
  font-weight: 700;
}
.help {
  margin: 0.5rem 0 1rem;
}
.tiles {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 1rem;
  margin-bottom: 0.75rem;
}
.tile span {
  font-size: 0.85rem;
  color: var(--cocoa-soft);
  font-weight: 600;
}
.rows {
  list-style: none;
  padding: 0;
  margin: 0 0 0.8rem;
  display: grid;
}
.rows li {
  display: grid;
  grid-template-columns: 5.5rem 1fr auto auto;
  align-items: center;
  gap: 0.75rem;
  padding: 0.65rem 0;
  border-bottom: 2px dotted var(--petal);
}
.rows li:last-child {
  border-bottom: 0;
}
.route {
  font-family: var(--font-display);
}
.actions {
  display: flex;
  gap: 0.4rem;
  flex-wrap: wrap;
  justify-content: flex-end;
}
@media (max-width: 640px) {
  .rows li {
    grid-template-columns: 1fr auto;
  }
  .time {
    display: none;
  }
  .actions {
    grid-column: 1 / -1;
    justify-content: flex-start;
  }
}
.error {
  border-color: var(--berry);
  font-weight: 600;
  margin-bottom: 1.25rem;
}
</style>
