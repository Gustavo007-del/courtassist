import { apiRequest } from './api';
export type Draft={id:string;title:string;content:string;status:string;updated_at:string};
export type Research={id:string;title:string;item_type:string;citation:string;summary:string;source_status:string};
export type FinanceSummary={agreed_fees:string;received:string;outstanding:string;expenses:string;net_cash_flow:string};
export const phase10Api={
 drafts:()=>apiRequest<Draft[]>('/draft-documents'), createDraft:(body:{title:string;content:string})=>apiRequest<Draft>('/draft-documents',{method:'POST',body:JSON.stringify(body)}), saveDraft:(id:string,body:Partial<Draft>)=>apiRequest<Draft>(`/draft-documents/${id}`,{method:'PATCH',body:JSON.stringify(body)}),
 research:(q='')=>apiRequest<{items:Research[]}>(`/research-items${q?`?q=${encodeURIComponent(q)}`:''}`).then(page=>page.items), createResearch:(body:Partial<Research>&{title:string})=>apiRequest<Research>('/research-items',{method:'POST',body:JSON.stringify(body)}),
 finance:()=>apiRequest<FinanceSummary>('/finance/summary'), payments:()=>apiRequest<Record<string,unknown>[]>('/payments'), expenses:()=>apiRequest<Record<string,unknown>[]>('/expenses'), agreements:()=>apiRequest<Record<string,unknown>[]>('/fee-agreements')
};
