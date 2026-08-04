<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute } from 'vue-router'
import Toast from 'primevue/toast'
import ConfirmDialog from 'primevue/confirmdialog'
import Sidebar from 'primevue/sidebar'
import Button from 'primevue/button'
import { useTheme } from './theme'

interface NavItem {
  label: string
  to: string
  icon: string
}

const navItems: NavItem[] = [
  { label: 'Models', to: '/models', icon: 'pi pi-code' },
  { label: 'Configurations', to: '/configurations', icon: 'pi pi-cog' },
  { label: 'Deployments', to: '/deployments', icon: 'pi pi-external-link' },
  { label: 'Training', to: '/results', icon: 'pi pi-check-square' },
  { label: 'Inference', to: '/inferences', icon: 'pi pi-sync' },
  { label: 'Datasources', to: '/datasources', icon: 'pi pi-book' },
  { label: 'Visualization', to: '/visualization', icon: 'pi pi-chart-line' },
  { label: 'IoT Devices', to: '/devices', icon: 'pi pi-wifi' }
]

const route = useRoute()
const mobileNavVisible = ref(false)
const { isDark, toggle } = useTheme()

// Sync <html>.dark with the persisted choice on first client render (the
// index.html boot script already applied it before paint; this just keeps
// the Vue-side `isDark` ref correct if it was set by the boot script).
onMounted(() => {
  isDark.value = document.documentElement.classList.contains('dark')
})

const currentLabel = computed(
  () => navItems.find((item) => route.path.startsWith(item.to))?.label ?? 'Kafka-ML'
)
</script>

<template>
  <div class="shell">
    <aside class="sidebar">
      <div class="brand">
        <span class="brand-mark">K</span>
        <span class="brand-text">Kafka-ML</span>
      </div>
      <nav class="sidenav">
        <router-link v-for="item in navItems" :key="item.to" :to="item.to" active-class="active">
          <i :class="item.icon"></i>
          <span>{{ item.label }}</span>
        </router-link>
      </nav>
      <div class="sidebar-footer">
        <button class="theme-toggle" type="button" @click="toggle" :title="isDark ? 'Switch to light' : 'Switch to dark'">
          <i :class="isDark ? 'pi pi-sun' : 'pi pi-moon'"></i>
          <span>{{ isDark ? 'Light mode' : 'Dark mode' }}</span>
        </button>
      </div>
    </aside>

    <div class="main-col">
      <header class="topbar">
        <Button
          class="menu-toggle p-button-text p-button-plain"
          icon="pi pi-bars"
          aria-label="Menu"
          @click="mobileNavVisible = true"
        />
        <span class="crumb">{{ currentLabel }}</span>
        <span class="spacer"></span>
        <Button
          class="p-button-text p-button-plain theme-toggle-compact"
          :icon="isDark ? 'pi pi-sun' : 'pi pi-moon'"
          aria-label="Toggle theme"
          @click="toggle"
        />
      </header>

      <main>
        <router-view />
      </main>
    </div>
  </div>

  <Sidebar v-model:visible="mobileNavVisible">
    <nav class="sidenav">
      <router-link
        v-for="item in navItems"
        :key="item.to"
        :to="item.to"
        active-class="active"
        @click="mobileNavVisible = false"
      >
        <i :class="item.icon"></i> {{ item.label }}
      </router-link>
    </nav>
  </Sidebar>

  <Toast position="bottom-center" />
  <ConfirmDialog />
</template>

<style scoped>
.shell {
  display: grid;
  grid-template-columns: var(--sidebar-w) 1fr;
  min-height: 100vh;
}

.sidebar {
  background: var(--surface-overlay, var(--surface-card));
  border-right: 1px solid var(--surface-border);
  display: flex;
  flex-direction: column;
  position: sticky;
  top: 0;
  height: 100vh;
}

.brand {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  padding: 1.15rem 1.25rem;
}

.brand-mark {
  width: 30px;
  height: 30px;
  border-radius: 9px;
  background: linear-gradient(135deg, var(--primary-color), var(--primary-600, var(--primary-color)));
  color: var(--primary-color-text, #fff);
  display: grid;
  place-items: center;
  font-weight: 800;
}

.brand-text {
  font-weight: 700;
  font-size: 1.05rem;
  letter-spacing: -0.01em;
}

.sidenav {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
  padding: 0.5rem 0.75rem;
  flex: 1;
}

.sidenav a {
  display: flex;
  align-items: center;
  gap: 0.7rem;
  padding: 0.62rem 0.75rem;
  color: var(--text-color-secondary);
  text-decoration: none;
  border-radius: var(--radius-md);
  font-size: 0.92rem;
  font-weight: 500;
}

.sidenav a i {
  font-size: 0.95rem;
  width: 1rem;
  text-align: center;
}

.sidenav a:hover {
  background: var(--surface-hover);
  color: var(--text-color);
}

.sidenav a.active {
  background: var(--primary-color);
  color: var(--primary-color-text, #fff);
}

.sidebar-footer {
  padding: 0.75rem;
  border-top: 1px solid var(--surface-border);
}

.theme-toggle {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  width: 100%;
  padding: 0.6rem 0.75rem;
  background: transparent;
  border: none;
  border-radius: var(--radius-md);
  color: var(--text-color-secondary);
  font: inherit;
  font-size: 0.88rem;
  cursor: pointer;
}

.theme-toggle:hover {
  background: var(--surface-hover);
  color: var(--text-color);
}

.main-col {
  min-width: 0;
}

.topbar {
  height: var(--topbar-h);
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0 1.25rem;
  border-bottom: 1px solid var(--surface-border);
  background: color-mix(in srgb, var(--surface-ground) 92%, transparent);
  backdrop-filter: blur(6px);
  position: sticky;
  top: 0;
  z-index: 5;
}

.crumb {
  font-weight: 600;
  font-size: 0.95rem;
}

.menu-toggle,
.theme-toggle-compact {
  display: none;
}

@media (max-width: 900px) {
  .shell {
    grid-template-columns: 1fr;
  }
  .sidebar {
    display: none;
  }
  .menu-toggle,
  .theme-toggle-compact {
    display: inline-flex;
  }
}
</style>
