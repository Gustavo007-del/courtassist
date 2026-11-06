import { apiRequest } from './api';
export type FinanceKind = 'fee-agreements' | 'payments' | 'expenses' | 'invoices';
export type FinancialRecord = {
  id: string;
  amount?: string;
  total?: string;
  status?: string;
  reference?: string;
  description?: string;
  category?: string;
  method?: string;
  number?: string;
  client_id?: string;
  case_id?: string;
  agreement_id?: string;
  due_date?: string;
  terms?: string;
  lines?: { description: string; quantity: string; unit_price: string }[];
  snapshot?: { advocate: string; client: string; rows: string[][]; total: string };
};
export type FinancialReport = {
  summary: Record<string, string>;
  monthly: { month: string; income: string; expenses: string; net_cash_flow: string }[];
  by_method: Record<string, string>;
  by_category: Record<string, string>;
  by_client: Record<string, Record<string, string>>;
  by_case: Record<string, Record<string, string>>;
  annual: Record<string, Record<string, string>>;
  payments: FinancialRecord[];
  expenses: FinancialRecord[];
};
export const financeApi = {
  list: (kind: FinanceKind, params: Record<string, string> = {}) =>
    apiRequest<FinancialRecord[]>(
      `/${kind}?${new URLSearchParams(Object.entries(params).filter(([, value]) => !!value)).toString()}`,
    ),
  detail: (kind: FinanceKind, id: string) => apiRequest<FinancialRecord>(`/${kind}/${id}`),
  create: (kind: FinanceKind, body: unknown, key?: string) =>
    apiRequest<FinancialRecord>(`/${kind}`, {
      method: 'POST',
      body: JSON.stringify(body),
      headers: key ? { 'Idempotency-Key': key } : {},
    }),
  action: (kind: FinanceKind, id: string, action: string, body?: unknown) =>
    apiRequest(`/${kind}/${id}/${action}`, {
      method: 'POST',
      ...(body ? { body: JSON.stringify(body) } : {}),
    }),
  pdf: (kind: FinanceKind, id: string) =>
    apiRequest<{ url: string }>(`/${kind}/${id}/${kind === 'payments' ? 'receipt' : 'pdf'}`),
  report: (params: Record<string, string>) =>
    apiRequest<FinancialReport>(
      `/finance/reports?${new URLSearchParams(Object.entries(params).filter(([, value]) => !!value)).toString()}`,
    ),
};
