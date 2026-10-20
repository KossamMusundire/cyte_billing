import frappe
from frappe.utils import today, add_months, getdate, now_datetime

TEMPLATE_PR = {
    "payment_gateway": "ClicknPay",
    "payment_gateway_account": "ClicknPay - USD - CSPL",
}

def log_billing(subscription=None, invoice=None, payment_request=None, status="Success", error=None):
    try:
        doc = frappe.new_doc("Billing Log")
        doc.datetime = now_datetime()
        doc.subscription = subscription
        doc.invoice = invoice
        doc.payment_request = payment_request
        doc.status = status
        doc.error = error
        doc.insert(ignore_permissions=True)
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Billing Log failed")

def process_subscriptions():
    """FR2: Daily 02:00 - Subscription due -> Invoice -> PR -> Email"""
    frappe.set_user("Administrator")
    today_date = getdate(today())
    
    subscriptions = frappe.get_all("Subscription", 
        filters={"status": "Active", "current_invoice_end": ["<=", today_date]},
        fields=["name","party"]
    )
    
    for sub in subscriptions:
        try:
            sub_doc = frappe.get_doc("Subscription", sub.name)
            plan_detail = sub_doc.plans[0] if sub_doc.plans else None
            if not plan_detail:
                continue
                
            plan = frappe.get_doc("Subscription Plan", plan_detail.plan)
            item_code = plan.item
            
            si = frappe.new_doc("Sales Invoice")
            si.customer = sub_doc.party
            si.due_date = today()
            si.custom_site_reference = getattr(sub_doc, "custom_site_reference", "") or f"{sub_doc.party.lower().replace(' ', '')}.cyteerp.cloud"
            si.custom_billing_period = f"{sub_doc.current_invoice_end} - {add_months(sub_doc.current_invoice_end, 1)}"
            
            si.append("items", {
                "item_code": item_code,
                "qty": plan_detail.qty or 1,
                "rate": plan.cost,
                "cost_center": plan.cost_center or "Main - CSPL",
                "description": f"{plan.name} - {si.custom_billing_period}"
            })
            
            si.insert(ignore_permissions=True)
            si.submit()
            
            # FR6 - ZIMRA
            frappe.enqueue("cyte_billing.zimra.fdms.enqueue_fiscalisation", queue="long", job_name=f"zimra-{si.name}", invoice_name=si.name)
            
            # FR2 - Create PR using validated template ACC-PRQ-2026-00014
            pr = frappe.new_doc("Payment Request")
            pr.payment_gateway = TEMPLATE_PR["payment_gateway"]
            pr.payment_gateway_account = TEMPLATE_PR["payment_gateway_account"]
            pr.reference_doctype = "Sales Invoice"
            pr.reference_name = si.name
            pr.grand_total = si.grand_total
            pr.outstanding_amount = si.grand_total
            pr.currency = si.currency or "USD"
            pr.is_a_subscription = 1
            pr.append("subscription_plans", {"plan": plan_detail.plan, "qty": plan_detail.qty or 1})
            pr.email_to = frappe.db.get_value("Customer", si.customer, "email_id") or frappe.db.get_value("Customer", si.customer, "custom_billing_email")
            pr.mute_email = 0
            
            pr.insert(ignore_permissions=True)
            pr.submit()
            
            # Update subscription
            sub_doc.current_invoice_start = sub_doc.current_invoice_end
            sub_doc.current_invoice_end = add_months(sub_doc.current_invoice_end, 1)
            sub_doc.save(ignore_permissions=True)
            
            # Email
            send_invoice_email(si, pr)
            
            log_billing(subscription=sub.name, invoice=si.name, payment_request=pr.name, status="Success")
            frappe.db.commit()
            
        except Exception as e:
            err = frappe.get_traceback()
            log_billing(subscription=sub.name, status="Failed", error=err)
            frappe.log_error(title=f"Billing failed {sub.name}", message=err)

def send_invoice_email(si, pr):
    try:
        subject = f"Invoice {si.name} - ${si.grand_total} due"
        body = f"""<p>Hi,</p><p>Your hosting invoice <b>{si.name}</b> for {si.custom_billing_period} is ready.</p><p>Total: ${si.grand_total} USD</p><p><a href="{pr.payment_url}" style="background:#4F46E5;color:white;padding:12px 24px;border-radius:6px;text-decoration:none;">Pay Now</a></p><p>Or log into https://cyteerp.frappe.cloud/billing/invoices</p>"""
        frappe.sendmail(recipients=pr.email_to, subject=subject, message=body, reference_doctype=si.doctype, reference_name=si.name)
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Invoice email failed")
