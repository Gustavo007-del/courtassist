import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import ts from 'typescript';
import { planActions, notificationPrefix } from '../src/services/notification-plan.ts';

test('stable local identifiers prevent duplicates and update changed times',()=>{
 const row={id:'one',title:'Court Assist',message:'A task reminder is due.',scheduled_at:'2030-01-01T10:00:00Z'};
 assert.deepEqual(planActions(['one'],[row],[{identifier:notificationPrefix+'one',at:row.scheduled_at}],0),{cancel:[],schedule:[]});
 const result=planActions(['one'],[row],[{identifier:notificationPrefix+'one',at:'2029-01-01'},{identifier:'court-assist-hearing-old'},{identifier:notificationPrefix+'deleted'}],0);
 assert.deepEqual(new Set(result.cancel),new Set([notificationPrefix+'one','court-assist-hearing-old',notificationPrefix+'deleted']));
 assert.equal(result.schedule.length,1);
});
test('due local reservations remain active and native queue is bounded',()=>{
 assert.deepEqual(planActions(['one'],[],[{identifier:notificationPrefix+'one'}],Date.now()),{cancel:[],schedule:[]});
 const rows=Array.from({length:200},(_,id)=>({id:String(id),scheduled_at:'2030-01-01T10:00:00Z'}));
 assert.equal(planActions(rows.map(r=>r.id),rows,[],0).schedule.length,50);
 assert.equal(planActions(['old'],[{id:'old',scheduled_at:'2000-01-01'}],[],Date.now()).schedule.length,0);
});

// Execute the actual native adapter against SDK-shaped mocks. This covers behavior,
// including declined permission, rather than matching strings in implementation.
async function managerFixture(){
 let permitted=false,requests=0,settings=0,scheduled=[],acknowledged=[],unregistered=0;
 const secure=new Map();let owner='advocate-one';let config={preferences:{push_notifications:false},capabilities:{push_configured:false}};
 let plan={active_ids:['one'],plans:[{id:'one',title:'Court Assist',message:'A task reminder is due.',scheduled_at:new Date(Date.now()+600000).toISOString()}]};
 let rejectRegistration=false;
 class ApiError extends Error{constructor(status){super();this.status=status;}}
 const notifications={setNotificationChannelAsync:async channel=>assert.equal(channel,'court-assist-reminders'),getPermissionsAsync:async()=>({granted:permitted}),requestPermissionsAsync:async()=>{requests++;return {granted:permitted};},getAllScheduledNotificationsAsync:async()=>scheduled,cancelScheduledNotificationAsync:async id=>{scheduled=scheduled.filter(r=>r.identifier!==id);},dismissAllNotificationsAsync:async()=>{},unregisterForNotificationsAsync:async()=>{unregistered++;},getDevicePushTokenAsync:async()=>({data:'native-fcm-token'}),SchedulableTriggerInputTypes:{DATE:'date'},scheduleNotificationAsync:async item=>{scheduled.push(item);}};
 const api={preferences:async()=>config,register:async()=>{if(rejectRegistration)throw new ApiError(409);return {id:'device-one'};},localPlan:async(_id,allowed)=>allowed?plan:{active_ids:[],plans:[]},ack:async(_device,row)=>{acknowledged.push(row);},observed:async()=>{}};
 const source=ts.transpileModule(fs.readFileSync(new URL('../src/services/notification-manager.ts',import.meta.url),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;
 const modules={'./api':{ApiError},'react-native':{Platform:{OS:'android'},Linking:{openSettings:async()=>{settings++;}}},'expo-notifications':notifications,'expo-secure-store':{getItemAsync:async key=>secure.get(key)??null,setItemAsync:async(key,value)=>secure.set(key,value)},'expo-crypto':{randomUUID:()=> 'installation-one'},'./notification-api':{notificationApi:api},'./notification-plan':{notificationPrefix,planActions},'../store/auth-store':{useAuthStore:{getState:()=>({user:owner?{id:owner}:null})}}};
 const exports={};new Function('require','exports',source)(name=>{assert.ok(modules[name],name);return modules[name];},exports);
 return {manager:exports,get state(){return {requests,settings,scheduled,acknowledged,unregistered};},allow:()=>{permitted=true;},revoke:()=>{rejectRegistration=true;},logout:()=>{owner=null;},setPlan:value=>{plan=value;},push:()=>{config={preferences:{push_notifications:true},capabilities:{push_configured:true}};}};
}
test('background synchronization never prompts for permission; denial is not repeatedly prompted',async()=>{
 const f=await managerFixture();await f.manager.syncNotifications();assert.equal(f.state.requests,0);assert.equal(f.state.scheduled.length,0);
 assert.equal(await f.manager.requestNotificationPermission(),false);assert.equal(f.state.requests,1);
 await f.manager.requestNotificationPermission();assert.equal(f.state.requests,1);assert.equal(f.state.settings,1);
 f.allow();assert.equal(await f.manager.requestNotificationPermission(),true);assert.equal(f.state.scheduled.length,1);assert.equal(f.state.acknowledged.length,1);
 await f.manager.syncNotifications();assert.equal(f.state.scheduled.length,1);assert.equal(f.state.acknowledged.length,1);
 assert.deepEqual(Object.keys(f.state.scheduled[0].content.data).sort(),['notification_id','scheduled_at']);
 f.setPlan({active_ids:[],plans:[]});await f.manager.syncNotifications();assert.equal(f.state.scheduled.length,0);
});
test('remote revocation clears local alarms; logout unregisters native tokens',async()=>{
 const f=await managerFixture();f.allow();await f.manager.syncNotifications();assert.equal(f.state.scheduled.length,1);
 f.revoke();await f.manager.syncNotifications();assert.equal(f.state.scheduled.length,0);assert.equal(f.manager.getNotificationDeviceId(),null);
 f.logout();await f.manager.clearNotifications();assert.ok(f.state.unregistered>=1);
});
test('untrusted notification routes and malformed IDs are rejected',async()=>{
 const {manager}=await managerFixture();assert.equal(manager.notificationId({url:'https://attacker.test'}),null);
 assert.equal(manager.notificationId({notification_id:'../private'}),null);
 const id='00000000-0000-4000-8000-000000000001';assert.equal(manager.notificationId({notification_id:id}),id);
 assert.equal(manager.notificationDestination({entity_type:'https://attacker.test',entity_id:id}),null);
 assert.equal(manager.notificationDestination({entity_type:'task',entity_id:id}),'/tasks/'+id);
});
test('English and Malayalam notification strings have matching keys',()=>{
 const en=JSON.parse(fs.readFileSync(new URL('../src/i18n/locales/en.json',import.meta.url),'utf8')).notifications;
 const ml=JSON.parse(fs.readFileSync(new URL('../src/i18n/locales/ml.json',import.meta.url),'utf8')).notifications;
 const keys=obj=>Object.entries(obj).flatMap(([key,value])=>typeof value==='object'?keys(value).map(child=>key+'.'+child):[key]).sort();
 assert.deepEqual(keys(en),keys(ml));
});

