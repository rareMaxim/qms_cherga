<template>
    <div class="display-board-container flex flex-col h-screen font-sans bg-slate-200 text-slate-800 overflow-hidden">

        <header
            class="p-3 sm:p-4 header-gradient shadow-2xl flex justify-between items-center shrink-0 text-slate-100 h-[60px] sm:h-[70px] md:h-[80px]">
            <div
                class="text-sm sm:text-base lg:text-lg font-medium text-slate-300 whitespace-nowrap mr-4 hidden sm:block">
                {{ currentDate }}
            </div>
            <h1
                class="text-base sm:text-lg md:text-xl lg:text-2xl font-bold text-sky-400 leading-tight text-center flex-grow">
                {{ officeDisplayName || 'Табло Електронної Черги' }}
            </h1>
            <div class="text-lg sm:text-xl lg:text-2xl font-semibold text-slate-100 whitespace-nowrap ml-4">
                {{ currentTime }}
            </div>
        </header>

        <section id="activeCallsSection" class="p-3 sm:p-4 shrink-0 bg-slate-100"
            :class="{ 'is-empty': activeCalls.length === 0 && officeStatus !== 'closed' }"
            v-show="activeCalls.length > 0 || officeStatus === 'closed'">
            <div v-if="officeStatus === 'closed'" class="text-center py-10">
                <h2 class="text-3xl md:text-4xl font-bold text-slate-700 mb-4">{{ officeClosedMessage }}</h2>
                <p v-if="infoMessageTicker" class="text-xl text-slate-600">{{ infoMessageTicker }}</p>
            </div>

            <div v-else>
                <h2 class="text-xl sm:text-2xl font-bold text-slate-700 mb-2 sm:mb-3 text-center shrink-0">
                    Запрошуються:
                </h2>
                <div id="activeCallsContainer"
                    class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3 sm:gap-4">
                    <transition-group name="call-card-anim">
                        <div v-for="call in activeCalls" :key="call.ticket_id"
                            class="call-card-item bg-gradient-to-br from-sky-500 via-blue-500 to-indigo-600 p-3 sm:p-4 rounded-xl shadow-xl text-white text-center flex flex-col justify-center items-center min-h-[120px] sm:min-h-[150px]">
                            <p class="text-3xl sm:text-4xl md:text-5xl lg:text-6xl font-extrabold drop-shadow-md">
                                {{ call.ticket_number_short }}
                            </p>
                            <p
                                class="text-lg sm:text-xl md:text-2xl font-bold text-yellow-300 mt-1 sm:mt-2 drop-shadow-sm">
                                {{ call.service_point_number || call.service_point_name }}
                            </p>
                        </div>
                    </transition-group>
                </div>
            </div>
        </section>

        <main class="flex-grow flex flex-col items-center justify-start p-3 sm:p-4 pt-0 overflow-hidden bg-slate-100"
            v-if="officeStatus === 'open'">
            <div class="w-full h-full bg-white p-4 sm:p-6 rounded-xl shadow-xl flex flex-col overflow-hidden">
                <h2 class="text-xl sm:text-2xl lg:text-3xl font-bold mb-3 sm:mb-4 text-center text-slate-700 shrink-0">
                    Наступні в черзі:</h2>
                <div id="waitingListContainer"
                    class="flex-grow grid grid-cols-2 xs:grid-cols-3 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-5 gap-2 sm:gap-3 overflow-y-auto custom-scrollbar pr-2">
                    <transition-group name="waiting-ticket-anim" class="contents">
                        <div v-for="ticket in waitingTickets" :key="ticket.ticket_id"
                            class="waiting-ticket-card rounded-lg text-center font-semibold transition-all duration-200 ease-in-out flex flex-col items-center justify-center text-sky-800 p-1 sm:p-2 h-28 sm:h-32 md:h-36">
                            <span class="text-xl sm:text-2xl md:text-3xl lg:text-4xl font-bold">{{
                                ticket.ticket_number_short }}</span>
                            <span class="text-sm sm:text-md md:text-lg mt-1 px-1 line-clamp-2 leading-tight">
                                {{ ticket.service_name }}
                            </span>
                        </div>
                    </transition-group>
                    <p v-if="waitingTickets.length === 0 && !loadingInitialData && !error && officeStatus === 'open'"
                        class="col-span-full text-center text-slate-500 py-8">
                        Черга порожня.
                    </p>
                    <p v-if="loadingInitialData && officeStatus === 'open'"
                        class="col-span-full text-center text-slate-500 py-8">
                        Завантаження даних черги...
                    </p>
                    <p v-if="error && officeStatus === 'open'" class="col-span-full text-center text-red-500 py-8">
                        Помилка завантаження даних: {{ error }}
                    </p>
                </div>
            </div>
        </main>

        <footer
            class="p-3 sm:p-4 bg-slate-900 shadow-lg shrink-0 h-[50px] sm:h-[60px] flex justify-between items-center">
            <div class="ticker-text-container flex-grow mr-4">
                <div class="ticker-text text-sm sm:text-base text-slate-300"
                    v-html="infoMessageTicker || defaultTickerText"></div>
            </div>
            <div class="socket-status-footer-indicator p-2 px-3 rounded text-white text-xs sm:text-sm shadow-md flex items-center gap-2 shrink-0"
                :style="{ backgroundColor: socketStatusDisplay.color }">
                <i :class="socketStatusDisplay.icon"></i>
                <span>{{ socketStatusDisplay.text }}</span>
                <span v-if="socketOfficeId" class="opacity-80 hidden sm:inline"> (Кімн: {{ socketOfficeId }})</span>
            </div>
        </footer>
    </div>
</template>

<script setup>
// ... (Ваш існуючий <script setup> код залишається майже без змін)
// Переконайтесь, що в handleQueueUpdate та fetchInitialBoardData
// ви правильно заповнюєте поле service_name для waitingTickets

import { ref, onMounted, onUnmounted, computed, watch } from 'vue';
import { useSocket } from '@/services/socketService';

const MAX_ACTIVE_CALLS = 5;
const MAX_WAITING_TICKETS_DISPLAY = 50; // Зменшено для тестування, можна повернути 56
const SOUND_NOTIFICATION_URL = '/assets/qms_cherga/sounds/notification.mp3'; // Виправлено шлях

const TICKER_MESSAGES = [
    "Вітаємо!",
    "Будь ласка, уважно слідкуйте за інформацією на табло.",
    "Дотримуйтесь правил.",
    "Заздалегідь підготуйте документи.",
    "Дякуємо за терпіння!"
];
const defaultTickerText = computed(() => TICKER_MESSAGES.join(" \u00A0 \u00A0 • \u00A0 \u00A0 "));

const officeId = ref('');
const officeDisplayName = ref('');

const currentDate = ref('');
const currentTime = ref('');

const officeStatus = ref('loading');
const officeClosedMessage = ref('');
const infoMessageTicker = ref('');

const activeCalls = ref([]);
const waitingTickets = ref([]);

let dateTimeIntervalId = null;
const notificationSound = ref(null);
const loadingInitialData = ref(true);
const error = ref(null);

const { connected, initSocket, listen, disconnectSocket, currentOfficeId: socketOfficeId } = useSocket();

const lastPongReceivedAt = ref(null);
const lastPingSentAt = ref(null);
const pingIntervalId = ref(null);
const PING_INTERVAL_MS = 25000;
const PONG_TIMEOUT_MS = 5000; // Збільшено таймаут для пінгу

const isPongLate = computed(() => {
    if (!lastPingSentAt.value || !connected.value) return false;
    if (lastPongReceivedAt.value && lastPongReceivedAt.value >= lastPingSentAt.value) return false;
    return (Date.now() - lastPingSentAt.value) > PONG_TIMEOUT_MS;
});

const socketStatusDisplay = computed(() => {
    if (error.value && officeStatus.value !== 'open') return { text: 'Помилка завантаження', color: '#B71C1C', icon: 'fas fa-exclamation-circle' };
    if (!connected.value) return { text: 'Відключено', color: '#d32f2f', icon: 'fas fa-times-circle' };
    if (isPongLate.value) return { text: 'Немає відповіді', color: '#FFA000', icon: 'fas fa-exclamation-triangle' };
    return { text: 'Підключено', color: '#388E3C', icon: 'fas fa-check-circle' };
});

function updateDateTime() {
    const now = new Date();
    const optionsDate = { year: 'numeric', month: 'long', day: 'numeric' };
    currentDate.value = now.toLocaleDateString('uk-UA', optionsDate);
    currentTime.value = now.toLocaleTimeString('uk-UA', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

function initializeAppParameters() {
    let officeIdFromSource = null;
    if (window.boot) {
        officeIdFromSource = window.boot.office_id || null;
    }
    const urlParams = new URLSearchParams(window.location.search);
    const officeFromUrl = urlParams.get('office');
    if (officeFromUrl) {
        officeIdFromSource = officeFromUrl;
    }
    officeId.value = officeIdFromSource;
    if (!officeId.value) { // Якщо ID офісу все ще не визначено
        officeStatus.value = 'error';
        error.value = "ID Офісу не вказано. Табло не може завантажити дані.";
        loadingInitialData.value = false;
        console.error(error.value);
    }
}

const frappeCall = async (method, args = {}) => {
    if (typeof frappe !== 'undefined' && frappe.call) {
        return new Promise((resolve, reject) => {
            frappe.call({
                method: method,
                args: args,
                callback: (r) => {
                    if (r.message && (r.message.status === 'success' || r.message.status === 'info')) {
                        resolve(r.message.data || r.message);
                    } else if (r.status === 'success' || r.status === 'info') {
                        resolve(r.data || r.message || r);
                    }
                    else {
                        console.error(`API Error in ${method}:`, r.message || r._server_messages || r);
                        const errorPayload = r.message || r._server_messages || { message: 'API call failed', details: r };
                        reject(errorPayload);
                    }
                },
                error: (err) => {
                    console.error(`Network/Frappe Error in ${method}:`, err);
                    reject(err);
                }
            });
        });
    } else {
        console.error('frappe.call is not available. Cannot make API requests.');
        return Promise.reject(new Error('frappe.call is not available'));
    }
};

async function fetchOfficeDetails() {
    if (!officeId.value) {
        officeDisplayName.value = "Табло Електронної Черги";
        return;
    }
    try {
        const data = await frappeCall('qms_cherga.api.get_office_info', { office: officeId.value });
        officeDisplayName.value = data.office_name || officeId.value;
    } catch (err) {
        console.error("Помилка fetchOfficeDetails:", err);
        officeDisplayName.value = officeId.value;
    }
}

function convertDisplayTimeToISO(timeStr) {
    if (!timeStr || !timeStr.includes(':')) return new Date().toISOString();
    const [hours, minutes, seconds] = timeStr.split(':');
    const date = new Date();
    date.setHours(parseInt(hours, 10), parseInt(minutes, 10), parseInt(seconds || "0", 10), 0);
    return date.toISOString();
}

async function fetchInitialBoardData() {
    loadingInitialData.value = true;
    error.value = null;
    try {
        const data = await frappeCall('qms_cherga.api.get_display_data', {
            office: officeId.value,
            limit_called: MAX_ACTIVE_CALLS,
            limit_waiting: MAX_WAITING_TICKETS_DISPLAY
        });

        officeStatus.value = data.office_status || 'unknown';
        infoMessageTicker.value = data.info_message || defaultTickerText.value;

        if (officeStatus.value === "closed") {
            officeClosedMessage.value = data.message || "Офіс наразі зачинено.";
            activeCalls.value = [];
            waitingTickets.value = [];
        } else if (officeStatus.value === "open") {
            officeClosedMessage.value = '';
            activeCalls.value = (data.last_called || []).slice(0, MAX_ACTIVE_CALLS).map(call => ({
                ticket_id: call.ticket_id || call.ticket,
                ticket_number_short: call.ticket,
                service_point_name: call.window,
                service_point_number: call.window_number || null,
                timestamp: call.time ? convertDisplayTimeToISO(call.time) : new Date().toISOString(),
                timerId: null
            }));
            waitingTickets.value = (data.waiting || []).slice(0, MAX_WAITING_TICKETS_DISPLAY).map(wait => ({
                ticket_id: wait.ticket_id || wait.ticket,
                ticket_number_short: wait.ticket,
                service_name: wait.service, // Поле `service` з API містить назву послуги
                service_id: wait.service_id
            }));
        } else {
            error.value = "Не вдалося визначити статус офісу.";
            infoMessageTicker.value = defaultTickerText.value;
        }
    } catch (err) {
        console.error("Помилка fetchInitialBoardData:", err);
        error.value = err.message || 'Помилка завантаження даних табло.';
        officeStatus.value = 'error';
        infoMessageTicker.value = defaultTickerText.value;
    } finally {
        loadingInitialData.value = false;
    }
}

function sendPing() {
    if (connected.value && officeId.value) { // Додано перевірку officeId.value
        lastPingSentAt.value = Date.now();
        frappeCall('qms_cherga.api.ping_display_board', {
            office_id: officeId.value,
            client_timestamp: new Date().toISOString()
        })
            .catch(err => {
                console.warn("[DisplayBoard] Ping API call failed:", err);
            });
    }
}

function playNotificationSound() {
    if (notificationSound.value) {
        notificationSound.value.currentTime = 0;
        notificationSound.value.allow = "autoplay"; // Це не стандартний атрибут
        notificationSound.value.play().catch(e => console.warn("Не вдалося відтворити звук:", e));
    }
}

function handleQueueUpdate(eventData) {
    if (!eventData || eventData.office !== officeId.value) {
        if (eventData) { // Логуємо, тільки якщо eventData існує, щоб уникнути помилки undefined.office
            console.warn(`[DisplayBoard] Event ignored. Office mismatch or no office in event. Board: ${officeId.value}, Event: ${eventData.office}`);
        }
        return;
    }
    // Використовуємо eventData.type, який ми додали на бекенді
    const type = eventData.type;

    console.log(`[DisplayBoard] Handling event type: ${type}`, eventData);


    if (type === 'Called') { // Порівнюємо з eventData.type
        const newCall = {
            ticket_id: eventData.name, // `name` з бекенду - це повний ID талону
            ticket_number_short: eventData.ticket_number,
            service_name: eventData.service_name,
            service_point_name: eventData.service_point_name,
            service_point_number: eventData.service_point_number, // Може бути null
            timestamp: eventData.call_time || eventData.timestamp || new Date().toISOString(), // Пріоритет call_time
            timerId: null
        };
        activeCalls.value = activeCalls.value.filter(call => call.ticket_id !== newCall.ticket_id);
        activeCalls.value.unshift(newCall);
        if (activeCalls.value.length > MAX_ACTIVE_CALLS) {
            activeCalls.value.pop();
        }
        playNotificationSound();
        waitingTickets.value = waitingTickets.value.filter(t => t.ticket_id !== newCall.ticket_id);
    }
    else if (type === 'Waiting') { // Порівнюємо з eventData.type
        if (!waitingTickets.value.find(t => t.ticket_id === eventData.ticket_id)) {
            waitingTickets.value.push({
                ticket_id: eventData.ticket_id, // або eventData.name
                ticket_number_short: eventData.ticket_number, // або eventData.ticket_number_short
                service_name: eventData.service_name, // Переконайтеся, що це поле є в eventData
                service_id: eventData.service_id
            });
            if (waitingTickets.value.length > MAX_WAITING_TICKETS_DISPLAY) {
                waitingTickets.value = waitingTickets.value.slice(-MAX_WAITING_TICKETS_DISPLAY);
            }
        }
    } else if (type === 'Updated') { // Порівнюємо з eventData.type

    } else if (type === 'Completed' || type === 'Cancelled' || type === 'NoShow' || type === 'Serving') { // Додано 'qms_ticket_serving'
        activeCalls.value = activeCalls.value.filter(call => call.ticket_id !== eventData.ticket_id);
        // Якщо талон обслуговується, він не має бути і в очікуванні
        if (type === 'Serving') {
            waitingTickets.value = waitingTickets.value.filter(t => t.ticket_id !== eventData.ticket_id);
        }
    } else if (type === 'qms_office_message_updated') { // Залишається без змін, якщо office_id є в eventData
        if (eventData.office_id === officeId.value) { // Має бути office_id, а не office
            infoMessageTicker.value = eventData.message || defaultTickerText.value;
        }
    } else if (type === 'qms_office_status_changed') { // Залишається без змін
        if (eventData.office_id === officeId.value) {
            officeStatus.value = eventData.status;
            infoMessageTicker.value = eventData.info_message || defaultTickerText.value;
            if (eventData.status !== 'open') {
                officeClosedMessage.value = eventData.message || (eventData.status === 'closed' ? 'Офіс наразі зачинено.' : '');
                activeCalls.value = [];
                waitingTickets.value = [];
            } else {
                officeClosedMessage.value = '';
                fetchInitialBoardData();
            }
        }
    } else if (type === 'qms_stats_update_needed') { // Обробка події для оновлення статистики
        console.log("[DisplayBoard] Stats update needed event received.", eventData);
        // Тут можна було б оновити статистику, але оскільки на табло її немає,
        // ця подія може бути проігнорована або використана для інших цілей у майбутньому.
    } else {
        console.warn("[DisplayBoard] Unhandled event type in handleQueueUpdate or type missing:", type, eventData);
    }
}


onMounted(async () => {
    updateDateTime();
    dateTimeIntervalId = setInterval(updateDateTime, 1000);

    initializeAppParameters();

    if (!officeId.value) { // Якщо officeId не встановлено, не продовжуємо
        return;
    }

    await fetchOfficeDetails();

    if (officeId.value) {
        await fetchInitialBoardData();
        initSocket(officeId.value);

        listen('display_board_pong_ack', (data) => {
            if (data.office_id === officeId.value) {
                lastPongReceivedAt.value = Date.now();
                console.log(`[DisplayBoard] Pong for office ${officeId.value} confirmed at ${new Date(lastPongReceivedAt.value).toLocaleTimeString()}`);
            }
        });

        // Підписуємося на події, які надсилає бекенд
        listen('qms_ticket_called', handleQueueUpdate); // Для викликаних талонів
        listen('qms_ticket_created', handleQueueUpdate); // Для нових талонів (якщо ви його використовуєте)
        // або 'qms_new_ticket_in_queue', якщо це ваша подія
        listen('qms_ticket_updated_doc', handleQueueUpdate); // Для оновлення статусів (Completed, Cancelled etc.)
        listen('qms_office_message_updated', handleQueueUpdate);
        listen('qms_office_status_changed', handleQueueUpdate);
        listen('qms_stats_updated', handleQueueUpdate); // Для події оновлення статистики (якщо вона впливає на табло)


        if (pingIntervalId.value) clearInterval(pingIntervalId.value);
        pingIntervalId.value = setInterval(sendPing, PING_INTERVAL_MS);

        const unwatchConnected = watch(connected, (newVal) => {
            if (newVal) {
                sendPing();
                unwatchConnected();
            }
        });
    }

    if (SOUND_NOTIFICATION_URL) {
        try {
            notificationSound.value = new Audio(SOUND_NOTIFICATION_URL); // Виправлено шлях
            notificationSound.value.load();
        } catch (e) { console.warn("Could not load notification sound:", e); }
    }
});

onUnmounted(() => {
    disconnectSocket();
    if (dateTimeIntervalId) clearInterval(dateTimeIntervalId);
    if (pingIntervalId.value) clearInterval(pingIntervalId.value);
});

</script>

<style scoped>
/* ... (ваші стилі залишаються без змін) ... */
.header-gradient {
    background-image: linear-gradient(to right, #0f172a, #1e293b, #0f172a);
}

.call-card-item {
    transition: all 0.5s cubic-bezier(0.25, 0.8, 0.25, 1);
}

.call-card-anim-enter-from,
.call-card-anim-leave-to {
    opacity: 0;
    transform: translateY(-20px) scale(0.95);
}

.call-card-anim-enter-to,
.call-card-anim-leave-from {
    opacity: 1;
    transform: translateY(0) scale(1);
}

.call-card-anim-leave-active {
    position: absolute;
}


.waiting-ticket-card {
    background-color: #e0f2fe;
    /* Світло-блакитний фон */
    /* color: #075985; Задано в span */
    border: 1px solid #bae6fd;
    /* Світло-блакитна рамка */
    box-shadow: 0 4px 8px -2px rgba(0, 0, 0, 0.08), 0 2px 4px -2px rgba(0, 0, 0, 0.05);
    display: flex;
    /* Для flex-col */
    flex-direction: column;
    /* Розмістити номер над назвою послуги */
    align-items: center;
    /* Центрувати по горизонталі */
    justify-content: center;
    /* Центрувати по вертикалі */
    padding: 0.5rem;
    /* Оновлено падінг */
    line-height: 1.2;
    /* Для кращого відображення тексту в кілька рядків */
}

.waiting-ticket-card:hover {
    background-color: #ccecfc;
    border-color: #7dd3fc;
    transform: translateY(-2px);
    box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.08), 0 4px 6px -2px rgba(0, 0, 0, 0.04);
}

.waiting-ticket-anim-enter-from,
.waiting-ticket-anim-leave-to {
    opacity: 0;
    transform: scale(0.9) translateY(10px);
}

.waiting-ticket-anim-enter-active,
.waiting-ticket-anim-leave-active {
    transition: opacity 0.3s ease-out, transform 0.3s ease-out;
}

.waiting-ticket-anim-leave-active {
    position: absolute;
}

.list-anim-move {
    transition: transform 0.5s ease;
}

.custom-scrollbar::-webkit-scrollbar {
    width: 10px;
}

.custom-scrollbar::-webkit-scrollbar-track {
    background: #cbd5e1;
    border-radius: 10px;
}

.custom-scrollbar::-webkit-scrollbar-thumb {
    background: #64748b;
    border-radius: 10px;
    border: 2px solid #cbd5e1;
}

.custom-scrollbar::-webkit-scrollbar-thumb:hover {
    background: #475569;
}

.ticker-text-container {
    width: 100%;
    overflow: hidden;
}

.ticker-text {
    animation: ticker-scroll 40s linear infinite;
    white-space: nowrap;
    display: inline-block;
}

@keyframes ticker-scroll {
    0% {
        transform: translateX(100%);
    }

    100% {
        transform: translateX(-120%);
    }
}

#activeCallsSection.is-empty {
    opacity: 0;
    max-height: 0 !important;
    padding-top: 0 !important;
    padding-bottom: 0 !important;
    margin-bottom: 0 !important;
    overflow: hidden;
    transition: opacity 0.4s ease-in-out, max-height 0.5s ease-in-out, padding-top 0.5s ease-in-out, padding-bottom 0.5s ease-in-out, margin-bottom 0.5s ease-in-out;
}

#activeCallsSection {
    transition: opacity 0.4s ease-in-out, max-height 0.5s ease-in-out, padding-top 0.5s ease-in-out, padding-bottom 0.5s ease-in-out, margin-bottom 0.5s ease-in-out;
}

/* Додаткові класи для обмеження тексту в кілька рядків */
.line-clamp-2 {
    overflow: hidden;
    display: -webkit-box;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 2;
    /* white-space: normal; -- прибираємо, бо -webkit-box-orient: vertical; вже це робить */
}
</style>