export const CURRENCIES = ["EUR", "USD", "GBP", "CHF"];

export const CATEGORIES = [
  "MANAGEMENT_FEE",
  "BANK_FEE",
  "PROFESSIONAL_SERVICES",
  "SUBSCRIPTION",
  "SOFTWARE",
  "AUDIT",
  "INTEREST_PAYMENT",
  "EXPENSE_REIMBURSEMENT",
  "REGULATORY_FEE",
  "REDEMPTION",
  "CORPORATE_SERVICES",
  "FX_ADJUSTMENT",
  "INSURANCE",
  "ADMINISTRATION_FEE",
  "OTHER",
];

export const PAYMENT_METHODS = ["BANK_TRANSFER", "DIRECT_DEBIT", "CARD", "INTERNAL"];

export const EDITABLE_FIELDS = [
  { key: "reference", label: "Reference", type: "text" },
  { key: "transaction_date", label: "Transaction date", type: "date" },
  { key: "value_date", label: "Value date", type: "date" },
  { key: "description", label: "Description", type: "text", full: true },
  { key: "gross_amount", label: "Gross amount", type: "text" },
  { key: "fee_amount", label: "Fee amount", type: "text" },
  { key: "tax_amount", label: "Tax amount", type: "text" },
  { key: "net_amount", label: "Net amount", type: "text" },
  { key: "currency", label: "Currency", type: "select", options: CURRENCIES },
  { key: "counterparty_name", label: "Counterparty name", type: "text", full: true },
  { key: "counterparty_account", label: "Counterparty account", type: "text", full: true },
  { key: "country", label: "Country (ISO alpha-2)", type: "text" },
  { key: "category", label: "Category", type: "select", options: CATEGORIES },
  { key: "invoice_number", label: "Invoice number", type: "text" },
  { key: "payment_method", label: "Payment method", type: "select", options: PAYMENT_METHODS },
];
