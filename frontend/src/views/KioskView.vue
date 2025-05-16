<template>
    <div class="kiosk-container w-full flex flex-col items-center font-sans">
        <div id="pageServiceSelection" v-if="currentView === 'services'" class="w-full max-w-5xl">
            <div class="text-center mb-8 md:mb-12">
                <h3 v-if="loadingOfficeInfo" class="text-xl sm:text-2xl font-medium text-sky-700 mb-4">
                    Завантаження інформації про офіс...
                </h3>
                <h2 v-else-if="officeDisplayNameFromApi" class="text-xl sm:text-2xl font-medium text-sky-700 mb-4">
                    {{ officeDisplayNameFromApi }}
                </h2>
                <h1 class="text-4xl sm:text-5xl md:text-6xl font-bold text-slate-800">Електронна черга</h1>
                <p class="text-lg sm:text-xl text-slate-600 mt-2">Будь ласка, оберіть потрібну послугу</p>
            </div>

            <div v-if="loadingServices && !loadingOfficeInfo" class="text-center py-10">
                <p class="text-xl text-slate-600">Завантаження послуг...</p>
            </div>
            <div v-if="error"
                class="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded relative mb-6 max-w-xl mx-auto"
                role="alert">
                <strong class="font-bold">Помилка!</strong>
                <span class="block sm:inline whitespace-pre-wrap"> {{ error }}</span>
            </div>

            <div v-if="!loadingServices && !loadingOfficeInfo && services.length === 0 && !error"
                class="text-center py-10">
                <p class="text-xl text-slate-600">Наразі доступних послуг немає.</p>
            </div>

            <div id="servicesGrid" v-if="!loadingOfficeInfo && !loadingServices"
                class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6 md:gap-8 w-full">
                <ServiceItem v-for="service in services" :key="service.name" :service="service"
                    @service-selected="handleServiceSelection" />
            </div>
        </div>

        <div id="pageTicketDisplay" v-if="currentView === 'ticket'" class="w-full max-w-md mt-2 md:mt-8">
            <div id="ticketContentWrapper"
                class="border-2 border-dashed border-gray-400 p-6 sm:p-8 rounded-lg bg-gray-50 text-center shadow-lg">
                <h3 v-if="officeDisplayNameFromApi" class="text-lg font-medium text-slate-600 mb-1">{{
                    officeDisplayNameFromApi }}</h3>
                <h2 class="text-2xl font-bold text-blue-600 mb-3">ВАШ ТАЛОН</h2>
                <p class="text-slate-700 text-lg mb-2">Послуга: <span class="font-semibold">{{ ticketInfo?.service_name
                }}</span></p>
                <p class="text-slate-700 text-4xl font-bold my-4">{{ ticketInfo?.ticket_number_short }}</p>
                <p class="text-slate-600 mb-1">Дата: <span>{{ formatTicketDate(ticketInfo?.creation) }}</span></p>
                <p class="text-slate-600">Час: <span>{{ formatTicketTime(ticketInfo?.creation) }}</span></p>
                <p v-if="ticketInfo?.service_letter" class="text-slate-600">Літера черги: <span class="font-semibold">{{
                    ticketInfo.service_letter }}</span></p>
                <p v-if="ticketInfo?.people_ahead !== undefined && ticketInfo?.people_ahead !== null"
                    class="text-slate-600">
                    Перед вами в черзі: <span class="font-semibold">{{ ticketInfo.people_ahead }}</span>
                </p>
                <p v-else class="text-slate-600">
                    Будь ласка, очікуйте на виклик.
                </p>
                <p class="text-sm text-slate-500 mt-6">Зберігайте талон до завершення обслуговування.</p>

                <p v-if="ticketReturnTimeoutSeconds > 0" class="text-sm text-slate-500 mt-4">
                    Повернення до вибору послуг через: {{ ticketReturnTimeoutSeconds }} сек.
                </p>
            </div>
            <div class="mt-8 flex flex-col sm:flex-row gap-4 justify-center">
                <button @click="goBackToServices"
                    class="w-full sm:w-auto bg-blue-600 hover:bg-blue-700 text-white font-semibold py-3 px-8 rounded-lg shadow-md transition duration-150 ease-in-out">
                    Обрати іншу послугу ({{ ticketReturnTimeoutSeconds }} сек)
                </button>
            </div>
        </div>
    </div>
</template>

<script setup>
import { ref, onMounted, nextTick, watch } from 'vue';
import ServiceItem from '../components/ServiceItem.vue';
// LucidePrinter більше не використовується на цій сторінці, якщо кнопка друку видалена
// import { Printer as LucidePrinter } from 'lucide-vue-next'; 

// --- Конфігурація ---
const API_BASE_URL = '';
const OFFICE_ID_FALLBACK = 'olxndr-dracs-zp';
const OFFICE_DISPLAY_NAME_FALLBACK = 'Завантаження...';
const ORGANIZATION_NAME_FALLBACK = 'Назва Вашої Організації (Резерв)';
const FRAPPE_PRINT_FORMAT = "QMS Ticket Thermal";
const TICKET_DISPLAY_DURATION_SECONDS = 8; // Час відображення талону перед поверненням

// --- Реактивні змінні ---
const services = ref([]);
const loadingServices = ref(true);
const loadingOfficeInfo = ref(true);
const error = ref(null);
const officeId = ref(OFFICE_ID_FALLBACK);
const officeDisplayName = ref(OFFICE_DISPLAY_NAME_FALLBACK);
const officeDisplayNameFromApi = ref('');
const organizationName = ref(ORGANIZATION_NAME_FALLBACK);

const currentView = ref('services');
const ticketInfo = ref(null);

const ticketReturnTimerId = ref(null); // ID для setTimeout
const ticketReturnTimeoutSeconds = ref(TICKET_DISPLAY_DURATION_SECONDS); // Секунди для зворотнього відліку

// --- Функції ---
const getCsrfToken = () => {
    if (window.boot && window.boot.csrf_token) return window.boot.csrf_token;
    if (window.csrf_token) return window.csrf_token;
    if (typeof frappe !== 'undefined' && frappe.csrf_token) return frappe.csrf_token;
    console.warn('CSRF token not found for POST requests.');
    return null;
};

function initializeAppParameters() {
    let officeIdFromSource = null;
    let officeDisplayNameFromBoot = null;
    let orgNameFromSource = null;

    if (window.boot) {
        officeIdFromSource = window.boot.office_id || null;
        officeDisplayNameFromBoot = window.boot.office_display_name || null;
        orgNameFromSource = window.boot.organization_name || (window.boot.sysdefaults && window.boot.sysdefaults.company_name) || null;
    }

    const urlParams = new URLSearchParams(window.location.search);
    const officeFromUrl = urlParams.get('office');
    if (officeFromUrl && !officeIdFromSource) {
        officeIdFromSource = officeFromUrl;
    }

    officeId.value = officeIdFromSource || OFFICE_ID_FALLBACK;

    if (officeDisplayNameFromBoot) {
        officeDisplayNameFromApi.value = officeDisplayNameFromBoot;
        officeDisplayName.value = officeDisplayNameFromBoot;
        loadingOfficeInfo.value = false;
    } else {
        officeDisplayName.value = OFFICE_DISPLAY_NAME_FALLBACK;
    }
    organizationName.value = orgNameFromSource || ORGANIZATION_NAME_FALLBACK;
}

async function fetchOfficeInfo() {
    if (officeDisplayNameFromApi.value && officeDisplayNameFromApi.value !== OFFICE_DISPLAY_NAME_FALLBACK) {
        loadingOfficeInfo.value = false;
        return;
    }
    if (!officeId.value) {
        error.value = "ID офісу не визначено, неможливо завантажити інформацію про офіс.";
        loadingOfficeInfo.value = false;
        return;
    }
    loadingOfficeInfo.value = true;
    try {
        const response = await fetch(`${API_BASE_URL}/api/method/qms_cherga.api.get_office_info?office=${officeId.value}`);
        if (!response.ok) {
            let errMsg = `Помилка ${response.status}: ${response.statusText || 'Не вдалося завантажити інформацію про офіс'}`;
            try { const errData = await response.json(); errMsg = errData.message || errData.exception || (errData.data && errData.data.message) || errMsg; } catch (e) { }
            throw new Error(errMsg);
        }
        const data = await response.json();
        if (data.message && data.message.office_name) {
            officeDisplayNameFromApi.value = data.message.office_name;
        } else if (data.message && data.message.data && data.message.data.office_name) {
            officeDisplayNameFromApi.value = data.message.data.office_name;
        } else {
            console.warn("Відповідь API get_office_info не містить 'office_name'. Отримано:", data);
            officeDisplayNameFromApi.value = officeId.value;
        }
    } catch (err) {
        console.error("Помилка fetchOfficeInfo:", err);
        error.value = (error.value ? error.value + '\n' : '') + `Дані офісу: ${err.message}`;
        officeDisplayNameFromApi.value = officeId.value;
    } finally {
        loadingOfficeInfo.value = false;
    }
}

async function fetchServices() {
    loadingServices.value = true;
    services.value = [];
    try {
        const response = await fetch(`${API_BASE_URL}/api/method/qms_cherga.api.get_kiosk_services?office=${officeId.value}`);
        if (!response.ok) {
            let errMsg = `Помилка ${response.status}: ${response.statusText || 'Не вдалося завантажити послуги'}`;
            try { const errData = await response.json(); errMsg = errData.message || errData.exception || (errData.data && errData.data.message) || errMsg; } catch (e) { }
            throw new Error(errMsg);
        }
        const data = await response.json();
        if (data && data.message && data.message.status === 'success' && data.message.data) {
            const apiServices = data.message.data.services_no_category || [];
            services.value = apiServices.map(s => ({
                name: s.id,
                service_name: s.label,
                icon: s.icon,
                letter: s.letter || null
            }));
            if (services.value.length === 0 && apiServices.length > 0) {
                console.warn("Мапінг послуг дав порожній результат, хоча API повернув дані.");
            } else if (apiServices.length === 0) {
                console.warn("Список послуг порожній (API повернув успіх, але services_no_category порожній).");
            }
        } else {
            const serviceError = (data && data.message && data.message.message) || "Неправильний формат відповіді від сервера послуг.";
            error.value = (error.value ? error.value + '\n' : '') + serviceError;
            console.warn("Відповідь API послуг не містить очікуваної структури:", data);
        }
    } catch (err) {
        console.error("Помилка fetchServices:", err);
        error.value = (error.value ? error.value + '\n' : '') + `Послуги: ${err.message}`;
    } finally {
        loadingServices.value = false;
    }
}

async function handleServiceSelection(selectedService) {
    loadingServices.value = true;
    error.value = null;
    try {
        const payload = {
            service: selectedService.name,
            office: officeId.value,
        };
        const csrfToken = getCsrfToken();
        const headers = { 'Content-Type': 'application/json' };
        if (csrfToken) {
            headers['X-Frappe-CSRF-Token'] = csrfToken;
        } else {
            console.warn('CSRF token is missing for ticket creation.');
        }
        const response = await fetch(`${API_BASE_URL}/api/method/qms_cherga.api.create_live_queue_ticket`, {
            method: 'POST',
            headers: headers,
            body: JSON.stringify(payload)
        });
        if (!response.ok) {
            let errMsg = `Помилка ${response.status}: ${response.statusText || 'Не вдалося створити талон'}`;
            const errorData = await response.json().catch(() => null);
            if (errorData) {
                if (errorData._server_messages) {
                    try {
                        const serverMessages = JSON.parse(errorData._server_messages);
                        if (Array.isArray(serverMessages) && serverMessages.length > 0) {
                            const firstMessage = JSON.parse(serverMessages[0]);
                            errMsg = firstMessage.message || errMsg;
                        }
                    } catch (e) { /* ігнор */ }
                } else if (errorData.message) { errMsg = errorData.message; }
                else if (errorData.exception) { errMsg = errorData.exception; }
                else if (errorData.exc_type === "CSRFTokenError") { errMsg = "Помилка CSRF. Оновіть сторінку."; }
            }
            throw new Error(errMsg);
        }
        const responseData = await response.json();
        if (responseData.message && responseData.message.status === 'success' && responseData.message.data && responseData.message.data.ticket_name) {
            const apiTicketData = responseData.message.data;
            ticketInfo.value = {
                name: apiTicketData.ticket_name,
                ticket_number_short: apiTicketData.ticket_number,
                service_id: apiTicketData.service,
                office_id: apiTicketData.office,
                service_name: selectedService.service_name,
                service_letter: apiTicketData.service_letter || selectedService.letter,
                people_ahead: apiTicketData.people_ahead,
                creation: apiTicketData.creation_timestamp || apiTicketData.creation || new Date().toISOString(),
            };
            currentView.value = 'ticket'; // Перемикає на сторінку талону

            if (ticketInfo.value && ticketInfo.value.name) {
                await nextTick();
                triggerFrappePrint(ticketInfo.value.name, FRAPPE_PRINT_FORMAT);
            }
        } else {
            throw new Error((responseData.message && responseData.message.message) || 'Некоректна відповідь сервера при створенні талону.');
        }
    } catch (err) {
        console.error("Помилка handleServiceSelection (створення талону):", err);
        error.value = err.message;
    } finally {
        loadingServices.value = false;
    }
}

function triggerFrappePrint(ticketDocumentName, printFormat) {
    // ... (код функції без змін з попереднього кроку) ...
    if (!ticketDocumentName) {
        console.error("Немає ID талону для друку через Frappe.");
        return;
    }
    const printUrl = `${API_BASE_URL}/printview?doctype=QMS%20Ticket&name=${encodeURIComponent(ticketDocumentName)}&format=${encodeURIComponent(printFormat)}&no_letterhead=1`;

    console.log("Спроба друку через Frappe Print Format URL:", printUrl);

    const printFrame = document.createElement('iframe');
    printFrame.style.position = 'absolute';
    printFrame.style.width = '0px';
    printFrame.style.height = '0px';
    printFrame.style.border = '0';
    printFrame.setAttribute('aria-hidden', 'true');
    printFrame.src = printUrl;

    printFrame.onload = function () {
        try {
            const iframeWindow = printFrame.contentWindow;
            if (iframeWindow) {
                iframeWindow.focus();
                const printResult = iframeWindow.print();
                console.log("Print dialog initiated via iframe.", printResult);
                setTimeout(() => {
                    if (document.body.contains(printFrame)) {
                        document.body.removeChild(printFrame);
                        console.log("Print iframe removed.");
                    }
                }, 10000);
            } else {
                throw new Error("contentWindow is null in print iframe");
            }
        } catch (e) {
            console.error("Помилка виклику друку в iframe (Frappe Print):", e);
            alert("Не вдалося автоматично ініціювати друк.");
        }
    };
    printFrame.onerror = function () {
        console.error("Помилка завантаження iframe для Frappe Print URL: " + printUrl);
        alert("Помилка завантаження сторінки для друку через Frappe.");
        if (document.body.contains(printFrame)) {
            document.body.removeChild(printFrame);
        }
    };
    document.body.appendChild(printFrame);
}

// Нова функція для запуску таймера повернення
function startReturnToServicesTimer() {
    clearTimeout(ticketReturnTimerId.value); // Очистити попередній таймер, якщо є
    ticketReturnTimeoutSeconds.value = TICKET_DISPLAY_DURATION_SECONDS;

    ticketReturnTimerId.value = setInterval(() => {
        ticketReturnTimeoutSeconds.value -= 1;
        if (ticketReturnTimeoutSeconds.value <= 0) {
            goBackToServices(); // Автоматичне повернення
        }
    }, 1000);
}

// Спостерігаємо за зміною currentView
watch(currentView, (newView, oldView) => {
    if (newView === 'ticket') {
        startReturnToServicesTimer(); // Запускаємо таймер при переході на сторінку талону
    } else if (oldView === 'ticket') {
        clearTimeout(ticketReturnTimerId.value); // Очищаємо таймер при покиданні сторінки талону
        ticketReturnTimerId.value = null;
    }
});

function goBackToServices() {
    clearTimeout(ticketReturnTimerId.value); // Очистити таймер при ручному поверненні
    ticketReturnTimerId.value = null;
    currentView.value = 'services';
    ticketInfo.value = null;
    error.value = null;
    const oldPrintFrame = document.querySelector('iframe[src*="printview"]');
    if (oldPrintFrame && document.body.contains(oldPrintFrame)) {
        document.body.removeChild(oldPrintFrame);
    }
    if (!services.value || services.value.length === 0) {
        fetchServices();
    }
}

function formatTicketDate(dateTimeStr) {
    if (!dateTimeStr) return '';
    try { return new Date(dateTimeStr).toLocaleDateString('uk-UA', { day: '2-digit', month: '2-digit', year: 'numeric' }); }
    catch (e) { return dateTimeStr; }
}

function formatTicketTime(dateTimeStr) {
    if (!dateTimeStr) return '';
    try { return new Date(dateTimeStr).toLocaleTimeString('uk-UA', { hour: '2-digit', minute: '2-digit', second: '2-digit' }); }
    catch (e) { return dateTimeStr; }
}

onMounted(async () => {
    initializeAppParameters();
    const promises = [];
    if (!officeDisplayNameFromApi.value || officeDisplayNameFromApi.value === OFFICE_DISPLAY_NAME_FALLBACK) {
        promises.push(fetchOfficeInfo());
    } else {
        loadingOfficeInfo.value = false;
    }
    promises.push(fetchServices());
    try {
        await Promise.all(promises);
    } catch (e) {
        console.warn("Одна або більше операцій завантаження завершилися з помилкою.");
    }
});
</script>

<style scoped>
.whitespace-pre-wrap {
    white-space: pre-wrap;
}
</style>