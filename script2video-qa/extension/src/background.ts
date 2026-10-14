import {readPageContext} from './content/detect';
const API = 'http://127.0.0.1:8000';
async function request(path:string, init:RequestInit={}) {
  const response = await fetch(`${API}${path}`, {...init, credentials:'omit', headers:{'Content-Type':'application/json',...(init.headers||{})}});
  const body = await response.json().catch(()=>({detail:`HTTP ${response.status}`}));
  if(!response.ok) throw new Error(typeof body.detail==='string'?body.detail:body.detail?.message||`Backend returned ${response.status}`);
  return body;
}
async function activeTab(){const [tab]=await chrome.tabs.query({active:true,currentWindow:true});if(!tab?.id||!tab.url?.startsWith('http'))throw new Error('Open an HTTP or HTTPS clip page in the active tab first.');return tab;}
function youtubeIdFromUrl(raw:string){try{const u=new URL(raw);const h=u.hostname.toLowerCase();if(!['youtube.com','www.youtube.com','m.youtube.com','youtu.be'].includes(h))return null;const id=h==='youtu.be'?u.pathname.split('/')[1]:u.searchParams.get('v')||u.pathname.match(/^\/(?:shorts|embed|live)\/([^/?]+)/)?.[1];return id&&/^[A-Za-z0-9_-]{11}$/.test(id)?id:null}catch{return null}}
async function detect(){const tab=await activeTab();const [injected]=await chrome.scripting.executeScript({target:{tabId:tab.id!},func:readPageContext});const page=injected.result as any;return {...page,hostname:new URL(tab.url!).hostname,youtubeVideoId:youtubeIdFromUrl(tab.url!)||page.youtubeVideoId};}
chrome.runtime.onMessage.addListener((msg,_sender,sendResponse)=>{
  (async()=>{
    switch(msg?.type){
      case 'PING': return await request('/api/v1/settings');
      case 'DETECT': return await detect();
      case 'START': return await request('/api/v1/tests',{method:'POST',body:JSON.stringify({clip_number:msg.clipNumber,voice_testing:!!msg.voiceTesting})});
      case 'START_YOUTUBE': return await request('/api/v1/tests/youtube',{method:'POST',body:JSON.stringify(msg.payload)});
      case 'STATUS': return await request(`/api/v1/tests/${encodeURIComponent(msg.testId)}`);
      case 'CANCEL': return await request(`/api/v1/tests/${encodeURIComponent(msg.testId)}/cancel`,{method:'POST'});
      case 'HISTORY': return await request('/api/v1/reports');
      case 'REPORT': return await request(`/api/v1/reports/${encodeURIComponent(msg.testId)}`);
      case 'SETTINGS': return await request('/api/v1/settings');
      case 'SET_SETTING': return await request('/api/v1/settings',{method:'PUT',body:JSON.stringify({voice_testing:!!msg.voiceTesting})});
      default: throw new Error('Unknown extension request.');
    }
  })().then(data=>sendResponse({ok:true,data})).catch(error=>sendResponse({ok:false,error:error instanceof Error?error.message:'Request failed'}));
  return true;
});
