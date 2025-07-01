frappe.views.calendar['QMS Ticket'] = {
    field_map: {
        start: 'call_time ',
        end: 'completion_time',
        id: 'name',
        title: 'ticket_number',
        status: 'status',
        color: 'color',
    },
    gantt: { // The values set here will override the values set in the object just for Gantt View
        order_by: 'issue_time',
    },
    order_by: 'issue_time',
    get_events_method: 'qms_cherga.api.get_ticket_events',
}
