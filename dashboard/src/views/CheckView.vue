<script setup>
import { computed, reactive, ref } from 'vue'
import { api } from '../api'
import { blankOrder, presets, STATES, toPayload } from '../presets'
import { featureLabel, pct, t } from '../i18n'
import ScoreRing from '../components/ScoreRing.vue'
import BarList from '../components/BarList.vue'

const form = reactive(blankOrder())
const activePreset = ref('rio')
const loading = ref(false)
const error = ref('')
const result = ref(null)

function applyPreset(p) {
  Object.assign(form, blankOrder(), p.patch)
  activePreset.value = p.id
}

async function submit() {
  loading.value = true
  error.value = ''
  try {
    result.value = await api.predict(toPayload(form))
  } catch (e) {
    result.value = null
    error.value = e.code === 'network' ? t('errNetwork') : e.code === 503 ? t('errModel') : e.message
  } finally {
    loading.value = false
  }
}

const reasonRows = computed(() =>
  (result.value?.reasons ?? []).map((r) => ({
    key: r.feature,
    label: featureLabel(r.feature, r.label),
    sub: r.value ? String(r.value) : '',
    size: r.impact,
    tone: r.direction,
  })),
)
const paymentTypes = ['credit_card', 'boleto', 'voucher', 'debit_card']
</script>

<template>
  <div class="layout">
    <form class="card form" @submit.prevent="submit">
      <div class="presets" role="group" :aria-label="t('quickFill')">
        <span class="muted">{{ t('quickFill') }}</span>
        <button
          v-for="p in presets"
          :key="p.id"
          type="button"
          class="chip-btn"
          :aria-pressed="activePreset === p.id"
          @click="applyPreset(p)"
        >
          {{ t('ex_' + p.id) }}
        </button>
      </div>

      <fieldset>
        <legend>{{ t('secRoute') }}</legend>
        <div class="grid">
          <div class="field">
            <label for="ss">{{ t('sellerState') }}</label>
            <select id="ss" v-model="form.seller_state">
              <option v-for="s in STATES" :key="s">{{ s }}</option>
            </select>
          </div>
          <div class="field">
            <label for="sz">{{ t('sellerZip') }}</label>
            <input id="sz" v-model.number="form.seller_zip_code_prefix" type="number" min="1000" max="99999" required />
          </div>
          <div class="field">
            <label for="cs">{{ t('customerState') }}</label>
            <select id="cs" v-model="form.customer_state">
              <option v-for="s in STATES" :key="s">{{ s }}</option>
            </select>
          </div>
          <div class="field">
            <label for="cz">{{ t('customerZip') }}</label>
            <input id="cz" v-model.number="form.customer_zip_code_prefix" type="number" min="1000" max="99999" required />
          </div>
          <div class="field wide">
            <label for="sid">{{ t('sellerId') }}</label>
            <input id="sid" v-model="form.seller_id" type="text" autocomplete="off" />
            <span class="hint">{{ t('sellerIdHint') }}</span>
          </div>
        </div>
      </fieldset>

      <fieldset>
        <legend>{{ t('secTiming') }}</legend>
        <div class="grid">
          <div class="field">
            <label for="pu">{{ t('purchase') }}</label>
            <input id="pu" v-model="form.purchase" type="datetime-local" required />
          </div>
          <div class="field">
            <label for="pr">{{ t('promised') }}</label>
            <input id="pr" v-model="form.promised" type="date" required />
          </div>
        </div>
      </fieldset>

      <fieldset>
        <legend>{{ t('secBasket') }}</legend>
        <div class="grid">
          <div class="field">
            <label for="it">{{ t('items') }}</label>
            <input id="it" v-model.number="form.total_items" type="number" min="1" required />
          </div>
          <div class="field">
            <label for="pc">{{ t('price') }}</label>
            <input id="pc" v-model.number="form.total_item_price" type="number" min="0" step="0.01" required />
          </div>
          <div class="field">
            <label for="fr">{{ t('freight') }}</label>
            <input id="fr" v-model.number="form.total_freight" type="number" min="0" step="0.01" required />
          </div>
          <div class="field">
            <label for="wg">{{ t('weight') }}</label>
            <input id="wg" v-model="form.avg_product_weight_g" type="number" min="0" />
          </div>
          <div class="field">
            <label for="vo">{{ t('volume') }}</label>
            <input id="vo" v-model="form.avg_volume_cm3" type="number" min="0" />
          </div>
        </div>
      </fieldset>

      <fieldset>
        <legend>{{ t('secPayment') }}</legend>
        <div class="grid">
          <div class="field">
            <label for="pt">{{ t('paymentType') }}</label>
            <select id="pt" v-model="form.payment_type">
              <option v-for="p in paymentTypes" :key="p" :value="p">{{ t(p) }}</option>
            </select>
          </div>
          <div class="field">
            <label for="in">{{ t('installments') }}</label>
            <input id="in" v-model.number="form.max_installments" type="number" min="0" max="36" required />
          </div>
        </div>
      </fieldset>

      <button class="btn" type="submit" :disabled="loading">
        {{ loading ? t('checking') : t('checkRisk') }}
      </button>
    </form>

    <section class="card result" aria-live="polite">
      <ScoreRing :value="result ? result.probability : null" :level="result ? result.risk_level : null" />

      <p v-if="error" class="error" role="alert">{{ error }}</p>

      <p v-else-if="!result" class="muted empty">{{ t('resultEmpty') }}</p>

      <template v-else>
        <div class="verdict">
          <span class="chip" :class="result.risk_level">{{ t('level_' + result.risk_level) }}</span>
          <p class="advice">{{ t('advice_' + result.risk_level) }}</p>
          <p class="hint">{{ t('flagThreshold', { t: pct(result.threshold) }) }}</p>
        </div>
        <h2>{{ t('whyTitle') }}</h2>
        <BarList :rows="reasonRows" />
        <p class="hint logged">{{ t('loggedNote') }}</p>
      </template>
    </section>
  </div>
</template>

<style scoped>
.layout {
  display: grid;
  gap: 1.75rem;
  align-items: start;
}
@media (min-width: 980px) {
  .layout {
    grid-template-columns: 1.3fr 1fr;
  }
  .result {
    position: sticky;
    top: 1.25rem;
  }
}
.form {
  display: grid;
  gap: 1.25rem;
}
.presets {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem;
}
fieldset {
  border: 0;
  padding: 0;
  margin: 0;
}
legend {
  font-family: var(--font-display);
  font-size: 1.1rem;
  margin-bottom: 0.6rem;
  padding: 0;
}
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
  gap: 0.8rem;
}
.wide {
  grid-column: 1 / -1;
}
.btn {
  justify-self: start;
}
.verdict {
  text-align: center;
  margin: 0.6rem 0 1.4rem;
}
.advice {
  margin: 0.5rem 0 0.25rem;
  font-weight: 600;
}
.empty {
  text-align: center;
  margin: 0.5rem auto 0;
  max-width: 28ch;
}
.error {
  background: var(--petal);
  border: 2px solid var(--berry);
  border-radius: var(--radius-field);
  padding: 0.7rem 0.9rem;
  margin: 1rem 0 0;
  font-weight: 600;
  overflow-wrap: anywhere;
}
.logged {
  margin-top: 1.25rem;
}
</style>
