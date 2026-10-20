import frappe
from frappe import _

@frappe.whitelist()
def get_billing_data(tab="invoices"):
    """FR4: Secure portal API - enforces customer = self"""
    user = frappe.session.user
    if user == "Guest":
        frappe.throw(_("Not permitted"), frappe.PermissionError)

    customer = frappe.db.get_value("Customer", {"custom_portal_user": user}, "name")
    if not customer:
        contact = frappe.db.get_value("Contact", {"user": user}, "name")
        if contact:
            customer = frappe.db.get_value("Dynamic Link", {"parent": contact, "parenttype": "Contact", "link_doctype": "Customer"}, "link_name")
    if not customer:
        frappe.throw(_("No customer linked to this user"))

    data = {"customer": customer}

    if tab == "subscriptions":
        subs = frappe.get_all("Subscription", filters={"party_type": "Customer", "party": customer}, fields=["name","status","current_invoice_start","current_invoice_end","total_months"])
        for s in subs:
            s["plans"] = frappe.get_all("Subscription Plan Detail", filters={"parent": s.name}, fields=["plan","qty"])
        data["subscriptions"] = subs
        data["sites_count"] = len(subs)

    elif tab == "invoices":
        invoices = frappe.get_all("Sales Invoice", 
            filters={"customer": customer, "docstatus": 1},
            fields=["name","posting_date","due_date","grand_total","outstanding_amount","status","custom_fiscal_status","custom_site_reference","custom_billing_period"],
            order_by="posting_date desc",
            limit_page_length=20
        )
        for inv in invoices:
            pr = frappe.db.get_value("Payment Request", {"reference_doctype": "Sales Invoice", "reference_name": inv.name, "docstatus": 1}, ["name","status","payment_url"], as_dict=True)
            inv["payment_request"] = pr
            # Status pill
            if inv.outstanding_amount == 0:
                inv["status_pill"] = {"label": "Paid", "color": "green"}
            elif frappe.utils.getdate(inv.due_date) < frappe.utils.getdate():
                inv["status_pill"] = {"label": "Overdue", "color": "red"}
            elif pr:
                inv["status_pill"] = {"label": "Requested", "color": "orange"}
            else:
                inv["status_pill"] = {"label": "Draft", "color": "grey"}
        data["invoices"] = invoices

    elif tab == "balances":
        total_outstanding = frappe.db.sql("select sum(outstanding_amount) from `tabSales Invoice` where customer=%s and docstatus=1 and outstanding_amount>0", (customer,))[0][0] or 0
        data["total_outstanding"] = total_outstanding

    return data
