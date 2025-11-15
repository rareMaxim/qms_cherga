<template>
  <ErrorBoundary>
    <DisplayBoardView />
  </ErrorBoundary>
</template>

<script setup>
import ErrorBoundary from './components/ErrorBoundary.vue'
import DisplayBoardView from './views/DisplayBoardView.vue'
</script>
