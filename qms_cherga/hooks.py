app_name = "qms_cherga"
app_title = "Qms Cherga"
app_publisher = "Maxym Sysoiev"
app_description = "Open-source система керування електронною чергою (QMS) на Frappe. SaaS. Жива черга, запис, кіоск, табло."
app_email = "maks4a@gmail.com"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "qms_cherga",
# 		"logo": "/assets/qms_cherga/logo.png",
# 		"title": "Qms Cherga",
# 		"route": "/qms_cherga",
# 		"has_permission": "qms_cherga.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/qms_cherga/css/qms_cherga.css"
# app_include_js = "/assets/qms_cherga/js/qms_cherga.js"

# include js, css files in header of web template
# web_include_css = "/assets/qms_cherga/css/qms_cherga.css"
# web_include_js = "/assets/qms_cherga/js/qms_cherga.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "qms_cherga/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "qms_cherga/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# automatically load and sync documents of this doctype from downstream apps
# importable_doctypes = [doctype_1]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "qms_cherga.utils.jinja_methods",
# 	"filters": "qms_cherga.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "qms_cherga.install.before_install"
# after_install = "qms_cherga.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "qms_cherga.uninstall.before_uninstall"
# after_uninstall = "qms_cherga.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "qms_cherga.utils.before_app_install"
# after_app_install = "qms_cherga.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "qms_cherga.utils.before_app_uninstall"
# after_app_uninstall = "qms_cherga.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "qms_cherga.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"qms_cherga.tasks.all"
# 	],
# 	"daily": [
# 		"qms_cherga.tasks.daily"
# 	],
# 	"hourly": [
# 		"qms_cherga.tasks.hourly"
# 	],
# 	"weekly": [
# 		"qms_cherga.tasks.weekly"
# 	],
# 	"monthly": [
# 		"qms_cherga.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "qms_cherga.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "qms_cherga.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "qms_cherga.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["qms_cherga.utils.before_request"]
# after_request = ["qms_cherga.utils.after_request"]

# Job Events
# ----------
# before_job = ["qms_cherga.utils.before_job"]
# after_job = ["qms_cherga.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"qms_cherga.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
export_python_type_annotations = True

default_log_clearing_doctypes = {
    "Logging DocType Name": 30  # days to retain logs
}
