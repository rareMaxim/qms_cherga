document.addEventListener('DOMContentLoaded', () => {
    // --- Configuration ---
    const API_ENDPOINT = "qms_cherga.api.get_display_data"; // Шлях до API
    const POLLING_INTERVAL = 7000; // Інтервал оновлення в мс
    const CALLED_LIMIT = 3;        // Кількість останніх викликаних
    const WAITING_LIMIT = 30;      // Макс. кількість очікуючих для показу
    const HIGHLIGHT_DURATION = 8000; // Тривалість підсвічування нового виклику
    // ---------------------

    let officeId = null;

    // --- Функції отримання параметрів URL та ініціалізації (без змін) ---
    function getUrlParameter(name) {
        name = name.replace(/[\[]/, '\\[').replace(/[\]]/, '\\]');
        const regex = new RegExp('[\\?&]' + name + '=([^&#]*)');
        const results = regex.exec(location.search);
        return results === null ? '' : decodeURIComponent(results[1].replace(/\+/g, ' '));
    }
    function initializeDisplayBoard() {
        officeId = getUrlParameter('office');
        if (!officeId) {
            document.body.innerHTML = `<div class="container"><div class="error-message" style="color: red; text-align: center; padding: 50px; font-size: 1.2em;">${__("Error: Parameter 'office' not specified in the display board URL.")}<br>${__("Example:")} /qms_display_board.html?office=YOUR_OFFICE_ID</div></div>`;
            console.error("Office ID not found in URL parameters for display board.");
            return false;
        }
        console.log(`Display board initialized for Office ID: ${officeId}`);
        return true;
    }

    // --- DOM References (додано lastCalledSeparatorEl) ---
    const currentDateEl = document.getElementById('current-date');
    const currentTimeEl = document.getElementById('current-time');
    const lastCallsListEl = document.getElementById('last-calls-list');
    const kioskNextListEl = document.getElementById('kiosk-next-list');
    const lastCalledBarEl = document.getElementById('last-called-bar');
    const callSound = document.getElementById('call-sound');
    const officeClosedOverlayEl = document.getElementById('office-closed-overlay');
    const mainContentEl = document.getElementById('main-content');
    const timeBarEl = document.getElementById('time-bar');
    const infoMessageBarEl = document.getElementById('info-message-bar');
    const lastCalledSeparatorEl = document.getElementById('last-called-separator'); // Додано

    let lastCalledDataSignature = '';
    let previousCallItemsMap = new Map();

    // --- Функції форматування дати/часу та оновлення часу (без змін) ---
    function formatDate(date) {
        const options = {
            year: 'numeric',
            month: 'long',
            day: 'numeric'
        };
        return date.toLocaleDateString('uk-UA', options);
    }
    function formatTime(date) {
        const options = {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        };
        return date.toLocaleTimeString('uk-UA', options);
    }
    function updateTime() {
        const now = new Date();
        if (currentDateEl)
            currentDateEl.textContent = formatDate(now);
        if (currentTimeEl)
            currentTimeEl.textContent = formatTime(now);
    }

    // --- Функції оновлення блоків "Last Called" та "Next Up" ---
    // --- Оновлено updateLastCalled ---
    function updateLastCalled(calls) {
        // Додано перевірку наявності елементів
        if (!lastCallsListEl || !lastCalledBarEl || !lastCalledSeparatorEl)
            return;

        const hasCalls = calls && calls.length > 0;
        const currentDataSignature = JSON.stringify(calls);

        if (hasCalls) {
            // Показуємо блок та роздільник
            lastCalledBarEl.style.display = 'block'; // Або інший стиль за замовчуванням, якщо використовували класи
            lastCalledSeparatorEl.style.display = 'block';

            const fragment = document.createDocumentFragment();
            let newCallDetected = false;
            const currentCallIdentifiers = new Set();
            const nowTimestamp = Date.now();

            calls.forEach(call => {
                const callIdentifier = `${call.ticket}-${call.window}`;
                currentCallIdentifiers.add(callIdentifier);
                const previousTimestamp = previousCallItemsMap.get(callIdentifier);
                if (lastCalledDataSignature !== '' && previousTimestamp === undefined) {
                    newCallDetected = true;
                    console.log(`New call detected: ${call.ticket} to ${call.window}`);
                    previousCallItemsMap.set(callIdentifier, nowTimestamp);
                    call.isNew = true;
                }
                else if (previousTimestamp !== undefined) {
                    previousCallItemsMap.set(callIdentifier, nowTimestamp);
                } else {
                    previousCallItemsMap.set(callIdentifier, nowTimestamp);
                }
                const item = document.createElement('div');
                item.classList.add('call-item');
                item.dataset.callId = callIdentifier;
                item.innerHTML = ` ${call.ticket || 'N/A'} <span class="window-info">${call.window ? call.window : 'N/A'}</span> <span class="time-info">(${call.time || '--:--'})</span> `;
                if (call.isNew) {
                    item.classList.add('new-call-highlight');
                    setTimeout(() => {
                        const elementToClear = lastCallsListEl.querySelector(`[data-call-id="${callIdentifier}"]`);
                        if (elementToClear) {
                            elementToClear.classList.remove('new-call-highlight');
                            elementToClear.style.animation = 'none';
                        }
                    }, HIGHLIGHT_DURATION);
                } fragment.appendChild(item);
            });

            const currentKeys = Array.from(previousCallItemsMap.keys());
            currentKeys.forEach(key => {
                if (!currentCallIdentifiers.has(key)) {
                    previousCallItemsMap.delete(key);
                }
            });

            if (newCallDetected && callSound) {
                callSound.play().catch(error => {
                    console.warn("Sound playback failed. Reason:", error);
                });
                if (lastCalledBarEl) {
                    lastCalledBarEl.classList.remove('updated');
                    void lastCalledBarEl.offsetWidth;
                    lastCalledBarEl.classList.add('updated');
                }
            }
            lastCallsListEl.innerHTML = ''; // Очищаємо перед додаванням нових
            lastCallsListEl.appendChild(fragment);

        } else {
            // Ховаємо блок та роздільник
            lastCalledBarEl.style.display = 'none';
            lastCalledSeparatorEl.style.display = 'none';
            lastCallsListEl.innerHTML = ''; // Очищаємо вміст (placeholder не потрібен)
            previousCallItemsMap.clear(); // Очищаємо мапу, якщо викликів немає
        }

        lastCalledDataSignature = currentDataSignature;
    }
    // --- updateKioskNext залишається без змін ---
    function updateKioskNext(tickets) {
        if (!kioskNextListEl)
            return;
        const placeholder = kioskNextListEl.querySelector('.placeholder');
        if (placeholder)
            placeholder.remove();
        const fragment = document.createDocumentFragment();
        if (!tickets || tickets.length === 0) {
            if (!kioskNextListEl.querySelector('.placeholder')) {
                kioskNextListEl.innerHTML = `<li class="placeholder">${__("Queue is empty")}</li>`;
            } return;
        } tickets.forEach(ticketData => {
            const li = document.createElement('li');
            li.dataset.ticket = ticketData.ticket;
            if (ticketData.service_id) {
                li.dataset.serviceId = ticketData.service_id;
            }
            else if (ticketData.service) {
                const safeServiceId = ticketData.service.replace(/\s+/g, '-').toLowerCase();
                li.dataset.serviceName = safeServiceId;
            }
            li.innerHTML = ` <span class="ticket-number">${ticketData.ticket || 'N/A'}</span> <span class="service-name">${ticketData.service || 'N/A'}</span> `;
            fragment.appendChild(li);
        });
        kioskNextListEl.innerHTML = '';
        kioskNextListEl.appendChild(fragment);
        if (kioskNextListEl.children.length === 0 && !kioskNextListEl.querySelector('.placeholder')) {
            kioskNextListEl.innerHTML = `<li class="placeholder">${__("Queue is empty")}</li>`;
        }
    }

    // --- Fetch Data (без змін) ---
    async function fetchData() {
        if (!officeId) {
            console.warn("fetchData called but officeId is not set. Skipping.");
            return;
        }

        try {
            // Використовуємо frappe.call для автоматичної обробки сесії та CSRF
            const response = await frappe.call({
                method: API_ENDPOINT, // Використовуємо константу
                args: {
                    office: officeId,
                    limit_called: CALLED_LIMIT,
                    limit_waiting: WAITING_LIMIT
                },
                // Важливо: Не використовуємо type: "GET", бо frappe.call за замовчуванням POST
                // Можна додати freeze: true, freeze_message: "Оновлення..." для індикатора Frappe
            });

            // Перевіряємо стандартизовану відповідь у response.message
            if (response.message && response.message.status === 'success') {
                const displayData = response.message.data; // Дані тепер тут
                console.log("Data received:", displayData);

                // Обробка інформаційного повідомлення (якщо є)
                if (infoMessageBarEl) {
                    infoMessageBarEl.innerHTML = displayData.info_message; // Використовуємо innerHTML для можливих тегів
                    if (infoMessageBarEl.textContent) {
                        infoMessageBarEl.style.display = (displayData.info_message.trim() === '') ? 'none' : 'block'; //
                        infoMessageBarEl.setAttribute('aria-hidden', infoMessageBarEl.style.display === 'none'); //
                    } else {
                        infoMessageBarEl.textContent = ''; //
                        infoMessageBarEl.style.display = 'none'; //
                        infoMessageBarEl.setAttribute('aria-hidden', 'true'); //
                    }
                }

                // Перевіряємо статус офісу всередині data
                if (displayData.office_status === "open") { //
                    hideOverlay(); // Сховати оверлей, якщо був показаний
                    updateLastCalled(displayData.last_called || []); //
                    updateKioskNext(displayData.waiting || []); //
                } else {
                    // Якщо статус не 'open', але відповідь 'success', показуємо оверлей з повідомленням за замовчуванням
                    showOverlay(__("Queue management system is currently inactive.")); //
                    updateLastCalled([]); //
                    updateKioskNext([]); //
                }
            }
            else if (response.message && response.message.status === 'info') {
                // Обробка інформаційних відповідей (наприклад, офіс зачинено)
                const displayData = response.message.data; // Можуть бути дані, напр. office_status
                const message = response.message.message || __("Queue management system is currently inactive."); //
                console.info("Info from get_display_data:", message, displayData);

                showOverlay(message); // Показуємо оверлей з повідомленням від API
                // Очищаємо списки
                updateLastCalled([]); //
                updateKioskNext([]); //
                // Очищаємо інфо-бар
                if (infoMessageBarEl) {
                    infoMessageBarEl.style.display = 'none'; //
                    infoMessageBarEl.setAttribute('aria-hidden', 'true'); //
                }

            } else {
                // Обробка помилок, що повернув бекенд (status === 'error')
                const errorMessage = response.message?.message || __("Unexpected response structure from server."); //
                console.error("API Error (get_display_data):", errorMessage, response.message?.details);
                showOverlay(`${__("Error")}: ${errorMessage}`); //
                // Очищаємо дані при помилці
                updateLastCalled([]); //
                updateKioskNext([]); //
                if (infoMessageBarEl)
                    infoMessageBarEl.style.display = 'none'; //
            }

        } catch (error) {
            // Обробка помилок зв'язку або системних помилок frappe.call
            console.error("Error fetching display data:", error);
            // Показуємо помилку зв'язку
            const networkErrorMsg = __("Error connecting to the server."); //
            // Перевіряємо, чи є повідомлення про помилку в об'єкті error
            const specificErrorMsg = error.message || (error.responseText ? JSON.parse(error.responseText)?._error_message : null); //
            showOverlay(specificErrorMsg || networkErrorMsg); //

            // Очищаємо дані при помилці зв'язку
            updateLastCalled([]); //
            updateKioskNext([]); //
            if (infoMessageBarEl)
                infoMessageBarEl.style.display = 'none'; //
        }
    }

    // --- Функції керування оверлеєм (змінено: приховуємо last-called-bar) ---
    function showOverlay(message) {
        if (officeClosedOverlayEl) {
            const messageSpan = officeClosedOverlayEl.querySelector('span');
            if (messageSpan)
                messageSpan.innerHTML = message.replace('\n', '<br>');
            officeClosedOverlayEl.style.display = 'flex';
        }
        if (mainContentEl)
            mainContentEl.style.display = 'none';
        // Змінено: Ховаємо last-called-bar та роздільник при показі оверлея
        if (lastCalledBarEl)
            lastCalledBarEl.style.display = 'none';
        if (lastCalledSeparatorEl)
            lastCalledSeparatorEl.style.display = 'none';
        // Кінець зміни
        if (timeBarEl) timeBarEl.style.display = 'none';
        // Також ховаємо інфо-бар при показі оверлея
        if (infoMessageBarEl)
            infoMessageBarEl.style.display = 'none';
    }
    function hideOverlay() {
        if (officeClosedOverlayEl) {
            officeClosedOverlayEl.style.display = 'none';
        }
        if (mainContentEl)
            mainContentEl.style.display = 'flex';
        // Змінено: Не показуємо last-called-bar тут, це робить updateLastCalled
        // if (lastCalledBarEl)
        //     lastCalledBarEl.style.display = 'block';
        // Кінець зміни
        if (timeBarEl) timeBarEl.style.display = 'flex';
        // Інфо-бар показується/ховається в fetchData
    }


    // --- INITIALIZATION & INTERVALS (без змін) ---
    if (initializeDisplayBoard()) {
        updateTime();
        setInterval(updateTime, 1000);
        fetchData(); // Initial data load
        setInterval(fetchData, POLLING_INTERVAL); // Start polling
    }
});