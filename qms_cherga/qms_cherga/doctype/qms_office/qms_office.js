// Copyright (c) 2025, Maxym Sysoiev and contributors
// For license information, please see license.txt

frappe.ui.form.on("QMS Office", {
    refresh(frm) {
        // --- Додавання пунктів у спадне Меню форми ("Menu") ---

        // Перевіряємо, чи документ вже збережений (має ім'я/абревіатуру)
        if (frm.doc.name && !frm.is_new()) {
            const office_abbr = frm.doc.name; // 'name' містить абревіатуру
            const base_url = window.location.origin;
            // Додаємо пункт меню для Кіоску
            frm.page.add_action_item(__("Кіоск"), function () {
                // Формуємо URL для Кіоску
                const kiosk_url = `${base_url}/qms_kiosk.html?office=${encodeURIComponent(office_abbr)}`;
                // Дія при натисканні: відкрити URL у новій вкладці
                window.open(kiosk_url, '_blank');
            }, "Посилання"); // Додаємо до підгрупи "Посилання"

            // Додаємо пункт меню для Табло
            frm.page.add_action_item(__("Табло"), function () {
                // Формуємо URL для Табло
                const display_url = `${base_url}/qms_display_board.html?office=${encodeURIComponent(office_abbr)}`;
                // Дія при натисканні: відкрити URL у новій вкладці
                window.open(display_url, '_blank');
            }, "Посилання"); // Додаємо до підгрупи "Посилання"
            // Додаємо пункт меню для Панелі адміністратора
            frm.page.add_action_item(__("Панель оператора"), function () {
                // Формуємо URL для Панелі адміністратора
                const admin_url = `${base_url}/qms_operator_dashboard`;
                // Дія при натисканні: відкрити URL у новій вкладці
                window.open(admin_url, '_blank');
            }, "Посилання"); // Додаємо до підгрупи "Посилання"

            // Примітка: Додавання однакових пунктів меню в 'refresh' зазвичай
            // не призводить до дублювання, Frappe оновлює існуючі або замінює їх.
            // Третій аргумент (в даному випадку "Посилання") створює підгрупу в меню.
        }
        // Якщо документ новий, пункти меню просто не будуть додані в цьому циклі refresh.
        // --- Кінець додавання пунктів у спадне Меню форми ("Menu") ---
    },
});
