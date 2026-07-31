import { createApp } from 'vue'
import PrimeVue from 'primevue/config'
import ToastService from 'primevue/toastservice'
import ConfirmationService from 'primevue/confirmationservice'

// The PrimeVue *theme* is NOT imported here — it is a swappable <link> in
// index.html (see src/theme.ts). Only the structural CSS is bundled.
import 'primevue/resources/primevue.min.css'
import 'primeicons/primeicons.css'
import '@fontsource-variable/inter'
import './styles.css'
// monacoEnvironment.ts is intentionally NOT imported here — it's pulled in
// lazily by CodeEditor.vue so Monaco never lands in the app's main chunk.

import App from './App.vue'
import router from './router'

const app = createApp(App)
app.use(PrimeVue)
app.use(ToastService)
app.use(ConfirmationService)
app.use(router)
app.mount('#app')
