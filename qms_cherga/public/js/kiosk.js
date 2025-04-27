// qms_cherga/public/js/kiosk.js

frappe.ready(function () {
    console.log("Kiosk JS loaded");

    // Отримуємо назву офісу з контексту, переданого з kiosk.py
    // Зверніть увагу: frappe.boot.office_name - це лише приклад,
    // вам потрібно переконатись, що context.office_name з kiosk.py
    // доступний тут (можливо, через frappe.provide і передачу в get_context).
    // Простіший варіант для тесту: const officeName = "Назва-Вашого-Офісу";
    // Або отримувати з URL: const officeName = frappe.utils.get_url_arg("office");

    const officeName = frappe.boot.office_name || frappe.utils.get_url_arg("office"); // Потрібно налаштувати передачу office_name!
    const serviceSelectionDiv = document.getElementById('service-selection');
    const resultAreaDiv = document.getElementById('result-area');
    const spinner = serviceSelectionDiv.querySelector('.spinner-container');

    if (!officeName) {
        serviceSelectionDiv.innerHTML = `<div class="alert alert-warning">Не вдалося визначити офіс для цього кіоску.</div>`;
        return;
    }

    if (!serviceSelectionDiv || !resultAreaDiv) {
        console.error("Required HTML elements not found!");
        return;
    }

    // Функція для відображення кнопок
    function renderButtons(data) {
        let html = '';

        // Спочатку послуги без категорій
        if (data.services_no_category && data.services_no_category.length > 0) {
            data.services_no_category.forEach(service => {
                html += `<button class="btn btn-primary service-button" data-service-name="${service.name}">${service.label}</button>`;
            });
        }

        // Потім категорії
        if (data.categories && data.categories.length > 0) {
            data.categories.forEach(category => {
                // Показуємо кнопку категорії
                html += `<h2>${category.label}</h2>`; // Показати назву категорії
                category.services.forEach(service => {
                    html += `<button class="btn btn-secondary service-button" data-service-name="${service.name}">${service.label}</button>`;
                });
            });
        }
        serviceSelectionDiv.innerHTML = html;
        addEventListeners(); // Додаємо обробники подій до нових кнопок
    }

    // Функція для виклику API створення талону
    function createTicket(serviceName) {
        resultAreaDiv.innerHTML = `<div class="alert alert-info">Створюємо ваш талон...</div>`; // Повідомлення про завантаження

        frappe.call({
            method: "qms_cherga.api.create_live_queue_ticket",
            args: {
                service: serviceName,
                office: officeName
                // visitor_phone: Тут можна додати логіку запиту телефону
            },
            callback: function (response) {
                if (response.message && response.message.status === "success") {
                    console.log("Ticket created:", response.message.ticket_number);
                    // Показуємо номер талону відвідувачу
                    resultAreaDiv.innerHTML = `
                        <div class="alert alert-success">
                            <p>Ваш номер у черзі:</p>
                            <p style="font-size: 2.5em; font-weight: bold;">${response.message.ticket_number}</p>
                            <p>Будь ласка, очікуйте на виклик.</p>
                        </div>`;
                    // TODO: Додати логіку друку талону (потрібна інтеграція)

                    // Можливо, через 10-15 секунд повернути на головний екран
                    setTimeout(() => { loadServices(); }, 15000);

                } else {
                    console.error("Error creating ticket:", response.message);
                    // Показуємо повідомлення про помилку відвідувачу
                    resultAreaDiv.innerHTML = `<div class="alert alert-danger">Помилка: ${response.message ? response.message.message : 'Невідома помилка'}</div>`;
                    // Можливо, кнопка "Спробувати ще" або повернути на головний екран
                    setTimeout(() => { loadServices(); }, 10000);
                }
            },
            error: function (err) {
                console.error("API call failed:", err);
                resultAreaDiv.innerHTML = `<div class="alert alert-danger">Помилка зв'язку з сервером.</div>`;
                setTimeout(() => { loadServices(); }, 10000);
            }
        });
    }

    // Функція для додавання обробників подій
    function addEventListeners() {
        const buttons = serviceSelectionDiv.querySelectorAll('.service-button');
        buttons.forEach(button => {
            button.addEventListener('click', function () {
                const serviceName = this.getAttribute('data-service-name');
                console.log("Service selected:", serviceName);
                serviceSelectionDiv.innerHTML = ''; // Очищуємо кнопки
                createTicket(serviceName); // Викликаємо API
            });
        });
        // Тут можна додати обробники для кнопок категорій, якщо потрібна дворівнева навігація
    }


    // Функція завантаження послуг
    function loadServices() {
        resultAreaDiv.innerHTML = ''; // Очищуємо результат
        spinner.style.display = 'block'; // Показуємо спіннер
        serviceSelectionDiv.innerHTML = ''; // Очищаємо старі кнопки (якщо є)
        serviceSelectionDiv.appendChild(spinner);


        frappe.call({
            method: "qms_cherga.www.kiosk.get_available_services",
            args: { office: officeName },
            callback: function (r) {
                spinner.style.display = 'none'; // Ховаємо спіннер
                if (r.message && !r.message.error) {
                    console.log("Services loaded:", r.message);
                    renderButtons(r.message);
                } else {
                    serviceSelectionDiv.innerHTML = `<div class="alert alert-danger">Помилка завантаження послуг: ${r.message ? r.message.error : 'Невідома помилка'}</div>`;
                }
            },
            error: function (err) {
                spinner.style.display = 'none';
                console.error("Failed to load services:", err);
                serviceSelectionDiv.innerHTML = `<div class="alert alert-danger">Помилка зв'язку з сервером при завантаженні послуг.</div>`;
            }
        });
    }

    // Завантажуємо послуги при завантаженні сторінки
    loadServices();

});