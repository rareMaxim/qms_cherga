<template>
    <div id="qms-app-container" class="font-sans bg-slate-100 min-h-screen flex flex-col items-center p-4">
        <main class="w-full">
            <KioskView />
        </main>

        <footer class="mt-auto pt-8 text-center text-slate-500 text-sm">
            <p>&copy; <span id="currentYear">{{ new Date().getFullYear() }}</span> Всі права захищено.</p>
        </footer>
    </div>
</template>

<script setup>
import KioskView from './views/KioskView.vue';
// Логіка для App.vue, якщо потрібна
</script>

<style scoped>
/* Стилі з body перенесено сюди, щоб ізолювати їх для Vue-додатку */
#qms-app-container {
    font-family: 'Inter', sans-serif;
    /* Задається через клас Tailwind 'font-sans' */
    background-color: #f0f4f8;
    /* bg-slate-100 або інший відповідник Tailwind */
    /* min-height: 100vh; */
    /* min-h-screen від Tailwind */
    /* display: flex; flex-direction: column; align-items: center; */
    /* flex flex-col items-center від Tailwind */
    /* padding: 1rem; */
    /* p-4 від Tailwind */
}

/* Можна видалити ці стилі, якщо Tailwind-класи застосовані правильно */
</style>