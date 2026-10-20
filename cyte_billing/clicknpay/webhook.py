import frappe
import hmac, hashlib
from frappe.utils import today, get_url

SUCCESS_STATUSES = ("SUCCESS","PAID","COMPLETED","APPROVED","TOP-PAID")

def get_secret():
    try:
        s = frappe.db.get_single_value("ClicknPay Settings", "webhook_secret") or frappe.conf.get("clicknpay_webhook_secret") or "change-me"
        return s
    except:
        return frappe.conf.get("clicknpay_webhook_secret") or "change-me"

def verify_signature():
    expected = get_secret()
    if expected == "change-me":
        return
    provided = frappe.form_dict.get("secret") or frappe.get_request_header("X-ClicknPay-Signature") or ""
    ref = frappe.form_dict.get("clientReference") or ""
    calc = hmac.new(expected.encode(), ref.encode(), hashlib.sha256).hexdigest()
    if not (hmac.compare_digest(provided, expected) or hmac.compare_digest(provided, calc)):
        frappe.throw("Invalid signature", frappe.PermissionError)

@frappe.whitelist(allow_guest=True)
def webhook():
    """FR5: /api/method/cyte_billing.clicknpay.webhook - Secure callback"""
    verify_signature()
    
    client_ref = (frappe.form_dict.get("clientReference") or "UNKNOWN").strip()
    sinv_ref = client_ref.split("-ACC-PRQ-")[0] if "-ACC-PRQ-" in client_ref else client_ref
    
    if frappe.db.exists("Payment Request", client_ref):
        sinv_ref = frappe.db.get_value("Payment Request", client_ref, "reference_name") or sinv_ref
    
    from clicknpay_integration.api import check_status
    detail = check_status(client_ref)
    real_status = (detail.get("status") or detail.get("paymentStatus") or "UNKNOWN").upper() if isinstance(detail, dict) else "UNKNOWN"
    
    if real_status not in SUCCESS_STATUSES:
        frappe.local.response["type"] = "redirect"
        frappe.local.response["location"] = f"{get_url()}/billing/invoices?status={real_status}"
        return
    
    if frappe.db.exists("Sales Invoice", sinv_ref):
        inv = frappe.get_doc("Sales Invoice", sinv_ref)
        gw_amount = float(detail.get("amount") or detail.get("total") or 0)
        if gw_amount and abs(gw_amount - float(inv.outstanding_amount)) > 0.02 and abs(gw_amount - float(inv.grand_total)) > 0.02:
            frappe.log_error(title=f"Amount mismatch {client_ref}", message=f"gw={gw_amount} inv={inv.outstanding_amount}")
            frappe.local.response["type"] = "redirect"
            frappe.local.response["location"] = f"{get_url()}/billing/invoices?status=AMOUNT_MISMATCH"
            return
        
        if inv.docstatus == 1 and inv.outstanding_amount > 0:
            if not frappe.db.exists("Payment Entry", {"reference_no": client_ref, "docstatus": ["<", 2]}):
                paid_to = frappe.db.get_value("Mode of Payment Account", {"parent": "ClicknPay", "company": inv.company}, "default_account") or frappe.db.get_value("Company", inv.company, "default_bank_account")
                pe = frappe.new_doc("Payment Entry")
                pe.company = inv.company
                pe.payment_type = "Receive"
                pe.party_type = "Customer"
                pe.party = inv.customer
                pe.paid_from = inv.debit_to
                pe.paid_to = paid_to
                pe.mode_of_payment = "ClicknPay"
                pe.posting_date = today()
                pe.paid_amount = inv.outstanding_amount
                pe.received_amount = inv.outstanding_amount
                pe.reference_no = client_ref
                pe.reference_date = today()
                pe.append("references", {"reference_doctype": "Sales Invoice", "reference_name": sinv_ref, "allocated_amount": inv.outstanding_amount})
                pe.insert(ignore_permissions=True)
                pe.submit()
                frappe.db.commit()
        
        pr_name = frappe.db.get_value("Payment Request", {"reference_name": sinv_ref, "docstatus": 1}, "name")
        if pr_name:
            frappe.db.set_value("Payment Request", pr_name, "status", "Paid")
        
        try:
            bl = frappe.new_doc("Billing Log")
            bl.datetime = frappe.utils.now_datetime()
            bl.invoice = sinv_ref
            bl.payment_request = client_ref
            bl.status = "Paid"
            bl.insert(ignore_permissions=True)
        except:
            pass
    
    frappe.local.response["type"] = "redirect"
    frappe.local.response["location"] = f"{get_url()}/billing/invoices?status=Paid&invoice={sinv_ref}"
