// qms_cherga/public/js/qms_kiosk_tailwind.js

document.addEventListener('DOMContentLoaded', () => {
    // --- DOM References ---
    const pages = document.querySelectorAll('.kiosk-page');
    const welcomePage = document.getElementById('page-welcome');
    const servicePage = document.getElementById('page-service');
    const infoPage = document.getElementById('page-info');
    const schedulePage = document.getElementById('page-schedule'); // Додано
    const confirmationPage = document.getElementById('page-confirmation');

    const officeNameDisplay = document.getElementById('office-name-display');
    const serviceContainer = document.getElementById('service-container');
    const nameInput = document.getElementById('input-name'); // Додано
    const phoneInput = document.getElementById('input-phone');
    const confirmationContent = document.getElementById('confirmation-content');
    const printingMessage = document.getElementById('printing-message');
    const timeoutCounterDisplay = document.getElementById('timeout-counter');
    const kioskLoadingIndicator = document.getElementById('kiosk-loading-indicator');
    const kioskErrorMessage = document.getElementById('kiosk-error-message');
    const startButtonContainer = document.getElementById('start-button-container');
    const dateGrid = document.getElementById('date-grid'); // Додано
    const timeSelectionSection = document.getElementById('time-selection-section'); // Додано
    const timeGrid = document.getElementById('time-grid'); // Додано
    const btnConfirmSchedule = document.getElementById('btn-confirm-schedule'); // Додано

    // --- State Variables ---
    let officeId = null;
    let officeInfo = null;
    let selectedServiceId = null;
    let selectedServiceName = null;
    let selectedDate = null; // Додано
    let selectedTime = null; // Додано
    let selectedAppointmentDateTime = null; // Додано (повна дата-час для API)
    let activeInputId = null;
    let ticketTimeoutId = null;
    let kioskServicesData = {};

    // --- Configuration ---
    const {
        TICKET_TIMEOUT_SECONDS = 15,
        PRINT_DELAY_MS = 500,
        PRINT_CLEANUP_MS = 4000,
        APPOINTMENT_DAYS_AHEAD = 7 // Додано
    } = window.qms_config || {};

    // --- Utility Functions ---
    function getUrlParameter(name) {
        name = name.replace(/[\[]/, '\\[').replace(/[\]]/, '\\]');
        const regex = new RegExp('[\\?&]' + name + '=([^&#]*)');
        const results = regex.exec(location.search);
        return results === null ? '' : decodeURIComponent(results[1].replace(/\+/g, ' '));
    }

    function __(text) { return typeof frappe !== 'undefined' ? frappe._(text) : text; }
    function showElement(element) { if (element) element.style.display = 'block'; }
    function hideElement(element) { if (element) element.style.display = 'none'; }
    function showFlexElement(element) { if (element) element.style.display = 'flex'; }

    // --- Page Navigation ---
    function showPage(pageId) {
        pages.forEach(page => page.classList.remove('active'));
        const nextPage = document.getElementById(pageId);
        if (nextPage) {
            nextPage.classList.add('active');
            window.scrollTo(0, 0);
        } else {
            console.error("Page not found:", pageId);
        }

        // Reset states based on the page being shown
        if (pageId !== 'page-info') hideKeyboard();
        if (pageId !== 'page-confirmation' && ticketTimeoutId) {
            clearTimeout(ticketTimeoutId);
            ticketTimeoutId = null;
        }
        if (pageId === 'page-service') {
            selectedServiceId = null;
            selectedServiceName = null;
            if (kioskServicesData.categories || kioskServicesData.services_no_category) {
                renderServicePageContent(kioskServicesData);
            } else {
                loadKioskServices();
            }
        }
        if (pageId === 'page-info') {
            // Очищаємо поля при кожному вході на цю сторінку (можна змінити)
            if (nameInput) nameInput.value = '';
            if (phoneInput) phoneInput.value = '';
        }
        if (pageId === 'page-schedule') { // Додано обробку для сторінки запису
            selectedDate = null;
            selectedTime = null;
            selectedAppointmentDateTime = null;
            resetDateSelection();
            resetTimeSelection();
            if (btnConfirmSchedule) btnConfirmSchedule.disabled = true;
            if (timeSelectionSection) hideElement(timeSelectionSection);
            // Запускаємо завантаження дат при переході на цю сторінку
            generateDateSlots();
        }
        if (pageId === 'page-confirmation') {
            hideElement(printingMessage);
            confirmationContent.innerHTML = `<div class="loading-indicator">${__("Обробка запиту...")}</div>`;
        }
        if (pageId === 'page-welcome') {
            if (!officeInfo) { loadOfficeInfo(); }
        }
    }
    window.showPage = showPage;

    // --- Keyboard Logic ---
    function activateKeyboard(type, inputId) {
        hideKeyboard();
        const keyboardId = `keyboard-${type}`;
        const keyboardElement = document.getElementById(keyboardId);
        if (keyboardElement) {
            keyboardElement.classList.add('active');
            activeInputId = inputId;
        }
    }
    function hideKeyboard() {
        document.querySelectorAll('.keyboard').forEach(kb => kb.classList.remove('active'));
        activeInputId = null;
    }
    function inputChar(char) {
        if (activeInputId) {
            const inputField = document.getElementById(activeInputId);
            if (activeInputId === 'input-phone' && inputField.value.length >= 13 && char !== '+') return;
            inputField.value += char;
        }
    }
    function backspace() {
        if (activeInputId) {
            const inputField = document.getElementById(activeInputId);
            inputField.value = inputField.value.slice(0, -1);
        }
    }
    window.activateKeyboard = activateKeyboard;
    window.hideKeyboard = hideKeyboard;
    window.inputChar = inputChar;
    window.backspace = backspace;

    // --- Service Selection ---
    function selectService(serviceId, serviceName) {
        selectedServiceId = serviceId;
        selectedServiceName = serviceName;
        console.log("Service selected:", selectedServiceId, selectedServiceName);
        showPage('page-info');
    }
    window.selectService = selectService;

    // --- Live Ticket Registration ---
    function registerNow() {
        hideKeyboard();
        if (!selectedServiceId) {
            showError(__("Послугу не обрано. Будь ласка, поверніться та оберіть послугу."));
            return;
        }
        const phone = phoneInput ? phoneInput.value.trim() : null;
        const name = nameInput ? nameInput.value.trim() : null; // Отримуємо ім'я

        // Валідація телефону (проста)
        if (phone && !/^\+?3?8?0\d{9}$/.test(phone.replace(/ /g, ''))) {
            showError(__("Некоректний формат номеру телефону. Введіть у форматі +380XXXXXXXXX або залиште поле порожнім."), infoPage);
            return;
        }

        showPage('page-confirmation');

        if (typeof frappe !== 'undefined' && frappe.call) {
            frappe.call({
                method: "qms_cherga.api.create_live_queue_ticket",
                args: {
                    service: selectedServiceId,
                    office: officeId,
                    visitor_phone: phone || undefined,
                    // Можна додати 'visitor_name': name || undefined, якщо API підтримує
                },
                callback: function (r) { handleTicketCreationResponse(r, name, phone); }, // Передаємо ім'я та телефон
                error: function (err) {
                    console.error("API call failed (create_live_queue_ticket):", err);
                    confirmationContent.innerHTML = `<div class="error-message">${__("Помилка зв'язку з сервером при створенні талону.")}</div>`;
                }
            });
        } else {
            console.error("frappe.call is not available.");
            confirmationContent.innerHTML = `<div class="error-message">${__("Системна помилка: неможливо з'єднатися з сервером.")}</div>`;
        }
    }
    window.registerNow = registerNow;

    // Оновимо обробник відповіді, щоб показувати ім'я
    function handleTicketCreationResponse(r, visitorName, visitorPhone) {
        if (r.message && r.message.status === "success") {
            const ticketData = r.message.data;
            if (ticketData && ticketData.ticket_number && ticketData.ticket_name) {
                confirmationContent.innerHTML = `
                    <h1 class="text-4xl font-bold text-green-600 mb-6">${__("Реєстрація успішна!")}</h1>
                    <div class="text-xl text-gray-700 space-y-2">
                        <p><strong>${__("Послуга")}:</strong> ${selectedServiceName || 'Не обрано'}</p>
                        ${visitorName ? `<p><strong>${__("Ім'я")}:</strong> ${visitorName}</p>` : ''}
                        ${visitorPhone ? `<p><strong>${__("Телефон")}:</strong> ${visitorPhone}</p>` : ''}
                        <p class="text-2xl font-semibold mt-4">${__("Ваш номер у черзі")}:</p>
                        <p class="text-7xl font-bold text-blue-600 my-4">${ticketData.ticket_number}</p>
                        <p>${__("Очікуйте на виклик до вікна/кабінету.")}</p>
                    </div>
                `;
                showFlexElement(printingMessage);
                printingMessage.classList.add('active');
                startTicketTimeout();
                triggerPrint(ticketData.ticket_name);
            } else {
                console.error("Ticket number or name missing in success response:", ticketData);
                confirmationContent.innerHTML = `<div class="error-message">${__("Талон створено, але не вдалося отримати деталі для відображення/друку.")}</div>`;
            }
        } else {
            const errorMessage = r.message?.message || __("Невідома помилка при створенні талону.");
            console.error("Error creating ticket:", errorMessage, r.message?.details);
            confirmationContent.innerHTML = `<div class="error-message">${__("Помилка створення талону")}: ${errorMessage}</div>`;
        }
    }

    // --- Appointment Scheduling Logic ---
    function goToScheduling() {
        hideKeyboard();
        if (!selectedServiceId) {
            showError(__("Спочатку оберіть послугу."), infoPage); // Повідомлення на сторінці info
            return;
        }
        // Валідацію ПІБ/телефону можна додати тут, якщо вони обов'язкові для запису
        // const name = nameInput ? nameInput.value.trim() : null;
        // if (!name) {
        //     showError(__("Будь ласка, введіть Ваше ім'я для попереднього запису."), infoPage);
        //     return;
        // }
        showPage('page-schedule');
    }
    window.goToScheduling = goToScheduling;

    function resetDateSelection() {
        document.querySelectorAll('#date-grid .date-slot').forEach(slot => {
            slot.classList.remove('selected', 'bg-blue-600', 'text-white', 'border-blue-700');
            // Повертаємо стандартні класи (якщо вони не змінювались)
            if (!slot.classList.contains('disabled')) {
                slot.classList.add('bg-white');
            }
        });
        selectedDate = null;
    }

    function resetTimeSelection() {
        document.querySelectorAll('#time-grid .time-slot').forEach(slot => {
            slot.classList.remove('selected', 'bg-blue-600', 'text-white', 'border-blue-700');
            if (!slot.classList.contains('disabled')) {
                slot.classList.add('bg-white');
            }
        });
        selectedTime = null;
        selectedAppointmentDateTime = null;
        if (btnConfirmSchedule) btnConfirmSchedule.disabled = true;
    }

    // Генерує кнопки з датами
    function generateDateSlots() {
        if (!dateGrid) return;
        dateGrid.innerHTML = `<div class="loading-indicator col-span-full">${__("Завантаження дат...")}</div>`; // Показати завантаження

        const today = new Date();
        let availableDatesHtml = '';
        const dateOptions = { weekday: 'short', day: 'numeric', month: 'long' };

        // Симулюємо отримання доступних дат (в реальності - з API)
        // Наприклад, наступні N робочих днів
        let count = 0;
        let currentDate = new Date(today);
        while (count < APPOINTMENT_DAYS_AHEAD) {
            const dayOfWeek = currentDate.getDay(); // 0=Неділя, 6=Субота
            if (dayOfWeek !== 0 && dayOfWeek !== 6) { // Пропускаємо вихідні
                const dateStr = currentDate.toISOString().split('T')[0]; // YYYY-MM-DD
                const displayDate = currentDate.toLocaleDateString('uk-UA', dateOptions);
                // Припускаємо, що всі робочі дні доступні (потрібно перевіряти через API)
                const isAvailable = true; // Заглушка, має бути результат API
                availableDatesHtml += `
                    <button
                        class="date-slot ${!isAvailable ? 'disabled' : ''}"
                        onclick="${isAvailable ? `selectDate(this, '${dateStr}')` : ''}"
                        ${!isAvailable ? 'disabled' : ''}>
                        ${displayDate}
                    </button>
                 `;
                count++;
            }
            currentDate.setDate(currentDate.getDate() + 1); // Наступний день
        }

        if (availableDatesHtml) {
            dateGrid.innerHTML = availableDatesHtml;
        } else {
            dateGrid.innerHTML = `<div class="col-span-full text-center text-gray-500 py-4">${__("Немає доступних дат для запису.")}</div>`;
        }
    }

    function selectDate(element, dateStr) {
        if (element.classList.contains('disabled')) return;
        resetDateSelection();
        element.classList.add('selected', 'bg-blue-600', 'text-white', 'border-blue-700');
        element.classList.remove('bg-white');
        selectedDate = dateStr;
        console.log("Date selected:", selectedDate);
        showFlexElement(timeSelectionSection);
        generateTimeSlots(selectedDate); // Передаємо обрану дату
        resetTimeSelection();
    }
    window.selectDate = selectDate; // Робимо глобальною

    // Оновлена функція генерації слотів часу
    function generateTimeSlots(date) {
        if (!timeGrid) return;
        timeGrid.innerHTML = `<div class="loading-indicator col-span-full">${__("Завантаження доступного часу...")}</div>`;
        if (timeSelectionSection) showFlexElement(timeSelectionSection); // Показуємо секцію

        // --- !!! ЗАГЛУШКА: Потрібно викликати API get_available_appointment_slots ---
        console.log(`TODO: Fetch available slots for ${selectedServiceId} in ${officeId} on ${date}`);
        if (!officeId || !selectedServiceId || !date) {
            timeGrid.innerHTML = `<div class="error-message col-span-full">${__("Не вдалося завантажити час. Оберіть дату та послугу.")}</div>`;
            return;
        }
        // Викликаємо API
        frappe.call({
            method: "qms_cherga.api.get_available_appointment_slots",
            args: {
                office: officeId,
                service: selectedServiceId,
                date: date
            },
            callback: function (r) {
                timeGrid.innerHTML = ''; // Очистити індикатор завантаження/попередні слоти
                if (r.message && r.message.status === 'success' && r.message.data?.is_available) {
                    if (r.message.data.slots && r.message.data.slots.length > 0) {
                        r.message.data.slots.forEach(slot => {
                            const button = document.createElement('button');
                            button.classList.add('time-slot'); // Додаємо базовий клас
                            button.textContent = slot.time; // Встановлюємо текст часу
                            // Зберігаємо повну дату-час для відправки в API
                            button.dataset.datetime = slot.datetime;
                            // Додаємо обробник кліку
                            button.onclick = () => selectTime(button, slot.time, slot.datetime);
                            // Додаємо клас 'bg-white' для доступних слотів (Tailwind)
                            button.classList.add('bg-white');
                            timeGrid.appendChild(button);
                        });
                    } else {
                        timeGrid.innerHTML = `<div class="col-span-full text-center text-gray-500 py-4">${__("На обрану дату немає вільного часу.")}</div>`;
                    }

                } else if (r.message && r.message.status === 'info') {
                    // Обробка, якщо офіс зачинено в цей день або немає слотів
                    timeGrid.innerHTML = `<div class="col-span-full text-center text-gray-500 py-4">${r.message.message || __("На обрану дату немає вільного часу.")}</div>`;
                }
                else {
                    // Обробка помилки API
                    const errorMsg = r.message?.message || __("Помилка завантаження доступного часу.");
                    timeGrid.innerHTML = `<div class="error-message col-span-full">${errorMsg}</div>`;
                }
            },
            error: function (err) {
                console.error("API call failed (get_available_appointment_slots):", err);
                timeGrid.innerHTML = `<div class="error-message col-span-full">${__("Помилка зв'язку при завантаженні часу.")}</div>`;
            }
        });
    } // Оновлена функція вибору часу - тепер вона додає/прибирає клас 'selected'
    function selectTime(element, time, datetime) {
        if (!element || element.classList.contains('disabled')) return; // Перевірка наявності елемента

        // Знаходимо та скидаємо стиль попереднього обраного слоту
        const previouslySelected = timeGrid.querySelector('.time-slot.selected');
        if (previouslySelected) {
            previouslySelected.classList.remove('selected', 'bg-blue-600', 'text-white', 'border-blue-700');
            previouslySelected.classList.add('bg-white'); // Повертаємо білий фон
        }

        // Застосовуємо стиль до поточного обраного слоту
        element.classList.add('selected', 'bg-blue-600', 'text-white', 'border-blue-700');
        element.classList.remove('bg-white'); // Прибираємо білий фон

        selectedTime = time;
        selectedAppointmentDateTime = datetime;
        console.log("Time selected:", selectedTime, "DateTime for API:", selectedAppointmentDateTime);
        if (btnConfirmSchedule) btnConfirmSchedule.disabled = false;
    }
    window.selectTime = selectTime; // Робимо глобальною

    // --- Функція підтвердження запису (без змін, але тепер залежить від selectTime) ---
    function confirmSchedule() {
        if (!selectedDate || !selectedTime || !selectedAppointmentDateTime) {
            // Використовуємо showError для кращого повідомлення
            showError(__("Будь ласка, оберіть дату та час."), schedulePage);
            return;
        }
        const name = nameInput ? nameInput.value.trim() : null;
        const phone = phoneInput ? phoneInput.value.trim() : null;

        showPage('page-confirmation');
        confirmationContent.innerHTML = `<div class="loading-indicator">${__("Створення запису...")}</div>`;

        // --- !!! ЗАГЛУШКА: Потрібно викликати API create_appointment_ticket ---
        console.log(`TODO: Call create_appointment_ticket with:
            Service: ${selectedServiceId}, Office: ${officeId}, DateTime: ${selectedAppointmentDateTime}, Phone: ${phone}, Name: ${name}`);
        // Замінити цей блок реальним викликом frappe.call

        // Тимчасовий код для демонстрації (замінити викликом API)
        setTimeout(() => {
            const apiResponse = { // Симуляція відповіді
                status: "success",
                message: __("Запис успішно створено на {0} о {1}.").format(selectedDate, selectedTime),
                data: {
                    ticket_name: `APPT-${Math.random().toString(36).substring(7)}`,
                    ticket_number: `A${Math.floor(Math.random() * 900) + 100}`,
                    appointment_datetime_display: `${selectedDate} ${selectedTime}`,
                    is_appointment: true
                }
            };

            if (apiResponse.status === 'success') {
                const ticketData = apiResponse.data;
                confirmationContent.innerHTML = `
                    <h1 class="text-4xl font-bold text-green-600 mb-6">${__("Запис підтверджено!")}</h1>
                    <div class="text-xl text-gray-700 space-y-2">
                        <p><strong>${__("Послуга")}:</strong> ${selectedServiceName || 'Не обрано'}</p>
                        ${name ? `<p><strong>${__("Ім'я")}:</strong> ${name}</p>` : ''}
                        ${phone ? `<p><strong>${__("Телефон")}:</strong> ${phone}</p>` : ''}
                        <p class="text-2xl font-semibold mt-4">${__("Дата та час вашого візиту")}:</p>
                        <p class="text-3xl font-bold text-blue-600 my-4">${ticketData.appointment_datetime_display || (selectedDate + ' ' + selectedTime)}</p>
                        <p>${__("Будь ласка, прибудьте вчасно.")}</p>
                        ${ticketData.ticket_number ? `<p><small>${__("Номер вашого запису (для довідки)")}: ${ticketData.ticket_number}</small></p>` : ''}
                    </div>
                `;
            } else {
                const errorMsg = apiResponse.message || __("Не вдалося створити запис.");
                confirmationContent.innerHTML = `<div class="error-message">${__("Помилка запису")}: ${errorMsg}</div>`;
            }
        }, 1000); // Симуляція затримки API

    }
    window.confirmSchedule = confirmSchedule;

    // --- Printing Logic ---
    function triggerPrint(ticketName) {
        // ... (Код без змін з попередньої відповіді) ...
        if (!ticketName) {
            console.error("Cannot print: Ticket name is missing.");
            return;
        }
        const printFormat = "QMS Ticket Thermal"; // Назва формату друку
        const printUrl = `/printview?doctype=QMS%20Ticket&name=${encodeURIComponent(ticketName)}&format=${encodeURIComponent(printFormat)}&no_letterhead=1`;

        console.log("Attempting to print:", printUrl);

        setTimeout(() => {
            const printFrame = document.createElement('iframe');
            printFrame.style.position = 'absolute';
            printFrame.style.width = '0';
            printFrame.style.height = '0';
            printFrame.style.border = '0';
            printFrame.src = printUrl;

            printFrame.onload = function () {
                try {
                    console.log("Print iframe loaded.");
                    printFrame.contentWindow.focus();
                    printFrame.contentWindow.print();
                    console.log("Print command issued.");
                    setTimeout(() => {
                        if (document.body.contains(printFrame)) {
                            document.body.removeChild(printFrame);
                            console.log("Print iframe removed.");
                        }
                        if (printingMessage) printingMessage.classList.remove('active');
                    }, PRINT_CLEANUP_MS);
                } catch (e) {
                    console.error("Print call failed:", e);
                    showError(__("Не вдалося автоматично викликати друк. Перевірте налаштування принтера та блокування спливаючих вікон."), confirmationPage);
                    if (printingMessage) printingMessage.classList.remove('active');
                    if (document.body.contains(printFrame)) document.body.removeChild(printFrame);
                }
            };

            printFrame.onerror = function () {
                console.error("Error loading iframe for printing URL:", printUrl);
                showError(__("Помилка завантаження сторінки для друку."), confirmationPage);
                if (printingMessage) printingMessage.classList.remove('active');
                if (document.body.contains(printFrame)) document.body.removeChild(printFrame);
            };

            document.body.appendChild(printFrame);
        }, PRINT_DELAY_MS);
    }

    // --- Ticket Page Timeout ---
    function startTicketTimeout() {
        // ... (Код без змін з попередньої відповіді) ...
        clearTimeout(ticketTimeoutId);
        let counter = TICKET_TIMEOUT_SECONDS;
        if (timeoutCounterDisplay) timeoutCounterDisplay.textContent = counter;

        ticketTimeoutId = setInterval(() => {
            counter--;
            if (counter >= 0 && timeoutCounterDisplay) {
                timeoutCounterDisplay.textContent = counter;
            }
            if (counter < 0) {
                finish();
            }
        }, 1000);
    }

    // --- Finish / Go Home ---
    function finish() {
        // ... (Код без змін з попередньої відповіді) ...
        clearTimeout(ticketTimeoutId);
        ticketTimeoutId = null;
        selectedServiceId = null;
        selectedServiceName = null;
        selectedDate = null;
        selectedTime = null;
        selectedAppointmentDateTime = null;
        if (nameInput) nameInput.value = '';
        if (phoneInput) phoneInput.value = '';
        hideKeyboard();
        showPage('page-welcome');
    }
    window.finish = finish;

    // --- Error Handling ---
    function showError(message, contextPage = null) {
        // ... (Код без змін з попередньої відповіді) ...
        console.error("Kiosk Error:", message);
        const errorHtml = `<div class="error-message">${message}</div>`;
        if (contextPage) {
            if (contextPage.id === 'page-confirmation' && confirmationContent) {
                confirmationContent.innerHTML = errorHtml;
            } else if (contextPage.id === 'page-schedule' && (dateGrid || timeGrid)) {
                if (dateGrid) dateGrid.innerHTML = `<div class="col-span-full">${errorHtml}</div>`;
                if (timeGrid) timeGrid.innerHTML = '';
                if (timeSelectionSection) hideElement(timeSelectionSection);
            } else if (contextPage.id === 'page-service' && serviceContainer) {
                serviceContainer.innerHTML = errorHtml;
            }
            else if (contextPage.id === 'page-info') {
                alert(message); // Простий alert для сторінки вводу
            } else if (contextPage.id === 'page-welcome') {
                hideElement(kioskLoadingIndicator);
                hideElement(startButtonContainer);
                if (kioskErrorMessage) {
                    kioskErrorMessage.innerHTML = message; // Використовуємо innerHTML для можливих тегів <br>
                    showElement(kioskErrorMessage);
                }
            }
            else {
                // Fallback на головну сторінку
                showError(message, welcomePage);
            }
        } else {
            // Якщо контекст не вказано, показуємо на головній
            showError(message, welcomePage);
        }
    }

    // --- Initial Data Loading ---
    function loadOfficeInfo() {
        // ... (Код без змін з попередньої відповіді) ...
        console.log("Loading office info for:", officeId);
        hideElement(startButtonContainer);
        showElement(kioskLoadingIndicator);
        hideElement(kioskErrorMessage);

        if (typeof frappe !== 'undefined' && frappe.call) {
            frappe.call({
                method: "qms_cherga.api.get_office_info",
                args: { office: officeId },
                callback: function (r) {
                    hideElement(kioskLoadingIndicator);
                    if (r.message && r.message.status === 'success') {
                        officeInfo = r.message.data;
                        console.log("Office info loaded:", officeInfo);
                        if (officeNameDisplay && officeInfo.office_name) {
                            officeNameDisplay.textContent = officeInfo.office_name;
                        }
                        showElement(startButtonContainer);
                        loadKioskServices(); // Завантажуємо послуги після інфо про офіс
                    } else {
                        const errorMsg = r.message?.message || __("Не вдалося завантажити інформацію про офіс.");
                        showError(errorMsg, welcomePage);
                    }
                },
                error: function (err) {
                    console.error("API call failed (get_office_info):", err);
                    hideElement(kioskLoadingIndicator);
                    showError(__("Помилка зв'язку при завантаженні інформації про офіс."), welcomePage);
                }
            });
        } else {
            hideElement(kioskLoadingIndicator);
            showError(__("Системна помилка: Frappe недоступний."), welcomePage);
        }
    }

    function loadKioskServices() {
        // ... (Код без змін з попередньої відповіді) ...
        serviceContainer.innerHTML = `<div class="loading-indicator">${__("Завантаження послуг...")}</div>`;

        if (typeof frappe !== 'undefined' && frappe.call) {
            frappe.call({
                method: "qms_cherga.api.get_kiosk_services",
                args: { office: officeId },
                callback: function (r) {
                    if (r.message && r.message.status === 'success') {
                        kioskServicesData = r.message.data || {};
                        renderServicePageContent(kioskServicesData);
                    } else {
                        const errorMsg = r.message?.message || __("Не вдалося завантажити список послуг.");
                        if (r.message?.status === 'info') { // Офіс зачинено або інша інфо
                            showError(errorMsg, welcomePage);
                            hideElement(startButtonContainer);
                        } else { // Реальна помилка
                            serviceContainer.innerHTML = `<div class="error-message">${errorMsg}</div>`;
                        }
                    }
                },
                error: function (err) {
                    console.error("API call failed (get_kiosk_services):", err);
                    serviceContainer.innerHTML = `<div class="error-message">${__("Помилка зв'язку при завантаженні послуг.")}</div>`;
                }
            });
        } else {
            serviceContainer.innerHTML = `<div class="error-message">${__("Системна помилка: Frappe недоступний.")}</div>`;
        }
    }

    // --- Rendering Service Page ---
    function renderServicePageContent(data) {
        // ... (Код без змін з попередньої відповіді) ...
        serviceContainer.innerHTML = '';

        if (!data || (!data.categories?.length && !data.services_no_category?.length)) {
            serviceContainer.innerHTML = `<div class="error-message">${__("Для цього кіоску не знайдено доступних послуг.")}</div>`;
            return;
        }

        const createServiceButton = (service) => {
            const button = document.createElement('button');
            button.classList.add('kiosk-button', 'kiosk-button-secondary');
            button.dataset.serviceId = service.id;

            if (service.icon) {
                const iconEl = document.createElement('i');
                service.icon.split(' ').forEach(cls => { if (cls) iconEl.classList.add(cls); });
                button.appendChild(iconEl);
            } else {
                const placeholder = document.createElement('span');
                placeholder.style.display = 'inline-block';
                placeholder.style.width = '1.5em';
                button.appendChild(placeholder);
            }

            const labelSpan = document.createElement('span');
            labelSpan.classList.add('service-label');
            labelSpan.textContent = service.label;
            button.appendChild(labelSpan);

            button.addEventListener('click', () => selectService(service.id, service.label));
            return button;
        };

        if (data.services_no_category && data.services_no_category.length > 0) {
            const noCategoryGroup = document.createElement('div');
            noCategoryGroup.classList.add('category-group');
            const grid = document.createElement('div');
            grid.classList.add('grid-container');
            data.services_no_category.forEach(service => grid.appendChild(createServiceButton(service)));
            noCategoryGroup.appendChild(grid);
            serviceContainer.appendChild(noCategoryGroup);
        }

        if (data.categories && data.categories.length > 0) {
            data.categories.forEach(category => {
                if (category.services && category.services.length > 0) {
                    const categoryGroup = document.createElement('div');
                    categoryGroup.classList.add('category-group');
                    const header = document.createElement('h2');
                    header.textContent = category.label;
                    categoryGroup.appendChild(header);
                    const grid = document.createElement('div');
                    grid.classList.add('grid-container');
                    category.services.forEach(service => grid.appendChild(createServiceButton(service)));
                    categoryGroup.appendChild(grid);
                    serviceContainer.appendChild(categoryGroup);
                }
            });
        }
    }

    // --- Initialization ---
    function initializeKiosk() {
        // ... (Код без змін з попередньої відповіді) ...
        officeId = getUrlParameter('office');
        if (!officeId) {
            showError(__("Помилка: Параметр 'office' не вказано в URL кіоску.<br>Приклад: /qms_kiosk_tailwind.html?office=YOUR_OFFICE_ID"), welcomePage);
            hideElement(kioskLoadingIndicator);
            hideElement(startButtonContainer);
            return;
        }
        console.log(`Kiosk initialized for Office ID: ${officeId}`);
        loadOfficeInfo();
        showPage('page-welcome');
    }

    initializeKiosk();
});