<template>
  <div v-if="hasError" class="error-boundary min-h-screen flex items-center justify-center bg-red-50 p-4">
    <div class="max-w-md w-full bg-white shadow-lg rounded-lg p-6">
      <div class="flex items-center mb-4">
        <svg class="w-12 h-12 text-red-500 mr-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/>
        </svg>
        <h2 class="text-2xl font-bold text-gray-800">Помилка</h2>
      </div>

      <p class="text-gray-600 mb-4">
        Виникла несподівана помилка. Будь ласка, спробуйте оновити сторінку.
      </p>

      <div v-if="errorDetails && isDevelopment" class="mb-4 p-3 bg-gray-100 rounded text-sm text-gray-700 overflow-auto max-h-40">
        <p class="font-semibold mb-1">Деталі помилки:</p>
        <pre class="whitespace-pre-wrap">{{ errorDetails }}</pre>
      </div>

      <div class="flex gap-3">
        <button
          @click="reload"
          class="flex-1 bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-4 rounded transition-colors"
        >
          Оновити сторінку
        </button>
        <button
          v-if="canReset"
          @click="reset"
          class="flex-1 bg-gray-600 hover:bg-gray-700 text-white font-medium py-2 px-4 rounded transition-colors"
        >
          Спробувати знову
        </button>
      </div>
    </div>
  </div>

  <slot v-else></slot>
</template>

<script setup>
import { ref, onErrorCaptured } from 'vue'

const hasError = ref(false)
const errorDetails = ref('')
const isDevelopment = import.meta.env.DEV

const props = defineProps({
  canReset: {
    type: Boolean,
    default: true
  }
})

onErrorCaptured((err, instance, info) => {
  hasError.value = true

  // Формуємо деталі помилки
  errorDetails.value = `${err.message}\n\nStack: ${err.stack}\n\nInfo: ${info}`

  // Логуємо помилку в консоль
  console.error('Vue Error Boundary caught error:', err, info)

  // Відправляємо помилку на сервер (опціонально)
  if (!isDevelopment) {
    reportError(err, info)
  }

  // Запобігаємо поширенню помилки далі
  return false
})

function reload() {
  window.location.reload()
}

function reset() {
  hasError.value = false
  errorDetails.value = ''
}

function reportError(err, info) {
  // Тут можна відправити помилку на сервер для моніторингу
  try {
    fetch('/api/method/qms_cherga.api.log_client_error', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        error: err.message,
        stack: err.stack,
        info: info,
        url: window.location.href,
        userAgent: navigator.userAgent,
        timestamp: new Date().toISOString()
      })
    }).catch(() => {
      // Ігноруємо помилки при відправці логів
    })
  } catch (e) {
    // Ігноруємо помилки при спробі логування
  }
}
</script>

<style scoped>
.error-boundary {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
}
</style>
