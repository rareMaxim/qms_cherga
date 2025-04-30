// Copyright (c) 2025, Maxym Sysoiev and contributors
// For license information, please see license.txt

frappe.ui.form.on("QMS Operator", {
    refresh(frm) {

    },
    // Обробник для нової кнопки
    add_office_skills_button(frm) {
        // Перевіряємо, чи обрано офіс
        if (!frm.doc.default_office) {
            frappe.msgprint({
                title: __("Помилка"),
                indicator: "red",
                message: __("Будь ласка, спочатку оберіть 'Default Office'.")
            });
            return;
        }

        // Викликаємо серверний метод для отримання послуг
        frappe.call({
            // Якщо метод всередині класу QMSOperator:
            doc: frm.doc, // Передаємо поточний документ для виклику його методу
            method: 'get_services_for_office',
            // Якщо метод поза класом:
            // method: 'qms_cherga.qms_cherga.doctype.qms_operator.qms_operator.get_services_for_office',
            args: {
                office_id: frm.doc.default_office
            },
            callback: function (r) {
                if (r.message && r.message.length > 0) {
                    let existing_services = (frm.doc.operator_skills || []).map(skill => skill.service);
                    let added_count = 0;

                    r.message.forEach(service_id => {
                        // Додаємо послугу тільки якщо її ще немає у списку
                        if (!existing_services.includes(service_id)) {
                            let new_skill = frm.add_child('operator_skills', {
                                service: service_id,
                                skill_level: 'Proficient' // Встановлюємо рівень за замовчуванням
                                // Можна додати інші поля за замовчуванням, якщо потрібно
                            });
                            added_count++;
                        }
                    });

                    if (added_count > 0) {
                        frm.refresh_field('operator_skills'); // Оновлюємо відображення таблиці
                        frappe.show_alert({
                            message: __("Додано {0} нових навичок з офісу.", [added_count]),
                            indicator: 'green'
                        }, 5);
                    } else {
                        frappe.show_alert({
                            message: __("Всі послуги з обраного офісу вже додані до навичок оператора."),
                            indicator: 'info'
                        }, 5);
                    }

                } else if (r.message && r.message.length === 0) {
                    frappe.show_alert({
                        message: __("В обраному офісі не знайдено активних послуг."),
                        indicator: 'orange'
                    }, 5);
                } else {
                    // Обробка можливих помилок з бекенду
                    frappe.msgprint({
                        title: __("Помилка"),
                        indicator: "red",
                        message: __("Не вдалося отримати список послуг з офісу.")
                    });
                }
            },
            error: function (r) {
                frappe.msgprint({
                    title: __("Помилка Зв'язку"),
                    indicator: "red",
                    message: __("Не вдалося виконати запит до сервера.")
                });
            }
        });
    }
});
