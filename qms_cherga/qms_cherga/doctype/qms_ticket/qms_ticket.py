# qms_ticket.py

import time
import frappe
from frappe.model.document import Document
from frappe.utils import today, cint, get_date_str


class QMSTicket(Document):

    # --- Налаштування DocType ---
    # У визначенні DocType 'QMS Ticket' (через UI або qms_ticket.json):
    # 1. Встановіть властивість 'Autoname' на 'method'.
    #    (Або 'python:autoname', якщо ви хочете вказати ім'я методу явно).
    # 2. Приберіть інші правила Autoname ('naming_series', 'prompt', 'field:...' тощо).

    def autoname(self):
        """
        Цей метод автоматично викликається Frappe для встановлення
        первинного ключа документа (self.name), якщо Autoname='method'.
        Він виконується *перед* before_insert.
        """
        # 1. Перевірка наявності офісу
        if not self.office:
            frappe.throw(
                "Необхідно вказати 'Office' для генерації імені талону")

        # 2. Отримання поточної дати
        current_date_str = today()  # Формат: YYYY-MM-DD

        # 3. Отримання наступного номера послідовності
        try:
            # Передаємо дату для консистентності
            next_num = self.get_next_ticket_sequence_orm(current_date_str)
        except Exception as e:
            # Логуємо помилку і перериваємо процес, якщо лічильник недоступний
            frappe.log_error(frappe.get_traceback(),
                             "QMSTicket Autoname Counter Fetch Error")
            frappe.throw(
                f"Не вдалося отримати лічильник для автоматичного іменування: {e}")

        # 4. Форматування лічильника (наприклад, 4 цифри)
        counter_str = str(next_num).zfill(4)

        # 5. Форматування дати (наприклад, YYYYMMDD)
        date_str_formatted = current_date_str.replace("-", "")

        # 6. Отримання абревіатури (ABBR) з поля 'office'
        abbr = self.office

        # 7. Створення фінального імені: TIKET-OFFICE ABBR-Date-COunter
        # Налаштуйте префікс та роздільники відповідно до ваших вимог
        generated_name = f"TIKET-{abbr}-{date_str_formatted}-{counter_str}"

        # 8. Присвоєння згенерованого імені полю self.name
        self.name = generated_name

        # --- Опціонально: Встановлення поля ticket_number ---
        # Якщо ви хочете, щоб поле ticket_number також встановлювалось тут
        # (це може бути логічніше, ніж у before_insert)
        if not self.ticket_number:
            self.ticket_number = counter_str
            # Або якщо потрібне числове значення:
            # self.ticket_number = next_num

    def before_insert(self):
        # Метод autoname вже встановив self.name.
        # Цей метод тепер можна використовувати для іншої логіки,
        # яка має виконатися після autoname, але перед першим збереженням.
        # Наприклад, валідації, встановлення інших полів тощо.

        # Якщо ви НЕ встановили self.ticket_number у методі autoname,
        # це можна зробити тут, хоча це менш чисто.
        # Наприклад, витягнувши лічильник з self.name (але краще встановити в autoname).
        #
        # if not self.ticket_number and self.name:
        #     try:
        #         self.ticket_number = self.name.split('-')[-1]
        #     except Exception:
        #         pass # Обробка помилки, якщо формат імені несподіваний

        # Наразі метод може бути порожнім, якщо інша логіка не потрібна
        pass

    # Метод get_next_ticket_sequence_orm залишається без змін (як у попередньому варіанті)
    def get_next_ticket_sequence_orm(self, current_date_str):
        """
        Отримує наступний номер послідовності з 'QMS Daily Counter'.
        (Код ідентичний попередньому)
        """
        if not self.office:
            frappe.throw("Не вказано 'Office' для генерації послідовності")

        counter_doc_name = f"{self.office}-{current_date_str}"
        new_number = 0
        max_attempts = 5  # Кількість спроб

        for attempt in range(max_attempts):
            counter_doc = None
            try:
                # Use exists for check
                if frappe.db.exists("QMS Daily Counter", counter_doc_name):
                    # Use get_doc for loading
                    counter_doc = frappe.get_doc(
                        "QMS Daily Counter", counter_doc_name)
                    # Re-read from DB before incrementing
                    counter_doc.load_from_db()
                    new_number = cint(counter_doc.last_number) + 1  # Use cint
                    counter_doc.last_number = new_number
                else:
                    # Create new counter document
                    new_number = 1
                    counter_doc = frappe.new_doc("QMS Daily Counter")
                    counter_doc.name = counter_doc_name  # Set name explicitly
                    counter_doc.office = self.office
                    counter_doc.date = current_date_str
                    counter_doc.last_number = new_number

                # Save the counter doc
                counter_doc.flags.ignore_permissions = True
                counter_doc.save(ignore_version=True)
                frappe.db.commit()  # Commit immediately

                # If save successful, return the number
                return new_number

            except frappe.DuplicateEntryError:
                frappe.db.rollback()
                frappe.log_warning(
                    f"Attempt {attempt + 1}: Duplicate entry error for {counter_doc_name}. Retrying.", "QMSTicket ORM Counter")

            except Exception as e:
                frappe.db.rollback()
                frappe.log_error(frappe.get_traceback(
                ), f"QMS Ticket Counter Error (ORM Attempt {attempt + 1})")
                # Перекидаємо помилку, щоб її зловили у методі autoname
                raise frappe._(
                    "Не вдалося оновити лічильник талонів: {0}").format(e)

            # Wait before retrying
            time.sleep(0.1 + (0.1 * attempt))  # Progressive delay

        # If loop finishes without returning
        frappe.db.rollback()
        # Перекидаємо помилку, щоб її зловили у методі autoname
        raise frappe._(
            f"Не вдалося отримати унікальний номер талону для офісу {self.office} ({current_date_str}) після {max_attempts} спроб (ORM метод). Можливе високе навантаження."
        )
