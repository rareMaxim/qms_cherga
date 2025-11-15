<template>
  <ErrorBoundary>
    <KioskView />
  </ErrorBoundary>
</template>

<script setup>
import ErrorBoundary from './components/ErrorBoundary.vue'
import KioskView from './views/KioskView.vue'
</script>
