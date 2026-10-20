import frappe, requests, json

def get_settings():
    return frappe.get_single("ZIMRA FDMS Settings")

def enqueue_fiscalisation(invoice_name=None):
    if not invoice_name:
        invoice_name = frappe.form_dict.get("invoice_name")
    frappe.enqueue("cyte_billing.zimra.fdms.fiscalise_invoice", queue="long", job_name=f"zimra-{invoice_name}", invoice_name=invoice_name)

def fiscalise_invoice(invoice_name):
    try:
        settings = get_settings()
        if not settings.enabled:
            return
        si = frappe.get_doc("Sales Invoice", invoice_name)
        if si.custom_fiscal_status == "Fiscalised":
            return
        
        payload = {
            "deviceID": settings.device_id,
            "invoiceNo": si.name,
            "invoiceDate": str(si.posting_date),
            "items": [{"itemCode": i.item_code, "qty": float(i.qty), "price": float(i.rate), "total": float(i.amount)} for i in si.items],
            "total": float(si.grand_total)
        }
        
        resp = requests.post(f"{settings.fdms_url}/SubmitReceipt", json=payload, timeout=30)
        result = resp.json()
        
        if resp.status_code == 200 and result.get("fiscalCode"):
            frappe.db.set_value("Sales Invoice", invoice_name, {
                "custom_fiscal_code": result.get("fiscalCode"),
                "custom_qr_code": result.get("qrCode") or result.get("qr"),
                "custom_fiscal_status": "Fiscalised"
            })
            frappe.db.commit()
        else:
            raise Exception(f"FDMS failed: {result}")
            
    except Exception as e:
        try:
            fail = frappe.new_doc("ZIMRA Failure Log")
            fail.invoice = invoice_name
            fail.response = str(e)[:1000]
            fail.retry_count = (frappe.db.get_value("ZIMRA Failure Log", {"invoice": invoice_name}, "retry_count") or 0) + 1
            fail.insert(ignore_permissions=True)
            frappe.db.commit()
            if fail.retry_count < 3:
                frappe.enqueue("cyte_billing.zimra.fdms.fiscalise_invoice", queue="long", invoice_name=invoice_name, job_name=f"zimra-retry-{invoice_name}")
            frappe.db.set_value("Sales Invoice", invoice_name, "custom_fiscal_status", "Failed")
        except:
            frappe.log_error(frappe.get_traceback(), f"ZIMRA failed {invoice_name}")
