app_name = "cyte_billing"
app_title = "Cyte Billing"
app_publisher = "CyteERP"
app_description = "Billing Automation & Customer Portal - Clone Frappe Cloud billing"
app_version = "1.0.0"

scheduler_events = {
    "cron": {
        "0 2 * * *": ["cyte_billing.billing_engine.process_subscriptions"],
        "0 8 * * *": ["cyte_billing.dunning.process_overdue"]
    }
}

website_route_rules = [
    {"from_route": "/billing", "to_route": "billing"},
    {"from_route": "/billing/<path:app_path>", "to_route": "billing"},
]

doc_events = {
    "Sales Invoice": {
        "on_submit": "cyte_billing.zimra.fdms.enqueue_fiscalisation"
    }
}
