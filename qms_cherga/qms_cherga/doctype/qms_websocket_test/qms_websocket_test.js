// Copyright (c) 2025, Maxym Sysoiev and contributors
// For license information, please see license.txt

frappe.ui.form.on('WebSocket Test', {
    refresh: function (frm) {
        // Підписуємося на подію, коли форма завантажується або оновлюється
        console.log("Підписка на подію websocket_test_updated для документа:", frm.doc.name);

        // Перевірка, чи підписка вже існує (щоб уникнути дублювання при refresh)
        // Простий варіант - просто підписуватись завжди при refresh,
        // Frappe може обробляти це коректно, але для складних випадків потрібен кращий контроль стану.

        frappe.realtime.on('websocket_test_updated', function (data) {
            console.log("Отримано подію websocket_test_updated:", data);
            // Перевіряємо, чи повідомлення стосується саме цього відкритого документа
            if (data.docname && data.docname === frm.doc.name) {
                // Оновлюємо поле 'status_message'
                frm.set_value('status_message', data.message);
                // Показуємо сповіщення для наочності
                frappe.show_alert({
                    message: __('Отримано оновлення через WebSocket: {0}', [data.message]),
                    indicator: 'green'
                }, 5); // Показати на 5 секунд
            }
        });

        // Можна додати слухач для події видалення, якщо реалізовано в Python
        // frappe.realtime.on('websocket_test_deleted', function(data) {
        //     if (data.docname && data.docname === frm.doc.name) {
        //         frappe.show_alert({
        //             message: __('Документ видалено (отримано через WebSocket)'),
        //             indicator: 'red'
        //         }, 7);
        //         // Можливо, закрити форму або перенаправити користувача
        //     }
        // });
    },

    // Необов'язково, але гарна практика - відписуватися від подій, коли форма закривається
    // on_unload: function(frm) {
    //     console.log("Відписка від події websocket_test_updated при закритті форми:", frm.doc.name);
    //     // Важливо: frappe.realtime.off може потребувати точного посилання на функцію,
    //     // яку було передано в .on(), або специфічного ідентифікатора, якщо API це підтримує.
    //     // У простих випадках цей крок можна пропустити, але у складних додатках він важливий.
    //     // frappe.realtime.off('websocket_test_updated'); // Може не спрацювати як очікується без деталей
    // }
});