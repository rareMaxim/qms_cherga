document.addEventListener('DOMContentLoaded', () => {
    // --- Configuration ---
    const API_ENDPOINT = "/api/method/qms_cherga.api.get_display_data";
    const POLLING_INTERVAL = 7000;
    const CALLED_LIMIT = 3; // Або більше, якщо потрібно
    const WAITING_LIMIT = 30; // Можна збільшити
    const HIGHLIGHT_DURATION = 8000; // Тривалість підсвічування нового виклику (мс)
    // ---------------------

    let officeId = null;

    function getUrlParameter(name) {
        name = name.replace(/[\[]/, '\\[').replace(/[\]]/, '\\]');
        const regex = new RegExp('[\\?&]' + name + '=([^&#]*)');
        const results = regex.exec(location.search);
        return results === null ? '' : decodeURIComponent(results[1].replace(/\+/g, ' '));
    }

    function initializeDisplayBoard() {
        officeId = getUrlParameter('office');
        if (!officeId) {
            document.body.innerHTML = '<div class="container"><div class="error-message" style="color: red; text-align: center; padding: 50px; font-size: 1.2em;">Помилка: Не вказано параметр "office" в URL адресі табло.<br>Приклад: /qms_display_board.html?office=YOUR_OFFICE_ID</div></div>';
            console.error("Office ID not found in URL parameters for display board.");
            return false;
        }
        console.log(`Display board initialized for Office ID: ${officeId}`);
        return true;
    }

    // DOM References
    const currentDateEl = document.getElementById('current-date');
    const currentTimeEl = document.getElementById('current-time');
    const lastCallsListEl = document.getElementById('last-calls-list');
    const kioskNextListEl = document.getElementById('kiosk-next-list');
    const lastCalledBarEl = document.getElementById('last-called-bar');
    const callSound = document.getElementById('call-sound');
    const officeClosedOverlayEl = document.getElementById('office-closed-overlay');
    const mainContentEl = document.getElementById('main-content');
    const timeBarEl = document.getElementById('time-bar'); // Додано для приховування
    const infoMessageBarEl = document.getElementById('info-message-bar');

    let lastCalledDataSignature = '';
    let previousCallItemsMap = new Map(); // Використовуємо Map для зберігання часу останньої появи

    // Date/Time Formatting
    function formatDate(date) {
        const options = { year: 'numeric', month: 'long', day: 'numeric' }; // Повний місяць
        return date.toLocaleDateString('uk-UA', options);
    }
    function formatTime(date) {
        const options = { hour: '2-digit', minute: '2-digit', second: '2-digit' };
        return date.toLocaleTimeString('uk-UA', options);
    }

    function updateTime() {
        const now = new Date();
        if (currentDateEl) currentDateEl.textContent = formatDate(now);
        if (currentTimeEl) currentTimeEl.textContent = formatTime(now);
    }

    // Update "Last Called" Block
    function updateLastCalled(calls) {
        if (!lastCallsListEl) return;

        const placeholder = lastCallsListEl.querySelector('.placeholder');
        if (placeholder) placeholder.remove();

        const fragment = document.createDocumentFragment();
        const currentDataSignature = JSON.stringify(calls);
        let newCallDetected = false;
        const currentCallIdentifiers = new Set(); // Зберігає унікальні ID поточних викликів
        const nowTimestamp = Date.now(); // Поточний час для порівняння

        if (!calls || calls.length === 0) {
            if (!lastCallsListEl.querySelector('.placeholder')) {
                lastCallsListEl.innerHTML = '<span class="placeholder" style="color: #ccc;">Немає активних викликів</span>';
            }
            lastCalledDataSignature = currentDataSignature;
            previousCallItemsMap.clear(); // Очистити Map
            return;
        }

        calls.forEach(call => {
            // Унікальний ідентифікатор (квиток + вікно, якщо немає кращого ID з бекенду)
            const callIdentifier = `${call.ticket}-${call.window}`;
            currentCallIdentifiers.add(callIdentifier);

            const previousTimestamp = previousCallItemsMap.get(callIdentifier);

            // Перевірка на новий виклик:
            // 1. Не було раніше (previousTimestamp === undefined)
            // 2. АБО був, але час змінився (хоча це менш надійно, якщо час постійно оновлюється)
            // 3. І це не перше завантаження даних (lastCalledDataSignature !== '')
            if (lastCalledDataSignature !== '' && previousTimestamp === undefined) {
                newCallDetected = true;
                console.log(`New call detected: ${call.ticket} to ${call.window}`);
                // Оновлюємо/додаємо в Map з поточним часом для відстеження
                previousCallItemsMap.set(callIdentifier, nowTimestamp);
                // Додаємо клас для підсвічування (буде додано до елемента нижче)
                call.isNew = true; // Додаємо тимчасовий прапорець
            } else if (previousTimestamp !== undefined) {
                // Якщо елемент вже був, просто оновлюємо час останньої появи
                previousCallItemsMap.set(callIdentifier, nowTimestamp);
            } else {
                // Якщо це перший запуск, просто додаємо в Map
                previousCallItemsMap.set(callIdentifier, nowTimestamp);
            }

            // Створення DOM-елемента
            const item = document.createElement('div');
            item.classList.add('call-item');
            item.dataset.callId = callIdentifier; // Додаємо ID для легшого пошуку
            item.innerHTML = `
                ${call.ticket || 'N/A'}
                <span class="window-info">${call.window ? 'Вікно ' + call.window : 'N/A'}</span>
                <span class="time-info">(${call.time || '--:--'})</span>
            `;
            // Якщо це новий виклик, додаємо клас і ставимо таймер на видалення класу
            if (call.isNew) {
                item.classList.add('new-call-highlight');
                setTimeout(() => {
                    // Шукаємо елемент знову (він міг бути перемальований)
                    const elementToClear = lastCallsListEl.querySelector(`[data-call-id="${callIdentifier}"]`);
                    if (elementToClear) {
                        elementToClear.classList.remove('new-call-highlight');
                        // Прибираємо анімацію
                        elementToClear.style.animation = 'none';
                    }
                }, HIGHLIGHT_DURATION);
            }
            fragment.appendChild(item);
        });

        // Очищаємо старі елементи з Map, яких вже немає у поточних даних
        const currentKeys = Array.from(previousCallItemsMap.keys());
        currentKeys.forEach(key => {
            if (!currentCallIdentifiers.has(key)) {
                previousCallItemsMap.delete(key);
            }
        });


        // Відтворення звуку, якщо виявлено НОВИЙ виклик (і не перше завантаження)
        if (newCallDetected && callSound) {
            callSound.play().catch(error => {
                console.warn("Sound playback failed. Reason:", error);
            });
            // Можна також застосувати загальну анімацію до #last-called-bar, якщо потрібно
            if (lastCalledBarEl) {
                lastCalledBarEl.classList.remove('updated');
                void lastCalledBarEl.offsetWidth; // Trigger reflow
                lastCalledBarEl.classList.add('updated');
            }
        }

        // Оновлення списку на екрані
        lastCallsListEl.innerHTML = '';
        lastCallsListEl.appendChild(fragment);

        // Зберігаємо поточний стан
        lastCalledDataSignature = currentDataSignature;
    }

    // Update "Next Up" Tile
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
            // Додаємо data-service-id (або інший атрибут, якщо бекенд повертає ID)
            // Припускаємо, що ticketData.service містить назву або ID послуги
            if (ticketData.service_id) { // Якщо бекенд повертає ID
                li.dataset.serviceId = ticketData.service_id;
            } else if (ticketData.service) {
                // Якщо ID немає, генеруємо атрибут з назви (менш надійно для стилізації)
                const safeServiceId = ticketData.service.replace(/\s+/g, '-').toLowerCase();
                li.dataset.serviceName = safeServiceId;
            }

            li.innerHTML = `
                <span class="ticket-number">${ticketData.ticket || 'N/A'}</span>
                <span class="service-name">${ticketData.service || 'N/A'}</span>
            `;
            fragment.appendChild(li);
        });

        // --- Логіка Плавного Оновлення (Базова) ---
        // Простий варіант: просто замінюємо весь вміст
        kioskNextListEl.innerHTML = '';
        kioskNextListEl.appendChild(fragment);
        // Складніший варіант (порівняння і додавання/видалення) потребує більше коду

        // --- Кінець Логіки Плавного Оновлення ---

        if (kioskNextListEl.children.length === 0 && !kioskNextListEl.querySelector('.placeholder')) {
            kioskNextListEl.innerHTML = '<li class="placeholder">Черга порожня</li>';
        }
    }


    // --- Fetch Data via API Polling ---
    async function fetchData() {
        if (!officeId) {
            console.warn("fetchData called but officeId is not set. Skipping.");
            return;
        }

        try {
            const url = new URL(API_ENDPOINT, window.location.origin);
            url.searchParams.append('office', officeId);
            url.searchParams.append('limit_called', CALLED_LIMIT);
            url.searchParams.append('limit_waiting', WAITING_LIMIT);

            const response = await fetch(url);
            if (!response.ok) {
                console.error(`API Error: ${response.status} ${response.statusText}`);
                showOverlay(`Помилка ${response.status}: Не вдалося завантажити дані.`);
                return;
            }

            const data = await response.json();

            if (data.message) {
                const displayData = data.message;
                console.log("Data received:", displayData);

                // --- Обробка інформаційного повідомлення ---
                if (infoMessageBarEl) {
                    if (displayData.info_message) {
                        infoMessageBarEl.innerHTML = displayData.info_message;
                        infoMessageBarEl.style.display = 'block'; // Показати блок
                        if (infoMessageBarEl.textContent.trim() === '') {

                            infoMessageBarEl.style.display = 'none'; // Сховати блок
                        }
                    } else {
                        infoMessageBarEl.textContent = ''; // Очистити
                        infoMessageBarEl.style.display = 'none'; // Сховати блок
                        infoMessageBarEl.setAttribute('aria-hidden', 'true'); // Додано для доступності
                    }
                }

                if (displayData.office_status === "closed") {
                    showOverlay(displayData.message || "Електронна черга наразі не працює.");
                    // Очищаємо дані, коли офіс закритий
                    updateLastCalled([]);
                    updateKioskNext([]);
                } else if (displayData.office_status === "open") {
                    hideOverlay();
                    updateLastCalled(displayData.last_called || []);
                    updateKioskNext(displayData.waiting || []);
                } else {
                    showOverlay(displayData.message || "Помилка: Не вдалося визначити статус черги.");
                }
            } else {
                if (infoMessageBarEl) infoMessageBarEl.style.display = 'none';
                showOverlay("Помилка: Неочікувана відповідь сервера.");
            }

        } catch (error) {
            console.error("Error fetching display data:", error);
            showOverlay("Помилка зв'язку з сервером.");
            // Очищаємо дані при помилці зв'язку
            updateLastCalled([]);
            updateKioskNext([]);
            if (infoMessageBarEl) infoMessageBarEl.style.display = 'none';
        }
    }

    // --- Функції для керування оверлеєм ---
    function showOverlay(message) {
        if (officeClosedOverlayEl) {
            const messageSpan = officeClosedOverlayEl.querySelector('span');
            if (messageSpan) messageSpan.innerHTML = message.replace('\n', '<br>'); // Дозволяємо переноси рядків
            officeClosedOverlayEl.style.display = 'flex';
        }
        // Ховаємо основний контент
        if (mainContentEl) mainContentEl.style.display = 'none'; // Використовуємо display none
        if (lastCalledBarEl) lastCalledBarEl.style.display = 'none';
        if (timeBarEl) timeBarEl.style.display = 'none';
    }

    function hideOverlay() {
        if (officeClosedOverlayEl) {
            officeClosedOverlayEl.style.display = 'none';
        }
        // Показуємо основний контент
        if (mainContentEl) mainContentEl.style.display = 'flex'; // Повертаємо display flex
        if (lastCalledBarEl) lastCalledBarEl.style.display = 'block'; // Або 'flex', залежно від початкового стану
        if (timeBarEl) timeBarEl.style.display = 'flex';
    }

    // --- INITIALIZATION & INTERVALS ---
    if (initializeDisplayBoard()) {
        updateTime();
        setInterval(updateTime, 1000);

        fetchData(); // Initial data load
        setInterval(fetchData, POLLING_INTERVAL); // Start polling
    }
    // --- END INITIALIZATION & INTERVALS ---
});