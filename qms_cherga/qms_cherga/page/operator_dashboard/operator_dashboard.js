// qms_cherga/qms_cherga/page/operator_dashboard/operator_dashboard.js

frappe.provide("qms_cherga");

// Допоміжні функції завантаження CSS та скорочення номера (без змін)
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
function get_short_ticket_number(fullTicketNumber) {
	if (!fullTicketNumber)
		return 'N/A';
	let shortNumber = fullTicketNumber.substring(fullTicketNumber.lastIndexOf('-') + 1);
	return (shortNumber && fullTicketNumber.lastIndexOf('-') !== -1) ? shortNumber : fullTicketNumber;
} //

frappe.pages['operator-dashboard'].on_page_load = function (wrapper) {
	let page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __('Operator Dashboard'), // Використовуємо __() для перекладу
		single_column: true,
	});

	wrapper.dashboard = new qms_cherga.OperatorDashboard(page, wrapper);
	$(wrapper).data("dashboard_obj", wrapper.dashboard); // Зберігаємо об'єкт для можливого доступу
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
		this.held_tickets = [];
		this.stats = { waiting: '?', served_today: '?' };

		this.make_ui();
		this.bind_events();
		this.load_initial_data();
	}

	make_ui() {
		// Завантаження CSS
		load_css("/assets/qms_cherga/css/operator_dashboard.css"); // [cite: 8]
		// Потрібно перевірити, чи потрібен Font Awesome і чи він вже не завантажений темою
		load_css("https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.15.4/css/all.min.css"); //

		// Рендер шаблону
		$(frappe.render_template("operator_dashboard_help", {})).appendTo(this.page.main); // [cite: 98]

		// Зберігаємо посилання на елементи DOM
		this.elements = {
			operatorName: $(this.wrapper).find('#operator-name'),
			operatorStatus: $(this.wrapper).find('#operator-status'),
			servicePointNameDisplay: $(this.wrapper).find('#service-point-display-name'), //
			servicePointSelector: $(this.wrapper).find('#service-point-selector'), //
			officeNameDisplay: $(this.wrapper).find('#office-display-name'), //
			waitingCount: $(this.wrapper).find('#waiting-count'),
			servedToday: $(this.wrapper).find('#served-today'),
			currentTicketInfo: $(this.wrapper).find('#current-ticket-info'),
			heldTicketsList: $(this.wrapper).find('#held-tickets-list'), //
			callNextButton: $(this.wrapper).find('#btn-call-next'),
			startServingButton: $(this.wrapper).find('#btn-start-serving'),
			finishServiceButton: $(this.wrapper).find('#btn-finish-service'),
			noShowButton: $(this.wrapper).find('#btn-no-show'),
			holdTicketButton: $(this.wrapper).find('#btn-hold-ticket'),
			transferTicketButton: $(this.wrapper).find('#btn-transfer-ticket'),
			refreshStatsButton: $(this.wrapper).find('#btn-refresh-stats')
		};

		// Перевірки наявності елементів (необов'язково, для налагодження)
		if (this.elements.heldTicketsList.length === 0)
			console.warn("Element #held-tickets-list not found."); //
		if (this.elements.officeNameDisplay.length === 0)
			console.warn("Element #office-display-name not found"); //
		if (this.elements.servicePointNameDisplay.length === 0)
			console.warn("Element #service-point-display-name not found"); //
	}

	bind_events() {
		// Кнопки дій
		this.elements.callNextButton?.on('click', () =>
			this.handle_call_next());
		this.elements.startServingButton?.on('click', () =>
			this.handle_action('start_serving', __("Starting service..."), __("Start Service"))); //
		this.elements.finishServiceButton?.on('click', () =>
			this.handle_action('finish_service', __("Finishing service..."), __("Finish Service"))); //
		this.elements.noShowButton?.on('click', () =>
			this.handle_action('mark_no_show', __("Marking as 'No Show'..."), __("No Show"))); //
		this.elements.holdTicketButton?.on('click', () =>
			this.handle_action('hold', __("Postponing ticket..."), __("Hold"))); //
		this.elements.transferTicketButton?.on('click', () =>
			this.handle_transfer()); // Залишається як заглушка
		this.elements.refreshStatsButton?.on('click', () =>
			this.refresh_queue_stats()); //

		// Зміна точки обслуговування
		this.elements.servicePointSelector?.on('change', (e) => { //
			this.service_point_id = $(e.target).val(); //
			const selected_option = $(e.target).find('option:selected'); //
			this.service_point_name = selected_option.text(); //
			this.elements.servicePointNameDisplay?.text(this.service_point_name || __('Not selected')); //
			console.log("Service point changed to:", this.service_point_id, this.service_point_name); //
			// Можливо, оновити доступність кнопок або іншу логіку при зміні точки
			this.update_ui_state(); //
		});

		// Делегування події для кнопки "Повернути"
		$(this.wrapper).on('click', '#held-tickets-list .btn-recall', (e) => { //
			const ticket_name = $(e.currentTarget).data('ticket-name'); //
			if (ticket_name) { //
				this.handle_recall_ticket(ticket_name, e.currentTarget); //
			}
		});

		// Realtime підписки (залишаються без змін, але обробник оновлено)
		frappe.realtime.on('qms_ticket_updated', (data) =>
			this.handle_realtime_update(data)); //
		frappe.realtime.on('qms_ticket_called', (data) =>
			this.handle_realtime_update(data)); //
		frappe.realtime.on('qms_stats_updated', (data) =>
			this.handle_realtime_update(data)); // Потрібно реалізувати надсилання цієї події з бекенду
	}

	// --- Обробники Realtime (ОНОВЛЕНО) ---
	handle_realtime_update(data) {
		console.log("Realtime event received:", data.event, data); //
		// Перевірка за офісом, якщо подія містить office_id
		let refreshStats = false;
		if (data.office && data.office === this.office_id) { //
			refreshStats = true; //
			// Якщо оновлення стосується відкладених (наприклад, скасовано адміном), оновлюємо список
			if (data.event === 'qms_ticket_updated' && data.previous_status === 'Postponed') { //
				this.refresh_held_tickets(); //
			}
		} else if (data.event === 'qms_stats_updated') { //
			// Якщо це загальне оновлення статистики для офісу
			if (data.office === this.office_id) { //
				refreshStats = true; //
			}
		}

		// Оновлюємо статистику, якщо потрібно
		if (refreshStats) { //
			this.refresh_queue_stats(); //
		}


		// Якщо оновлення стосується нашого поточного талону
		if (this.current_ticket && data.name && this.current_ticket.name === data.name) { //
			console.log(`Realtime update for current ticket ${data.name}`); //
			// Оновлюємо дані поточного талону даними з події
			// Переконуємось, що передаються всі потрібні поля
			if (data.updated_ticket_info) { // Якщо бекенд надсилає повний об'єкт
				this.current_ticket = data.updated_ticket_info; //
			} else { // Оновлюємо окремі поля, якщо вони є
				Object.assign(this.current_ticket, data); //
			}
			this.update_ui_state(); //
		}
		// Якщо прийшла подія про виклик ТАЛОНУ ЦИМ ОПЕРАТОРОМ
		// (перевіряємо, чи справді це наш виклик, щоб не реагувати на чужі)
		else if (data.event === 'qms_ticket_called' && data.operator === frappe.session.user) { //
			console.log(`Realtime: Ticket ${data.name} called by me.`); //
			// Оновлюємо поточний талон даними з події
			this.current_ticket = data.ticket_info || data; // Очікуємо ticket_info
			this.update_ui_state(); //
			this.refresh_queue_stats(); // Статистика змінилась
			this.refresh_held_tickets(); // Можливо, викликали відкладений
		}
		// Якщо талон, який був у нас поточним, завершено/скасовано/відкладено іншим чином (не через наш клік)
		else if (this.current_ticket && data.name && this.current_ticket.name === data.name && ['Completed', 'Cancelled', 'NoShow', 'Postponed'].includes(data.status)) { //
			console.log(`Realtime: Current ticket ${data.name} finalized externally.`); //
			this.current_ticket = null; //
			this.update_ui_state(); //
			if (data.status === 'Postponed') { // Якщо його відклали (можливо, автоматично?)
				this.refresh_held_tickets(); //
			}
		}
	}


	// --- Виклик наступного (ОНОВЛЕНО) ---
	handle_call_next() {
		if (!this.service_point_id) { //
			frappe.show_alert({
				message: __("Please select a service point."),
				indicator: "warning"
			}); //
			this.elements.servicePointSelector?.focus(); //
			return; //
		}
		// Блокуємо кнопку
		this.elements.callNextButton?.prop('disabled', true).addClass('btn-loading'); //
		frappe.show_alert({
			message: __("Calling next visitor to point {0}...", [this.service_point_name || this.service_point_id]),
			indicator: "info"
		}, 3); //

		frappe.call({
			method: "qms_cherga.api.call_next_visitor", // Викликаємо оновлений API
			args: { service_point_name: this.service_point_id }, // Передаємо ID
		}).then(r => { // Використовуємо .then() для кращої читабельності
			if (r.message && r.message.status === 'success') { //
				frappe.show_alert({
					message: r.message.message || __("Visitor called successfully."),
					indicator: "green"
				}, 5); //
				this.current_ticket = r.message.data?.ticket_info || null; // Дані тепер у data.ticket_info
			} else if (r.message && r.message.status === 'info') { //
				frappe.msgprint({
					title: __("Info"),
					indicator: "blue",
					message: r.message.message
				}); //
				this.current_ticket = null; //
			} else {
				// Обробка помилки з бекенду (status === 'error')
				frappe.msgprint({
					title: __("Error"),
					indicator: "red",
					message: r.message?.message || __("Failed to call next visitor.")
				}); //
				this.current_ticket = null; //
			}
		}).catch(err => {
			// Обробка помилки зв'язку
			frappe.msgprint({
				title: __("Communication Error"),
				indicator: "red",
				message: __("Could not execute the request.")
			}); //
			console.error("Call Next API Error:", err); //
			this.current_ticket = null; //
		}).always(() => {
			// Розблокуємо кнопку та оновлюємо UI в будь-якому випадку
			this.elements.callNextButton?.prop('disabled', false).removeClass('btn-loading'); //
			// Оновлюємо стан UI (кнопки, картка талону)
			this.update_ui_state(); //
			// Оновлюємо статистику в будь-якому випадку (кількість очікуючих могла змінитись)
			this.refresh_queue_stats(); //
		});
	}

	// --- Обробка дій з талоном (ОНОВЛЕНО) ---
	handle_action(action_type, loading_message, button_label) {
		if (!this.current_ticket) { //
			frappe.show_alert({
				message: __("No active ticket for this action."),
				indicator: "warning"
			}); //
			return; //
		}
		const ticket_name = this.current_ticket.name; //
		if (!ticket_name) { //
			frappe.show_alert({
				message: __("Error: Cannot identify active ticket name."),
				indicator: "danger"
			}); //
			return; //
		}

		// Знаходимо кнопку і блокуємо її
		const button_id_map = { // Мапування типів дій на ID кнопок
			'start_serving': '#btn-start-serving', //
			'finish_service': '#btn-finish-service', //
			'mark_no_show': '#btn-no-show', //
			'hold': '#btn-hold-ticket', //
			// Додайте інші дії тут
		}; //
		const button_selector = button_id_map[action_type]; //
		const button = button_selector ? $(this.wrapper).find(button_selector) : null; //
		button?.prop('disabled', true).addClass('btn-loading'); // Додаємо клас для спінера

		frappe.show_alert({
			message: loading_message || __("Processing action for {0}...", [ticket_name]),
			indicator: "info"
		}, 2); //

		frappe.call({
			// Викликаємо методи з operator_dashboard.py
			method: `qms_cherga.qms_cherga.page.operator_dashboard.operator_dashboard.${action_type}_ticket`, //
			args: { ticket_name: ticket_name } //
		}).then(r => {
			if (r.message && r.message.status === 'success') { //
				frappe.show_alert({
					message: r.message.message || __("{0} successful.", [button_label]),
					indicator: "green"
				}, 5); //
				// Оновлюємо стан на основі дії
				if (['finish_service', 'mark_no_show', 'hold'].includes(action_type)) { //
					this.current_ticket = null; // Талон більше не активний у оператора
					if (action_type === 'hold') { //
						this.refresh_held_tickets(); // Оновити список відкладених
					}
				} else if (action_type === 'start_serving') { //
					// Оновлюємо дані поточного талону, якщо вони повернулись
					this.current_ticket = r.message.data?.ticket_info || this.current_ticket; //
					if (this.current_ticket)
						this.current_ticket.status = 'Serving'; // Встановлюємо статус вручну, якщо API не повернув
				} else {
					// Для інших можливих дій, оновлюємо, якщо є дані
					this.current_ticket = r.message.data?.ticket_info || this.current_ticket; //
				}
			} else {
				// Обробка помилки з бекенду (status === 'error')
				frappe.msgprint({
					title: __("Error"),
					indicator: "red",
					message: r.message?.message || __("Failed to perform action {0}.", [button_label])
				}); //
			}
		}).catch(err => {
			// Обробка помилки зв'язку
			frappe.msgprint({
				title: __("Communication Error"),
				indicator: "red",
				message: __("Error performing action {0}.", [button_label])
			}); //
			console.error(`${action_type} API Error:`, err); //
		}).always(() => {
			// Розблокування кнопки та оновлення UI
			button?.prop('disabled', false).removeClass('btn-loading'); //
			this.update_ui_state(); //
			this.refresh_queue_stats(); // Статистика могла змінитись
		});
	}

	// --- Обробка повернення талону (ОНОВЛЕНО) ---
	handle_recall_ticket(ticket_name, button_element) {
		if (!ticket_name)
			return; //
		if (this.current_ticket) { //
			frappe.show_alert({
				message: __("Please finish or postpone the current ticket before recalling another."),
				indicator: "warning"
			}); //
			return; //
		}

		const $button = $(button_element); //
		$button.prop('disabled', true).text(__("Recalling...")); // Додаємо текст завантаження

		frappe.call({
			method: "qms_cherga.qms_cherga.page.operator_dashboard.operator_dashboard.recall_ticket", //
			args: { ticket_name: ticket_name } //
		}).then(r => {
			if (r.message && r.message.status === 'success') { //
				frappe.show_alert({
					message: r.message.message || __("Ticket recalled successfully."),
					indicator: "green"
				}, 5); //
				this.current_ticket = r.message.data?.ticket_info || null; // Встановлюємо як поточний
			} else {
				// Обробка помилки з бекенду (status === 'error')
				frappe.msgprint({
					title: __("Error"),
					indicator: "red",
					message: r.message?.message || __("Failed to recall ticket.")
				}); //
			}
		}).catch(err => {
			// Обробка помилки зв'язку
			frappe.msgprint({ title: __("Communication Error"), indicator: "red", message: __("Could not execute the recall request.") }); //
			console.error("Recall Ticket API Error:", err); //
		}).always(() => {
			// Оновлення UI відбувається в кінці, незалежно від результату
			$button.prop('disabled', false).text(__("Recall")); // Повертаємо текст кнопки (можливо, кнопка зникне)
			this.update_ui_state(); // Оновлюємо UI (картка поточного талону, кнопки)
			this.refresh_held_tickets(); // Оновлюємо список відкладених (цей має зникнути)
			this.refresh_queue_stats(); // Статистика могла змінитись
		});
	}


	// --- Заглушка для перенаправлення ---
	handle_transfer() {
		if (!this.current_ticket) { //
			frappe.show_alert({
				message: __("No active ticket to transfer."),
				indicator: "warning"
			}); //
			return; //
		};
		// TODO: Реалізувати логіку перенаправлення (можливо, діалогове вікно для вибору точки/оператора/послуги)
		frappe.msgprint(__("Transfer functionality is not yet implemented.")); //
	}

	// --- Оновлення інтерфейсу (без суттєвих змін, але перевіряємо статус) ---
	update_ui_state() {
		const has_current_ticket = !!this.current_ticket; //
		const status = this.current_ticket?.status; //

		// Оновлення картки поточного талону
		if (this.elements.currentTicketInfo) { //
			if (this.current_ticket) { //
				const shortTicketNumber = get_short_ticket_number(this.current_ticket.ticket_number); //
				// Використовуємо назви, які повернув API
				const serviceLabel = this.current_ticket.service_name || this.current_ticket.service || 'N/A'; //
				const pointLabel = this.current_ticket.service_point_name || this.current_ticket.service_point || 'N/A'; //
				this.elements.currentTicketInfo.html(`
                    <p><strong>${__("Number")}:</strong> <span style="font-size: 1.3em; font-weight: bold;">${shortTicketNumber}</span></p>
                    <p><strong>${__("Service")}:</strong> ${serviceLabel}</p>
                    <p><strong>${__("Point")}:</strong> ${pointLabel}</p>
                    <p><strong>${__("Status")}:</strong> <span class="badge bg-${this.get_status_badge(status)}">${status || 'N/A'}</span></p>
                    <p><strong>${__("Phone")}:</strong> ${this.current_ticket.visitor_phone || '-'}</p>
                    <p><small>${__("Called")}: ${this.format_time(this.current_ticket.call_time)} | ${__("Started")}: ${this.format_time(this.current_ticket.start_service_time)}</small></p>
                `); //
			} else {
				this.elements.currentTicketInfo.html(`<p class="text-muted">${__("No active ticket.")}</p>`); //
			}
		}

		// Оновлення доступності кнопок
		const can_select_point = !has_current_ticket; // Можна обирати точку, тільки якщо немає активного талону?
		this.elements.servicePointSelector?.prop('disabled', !can_select_point); //

		const can_call_next = !has_current_ticket && !!this.service_point_id; // Можна викликати, якщо немає талону І ОБРАНО точку
		this.elements.callNextButton?.prop('disabled', !can_call_next); //

		this.elements.startServingButton?.prop('disabled', !(has_current_ticket && status === 'Called')); //
		this.elements.finishServiceButton?.prop('disabled', !(has_current_ticket && status === 'Serving')); //
		this.elements.noShowButton?.prop('disabled', !(has_current_ticket && (status === 'Called' || status === 'Serving'))); //
		this.elements.holdTicketButton?.prop('disabled', !(has_current_ticket && status === 'Serving')); //
		this.elements.transferTicketButton?.prop('disabled', !(has_current_ticket && (status === 'Called' || status === 'Serving'))); // Залишаємо логіку або міняємо

		// Оновлення статусу оператора
		let op_status_text = __('Available'); //
		let op_status_class = 'bg-success'; //
		if (status === 'Serving') {
			op_status_text = __('Serving');
			op_status_class = 'bg-warning text-dark';
		} //
		else if (status === 'Called') {
			op_status_text = __('Called');
			op_status_class = 'bg-info text-dark';
		} //
		else if (!this.service_point_id) {
			op_status_text = __('Select Point');
			op_status_class = 'bg-secondary';
		} //

		this.elements.operatorStatus?.text(op_status_text).removeClass('bg-secondary bg-success bg-warning bg-info text-dark').addClass(op_status_class); //
	}

	// --- Завантаження початкових даних (ОНОВЛЕНО) ---
	load_initial_data() {
		frappe.show_alert({ message: __("Loading initial data..."), indicator: "info" }, 2); //
		frappe.call({
			method: "qms_cherga.qms_cherga.page.operator_dashboard.operator_dashboard.get_initial_data" //
		}).then(r => {
			if (r.message && r.message.status === 'success') { //
				const data = r.message.data; // Дані тепер у data
				this.operator_info = data.operator_info; //
				this.current_ticket = data.current_ticket; // Може бути null
				this.office_id = this.operator_info?.default_office_id; //
				this.office_name = this.operator_info?.default_office_name; //

				this.elements.operatorName?.text(this.operator_info?.full_name || frappe.session.user); //
				this.elements.officeNameDisplay?.text(this.office_name || __('Office not defined')); //

				// Заповнюємо селектор точок
				const points = data.available_service_points || []; //
				const selector = this.elements.servicePointSelector; //
				if (selector?.length > 0) { //
					selector.empty().append(`<option value="">-- ${__("Select Point")} --</option>`); //
					let initial_point_id = null; //
					let initial_point_label = __('Not selected'); //
					points.forEach(point => { //
						selector.append(`<option value="${point.value}">${point.label}</option>`); //
					});

					// Спробувати відновити точку з поточного талону, якщо він є
					if (this.current_ticket && this.current_ticket.service_point) { //
						initial_point_id = this.current_ticket.service_point; //
						// Знайти label для цього ID
						const selected_point = points.find(p => p.value === initial_point_id); //
						initial_point_label = selected_point ? selected_point.label : initial_point_id; // Fallback на ID
						selector.val(initial_point_id); //
					} else if (points.length === 1) { //
						// Якщо точка одна, обираємо її за замовчуванням
						initial_point_id = points[0].value; //
						initial_point_label = points[0].label; //
						selector.val(initial_point_id); //
					}
					this.service_point_id = initial_point_id; //
					this.service_point_name = initial_point_label === initial_point_id ? __('Not selected') : initial_point_label; // Коригуємо мітку
					this.elements.servicePointNameDisplay?.text(this.service_point_name); //

				} else {
					this.elements.servicePointNameDisplay?.text(__('No points loaded')); //
				}

				// Запускаємо оновлення залежних даних
				this.refresh_queue_stats(); //
				this.refresh_held_tickets(); //
				this.update_ui_state(); // Оновлюємо кнопки/статус на основі завантажених даних

			} else {
				// Обробка помилки з бекенду (status === 'error' or 'info' with error message?)
				frappe.msgprint({
					title: __("Error"), message: r.message?.message || __("Failed to load initial data."),
					indicator: 'red'
				}); //
				// Можна заблокувати інтерфейс або показати повідомлення про помилку
				this.elements.operatorName?.text(__("Error Loading Data")); //
				this.elements.officeNameDisplay?.text(__("Error")); //
				this.elements.servicePointNameDisplay?.text(__("Error")); //
				// Блокуємо всі кнопки
				this.elements.callNextButton?.prop('disabled', true); //
				this.elements.startServingButton?.prop('disabled', true); //
				this.elements.finishServiceButton?.prop('disabled', true); //
				this.elements.noShowButton?.prop('disabled', true); //
				this.elements.holdTicketButton?.prop('disabled', true); //
				this.elements.transferTicketButton?.prop('disabled', true); //
				this.elements.refreshStatsButton?.prop('disabled', true); //

			}
		}).catch(err => {
			// Обробка помилки зв'язку
			frappe.msgprint({
				title: __("Communication Error"),
				message: __("Could not load initial dashboard data."),
				indicator: 'red'
			}); //
			console.error("Load Initial Data API Error:", err); //
		});
	}

	// --- Оновлення списку відкладених (ОНОВЛЕНО) ---
	refresh_held_tickets() {
		if (!this.elements.heldTicketsList || this.elements.heldTicketsList.length === 0)
			return; //
		this.elements.heldTicketsList.html(`<p class="text-muted p-2">${__("Updating...")}</p>`); // Додав padding

		frappe.call({
			method: "qms_cherga.qms_cherga.page.operator_dashboard.operator_dashboard.get_my_held_tickets" //
		}).then(r => {
			const targetDiv = this.elements.heldTicketsList; //
			targetDiv.empty(); // Очищаємо перед заповненням

			if (r.message && r.message.status === 'success') { //
				this.held_tickets = r.message.data?.held_tickets || []; // Дані тепер у data.held_tickets
				if (this.held_tickets.length > 0) { //
					let listHtml = '<ul class="list-group list-group-flush">'; // Використовуємо flush для кращого вигляду
					this.held_tickets.forEach(ticket => { //
						const shortTicketNumber = get_short_ticket_number(ticket.ticket_number); //
						const serviceLabel = ticket.service_name || ticket.service || 'N/A'; //
						listHtml += `
                            <li class="list-group-item d-flex justify-content-between align-items-center p-2">
                                <span>
                                    <strong style="margin-right: 10px;">${shortTicketNumber}</strong>
                                    <small class="text-muted">${serviceLabel}</small>
                                </span>
                                <button class="btn btn-sm btn-outline-primary btn-recall" data-ticket-name="${ticket.name}">${__("Recall")}</button>
                            </li>`; //
					});
					listHtml += '</ul>'; //
					targetDiv.html(listHtml); //
				} else {
					targetDiv.html(`<p class="text-muted p-2">${__("No postponed tickets.")}</p>`); //
				}
			} else {
				// Обробка помилки з бекенду (status === 'error' or 'info')
				const errorMsg = r.message?.message || __("Failed to load postponed tickets."); //
				targetDiv.html(`<p class="text-danger p-2">${errorMsg}</p>`); //
				console.error("Refresh Held Tickets Error:", errorMsg, r.message?.details); //
			}
		}).catch(err => {
			// Обробка помилки зв'язку
			this.elements.heldTicketsList?.html(`<p class="text-danger p-2">${__("Error loading data.")}</p>`); //
			console.error("Failed to refresh held tickets (API Call):", err); //
		});
	}


	// --- Оновлення статистики черги (ОНОВЛЕНО) ---
	refresh_queue_stats() {
		if (!this.office_id) { //
			console.warn("Office ID not set, cannot refresh queue stats."); //
			this.elements.waitingCount?.text('?'); this.elements.servedToday?.text('?'); //
			return; //
		}
		// Показуємо індикацію завантаження
		this.elements.waitingCount?.html('<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>'); //
		this.elements.servedToday?.html('<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>'); //

		frappe.call({
			method: "qms_cherga.qms_cherga.page.operator_dashboard.operator_dashboard.get_queue_stats", //
			args: { office: this.office_id } //
		}).then(r => {
			if (r.message && r.message.status === 'success') { //
				this.stats = r.message.data || { waiting: '?', served_today: '?' }; // Дані тепер у data
				this.elements.waitingCount?.text(this.stats.waiting); //
				this.elements.servedToday?.text(this.stats.served_today); //
			} else {
				// Обробка помилки з бекенду (status === 'error' or 'info')
				const errorMsg = r.message?.message || __("Failed to load statistics."); //
				console.error("Refresh Stats Error:", errorMsg, r.message?.details); //
				this.elements.waitingCount?.text('!'); this.elements.servedToday?.text('!'); //
				frappe.show_alert({ message: errorMsg, indicator: 'warning' }); // Невеличке сповіщення
			}
		}).catch(err => {
			// Обробка помилки зв'язку
			this.elements.waitingCount?.text('!');
			this.elements.servedToday?.text('!'); //
			console.error("Failed to refresh stats (API Call):", err); //
			frappe.show_alert({ message: __("Error loading queue statistics."), indicator: 'warning' }); //
		});
	}

	// --- Допоміжні функції форматування (без змін) ---
	get_status_badge(status) {
		const status_map = {
			"Waiting": "secondary",
			"Called": "info",
			"Serving": "warning",
			"Completed": "success",
			"NoShow": "danger",
			"Cancelled": "dark",
			"Postponed": "light text-dark"
		};
		return status_map[status] || "secondary";
	} // Додав text-dark для Postponed
	format_time(datetime_str) {
		if (!datetime_str || typeof datetime_str !== 'string')
			return '-';
		try { /* Використовуємо frappe.datetime */
			return frappe.datetime.str_to_user(datetime_str).split(' ')[1] || '-';
		}
		catch (e) {
			console.error("Error formatting time:", datetime_str, e);
			return '-';
		}
	} //

};