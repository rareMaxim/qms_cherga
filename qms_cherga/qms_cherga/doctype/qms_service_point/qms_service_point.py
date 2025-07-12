# Copyright (c) 2025, Maxym Sysoiev and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class QMSServicePoint(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		assigned_operator: DF.Link | None
		description: DF.SmallText | None
		ip_address: DF.Data | None
		is_active: DF.Check
		office: DF.Link | None
		point_name: DF.Data
	# end: auto-generated types

	pass
