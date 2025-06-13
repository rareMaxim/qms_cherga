<template>
    <div class="operator-dashboard bg-slate-100 min-h-screen font-sans p-4">
        <header class="bg-white p-4 rounded-lg shadow-md mb-4 flex justify-between items-center">
            <div>
                <h1 class="text-2xl font-bold text-slate-800">{{ operatorInfo.full_name || 'Завантаження...' }}</h1>
                <p class="text-slate-600">{{ operatorInfo.office_name || 'Офіс не визначено' }}</p>
            </div>
            <div class="flex items-center gap-4">
                <div class="relative">
                    <select v-model="selectedServicePoint" class="p-2 border rounded-md appearance-none bg-white pr-8">
                        <option :value="null" disabled>Оберіть точку обслуговування</option>
                        <option v-for="point in servicePoints" :key="point.name" :value="point.name">
                            {{ point.point_name }}
                        </option>
                    </select>
                </div>
                <button @click="callNext" :disabled="!selectedServicePoint || loading"
                    class="bg-blue-600 text-white font-bold py-2 px-4 rounded-lg hover:bg-blue-700 disabled:bg-slate-400">
                    Викликати наступного
                </button>
            </div>
        </header>

        <div v-if="error" class="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded relative mb-4"
            role="alert">
            <strong class="font-bold">Помилка!</strong>
            <span class="block sm:inline">{{ error }}</span>
        </div>

        <main class="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <div class="lg:col-span-2">
                <div class="bg-white p-6 rounded-lg shadow-md">
                    <h2 class="text-xl font-semibold mb-4 text-slate-700">Поточне обслуговування</h2>
                    <div v-if="loading" class="text-center py-8">
                        <p>Оновлення даних...</p>
                    </div>
                    <div v-else-if="activeTicket"
                        class="active-ticket-card bg-sky-50 p-6 rounded-lg border border-sky-200">
                        <p class="text-5xl font-extrabold text-sky-800 text-center mb-2">{{ activeTicket.ticket_number
                        }}</p>
                        <p class="text-lg text-slate-700 text-center mb-4">{{ activeTicket.service_name }}</p>
                        <div class="text-sm text-slate-600 text-center">
                            <p>Статус: <span class="font-semibold" :class="statusColor(activeTicket.status)">{{
                                activeTicket.status }}</span></p>
                            <p>Час виклику: {{ formatTime(activeTicket.call_time) }}</p>
                            <p v-if="activeTicket.start_service_time">Час початку: {{
                                formatTime(activeTicket.start_service_time) }}</p>
                        </div>
                        <div class="mt-6 flex justify-center gap-2 flex-wrap">
                            <button v-if="activeTicket.status === 'Called'"
                                @click="handleAction('start_service', activeTicket.name)"
                                class="bg-green-500 text-white font-bold py-2 px-4 rounded-lg shadow-md transition-transform transform hover:scale-105 disabled:bg-slate-400">Почати
                                обслуговування</button>
                            <button v-if="activeTicket.status === 'Serving'"
                                @click="handleAction('finish_service', activeTicket.name)"
                                class="bg-green-500 text-white font-bold py-2 px-4 rounded-lg shadow-md transition-transform transform hover:scale-105 disabled:bg-slate-400">Завершити</button>
                            <button v-if="activeTicket.status === 'Serving'"
                                @click="handleAction('postpone_ticket', activeTicket.name)"
                                class="bg-yellow-500 text-white font-bold py-2 px-4 rounded-lg shadow-md transition-transform transform hover:scale-105 disabled:bg-slate-400">Відкласти</button>
                            <button @click="handleAction('mark_as_no_show', activeTicket.name)"
                                class="bg-red-500 text-white font-bold py-2 px-4 rounded-lg shadow-md transition-transform transform hover:scale-105 disabled:bg-slate-400">Не
                                з'явився</button>
                        </div>
                    </div>
                    <div v-else class="text-center py-8 text-slate-500">
                        <p>Немає активного талону. Викличте наступного відвідувача.</p>
                    </div>
                </div>
            </div>

            <aside>
                <div class="bg-white p-4 rounded-lg shadow-md">
                    <h3 class="text-lg font-semibold mb-3 text-slate-700">Статистика черги</h3>
                    <p class="text-slate-500 text-sm">Статистика буде реалізована в наступних кроках.</p>
                </div>
                <div class="bg-white p-4 rounded-lg shadow-md mt-4">
                    <h3 class="text-lg font-semibold mb-3 text-slate-700">Відкладені талони</h3>
                    <p class="text-slate-500 text-sm">Список відкладених талонів буде реалізований в наступних кроках.
                    </p>
                </div>
            </aside>
        </main>
    </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue';
import { useSocket } from '../services/socketService';

// --- Реактивні змінні ---
const operatorInfo = ref({});
const servicePoints = ref([]);
const selectedServicePoint = ref(null);
const activeTicket = ref(null);
const loading = ref(true);
const error = ref(null);

const { initSocket, listen, off, disconnectSocket } = useSocket();

// --- Функції життєвого циклу ---
onMounted(async () => {
    loading.value = true;
    error.value = null;
    try {
        const response = await frappe.call({
            method: "qms_cherga.api.get_operator_dashboard_data",
            args: {}
        });

        if (response.message && response.message.status === 'success') {
            const data = response.message.data;
            operatorInfo.value = data.operator_info;
            servicePoints.value = data.service_points;
            activeTicket.value = data.active_ticket;

            if (servicePoints.value.length > 0) {
                selectedServicePoint.value = servicePoints.value[0].name;
            }

            // Ініціалізація сокетів після отримання ID офісу
            if (operatorInfo.value.office) {
                initSocket(operatorInfo.value.office);
                listen('qms_ticket_updated_doc', handleTicketUpdate);
                listen('qms_stats_updated', handleStatsUpdate);
            }
        } else {
            throw new Error(response.message.message || "Failed to load dashboard data");
        }
    } catch (e) {
        error.value = e.message;
        console.error(e);
    } finally {
        loading.value = false;
    }
});

onUnmounted(() => {
    disconnectSocket();
    off('qms_ticket_updated_doc', handleTicketUpdate);
    off('qms_stats_updated', handleStatsUpdate);
});

// --- Методи ---
const callNext = async () => {
    if (!selectedServicePoint.value) {
        error.value = "Будь ласка, оберіть точку обслуговування.";
        return;
    }
    loading.value = true;
    error.value = null;
    try {
        const response = await frappe.call({
            method: "qms_cherga.api.call_next_visitor",
            args: { service_point_name: selectedServicePoint.value }
        });

        if (response.message.status === 'success' && response.message.data.ticket_info) {
            // Оновлення відбувається через веб-сокет, тому тут можна не оновлювати activeTicket
        } else if (response.message.status === 'info') {
            frappe.show_alert({ message: response.message.message, indicator: 'blue' });
        } else {
            throw new Error(response.message.message || "Failed to call next visitor");
        }
    } catch (e) {
        error.value = e.message;
    } finally {
        loading.value = false;
    }
};

const handleAction = async (action, ticketName) => {
    loading.value = true;
    error.value = null;
    try {
        const response = await frappe.call({
            method: `qms_cherga.api.${action}`,
            args: { ticket_name: ticketName }
        });
        if (response.message.status !== 'success') {
            throw new Error(response.message.message || `Action ${action} failed`);
        }
        // Оновлення UI відбудеться через WebSocket
    } catch (e) {
        error.value = e.message;
    } finally {
        loading.value = false;
    }
};

// --- Обробники сокетів ---
const handleTicketUpdate = (data) => {
    console.log('WebSocket event received:', data);
    // Якщо подія стосується поточного оператора
    if (data.operator === operatorInfo.value.user) {
        if (['Called', 'Serving'].includes(data.status)) {
            activeTicket.value = data;
            activeTicket.value.service_name = data.service_name; // Переконуємось що назва є
        } else {
            // Якщо талон завершено, скасовано і т.д.
            if (activeTicket.value && activeTicket.value.name === data.name) {
                activeTicket.value = null;
            }
        }
    } else {
        // Якщо оновлення для іншого оператора, можна оновити лічильники
        handleStatsUpdate();
    }
};

const handleStatsUpdate = () => {
    console.log("Stats update triggered by WebSocket.");
    // Тут буде логіка для оновлення статистики черги
};

// --- Допоміжні функції ---
const formatTime = (dateTimeStr) => {
    if (!dateTimeStr) return 'N/A';
    return new Date(dateTimeStr).toLocaleTimeString('uk-UA');
};

const statusColor = (status) => {
    const colors = {
        'Called': 'text-blue-600',
        'Serving': 'text-green-600',
        'Postponed': 'text-yellow-600',
    };
    return colors[status] || 'text-slate-600';
};

</script>