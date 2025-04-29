// qms_cherga/public/js/kiosk.js

document.addEventListener('DOMContentLoaded', () => {

    // --- КОНФІГУРАЦІЯ ---
    // Видаляємо жорстко закодований OFFICE_ID
    // const OFFICE_ID = "ZP-RACS-OLXNDR";
    const TICKET_TIMEOUT_SECONDS = 15; // Час показу екрану талону
    // ---------------------

    let officeId = null; // Змінна для зберігання ID офісу з URL

    // Get DOM elements
    const screens = document.querySelectorAll('.screen');
    const mainServiceContainer = document.getElementById('service-container');
    const serviceListContainer = document.getElementById('service-list');
    const serviceCategoryTitle = document.getElementById('service-category-title');
    const backButton = document.getElementById('back-button');
    const ticketNumberDisplay = document.getElementById('ticket-number');
    const ticketServiceNameDisplay = document.getElementById('ticket-service-name');
    const timeoutCounterDisplay = document.getElementById('timeout-counter');
    const searchInput = document.getElementById('service-search-input');

    let ticketTimeoutId = null;
    let allServicesData = {}; // Зберігаємо завантажені дані

    // --- Функція для отримання параметра з URL ---
    function getUrlParameter(name) {
        name = name.replace(/[\[]/, '\\[').replace(/[\]]/, '\\]');
        const regex = new RegExp('[\\?&]' + name + '=([^&#]*)');
        const results = regex.exec(location.search);
        return results === null ? '' : decodeURIComponent(results[1].replace(/\+/g, ' '));
    }

    // --- Ініціалізація та отримання ID офісу ---
    function initializeKiosk() {
        officeId = getUrlParameter('office'); // Отримуємо ID з URL

        if (!officeId) {
            // Якщо параметр 'office' відсутній в URL, показуємо помилку
            mainServiceContainer.innerHTML = '<div class="error-message">Помилка: Не вказано параметр "office" в URL адресі кіоску.<br>Приклад: /qms_kiosk.html?office=YOUR_OFFICE_ID</div>';
            // Ховаємо всі екрани або показуємо спеціальний екран помилки, якщо він є
            screens.forEach(screen => screen.classList.remove('active'));
            const mainScreen = document.getElementById('main-screen');
            if (mainScreen) mainScreen.classList.add('active'); // Показуємо головний, де буде помилка
            console.error("Office ID not found in URL parameters.");
            return; // Зупиняємо подальшу ініціалізацію
        }

        console.log(`Kiosk initialized for Office ID: ${officeId}`);
        loadKioskServices(); // Завантажуємо послуги для отриманого ID
        showScreen('main-screen'); // Показуємо головний екран
    }
    // ------------------------------------------


    // Function to show a specific screen (без змін)
    function showScreen(screenId) {
        screens.forEach(screen => screen.classList.remove('active'));
        const screenToShow = document.getElementById(screenId);
        if (screenToShow) {
            screenToShow.classList.add('active');
            if (screenId === 'main-screen' || screenId === 'service-screen') {
                const contentArea = screenToShow.querySelector('.screen-content');
                if (contentArea) contentArea.scrollTop = 0;
                if (searchInput && screenId === 'service-screen') {
                    searchInput.value = '';
                    filterServices('');
                }
            }
        } else {
            console.warn(`Screen with id "${screenId}" not found, ignoring showScreen call.`);
        }
        if (screenId !== 'ticket-screen' && ticketTimeoutId) {
            clearTimeout(ticketTimeoutId);
            ticketTimeoutId = null;
        }
    }

    // Function to start the return timer from the ticket screen (без змін)
    function startTicketTimeout() {
        clearTimeout(ticketTimeoutId);
        let counter = TICKET_TIMEOUT_SECONDS;
        if (timeoutCounterDisplay) timeoutCounterDisplay.textContent = counter;
        ticketTimeoutId = setInterval(() => {
            counter--;
            if (counter >= 0 && timeoutCounterDisplay) {
                timeoutCounterDisplay.textContent = counter;
            }
            if (counter < 0) {
                clearInterval(ticketTimeoutId);
                ticketTimeoutId = null;
                showScreen('main-screen');
            }
        }, 1000);
    }

    // Function to handle service button click (API call)
    function handleServiceClick(serviceId, serviceName) {
        console.log(`Service selected: ID=${serviceId}, Name=${serviceName}`);

        // Перевірка, чи отримали ми officeId
        if (!officeId) {
            alert("Помилка: Не вдалося визначити ID офісу. Перевірте URL.");
            return;
        }

        if (typeof frappe !== 'undefined' && frappe.call) {
            frappe.call({
                method: "qms_cherga.api.create_live_queue_ticket",
                args: {
                    service: serviceId,
                    office: officeId // Використовуємо змінну officeId
                },
                callback: function (response) {
                    if (response.message && response.message.status === "success") {
                        ticketNumberDisplay.textContent = response.message.ticket_number;
                        ticketServiceNameDisplay.textContent = serviceName;
                        showScreen('ticket-screen');
                        startTicketTimeout();
                    } else {
                        console.error("Error creating ticket:", response.message);
                        alert("Помилка створення талону: " + (response.message ? response.message.message : "Невідома помилка"));
                        showScreen('main-screen');
                    }
                },
                error: function (err) {
                    console.error("API call failed:", err);
                    alert("Помилка зв'язку з сервером при створенні талону.");
                    showScreen('main-screen');
                }
            });
        } else {
            console.warn("frappe.call not available. Using fetch.");
        }
    }

    // --- Функції для відображення послуг ---
    function renderServices(container, services) {
        container.innerHTML = ''; // Очищуємо контейнер
        if (!services || services.length === 0) {
            container.innerHTML = '<p class="text-muted">Немає доступних послуг у цій категорії.</p>';
            return;
        }
        services.forEach(service => {
            const serviceButton = document.createElement('button');
            serviceButton.classList.add('service-button');
            serviceButton.dataset.serviceId = service.id; // Зберігаємо ID

            const buttonContent = document.createElement('span');
            buttonContent.classList.add('service-button-content');

            // Додаємо іконку/emoji, якщо icon_text не порожній
            if (service.icon) {
                const iconSpan = document.createElement('span');
                const iconText = service.icon.trim();

                // Перевіряємо, чи це клас Font Awesome (починається з 'fa ' або 'fa-')
                if (iconText.startsWith('fa ') || iconText.startsWith('fa-')) {
                    iconSpan.classList.add('service-icon');
                    // Створюємо тег <i> для Font Awesome
                    const iTag = document.createElement('i');
                    // Додаємо всі класи з iconText до тегу <i>
                    iconText.split(' ').forEach(cls => {
                        if (cls) iTag.classList.add(cls);
                    });
                    // Можна додати 'fa-fw' для фіксованої ширини, якщо потрібно
                    // iTag.classList.add('fa-fw');
                    iconSpan.appendChild(iTag);
                } else {
                    // Якщо це не клас Font Awesome, вважаємо, що це Emoji або символ
                    iconSpan.classList.add('service-icon', 'emoji-icon'); // Додаємо клас для можливої стилізації Emoji
                    iconSpan.textContent = iconText; // Просто вставляємо текст (Emoji)
                }
                buttonContent.appendChild(iconSpan);
            } else {
                // Можна додати плейсхолдер, якщо іконки немає
                const placeholderSpan = document.createElement('span');
                placeholderSpan.classList.add('service-icon', 'icon-placeholder');
                // placeholderSpan.innerHTML = '&nbsp;'; // Невидимий пробіл для збереження розміру
                buttonContent.appendChild(placeholderSpan);
            }

            // Додаємо текст послуги
            const textSpan = document.createElement('span');
            textSpan.classList.add('service-label');
            textSpan.textContent = service.label;
            buttonContent.appendChild(textSpan);

            // Додаємо контент до кнопки
            serviceButton.appendChild(buttonContent);

            serviceButton.addEventListener('click', () => handleServiceClick(service.id, service.label));
            container.appendChild(serviceButton);
        });
    }

    function renderMainScreen(data) {
        mainServiceContainer.innerHTML = '';
        if (!data || (!data.categories?.length && !data.services_no_category?.length)) {
            mainServiceContainer.innerHTML = '<div class="error-message">Не знайдено доступних послуг для цього кіоску.</div>';
            return;
        }
        if (data.services_no_category && data.services_no_category.length > 0) {
            renderServices(mainServiceContainer, data.services_no_category);
        }
        if (data.categories && data.categories.length > 0) {
            data.categories.forEach(category => {
                const categoryGroup = document.createElement('div');
                categoryGroup.classList.add('category-group');
                const categoryHeader = document.createElement('h3');
                categoryHeader.textContent = category.label;
                categoryGroup.appendChild(categoryHeader);
                renderServices(categoryGroup, category.services);
                mainServiceContainer.appendChild(categoryGroup);
            });
        }
    }

    // Function to filter services on service-screen (без змін)
    function filterServices(searchTerm) {
        if (!serviceListContainer) return;
        const lowerCaseSearchTerm = searchTerm.toLowerCase().trim();
        const serviceButtons = serviceListContainer.querySelectorAll('.service-button');
        serviceButtons.forEach(button => {
            const serviceName = button.textContent.toLowerCase();
            if (serviceName.includes(lowerCaseSearchTerm)) {
                button.classList.remove('hidden');
            } else {
                button.classList.add('hidden');
            }
        });
    }


    // --- Завантаження Послуг ---
    function loadKioskServices() {
        // Перевірка, чи отримали ми officeId
        if (!officeId) {
            console.error("Cannot load services: Office ID is missing.");
            mainServiceContainer.innerHTML = '<div class="error-message">Помилка: Не вдалося визначити ID офісу з URL.</div>';
            return;
        }

        mainServiceContainer.innerHTML = '<div class="loading-indicator">Завантаження послуг...</div>';

        if (typeof frappe !== 'undefined' && frappe.call) {
            console.info("Using frappe.call to load services.");
            frappe.call({
                method: "qms_cherga.api.get_kiosk_services",
                args: { office: officeId }, // Використовуємо змінну officeId
                callback: function (r) {
                    if (r.message && !r.message.error) {
                        console.log("Services loaded:", r.message);
                        allServicesData = r.message;
                        renderMainScreen(allServicesData);
                    } else {
                        console.error("Error loading services:", r.message);
                        mainServiceContainer.innerHTML = `<div class="error-message">Помилка завантаження послуг: ${r.message ? r.message.error : 'Невідома помилка'}</div>`;
                    }
                },
                error: function (err) {
                    console.error("API call failed to load services:", err);
                    mainServiceContainer.innerHTML = `<div class="error-message">Помилка зв'язку з сервером при завантаженні послуг.</div>`;
                }
            });
        } else {
            console.warn("frappe.call not available. Using fetch to load services.");
        }
    }

    // Event handler for the "Back" button (без змін)
    if (backButton) {
        backButton.addEventListener('click', () => {
            showScreen('main-screen');
        });
    }
    // Event listener for the search input field (без змін)
    if (searchInput) {
        searchInput.addEventListener('input', (event) => {
            filterServices(event.target.value);
        });
    }


    // Запускаємо ініціалізацію при завантаженні сторінки
    initializeKiosk();

});