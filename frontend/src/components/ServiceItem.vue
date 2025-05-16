<template>
    <div class="service-card bg-white rounded-xl shadow-lg text-center cursor-pointer flex flex-col items-center justify-center min-h-[200px] p-6 hover:transform hover:-translate-y-1 hover:shadow-xl"
        @click="selectService">
        <div v-if="service.icon"
            class="lucide-icon-placeholder w-12 h-12 mb-4 text-blue-600 flex items-center justify-center">
            <i :class="service.icon" style="font-size: 36px;"></i>
        </div>
        <h3 class="text-lg font-semibold text-slate-700 mb-1">{{ service.service_name }}</h3>
    </div>
</template>

<script setup>
import { defineProps, defineEmits } from 'vue';

const props = defineProps({
    service: {
        type: Object,
        required: true,
        default: () => ({
            name: '', // Раніше це був ID
            service_name: 'Невідома послуга',
            icon: '', // Клас іконки FontAwesome з API (наприклад, "fa-solid fa-baby-carriage")
            // icon_name: '', // Якщо б ми використовували назви іконок Lucide для unplugin-icons
            // description: '' // Якщо є опис
        })
    }
});

const emit = defineEmits(['service-selected']);

function selectService() {
    emit('service-selected', props.service);
}

// Допоміжна функція для unplugin-icons, якщо б використовували назви Lucide
// function toPascalCase(str) {
//   if (!str) return '';
//   return str.split('-').map(word => word.charAt(0).toUpperCase() + word.slice(1)).join('');
// }
</script>

<style scoped>
/* Стилі для service-card вже задані Tailwind класами в шаблоні. */
/* Додаткові стилі, якщо Tailwind не покриває все: */
.service-card {
    transition: transform 0.2s ease-in-out, box-shadow 0.2s ease-in-out;
    /* min-height тут і в класах Tailwind може дублюватися, оберіть один варіант */
}

/* .lucide-icon-placeholder i { */
/* Тут можна додати стилі, якщо потрібно для іконок FontAwesome, */
/* наприклад, для вирівнювання або розміру, хоча font-size: 36px вже є inline. */
/* } */
</style>