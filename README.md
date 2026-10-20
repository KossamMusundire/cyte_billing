# Cyte Billing

Cyte Billing is a Frappe application for subscription billing automation on an ERPNext site. It provides the app package, scheduler hooks, billing and dunning jobs, a `/billing` website page, a customer data API, and integration entry points for ClicknPay and ZIMRA FDMS.

## Requirements

- A compatible Frappe and ERPNext bench (Frappe v14 or later).
- ERPNext doctypes used by the app, including Customer, Subscription, Subscription Plan, Sales Invoice, Payment Request, and Payment Entry.
- A configured company, accounts, sales items, payment gateway, and email account.

The app does not install or configure ERPNext, gateway credentials, ZIMRA certificates, customer portal users, or the custom fields and doctypes described below.

## Install on a bench

From the bench directory, fetch this repository and install it on the target site:

```sh
bench get-app cyte_billing <repository-url>
bench --site <site-name> install-app cyte_billing
bench --site <site-name> migrate
```

Enable scheduler workers for subscription billing (02:00) and overdue reminders (08:00), then restart the bench processes. Configure the `ClicknPay` gateway and `ClicknPay - USD - CSPL` gateway account used by the billing jobs. Review `cyte_billing/hooks.py` before enabling production schedules.

## Features in this package

- Daily subscription invoice generation, payment request creation, and customer email.
- Daily overdue invoice processing and Day 1, 3, and 7 reminder emails.
- Customer billing page at `/billing` and a whitelisted `get_billing_data` API.
- Sales Invoice submit hook that queues ZIMRA FDMS fiscalisation.
- ClicknPay callback endpoint at `/api/method/cyte_billing.clicknpay.webhook.webhook`.
- Billing log helper and website route rules.

The customer portal expects the signed-in user's Customer link (or Contact-to-Customer Dynamic Link) to be configured. `get_billing_data` filters records by that linked customer.

## ERPNext site configuration

Before using the automation, configure the site to match the billing specification:

1. Create the hosting service item and its sales price, and configure Subscription Plans and Subscriptions with a customer, plan, quantity, and billing dates.
2. Add the Sales Invoice custom fields `custom_fiscal_code`, `custom_qr_code`, `custom_fiscal_status`, `custom_site_reference`, and `custom_billing_period`.
3. Add Customer fields `custom_portal_user` (Link to User) and `custom_billing_email`.
4. Add Subscription Plan fields `custom_site_type` and `custom_resources_json` if those fields are used by your workflow.
5. Create the Billing Log, ZIMRA FDMS Settings (Single), and ZIMRA Failure Log doctypes with the fields in the specification. Set role permissions and protect credentials.
6. Configure the ClicknPay webhook secret and payment-status lookup integration. Configure ZIMRA endpoint, device, certificate/private key, and the payload/signing details required for your FDMS environment.
7. Add a fiscal invoice print format that includes the fiscal code and QR code, and verify email templates and PDF downloads.

Do not use the example account, invoice, payment URL, or credentials from the specification as live configuration.

## Project layout

`cyte_billing/` is the importable Frappe app module. `pyproject.toml` defines Python build and project metadata; `setup.py` keeps bench-era setuptools installation compatible. `modules.txt` registers the Cyte Billing module in Frappe.

## Implementation notes

This repository contains the integration and automation entry points, not a complete declarative site setup. Custom DocType JSON, role permissions, fixtures, a full multi-tab portal, payment reconciliation hardening, and ZIMRA signing/offline queue behavior need to be completed and validated for the target Frappe/ERPNext version and provider configuration. In particular, the ClicknPay callback currently imports `clicknpay_integration.api.check_status`; that provider module must be installed and configured for callback processing to work. Protect the callback with the provider's real signature verification and keep secrets out of source control.

## License

Set the license here to match the terms under which this project is distributed.
