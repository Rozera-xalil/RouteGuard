<script setup>
import { computed } from 'vue'
import { t } from '../i18n'

// rows: [{ key, label, sub?, size (number), tone: 'raises' | 'lowers' | 'plain' }]
const props = defineProps({ rows: { type: Array, required: true } })
const max = computed(() => Math.max(...props.rows.map((r) => Math.abs(r.size)), 1e-9))
</script>

<template>
  <ul class="bars">
    <li v-for="r in rows" :key="r.key">
      <div class="top">
        <span class="name">{{ r.label }}</span>
        <span v-if="r.tone !== 'plain'" class="dir" :class="r.tone">{{ t(r.tone) }}</span>
        <span v-else-if="r.valueText" class="val">{{ r.valueText }}</span>
      </div>
      <div v-if="r.sub" class="hint">{{ r.sub }}</div>
      <div class="track">
        <div class="fill" :class="r.tone" :style="{ width: (Math.abs(r.size) / max) * 100 + '%' }" />
      </div>
    </li>
  </ul>
</template>

<style scoped>
.bars {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 0.85rem;
}
.top {
  display: flex;
  justify-content: space-between;
  gap: 0.75rem;
  font-weight: 700;
  font-size: 0.95rem;
}
.dir {
  font-size: 0.8rem;
  white-space: nowrap;
}
.dir.raises {
  color: var(--berry);
}
.dir.lowers {
  color: var(--mint-deep);
}
.val {
  font-family: var(--font-display);
  color: var(--cocoa-soft);
}
.track {
  height: 12px;
  border-radius: 999px;
  background: var(--petal);
  margin-top: 0.3rem;
  overflow: hidden;
}
.fill {
  height: 100%;
  border-radius: 999px;
  background: var(--peony);
  transition: width 0.6s ease;
}
.fill.raises {
  background: var(--berry);
}
.fill.lowers {
  background: #4fbf9a;
}
</style>
