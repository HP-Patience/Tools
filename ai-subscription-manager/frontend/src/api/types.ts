export type Contact = { kind: string; value: string };
export type Customer = {
  id: number;
  name: string;
  contacts: Contact[];
  notes: string;
  archived_at: string | null;
};
export type Supplier = {
  id: number;
  name: string;
  url: string;
  contact_name: string;
  contact_details: string;
  notes: string;
  is_active: boolean;
};
export type Product = {
  id: number;
  name: string;
  supplier_id: number;
  supplier_name?: string;
  platform: string;
  plan: string;
  delivery: string;
  source_name: string;
  source_url: string;
  tags: string[];
  cost_fen: number;
  price_fen: number;
  quoted_on: string | null;
  term_count: number | null;
  term_unit: string | null;
  quota_amount: string | null;
  quota_unit: string | null;
  warranty_notes: string;
  is_active: boolean;
};
export type Service = {
  id: number;
  customer_id: number;
  product_id: number;
  customer_name: string;
  product_name: string;
  supplier_name: string;
  contacts: Contact[];
  identifier: string;
  started_on: string;
  expires_on: string | null;
  quota_unit: string | null;
  purchased_quota: string;
  notes: string;
  ended_at: string | null;
  revision: number;
  status: string;
};
export type Sale = {
  id: number;
  customer_id: number;
  service_id: number;
  product_id: number;
  kind: string;
  sold_on: string;
  cost_fen: number;
  price_fen: number;
  voided_at: string | null;
  void_reason: string;
  snapshot: {
    customer_name: string;
    product_name: string;
    supplier_name: string;
    delivery: string;
    expires_on: string | null;
    warranty_notes: string;
    correction_history?: unknown[];
  };
  before_state: Record<string, unknown>;
  after_state: Record<string, unknown>;
};
export type Page<T> = {
  count: number;
  next: number | null;
  previous: number | null;
  results: T[];
};
export type Dashboard = {
  month: string;
  totals: { revenue_fen: number; cost_fen: number; profit_fen: number };
  sale_count: number;
  customer_count: number;
  service_count: number;
  due: Service[];
  recent_sales: Sale[];
};
export type MailSettings = {
  recipient: string;
  mail_ready: boolean;
  schedule: string;
  timezone: string;
  last_run: { started_at: string; status: string } | null;
};
export type MailBatch = {
  id: string;
  recipient: string;
  status: string;
  attempts_total: number;
  error_code: string;
  created_at: string;
  sent_at: string | null;
};
export type Run = {
  id: number;
  started_at: string;
  status: string;
  counts: Record<string, number>;
  error_code: string;
};
