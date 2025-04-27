// qms_cherga/qms_cherga/page/operator_dashboard/operator_dashboard.js

frappe.provide("qms_cherga");
// Допоміжна функція для динамічного завантаження CSS
function load_css(path) {
	// Перевіряємо, чи стиль вже не додано
	if (!$(`link[href^="${path}"]`).length) { // Використовуємо href^= для перевірки початку шляху (без ?v=...)
		let link = document.createElement('link');
		link.rel = 'stylesheet';
		link.type = 'text/css';
		// Додаємо версію файлу для локальних ресурсів, якщо це не CDN
		if (path.startsWith('/assets/')) {
			link.href = path + '?v=' + frappe.boot.build_version;
		} else {
			link.href = path; // Для CDN версію не додаємо
		}
		document.head.appendChild(link);
		console.log(`CSS dynamically linked: ${path}`);
	}
}

// Допоміжна функція для скорочення номера талону
function get_short_ticket_number(fullTicketNumber) {
	if (!fullTicketNumber) return 'N/A';
	let shortNumber = fullTicketNumber.substring(fullTicketNumber.lastIndexOf('-') + 1);
	return (shortNumber && fullTicketNumber.lastIndexOf('-') !== -1) ? shortNumber : fullTicketNumber;
}

frappe.pages['operator-dashboard'].on_page_load = function (wrapper) {

	let page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Дашбоард Оператора',
		single_column: false
	});

	wrapper.dashboard = new qms_cherga.OperatorDashboard(page, wrapper);
	$(wrapper).data("dashboard_obj", wrapper.dashboard);
};

qms_cherga.OperatorDashboard = class {
	constructor(page, wrapper) {
		this.page = page;
		this.wrapper = wrapper;
		this.operator_info = null;
		this.office_id = null;
		this.office_name = null;
		this.service_point_id = null;
		this.service_point_name = null;
		this.current_ticket = null;
		this.held_tickets = []; // Масив для зберігання списку відкладених
		this.stats = { waiting: '?', served_today: '?' };

		this.make_ui();
		this.bind_events();
		this.load_initial_data();
	}

	make_ui() {
		const dashboard_css_path = "/assets/qms_cherga/css/operator_dashboard.css";
		load_css(dashboard_css_path);
		const fontawesome_cdn_path = "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.15.4/css/all.min.css"; // Приклад! Перевірте актуальність.
		load_css(fontawesome_cdn_path);
		$(frappe.render_template("operator_dashboard_help", {})).appendTo(this.page.main);

		this.elements = {
			operatorName: $(this.wrapper).find('#operator-name'),
			operatorStatus: $(this.wrapper).find('#operator-status'),
			servicePointNameDisplay: $(this.wrapper).find('#service-point-display-name'), // Для відображення назви точки
			servicePointSelector: $(this.wrapper).find('#service-point-selector'), // Сам селектор
			officeNameDisplay: $(this.wrapper).find('#office-display-name'), // Для відображення назви офісу
			servicePointSelector: $(this.wrapper).find('#service-point-selector'),
			officeName: $(this.wrapper).find('#office-name'),
			waitingCount: $(this.wrapper).find('#waiting-count'),
			servedToday: $(this.wrapper).find('#served-today'),
			currentTicketInfo: $(this.wrapper).find('#current-ticket-info'),
			heldTicketsList: $(this.wrapper).find('#held-tickets-list'), // <--- Новий елемент
			callNextButton: $(this.wrapper).find('#btn-call-next'),
			startServingButton: $(this.wrapper).find('#btn-start-serving'),
			finishServiceButton: $(this.wrapper).find('#btn-finish-service'),
			noShowButton: $(this.wrapper).find('#btn-no-show'),
			holdTicketButton: $(this.wrapper).find('#btn-hold-ticket'),
			transferTicketButton: $(this.wrapper).find('#btn-transfer-ticket'),
			refreshStatsButton: $(this.wrapper).find('#btn-refresh-stats')
		};
		if (this.elements.heldTicketsList.length === 0) {
			console.warn("Held tickets list container (#held-tickets-list) not found in HTML template.");
		}
		if (this.elements.officeNameDisplay.length === 0) console.warn("Element #office-display-name not found");
		if (this.elements.servicePointNameDisplay.length === 0) console.warn("Element #service-point-display-name not found");
	}


	bind_events() {
		// Кнопки дій
		this.elements.callNextButton.on('click', () => this.handle_call_next());
		this.elements.startServingButton.on('click', () => this.handle_action('start_serving', 'Розпочинаємо обслуговування...', 'Почати Обслуговування'));
		this.elements.finishServiceButton.on('click', () => this.handle_action('finish_service', 'Завершуємо обслуговування...', 'Завершити'));
		this.elements.noShowButton.on('click', () => this.handle_action('mark_no_show', 'Відмічаємо як "Не з\'явився"...', 'Не з\'явився'));
		this.elements.holdTicketButton.on('click', () => this.handle_action('hold', 'Відкладаємо талон...', 'Відкласти'));
		this.elements.transferTicketButton.on('click', () => this.handle_transfer());
		this.elements.refreshStatsButton.on('click', () => this.refresh_queue_stats());
		// Зміна точки обслуговування
		this.elements.servicePointSelector.on('change', (e) => {
			this.service_point_id = $(e.target).val(); // Зберігаємо ID
			const selected_option = $(e.target).find('option:selected');
			this.service_point_name = selected_option.text(); // Зберігаємо Назву
			// --- ЗМІНЕНО: Оновлюємо текст елемента для назви точки ---
			this.elements.servicePointNameDisplay?.text(this.service_point_name || 'Не обрано');
			console.log("Service point changed to:", this.service_point_id, this.service_point_name);
		});


		// **НОВИЙ ОБРОБНИК для кнопки "Повернути"**
		// Використовуємо делегування подій, бо кнопки .btn-recall додаються динамічно
		$(this.wrapper).on('click', '#held-tickets-list .btn-recall', (e) => {
			const ticket_name = $(e.currentTarget).data('ticket-name');
			if (ticket_name) {
				this.handle_recall_ticket(ticket_name, e.currentTarget);
			}
		});

		// Realtime підписки
		frappe.realtime.on('qms_ticket_updated', (data) => this.handle_realtime_update(data));
		frappe.realtime.on('qms_ticket_called', (data) => this.handle_realtime_update(data));
		frappe.realtime.on('qms_stats_updated', (data) => this.handle_realtime_update(data));
	}
	// Обробник для Realtime подій (оновлюємо поточний талон, якщо збігається)
	handle_realtime_update(data) {
		console.log("Realtime event received:", data.event, data);
		// Перевіряємо за ID офісу
		if (data.office === this.office_id) {
			this.refresh_queue_stats();
			this.refresh_held_tickets();
		}
		// Якщо оновлення стосується поточного талону
		if (this.current_ticket && this.current_ticket.name === data.name) {
			// Оновлюємо дані поточного талону даними з події
			// Переконуємось, що передаються всі потрібні поля (вкл. service_name, service_point_name)
			Object.assign(this.current_ticket, data);
			this.update_ui_state();
		}
		// Якщо прийшла подія про виклик нового талону (і в нас немає активного)
		// Або якщо подія стосується талону, який ми щойно викликали
		else if (data.event === 'qms_ticket_called' && data.operator === frappe.session.user) {
			// Можливо, варто оновити this.current_ticket даними з події
			this.current_ticket = data; // Перезаписуємо/створюємо поточний талон
			this.update_ui_state();
			this.refresh_queue_stats();
		}
	}


	// Виклик наступного
	handle_call_next() {
		// --- ЗМІНЕНО: Перевіряємо ID точки ---
		if (!this.service_point_id) {
			frappe.show_alert({ message: "Будь ласка, оберіть точку обслуговування.", indicator: "warning" });
			this.elements.servicePointSelector?.focus();
			return;
		}
		// --- Кінець змін ---
		this.elements.callNextButton.prop('disabled', true);
		// Використовуємо НАЗВУ точки для повідомлення
		frappe.show_alert({ message: `Викликаємо наступного на точку ${this.service_point_name}...`, indicator: "info" }, 3);

		frappe.call({
			method: "qms_cherga.api.call_next_visitor",
			// --- ЗМІНЕНО: Передаємо ID точки ---
			args: { service_point_name: this.service_point_id },
			// --- Кінець змін ---
		}).then(r => {
			if (r.message && r.message.status === 'success') {
				frappe.show_alert({ message: r.message.message, indicator: "green" }, 5);
				this.current_ticket = r.message.ticket_info; // Отримуємо дані з назвами
			} else if (r.message && r.message.status === 'info') {
				frappe.msgprint({ title: "Інфо", indicator: "blue", message: r.message.message });
				this.current_ticket = null;
			} else {
				frappe.msgprint({ title: "Помилка", indicator: "red", message: r.message ? r.message.message : "Невідома помилка API" });
				this.current_ticket = null;
			}
			this.update_ui_state();
			this.refresh_queue_stats();
		}).catch(err => {
			frappe.msgprint({ title: "Помилка Зв'язку", indicator: "red", message: "Не вдалося виконати запит." });
			console.error(err);
			this.current_ticket = null;
			this.update_ui_state();
		}).finally(() => {
			this.update_ui_state();
		});
	} А

	handle_action(action_type, loading_message, button_label) {
		if (!this.current_ticket && !['hold'].includes(action_type)) { // Дозволяємо hold_ticket без current_ticket? Ні, тільки для активного.
			if (!this.current_ticket) {
				frappe.show_alert({ message: "Немає активного талону для цієї дії.", indicator: "warning" });
				return;
			}
		}
		const ticket_name = this.current_ticket?.name; // Безпечне отримання імені
		if (!ticket_name && action_type !== 'some_other_action_without_ticket') {
			frappe.show_alert({ message: "Помилка: Неможливо визначити ім'я активного талону.", indicator: "danger" });
			return;
		}

		const button_id = '#btn-' + action_type.replace(/_/g, '-');
		const button = $(this.wrapper).find(button_id);
		if (button.length > 0) button.prop('disabled', true);
		frappe.show_alert({ message: loading_message || `Виконуємо дію для ${ticket_name}...`, indicator: "info" }, 2);

		frappe.call({
			method: `qms_cherga.qms_cherga.page.operator_dashboard.operator_dashboard.${action_type}_ticket`,
			args: { ticket_name: ticket_name }
		}).then(r => {
			if (r.message && r.message.status === 'success') {
				frappe.show_alert({ message: r.message.message || `${button_label} виконано успішно.`, indicator: "green" }, 5);
				if (action_type === 'finish_service' || action_type === 'mark_no_show' || action_type === 'hold') {
					this.current_ticket = null;
					if (action_type === 'hold') {
						this.refresh_held_tickets(); // Оновити список відкладених одразу
					}
				} else {
					this.current_ticket = r.message.ticket_info || null;
				}
				this.update_ui_state();
				this.refresh_queue_stats();
			} else {
				frappe.msgprint({ title: "Помилка", indicator: "red", message: r.message ? r.message.message : `Не вдалося виконати дію ${button_label}` });
				this.update_ui_state(); // Оновити стан кнопок навіть при помилці
			}
		}).catch(err => {
			frappe.msgprint({ title: "Помилка Зв'язку", indicator: "red", message: `Помилка при виконанні дії ${button_label}.` });
			console.error(err);
			this.update_ui_state(); // Оновити стан кнопок при помилці зв'язку
		});
	}

	// **НОВА ФУНКЦІЯ для обробки повернення**
	handle_recall_ticket(ticket_name, button_element) {
		if (!ticket_name) return;
		if (this.current_ticket) {
			frappe.show_alert({ message: "Будь ласка, завершіть або відкладіть поточний талон перед поверненням іншого.", indicator: "warning" });
			return;
		}

		const $button = $(button_element);
		$button.prop('disabled', true).text('Повернення...');

		frappe.call({
			method: "qms_cherga.qms_cherga.page.operator_dashboard.operator_dashboard.recall_ticket",
			args: { ticket_name: ticket_name }
		}).then(r => {
			if (r.message && r.message.status === 'success') {
				frappe.show_alert({ message: r.message.message, indicator: "green" }, 5);
				this.current_ticket = r.message.ticket_info; // Встановлюємо повернутий талон як поточний
				this.update_ui_state(); // Оновлюємо UI
				this.refresh_held_tickets(); // Оновлюємо список відкладених (цей має зникнути)
				this.refresh_queue_stats(); // Оновлюємо статистику
			} else {
				frappe.msgprint({ title: "Помилка", indicator: "red", message: r.message ? r.message.message : "Не вдалося повернути талон." });
				$button.prop('disabled', false).text('Повернути'); // Розблокувати кнопку у разі помилки
			}
		}).catch(err => {
			frappe.msgprint({ title: "Помилка Зв'язку", indicator: "red", message: "Не вдалося виконати запит на повернення." });
			console.error(err);
			$button.prop('disabled', false).text('Повернути'); // Розблокувати кнопку у разі помилки
		});
	}


	handle_transfer() {
		if (!this.current_ticket) return;
		frappe.msgprint("Логіка перенаправлення ще не реалізована.");
	}

	// Оновлення інтерфейсу
	update_ui_state() {
		const has_current_ticket = !!this.current_ticket;
		const status = this.current_ticket?.status;

		// Оновлення картки поточного талону
		if (this.elements.currentTicketInfo) {
			if (this.current_ticket) {
				// --- ЗМІНЕНО: Використовуємо service_name та скорочений номер ---
				const shortTicketNumber = get_short_ticket_number(this.current_ticket.ticket_number);
				const serviceLabel = this.current_ticket.service_name || 'N/A';
				const pointLabel = this.current_ticket.service_point_name || 'N/A';
				// --- Кінець змін ---

				this.elements.currentTicketInfo.html(`
                    <p><strong>Номер:</strong> <span style="font-size: 1.3em; font-weight: bold;">${shortTicketNumber}</span></p>
                    <p><strong>Послуга:</strong> ${serviceLabel}</p>
                    <p><strong>Точка:</strong> ${pointLabel}</p>
                    <p><strong>Статус:</strong> <span class="badge bg-${this.get_status_badge(status)}">${status || 'N/A'}</span></p>
                    <p><strong>Телефон:</strong> ${this.current_ticket.visitor_phone || '-'}</p>
                    <p><small>Викликано: ${this.format_time(this.current_ticket.call_time)} | Початок: ${this.format_time(this.current_ticket.start_service_time)}</small></p>
                `);
			} else {
				this.elements.currentTicketInfo.html(`<p>Немає активного талону.</p>`);
			}
		}

		// Оновлення доступності кнопок (без змін)
		// ... (код оновлення кнопок) ...
		this.elements.callNextButton?.prop('disabled', has_current_ticket);
		this.elements.startServingButton?.prop('disabled', !(has_current_ticket && status === 'Called'));
		this.elements.finishServiceButton?.prop('disabled', !(has_current_ticket && status === 'Serving'));
		this.elements.noShowButton?.prop('disabled', !(has_current_ticket && (status === 'Called' || status === 'Serving')));
		this.elements.holdTicketButton?.prop('disabled', !(has_current_ticket && status === 'Serving'));
		this.elements.transferTicketButton?.prop('disabled', !(has_current_ticket && (status === 'Called' || status === 'Serving')));


		// Оновлення статусу оператора (без змін)
		// ... (код оновлення статусу оператора) ...
		let op_status_text = 'Вільний';
		let op_status_class = 'bg-success';
		if (status === 'Serving') { op_status_text = 'Обслуговує'; op_status_class = 'bg-warning'; }
		else if (status === 'Called') { op_status_text = 'Викликано'; op_status_class = 'bg-info'; }
		this.elements.operatorStatus?.text(op_status_text).removeClass('bg-secondary bg-success bg-warning bg-info').addClass(op_status_class);
	}

	// Завантаження початкових даних
	load_initial_data() {
		frappe.call({
			method: "qms_cherga.qms_cherga.page.operator_dashboard.operator_dashboard.get_initial_data"
		}).then(r => {
			if (r.message && !r.message.error) {
				this.operator_info = r.message.operator_info;
				this.current_ticket = r.message.current_ticket; // Вже має містити service_name, service_point_name
				// --- ЗМІНЕНО: Зберігаємо та відображаємо назву офісу ---
				this.office_id = this.operator_info?.default_office_id;
				this.office_name = this.operator_info?.default_office_name;
				this.elements.officeNameDisplay?.text(this.office_name || 'Офіс не визначено');
				// --- Кінець змін ---

				this.elements.operatorName?.text(this.operator_info?.full_name || frappe.session.user);

				// Заповнюємо селектор точок обслуговування
				// Використовуємо список { value: 'ID', label: 'Назва' } з бекенду
				const points = r.message.available_service_points || [];
				const selector = this.elements.servicePointSelector;
				if (selector?.length > 0) {
					selector.empty().append('<option value="">-- Оберіть точку --</option>');
					let initial_point_id = null;
					let initial_point_label = 'Не обрано';
					points.forEach(point => {
						selector.append(`<option value="${point.value}">${point.label}</option>`);
					});
					// Обираємо першу точку за замовчуванням, якщо вона одна
					if (points.length === 1) {
						initial_point_id = points[0].value;
						initial_point_label = points[0].label;
						selector.val(initial_point_id);
					}
					this.service_point_id = initial_point_id;
					this.service_point_name = initial_point_label;
					this.elements.servicePointNameDisplay?.text(initial_point_label);
				} else {
					this.elements.servicePointNameDisplay?.text('Точки не завантажені');
				}

				this.refresh_queue_stats(); // Викликаємо оновлення статистики (використовує office_id)
				this.refresh_held_tickets();
				this.update_ui_state();
			} else {
				frappe.msgprint({ title: "Помилка", message: r.message?.error || "Не вдалося завантажити дані.", indicator: 'red' });
			}
		}).catch(err => {
			frappe.msgprint({ title: "Помилка Зв'язку", message: "Не вдалося завантажити початкові дані.", indicator: 'red' });
			console.error(err);
		});
	}

	// Оновлення списку відкладених талонів
	refresh_held_tickets() {
		if (!this.elements.heldTicketsList || this.elements.heldTicketsList.length === 0) return;
		this.elements.heldTicketsList.html('<p class="text-muted">Оновлення...</p>');

		frappe.call({
			method: "qms_cherga.qms_cherga.page.operator_dashboard.operator_dashboard.get_my_held_tickets"
		}).then(r => {
			this.held_tickets = r.message || [];
			const targetDiv = this.elements.heldTicketsList;
			targetDiv.empty();

			if (this.held_tickets.length > 0) {
				let listHtml = '<ul class="list-group">';
				this.held_tickets.forEach(ticket => {
					// --- ЗМІНЕНО: Використовуємо service_name та скорочений номер ---
					const shortTicketNumber = get_short_ticket_number(ticket.ticket_number);
					const serviceLabel = ticket.service_name || 'N/A';
					// --- Кінець змін ---
					listHtml += `
                        <li class="list-group-item d-flex justify-content-between align-items-center">
                            <span>
                                <strong style="margin-right: 10px;">${shortTicketNumber}</strong>
                                <small class="text-muted">${serviceLabel}</small>
                            </span>
                            <button class="btn btn-sm btn-outline-primary btn-recall" data-ticket-name="${ticket.name}">Повернути</button>
                        </li>`;
				});
				listHtml += '</ul>';
				targetDiv.html(listHtml);
			} else {
				targetDiv.html('<p class="text-muted">Немає відкладених талонів.</p>');
			}
		}).catch(err => {
			this.elements.heldTicketsList.html('<p class="text-danger">Помилка завантаження.</p>');
			console.error("Failed to refresh held tickets:", err);
		});
	}

	// Оновлення статистики черги
	refresh_queue_stats() {
		// --- ЗМІНЕНО: Використовуємо ID офісу ---
		if (!this.office_id) {
			console.warn("Office ID not set, cannot refresh queue stats.");
			this.elements.waitingCount?.text('?'); this.elements.servedToday?.text('?'); return;
		}
		// --- Кінець змін ---
		this.elements.waitingCount?.text('...'); this.elements.servedToday?.text('...');
		frappe.call({
			method: "qms_cherga.qms_cherga.page.operator_dashboard.operator_dashboard.get_queue_stats",
			// --- ЗМІНЕНО: Передаємо ID офісу ---
			args: { office: this.office_id }
			// --- Кінець змін ---
		}).then(r => {
			// ... (обробка відповіді без змін) ...
			if (r.message && r.message.waiting !== undefined) {
				this.stats = r.message;
				this.elements.waitingCount?.text(this.stats.waiting);
				this.elements.servedToday?.text(this.stats.served_today);
			} else {
				this.elements.waitingCount?.text('Помилка'); this.elements.servedToday?.text('Помилка');
			}
		}).catch(err => {
			this.elements.waitingCount?.text('Помилка'); this.elements.servedToday?.text('Помилка');
			console.error("Failed to refresh stats:", err);
		});
	}

	// Допоміжні функції
	get_status_badge(status) { const status_map = { "Waiting": "secondary", "Called": "info", "Serving": "warning", "Completed": "success", "NoShow": "danger", "Cancelled": "dark", "Postponed": "light" }; return status_map[status] || "secondary"; }
	format_time(datetime_str) { if (!datetime_str || typeof datetime_str !== 'string') return '-'; try { if (window.moment) { return moment(datetime_str).format("HH:mm:ss"); } else { return new Date(datetime_str).toLocaleTimeString(); } } catch (e) { console.error("Error formatting time:", datetime_str, e); return '-'; } }
};