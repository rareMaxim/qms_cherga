document.addEventListener('DOMContentLoaded', () => {
    // --- Configuration ---
    // !!! ВАЖЛИВО: ID офісу тепер береться з URL-параметра '?office=' !!!
    const API_ENDPOINT = "/api/method/qms_cherga.api.get_display_data"; // Шлях до API
    const POLLING_INTERVAL = 7000; // Інтервал опитування в мілісекундах (7 секунд)
    const CALLED_LIMIT = 3; // Скільки останніх викликаних показувати
    const WAITING_LIMIT = 20; // Скільки очікуючих показувати
    // ---------------------

    // --- НОВЕ: Отримуємо ID офісу з URL ---
    let officeId = null;

    function getUrlParameter(name) {
        name = name.replace(/[\[]/, '\\[').replace(/[\]]/, '\\]');
        const regex = new RegExp('[\\?&]' + name + '=([^&#]*)');
        const results = regex.exec(location.search);
        return results === null ? '' : decodeURIComponent(results[1].replace(/\+/g, ' '));
    }

    function initializeDisplayBoard() {
        officeId = getUrlParameter('office'); // Отримуємо ID з URL

        if (!officeId) {
            // Якщо параметр 'office' відсутній в URL, показуємо помилку
            document.body.innerHTML = '<div class="container"><div class="error-message" style="color: red; text-align: center; padding: 50px; font-size: 1.2em;">Помилка: Не вказано параметр "office" в URL адресі табло.<br>Приклад: /qms_display_board.html?office=YOUR_OFFICE_ID</div></div>';
            console.error("Office ID not found in URL parameters for display board.");
            return false; // Повертаємо false, щоб зупинити подальшу ініціалізацію
        }
        console.log(`Display board initialized for Office ID: ${officeId}`);
        return true; // Повертаємо true, якщо ID знайдено
    }
    // --- КІНЕЦЬ НОВОГО КОДУ ---

    // DOM References (без змін)
    const currentDateEl = document.getElementById('current-date');
    const currentTimeEl = document.getElementById('current-time');
    const lastCallsListEl = document.getElementById('last-calls-list');
    const kioskNextListEl = document.getElementById('kiosk-next-list');
    const lastCalledBarEl = document.getElementById('last-called-bar');

    let lastCalledDataSignature = '';

    // Date/Time Formatting (без змін)
    function formatDate(date) {
        const options = { year: 'numeric', month: '2-digit', day: '2-digit' };
        return date.toLocaleDateString('uk-UA', options);
    }
    function formatTime(date) {
        const options = { hour: '2-digit', minute: '2-digit', second: '2-digit' };
        return date.toLocaleTimeString('uk-UA', options);
    }

    // Update Date/Time Display (без змін)
    function updateTime() {
        const now = new Date();
        if (currentDateEl) currentDateEl.textContent = formatDate(now);
        if (currentTimeEl) currentTimeEl.textContent = formatTime(now);
    }

    // Update "Last Called" Block (без змін)
    function updateLastCalled(calls) {
        if (!lastCallsListEl) return;

        const placeholder = lastCallsListEl.querySelector('.placeholder');
        if (placeholder) placeholder.remove();

        const fragment = document.createDocumentFragment();
        const currentDataSignature = JSON.stringify(calls);

        if (!calls || calls.length === 0) {
            if (!lastCallsListEl.querySelector('.placeholder')) {
                lastCallsListEl.innerHTML = '<span class="placeholder" style="color: #ccc;">Немає активних викликів</span>';
            }
            lastCalledDataSignature = currentDataSignature;
            return;
        }

        calls.forEach(call => {
            const item = document.createElement('div');
            item.classList.add('call-item');
            item.innerHTML = `
                ${call.ticket || 'N/A'}
                <span class="window-info">→ ${call.window || 'N/A'}</span>
                <span class="time-info">(${call.time || '--:--'})</span>
            `;
            fragment.appendChild(item);
        });

        lastCallsListEl.innerHTML = '';
        lastCallsListEl.appendChild(fragment);

        if (currentDataSignature !== lastCalledDataSignature && lastCalledDataSignature !== '') {
            if (lastCalledBarEl) {
                lastCalledBarEl.classList.remove('updated');
                void lastCalledBarEl.offsetWidth;
                lastCalledBarEl.classList.add('updated');
            }
        }
        lastCalledDataSignature = currentDataSignature;
    }

    // Update "Next Up" Tile (без змін)
    function updateKioskNext(tickets) {
        if (!kioskNextListEl) return;

        const placeholder = kioskNextListEl.querySelector('.placeholder');
        if (placeholder) placeholder.remove();

        const fragment = document.createDocumentFragment();

        if (!tickets || tickets.length === 0) {
            if (!kioskNextListEl.querySelector('.placeholder')) {
                kioskNextListEl.innerHTML = '<li class="placeholder">Черга порожня</li>';
            }
            return;
        }

        tickets.forEach(ticketData => {
            const li = document.createElement('li');
            li.dataset.ticket = ticketData.ticket;
            li.innerHTML = `
                <span class="ticket-number">${ticketData.ticket || 'N/A'}</span>
                <span class="service-name">${ticketData.service || 'N/A'}</span>
            `;
            fragment.appendChild(li);
        });

        kioskNextListEl.innerHTML = '';
        kioskNextListEl.appendChild(fragment);

        if (kioskNextListEl.children.length === 0 && !kioskNextListEl.querySelector('.placeholder')) {
            kioskNextListEl.innerHTML = '<li class="placeholder">Черга порожня</li>';
        }
    }

    // --- Fetch Data via API Polling ---
    async function fetchData() {
        // --- ЗМІНЕНО: Перевірка, чи є officeId ---
        if (!officeId) {
            console.warn("fetchData called but officeId is not set. Skipping.");
            return;
        }
        // --- КІНЕЦЬ ЗМІН ---
        console.log(`Fetching data for office: ${officeId}...`); // --- ЗМІНЕНО: Використовуємо officeId ---
        try {
            const url = new URL(API_ENDPOINT, window.location.origin);
            // --- ЗМІНЕНО: Використовуємо officeId ---
            url.searchParams.append('office', officeId);
            url.searchParams.append('limit_called', CALLED_LIMIT);
            url.searchParams.append('limit_waiting', WAITING_LIMIT);
            // --- КІНЕЦЬ ЗМІН ---

            const response = await fetch(url);

            if (!response.ok) {
                console.error(`API Error: ${response.status} ${response.statusText}`);
                updateLastCalled([{ ticket: "API Error", window: response.status, time: "" }]);
                updateKioskNext([{ ticket: "API Error", service: response.statusText }]);
                return;
            }

            const data = await response.json();

            if (data.error) {
                console.error(`API returned error: ${data.error}`);
                updateLastCalled([{ ticket: "API Error", window: "Config?", time: "" }]);
                updateKioskNext([{ ticket: "API Error", service: data.error }]);
            } else if (data.message) {
                const displayData = data.message;
                console.log("Data received:", displayData);
                updateLastCalled(displayData.last_called || []);
                updateKioskNext(displayData.waiting || []);
            } else {
                console.error("Unexpected API response format:", data);
                updateLastCalled([{ ticket: "API Format Error", window: "", time: "" }]);
                updateKioskNext([{ ticket: "API Format Error", service: "" }]);
            }

        } catch (error) {
            console.error("Error fetching display data:", error);
            updateLastCalled([{ ticket: "Network Error", window: "", time: "" }]);
            updateKioskNext([{ ticket: "Network Error", service: "" }]);
        }
    }
    // ------------------------------------

    // --- INITIALIZATION & INTERVALS ---
    // --- ЗМІНЕНО: Запускаємо логіку тільки якщо initializeDisplayBoard повернула true ---
    if (initializeDisplayBoard()) {
        updateTime(); // Initial time update
        setInterval(updateTime, 1000); // Update time every second

        fetchData(); // Initial data load from API
        setInterval(fetchData, POLLING_INTERVAL); // Start polling the API
    }
    // --- КІНЕЦЬ ЗМІН ---
    // ------------------------------------
});