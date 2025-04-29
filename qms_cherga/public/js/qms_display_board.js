document.addEventListener('DOMContentLoaded', () => {
    // --- Configuration ---
    const API_ENDPOINT = "/api/method/qms_cherga.api.get_display_data"; // Шлях до API
    const POLLING_INTERVAL = 7000; // Інтервал опитування в мілісекундах (7 секунд)
    const CALLED_LIMIT = 3; // Скільки останніх викликаних показувати
    const WAITING_LIMIT = 20; // Скільки очікуючих показувати
    // ---------------------

    // --- Отримуємо ID офісу з URL ---
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
            document.body.innerHTML = '<div class="container"><div class="error-message" style="color: red; text-align: center; padding: 50px; font-size: 1.2em;">Помилка: Не вказано параметр "office" в URL адресі табло.<br>Приклад: /qms_display_board.html?office=YOUR_OFFICE_ID</div></div>';
            console.error("Office ID not found in URL parameters for display board.");
            return false; // Зупиняємо ініціалізацію
        }
        console.log(`Display board initialized for Office ID: ${officeId}`);
        return true; // ID знайдено
    }
    // --- КІНЕЦЬ ОТРИМАННЯ ID ---

    // DOM References
    const currentDateEl = document.getElementById('current-date');
    const currentTimeEl = document.getElementById('current-time');
    const lastCallsListEl = document.getElementById('last-calls-list');
    const kioskNextListEl = document.getElementById('kiosk-next-list');
    const lastCalledBarEl = document.getElementById('last-called-bar');
    const callSound = document.getElementById('call-sound'); // NEW: Отримуємо посилання на аудіо елемент тут

    let lastCalledDataSignature = ''; // Зберігає "підпис" попереднього стану викликаних
    let previousCallItemsSet = new Set(); // NEW: Зберігає унікальні ідентифікатори попередніх викликів для легкого порівняння

    // Date/Time Formatting
    function formatDate(date) {
        const options = { year: 'numeric', month: '2-digit', day: '2-digit' };
        return date.toLocaleDateString('uk-UA', options);
    }
    function formatTime(date) {
        const options = { hour: '2-digit', minute: '2-digit', second: '2-digit' };
        return date.toLocaleTimeString('uk-UA', options);
    }

    // Update Date/Time Display
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
        const currentDataSignature = JSON.stringify(calls); // Поточний стан для загального порівняння

        if (!calls || calls.length === 0) {
            if (!lastCallsListEl.querySelector('.placeholder')) {
                lastCallsListEl.innerHTML = '<span class="placeholder" style="color: #ccc;">Немає активних викликів</span>';
            }
            lastCalledDataSignature = currentDataSignature;
            previousCallItemsSet = new Set(); // Очистити, якщо немає викликів
            return;
        }

        // --- Логіка для відтворення звуку при виявленні НОВОГО виклику ---
        let newCallDetected = false;
        const currentCallItemsSet = new Set(); // Зберігає унікальні ідентифікатори поточних викликів

        calls.forEach(call => {
            // Створюємо унікальний ідентифікатор для кожного виклику (квиток+вікно+час може бути не надійним, якщо час оновлюється)
            // Краще використовувати квиток+вікно, якщо це унікально, або додати ID виклику з бекенду, якщо є.
            // Припустимо, квиток+вікно достатньо унікальні для одного моменту часу.
            const callIdentifier = `${call.ticket}-${call.window}`;
            currentCallItemsSet.add(callIdentifier);

            // Перевіряємо, чи цей виклик був у попередньому оновленні
            if (!previousCallItemsSet.has(callIdentifier)) {
                newCallDetected = true;
                console.log(`New call detected: ${call.ticket} to ${call.window}`);
                // Анімація/виділення для нового квитка (якщо потрібно виділяти конкретний новий)
                // highlightCalledTicket(call.ticket, call.window); // Ваш існуючий виклик анімації
            }
        });

        // Відтворюємо звук, якщо:
        // 1. Був виявлений хоча б один новий виклик (newCallDetected = true)
        // 2. Це не перше завантаження даних (lastCalledDataSignature !== '')
        // 3. Є елемент <audio> (callSound існує)
        if (newCallDetected && lastCalledDataSignature !== '' && callSound) {
            // MODIFIED: Спроба відтворення звуку
            callSound.play().catch(error => {
                // Важливо: Браузери блокують авто-відтворення звуку до першої взаємодії користувача зі сторінкою (клік).
                // Це стандартна політика безпеки.
                // Якщо звук не грає автоматично, користувач має клікнути десь на сторінці один раз після завантаження.
                console.warn("Sound playback failed. Reason:", error, "- This might be due to browser autoplay restrictions. User interaction might be required first.");
            });
            // Якщо потрібно візуальне виділення всього блоку при новому виклику:
            highlightCalledTicket(null, null); // Викликаємо загальну анімацію
        }
        // --- Кінець логіки звуку ---

        // Оновлення списку на екрані (ваш існуючий код)
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

        // Зберігаємо поточний стан для наступного порівняння
        lastCalledDataSignature = currentDataSignature;
        previousCallItemsSet = currentCallItemsSet; // Оновлюємо набір попередніх викликів
    }

    // Update "Next Up" Tile
    function updateKioskNext(tickets) {
        // ... (ваш код без змін) ...
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

    // Функція для візуального виділення (MODIFIED: тепер викликається тільки при новому виклику, якщо потрібно)
    function highlightCalledTicket(ticketNumber, windowName) {
        if (lastCalledBarEl) {
            lastCalledBarEl.classList.remove('updated');
            void lastCalledBarEl.offsetWidth; // Trigger reflow
            lastCalledBarEl.classList.add('updated');
        }
        // Якщо ви хотіли виділяти конкретний рядок:
        // Знайдіть елемент за ticketNumber/windowName і додайте йому клас
    }

    // --- Fetch Data via API Polling ---
    async function fetchData() {
        if (!officeId) {
            console.warn("fetchData called but officeId is not set. Skipping.");
            return;
        }
        const overlayElement = document.getElementById('office-closed-overlay');
        const mainContentElement = document.getElementById('main-content'); // Можливо, сховати і його
        const lastCalledBarElement = document.getElementById('last-called-bar'); // І його теж

        try {
            const url = new URL(API_ENDPOINT, window.location.origin);
            url.searchParams.append('office', officeId);
            url.searchParams.append('limit_called', CALLED_LIMIT);
            url.searchParams.append('limit_waiting', WAITING_LIMIT);

            const response = await fetch(url);
            if (!response.ok) {
                console.error(`API Error: ${response.status} ${response.statusText}`);
                // Показуємо оверлей з помилкою
                if (overlayElement) {
                    overlayElement.querySelector('span').textContent = `Помилка ${response.status}: Не вдалося завантажити дані.`;
                    overlayElement.style.display = 'flex'; // Показати оверлей
                }
                // Ховаємо основний контент
                if (mainContentElement) mainContentElement.style.visibility = 'hidden';
                if (lastCalledBarElement) lastCalledBarElement.style.visibility = 'hidden';
                return;
            }

            const data = await response.json();

            if (data.message) {
                const displayData = data.message;
                console.log("Data received:", displayData);

                // Перевіряємо статус офісу
                if (displayData.office_status === "closed") {
                    console.log("Office is closed:", displayData.message);
                    if (overlayElement) {
                        overlayElement.querySelector('span').textContent = displayData.message || "Електронна черга наразі не працює.";
                        overlayElement.style.display = 'flex'; // Показати оверлей
                    }
                    // Ховаємо основний контент
                    if (mainContentElement) mainContentElement.style.visibility = 'hidden';
                    if (lastCalledBarElement) lastCalledBarElement.style.visibility = 'hidden';
                    // Очистити списки не обов'язково, бо вони приховані
                    updateLastCalled([]); // Очистка для консистентності
                    updateKioskNext([]); // Очистка для консистентності

                } else if (displayData.office_status === "open") {
                    console.log("Office is open.");
                    if (overlayElement) {
                        overlayElement.style.display = 'none'; // Сховати оверлей
                    }
                    // Показуємо основний контент
                    if (mainContentElement) mainContentElement.style.visibility = 'visible';
                    if (lastCalledBarElement) lastCalledBarElement.style.visibility = 'visible';
                    // Оновлюємо дані як зазвичай
                    updateLastCalled(displayData.last_called || []);
                    updateKioskNext(displayData.waiting || []);
                } else {
                    // Невідомий статус або помилка з бекенду
                    console.error("Unknown office_status or error from API:", displayData);
                    if (overlayElement) {
                        overlayElement.querySelector('span').textContent = displayData.message || "Помилка: Не вдалося визначити статус черги.";
                        overlayElement.style.display = 'flex';
                    }
                    if (mainContentElement) mainContentElement.style.visibility = 'hidden';
                    if (lastCalledBarElement) lastCalledBarElement.style.visibility = 'hidden';
                }
            } else {
                // Неочікуваний формат відповіді (немає message)
                console.error("Unexpected API response format:", data);
                if (overlayElement) {
                    overlayElement.querySelector('span').textContent = "Помилка: Неочікувана відповідь сервера.";
                    overlayElement.style.display = 'flex';
                }
                if (mainContentElement) mainContentElement.style.visibility = 'hidden';
                if (lastCalledBarElement) lastCalledBarElement.style.visibility = 'hidden';
            }

        } catch (error) {
            console.error("Error fetching display data:", error);
            // Показуємо оверлей з помилкою зв'язку
            if (overlayElement) {
                overlayElement.querySelector('span').textContent = "Помилка зв'язку з сервером.";
                overlayElement.style.display = 'flex'; // Показати оверлей
            }
            // Ховаємо основний контент
            if (mainContentElement) mainContentElement.style.visibility = 'hidden';
            if (lastCalledBarElement) lastCalledBarElement.style.visibility = 'hidden';
            // Очищення даних тут не обов'язкове, але можна зробити
            updateLastCalled([]);
            updateKioskNext([]);
        }

    }
    // ------------------------------------

    // --- INITIALIZATION & INTERVALS ---
    if (initializeDisplayBoard()) {
        updateTime(); // Initial time update
        setInterval(updateTime, 1000); // Update time every second

        fetchData(); // Initial data load from API
        setInterval(fetchData, POLLING_INTERVAL); // Start polling the API
    }
    // --- КІНЕЦЬ INITIALIZATION & INTERVALS ---
});