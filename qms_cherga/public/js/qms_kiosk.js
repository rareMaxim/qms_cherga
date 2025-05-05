// qms_cherga/public/js/qms_kiosk.js

document.addEventListener('DOMContentLoaded', () => {

    // --- КОНФІГУРАЦІЯ ---
    const TICKET_TIMEOUT_SECONDS = 5; // Таймаут для квитка (в секундах)
    // ---------------------

    let officeId = null;

    // DOM elements
    const screens = document.querySelectorAll('.screen');
    const mainServiceContainer = document.getElementById('service-container');
    const serviceListContainer = document.getElementById('service-list');
    // const serviceCategoryTitle = document.getElementById('service-category-title'); // Не використовується, можна видалити?
    const backButton = document.getElementById('back-button');
    const ticketNumberDisplay = document.getElementById('ticket-number');
    const ticketServiceNameDisplay = document.getElementById('ticket-service-name');
    const timeoutCounterDisplay = document.getElementById('timeout-counter');
    const searchInput = document.getElementById('service-search-input');

    let ticketTimeoutId = null;
    let allServicesData = {};

    // --- Функція для отримання параметра з URL ---
    function getUrlParameter(name) {
        // ... (код без змін) ...
        name = name.replace(/[\[]/, '\\[').replace(/[\]]/, '\\]');
        const regex = new RegExp('[\\?&]' + name + '=([^&#]*)');
        const results = regex.exec(location.search);
        return results === null ? '' : decodeURIComponent(results[1].replace(/\+/g, ' '));
    }

    // --- Ініціалізація та отримання ID офісу ---
    function initializeKiosk() {
        officeId = getUrlParameter('office');
        if (!officeId) {
            // Додано __() для перекладу
            mainServiceContainer.innerHTML = `<div class="error-message">${__('Error: Parameter "office" not specified in the kiosk URL address.')}<br>${__('Example:')} /qms_kiosk.html?office=YOUR_OFFICE_ID</div>`;
            screens.forEach(screen => screen.classList.remove('active'));
            const mainScreen = document.getElementById('main-screen');
            if (mainScreen) mainScreen.classList.add('active');
            console.error("Office ID not found in URL parameters.");
            return;
        }
        console.log(`Kiosk initialized for Office ID: ${officeId}`);
        loadKioskServices();
        showScreen('main-screen');
    }

    // --- Відображення екранів та таймаут (без змін) ---
    function showScreen(screenId) {
        // ... (код без змін) ...
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
    function startTicketTimeout() {
        // ... (код без змін) ...
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

    // --- Обробка кліку на послугу (ОНОВЛЕНО) ---
    function handleServiceClick(serviceId, serviceName) {
        console.log(`Service selected: ID=${serviceId}, Name=${serviceName}`);
        if (!officeId) {
            // Використовуємо alert або кращий механізм сповіщень
            alert(__("Error: Could not determine Office ID. Check the URL.")); // Вже було
            return;
        }
        // Можна показати індикатор завантаження
        // showLoadingIndicator(); // Потрібно реалізувати

        if (typeof frappe !== 'undefined' && frappe.call) {
            frappe.call({
                method: "qms_cherga.api.create_live_queue_ticket",
                args: {
                    service: serviceId,
                    office: officeId
                    // Тут можна додати visitor_phone, якщо збираєте
                },
                callback: function (r) { // 'r' - це повна відповідь Frappe
                    // hideLoadingIndicator(); // Сховати індикатор

                    // Перевіряємо новий стандартизований формат відповіді
                    if (r.message && r.message.status === "success") {
                        const ticketData = r.message.data; // Дані тепер у r.message.data
                        if (ticketData && ticketData.ticket_number && ticketData.ticket_name) {
                            ticketNumberDisplay.textContent = ticketData.ticket_number; // Номер для показу
                            ticketServiceNameDisplay.textContent = serviceName;
                            showScreen('ticket-screen');
                            startTicketTimeout();

                            // --- Логіка друку (залишається без змін, але залежить від ticketData.ticket_name) ---
                            const ticketName = ticketData.ticket_name;
                            const printFormat = "QMS Ticket Thermal";
                            const printUrl = `/printview?doctype=QMS%20Ticket&name=${encodeURIComponent(ticketName)}&format=${encodeURIComponent(printFormat)}&no_letterhead=1`;
                            // ... (решта логіки iframe для друку без змін) ...
                            const printFrame = document.createElement('iframe');
                            // ... (налаштування стилів iframe) ...
                            printFrame.style.position = 'absolute';
                            printFrame.style.width = '0';
                            printFrame.style.height = '0';
                            printFrame.style.border = '0';
                            printFrame.src = printUrl;

                            printFrame.onload = function () {
                                try {
                                    printFrame.contentWindow.focus();
                                    printFrame.contentWindow.print();
                                    setTimeout(() => { if (document.body.contains(printFrame)) document.body.removeChild(printFrame); }, 3000);
                                } catch (e) {
                                    console.error(__("Print call failed:"), e); // Технічне повідомлення
                                    alert(__("Could not initiate automatic printing. Please check printer settings and browser pop-up blockers.")); // Вже було
                                    // window.open(printUrl, '_blank'); // Fallback
                                }
                            };
                            printFrame.onerror = function () {
                                console.error(__("Error loading iframe for printing URL: ") + printUrl); // Технічне повідомлення
                                alert(__("Error loading page for printing.")); // Вже було
                                if (document.body.contains(printFrame)) document.body.removeChild(printFrame);
                            }
                            document.body.appendChild(printFrame);
                            // --- Кінець логіки друку ---
                        } else {
                            console.error("Ticket number or name missing in success response data:", ticketData); // Технічне повідомлення
                            alert(__("Ticket created, but failed to get ticket details for display/printing.")); // Вже було
                            showScreen('main-screen');
                        }
                    } else if (r.message && r.message.status === "info") {
                        // Обробка інформаційних повідомлень (наприклад, "Офіс зачинено")
                        console.info("Info from create_live_queue_ticket:", r.message.message); // Технічне повідомлення
                        alert(r.message.message); // Показати повідомлення користувачу (воно приходить з бекенду, вже перекладене)
                        showScreen('main-screen'); // Повернути на головний екран
                    }
                    else {
                        // Обробка помилок з бекенду (status === 'error' або інша структура)
                        const errorMessage = r.message?.message || __("Unknown error creating ticket."); // Вже було
                        console.error("Error creating ticket:", errorMessage, r.message?.details); // Технічне повідомлення
                        alert(__("Error creating ticket: ") + errorMessage); // Вже було
                        showScreen('main-screen');
                    }
                },
                error: function (err) { // Помилка зв'язку або системна помилка Frappe
                    // hideLoadingIndicator();
                    console.error("API call failed (create_live_queue_ticket):", err); // Технічне повідомлення
                    alert(__("Error communicating with the server when creating the ticket.")); // Вже було
                    showScreen('main-screen');
                }
            });
        } else {
            console.error("frappe.call is not available."); // Технічне повідомлення
            alert(__("System error: cannot connect to server.")); // Вже було
            // hideLoadingIndicator();
        }
    }

    // --- Функції для відображення послуг (без змін) ---
    function renderServices(container, services) {
        // Ця функція залишається без змін
        container.innerHTML = '';
        if (!services || services.length === 0) {
            container.innerHTML = `<p class="text-muted">${__("No available services in this category.")}</p>`;
            return;
        }
        services.forEach(service => {
            const serviceButton = document.createElement('button');
            serviceButton.classList.add('service-button');
            serviceButton.dataset.serviceId = service.id;

            const buttonContent = document.createElement('span');
            buttonContent.classList.add('service-button-content');

            // ... (решта коду створення іконки та тексту кнопки без змін) ...
            if (service.icon) {
                const iconSpan = document.createElement('span');
                const iconText = service.icon.trim();
                if (iconText.startsWith('fa ') || iconText.startsWith('fa-')) {
                    iconSpan.classList.add('service-icon');
                    const iTag = document.createElement('i');
                    iconText.split(' ').forEach(cls => { if (cls) iTag.classList.add(cls); });
                    iconSpan.appendChild(iTag);
                } else {
                    iconSpan.classList.add('service-icon', 'emoji-icon');
                    iconSpan.textContent = iconText;
                }
                buttonContent.appendChild(iconSpan);
            } else {
                const placeholderSpan = document.createElement('span');
                placeholderSpan.classList.add('service-icon', 'icon-placeholder');
                buttonContent.appendChild(placeholderSpan);
            }

            const textSpan = document.createElement('span');
            textSpan.classList.add('service-label');
            textSpan.textContent = service.label; // Використовуємо label
            buttonContent.appendChild(textSpan);

            serviceButton.appendChild(buttonContent);
            serviceButton.addEventListener('click', () => handleServiceClick(service.id, service.label));
            container.appendChild(serviceButton); // Додаємо кнопку до переданого контейнера
        });
    }

    function renderMainScreen(data) {
        mainServiceContainer.innerHTML = ''; // Очищаємо головний контейнер
        if (!data || (!data.categories?.length && !data.services_no_category?.length)) {
            mainServiceContainer.innerHTML = `<div class="error-message">${__("No available services found for this kiosk.")}</div>`;
            return;
        }

        // Функція для створення та заповнення групи послуг
        const createServiceGroup = (container, services, title = null) => {
            const categoryGroup = document.createElement('div');
            categoryGroup.classList.add('category-group');

            if (title) {
                const categoryHeader = document.createElement('h3');
                categoryHeader.textContent = title;
                categoryGroup.appendChild(categoryHeader);
            }

            // !!! Створюємо контейнер для сітки кнопок всередині групи !!!
            const serviceGridContainer = document.createElement('div');
            serviceGridContainer.classList.add('category-service-grid'); // Новий клас для CSS

            // Додаємо сітку до групи
            categoryGroup.appendChild(serviceGridContainer);

            // Рендеримо кнопки всередину нової сітки
            renderServices(serviceGridContainer, services); // Передаємо serviceGridContainer

            // Додаємо всю групу до головного контейнера
            container.appendChild(categoryGroup);
        };

        // Послуги без категорії
        if (data.services_no_category && data.services_no_category.length > 0) {
            // Передаємо mainServiceContainer як головний контейнер
            createServiceGroup(mainServiceContainer, data.services_no_category);
        }

        // Категорії
        if (data.categories && data.categories.length > 0) {
            data.categories.forEach(category => {
                // Передаємо mainServiceContainer як головний контейнер
                createServiceGroup(mainServiceContainer, category.services, category.label);
            });
        }
    }

    // --- Фільтрація послуг (без змін) ---
    function filterServices(searchTerm) {
        // ... (код без змін) ...
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

    // --- Завантаження Послуг (ОНОВЛЕНО) ---
    function loadKioskServices() {
        if (!officeId) {
            console.error("Cannot load services: Office ID is missing."); // Технічне
            mainServiceContainer.innerHTML = `<div class="error-message">${__("Error: Could not determine Office ID from URL.")}</div>`; // Вже було
            return;
        }
        mainServiceContainer.innerHTML = `<div class="loading-indicator">${__("Loading services...")}</div>`; // Вже було

        if (typeof frappe !== 'undefined' && frappe.call) {
            console.info("Using frappe.call to load services."); // Технічне
            frappe.call({
                method: "qms_cherga.api.get_kiosk_services",
                args: { office: officeId },
                callback: function (r) {
                    // Перевіряємо новий стандартизований формат
                    if (r.message && r.message.status === 'success') {
                        console.log("Services loaded:", r.message.data); // Технічне
                        allServicesData = r.message.data; // Дані тепер у r.message.data
                        renderMainScreen(allServicesData);
                    } else if (r.message && r.message.status === 'info') {
                        // Обробка інформаційних повідомлень (наприклад, "Офіс зачинено")
                        console.info("Info from get_kiosk_services:", r.message.message); // Технічне
                        // Відображаємо повідомлення замість списку послуг (воно з бекенду, вже перекладене)
                        mainServiceContainer.innerHTML = `<div class="info-message">${r.message.message}</div>`;
                        // Можна також сховати заголовок, якщо потрібно
                        const header = document.querySelector('#main-screen .screen-header h2');
                        if (header) header.style.display = 'none';
                    }
                    else {
                        // Обробка помилок з бекенду
                        const errorMessage = r.message?.message || __("Unknown error loading services."); // Вже було
                        console.error("Error loading services:", errorMessage, r.message?.details); // Технічне
                        mainServiceContainer.innerHTML = `<div class="error-message">${__("Error loading services:")} ${errorMessage}</div>`; // Вже було
                    }
                },
                error: function (err) { // Помилка зв'язку
                    console.error("API call failed (get_kiosk_services):", err); // Технічне
                    mainServiceContainer.innerHTML = `<div class="error-message">${__("Error communicating with the server when loading services.")}</div>`; // Вже було
                }
            });
        } else {
            console.warn("frappe.call not available. Using fetch to load services."); // Технічне
            mainServiceContainer.innerHTML = `<div class="error-message">${__("System error: cannot connect to server.")}</div>`; // Вже було
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

    // Запускаємо ініціалізацію
    initializeKiosk();

});