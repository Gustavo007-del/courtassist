// Pure scheduling decisions, shared by native integration and deterministic tests.
export const notificationPrefix='court-assist-notification-';
export type Plan={id:string;title:string;message:string;scheduled_at:string};
export function planActions(active:string[],plans:Plan[],scheduled:{identifier:string;at?:string}[],now:number){
 const valid=new Set(active.map(id=>notificationPrefix+id));
 const cancel=scheduled.filter(row=>row.identifier.startsWith('court-assist-')&&!valid.has(row.identifier)).map(row=>row.identifier);
 const schedule=plans.filter(row=>new Date(row.scheduled_at).getTime()>now).slice(0,50).filter(row=>{
  const existing=scheduled.find(item=>item.identifier===notificationPrefix+row.id);
  if(existing?.at===row.scheduled_at)return false;
  if(existing)cancel.push(existing.identifier);
  return true;
 });
 return {cancel,schedule};
}
