<script setup>
import { computed } from 'vue'
import { t, pct } from '../i18n'

const props = defineProps({
  value: { type: Number, default: null },
  level: { type: String, default: null },
})

const R = 92
const C = 2 * Math.PI * R
const COLORS = { low: '#4fbf9a', medium: '#ff9f5a', high: '#c92c66' }

const color = computed(() => COLORS[props.level] ?? '#f6b8cf')
const offset = computed(() => C * (1 - (props.value ?? 0)))
const label = computed(() =>
  props.value === null ? t('resultEmpty') : `${pct(props.value)} ${t('chanceLate')}`,
)
</script>

<template>
  <!-- The ring is a gift ribbon: it fills as the risk grows, and the bow takes the risk colour. -->
  <svg class="ring" viewBox="0 0 240 250" role="img" :aria-label="label">
    <circle cx="120" cy="136" :r="R" fill="none" stroke="#ffdce8" stroke-width="20" />
    <circle
      class="arc"
      cx="120"
      cy="136"
      :r="R"
      fill="none"
      :stroke="color"
      stroke-width="20"
      stroke-linecap="round"
      :stroke-dasharray="C"
      :stroke-dashoffset="offset"
      transform="rotate(-90 120 136)"
    />
    <g transform="translate(120 44)" :fill="color" stroke="#fff" stroke-width="3" stroke-linejoin="round">
      <path d="M-2 6 L-17 32 L-8 29 L-2 40 Z" />
      <path d="M2 6 L17 32 L8 29 L2 40 Z" />
      <path d="M0 0 C-14 -26 -48 -26 -46 -3 C-44 20 -14 13 0 0 Z" />
      <path d="M0 0 C14 -26 48 -26 46 -3 C44 20 14 13 0 0 Z" />
      <circle r="8" />
    </g>
    <g text-anchor="middle">
      <text v-if="value !== null" x="120" y="150" class="big">{{ pct(value) }}</text>
      <text v-else x="120" y="150" class="big dim">–</text>
      <text v-if="value !== null" x="120" y="178" class="small">{{ t('chanceLate') }}</text>
    </g>
  </svg>
</template>

<style scoped>
.ring {
  width: min(100%, 260px);
  display: block;
  margin-inline: auto;
}
.arc {
  transition: stroke-dashoffset 0.9s cubic-bezier(0.3, 0.8, 0.3, 1), stroke 0.4s;
}
.big {
  font-family: var(--font-display);
  font-weight: 600;
  font-size: 54px;
  fill: var(--cocoa);
}
.big.dim {
  fill: var(--petal-deep);
}
.small {
  font-family: var(--font-body);
  font-weight: 700;
  font-size: 14px;
  fill: var(--cocoa-soft);
}
</style>
