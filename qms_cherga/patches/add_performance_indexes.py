"""
Migration patch to add performance indexes to QMS tables.
"""
import frappe


def execute():
    """
    Додає індекси для покращення продуктивності запитів.
    """
    frappe.db.sql("""
        CREATE INDEX IF NOT EXISTS idx_qms_ticket_office_status_creation
        ON `tabQMS Ticket` (office, status, creation)
    """)

    frappe.db.sql("""
        CREATE INDEX IF NOT EXISTS idx_qms_ticket_service_status_appointment
        ON `tabQMS Ticket` (service, status, is_appointment)
    """)

    frappe.db.sql("""
        CREATE INDEX IF NOT EXISTS idx_qms_ticket_operator_status
        ON `tabQMS Ticket` (operator, status)
    """)

    frappe.db.sql("""
        CREATE INDEX IF NOT EXISTS idx_qms_ticket_appointment_datetime
        ON `tabQMS Ticket` (appointment_datetime)
    """)

    frappe.db.sql("""
        CREATE INDEX IF NOT EXISTS idx_qms_ticket_completion_time
        ON `tabQMS Ticket` (completion_time)
    """)

    frappe.db.sql("""
        CREATE INDEX IF NOT EXISTS idx_qms_daily_counter_office_date
        ON `tabQMS Daily Counter` (office, date)
    """)

    frappe.db.commit()

    print("Performance indexes added successfully")
