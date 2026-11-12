<script setup>
import { ref } from 'vue'
import { t, toggleLang } from './i18n'
import CheckView from './views/CheckView.vue'
import WatchView from './views/WatchView.vue'
import AboutView from './views/AboutView.vue'

const tabs = [
  { id: 'check', label: 'tabCheck', view: CheckView },
  { id: 'watch', label: 'tabWatch', view: WatchView },
  { id: 'about', label: 'tabAbout', view: AboutView },
]
const current = ref('check')
const viewOf = (id) => tabs.find((x) => x.id === id).view
</script>

<template>
  <div class="shell">
    <header>
      <div class="brand">
        <svg viewBox="0 0 48 48" width="46" height="46" aria-hidden="true">
          <rect width="48" height="48" rx="14" fill="#ffdce8" />
          <path d="M24 26c-8-9-14-5-11 1.5S24 31 24 26zm0 0c8-9 14-5 11 1.5S24 31 24 26z" fill="#c92c66" />
          <circle cx="24" cy="26" r="3.6" fill="#4a2238" />
        </svg>
        <div>
          <h1>{{ t('appName') }}</h1>
          <p class="tag">{{ t('tagline') }}</p>
        </div>
      </div>

      <nav role="tablist" class="tabs">
        <button
          v-for="tab in tabs"
          :id="'tab-' + tab.id"
          :key="tab.id"
          role="tab"
          :aria-selected="current === tab.id"
          :aria-controls="'panel-' + tab.id"
          @click="current = tab.id"
        >
          {{ t(tab.label) }}
        </button>
      </nav>

      <button class="lang" type="button" @click="toggleLang">{{ t('langSwitch') }}</button>
    </header>

    <main :id="'panel-' + current" role="tabpanel" :aria-labelledby="'tab-' + current">
      <KeepAlive>
        <component :is="viewOf(current)" />
      </KeepAlive>
    </main>
  </div>
</template>

<style scoped>
.shell {
  max-width: 1180px;
  margin: 0 auto;
  padding: 1.5rem clamp(1rem, 3vw, 2rem) 4rem;
}
header {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 1rem 1.5rem;
  margin-bottom: 2rem;
}
.brand {
  display: flex;
  align-items: center;
  gap: 0.8rem;
  margin-inline-end: auto;
}
h1 {
  font-size: 1.9rem;
  font-weight: 600;
  color: var(--berry);
}
.tag {
  margin: 0;
  font-weight: 700;
  color: var(--cocoa-soft);
}
.tabs {
  display: flex;
  gap: 0.35rem;
  padding: 0.3rem;
  background: var(--white);
  border: 2px solid var(--petal-deep);
  border-radius: 999px;
  flex-wrap: wrap;
}
.tabs button {
  border: 0;
  background: transparent;
  cursor: pointer;
  border-radius: 999px;
  padding: 0.5rem 1.1rem;
  font-weight: 700;
}
.tabs button:hover {
  background: var(--petal);
}
.tabs button[aria-selected='true'] {
  background: var(--berry);
  color: var(--white);
}
.lang {
  border: 2px solid var(--petal-deep);
  background: var(--white);
  border-radius: 999px;
  padding: 0.45rem 1rem;
  font-weight: 700;
  cursor: pointer;
}
.lang:hover {
  background: var(--petal);
}
</style>
