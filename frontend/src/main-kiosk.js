// frontend/src/main-kiosk.js
import { createApp } from 'vue'
import AppKiosk from './AppKiosk.vue'
import './style.css' // Ваш основний CSS (з Tailwind)

const app = createApp(AppKiosk)

app.mount('#app-kiosk')
