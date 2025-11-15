<template>
  <ErrorBoundary>
    <OperatorDashboardView />
  </ErrorBoundary>
</template>

<script setup>
import ErrorBoundary from './components/ErrorBoundary.vue'
import OperatorDashboardView from './views/OperatorDashboardView.vue'
</script>
