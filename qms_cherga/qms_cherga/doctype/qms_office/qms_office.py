# Copyright (c) 2025, Maxym Sysoiev and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class QMSOffice(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF
		from qms_cherga.qms_cherga.doctype.qms_office_service_assignment.qms_office_service_assignment import QMSOfficeServiceAssignment

		abbreviation: DF.Data | None
		address: DF.Text | None
		available_services: DF.Table[QMSOfficeServiceAssignment]
		contact_phone: DF.Data | None
		display_message_text: DF.TextEditor | None
		office_name: DF.Data
		organization: DF.Link
		schedule: DF.Link | None
		timezone: DF.Data
	# end: auto-generated types

	pass
