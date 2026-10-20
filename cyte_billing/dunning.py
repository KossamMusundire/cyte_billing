import frappe
from frappe.utils import today, getdate
from .billing_engine import log_billing, TEMPLATE_PR

def process_overdue():
    """FR3: Daily 08:00 - Outstanding & Dunning Day1, Day3, Day7"""
    frappe.set_user("Administrator")
    overdue_invoices = frappe.get_all("Sales Invoice", 
        filters={"docstatus": 1, "outstanding_amount": [">", 0], "due_date": ["<", getdate(today())]},
        fields=["name","customer","due_date","grand_total"]
    )
    
    for inv in overdue_invoices:
        days_overdue = (getdate(today()) - getdate(inv.due_date)).days
        pr_exists = frappe.db.exists("Payment Request", {"reference_name": inv.name, "docstatus": 1, "status": "Requested"})
        if not pr_exists:
            create_new_pr_for_overdue(inv.name)
        if days_overdue in (1,3,7):
            send_dunning_email(inv, days_overdue)

def create_new_pr_for_overdue(invoice_name):
    try:
        si = frappe.get_doc("Sales Invoice", invoice_name)
        pr = frappe.new_doc("Payment Request")
        pr.payment_gateway = TEMPLATE_PR["payment_gateway"]
        pr.payment_gateway_account = TEMPLATE_PR["payment_gateway_account"]
        pr.reference_doctype = "Sales Invoice"
        pr.reference_name = si.name
        pr.grand_total = si.grand_total
        pr.outstanding_amount = si.outstanding_amount
        pr.currency = si.currency
        pr.is_a_subscription = 1
        pr.email_to = frappe.db.get_value("Customer", si.customer, "email_id")
        pr.insert(ignore_permissions=True)
        pr.submit()
        log_billing(invoice=si.name, payment_request=pr.name, status=f"Dunning PR")
        frappe.db.commit()
    except Exception:
        frappe.log_error(frappe.get_traceback(), f"Dunning PR failed {invoice_name}")

def send_dunning_email(inv, days):
    try:
        customer_email = frappe.db.get_value("Customer", inv.customer, "email_id")
        pr = frappe.db.get_value("Payment Request", {"reference_name": inv.name, "docstatus": 1}, "payment_url")
        subject = f"Reminder: Invoice {inv.name} overdue by {days} days"
        body = f"<p>Invoice {inv.name} ${inv.grand_total} overdue {days} days. <a href='{pr}'>Pay Now</a></p>"
        frappe.sendmail(recipients=customer_email, subject=subject, message=body, mute_email=1)
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Dunning email failed")
