// Compatibility for an older service worker that injects content.js and then
// sends S2VQA_DETECT_PAGE. The current service worker uses executeScript(func).
chrome.runtime.onMessage.addListener((message,_sender,sendResponse)=>{
  if(message?.type!=='S2VQA_DETECT_PAGE')return;
  const text=`${location.pathname} ${document.title} ${document.body?.innerText?.slice(0,12000)??''}`;
  const clipId=text.match(/\bCLIP[-_ ]?\d{2,}\b/i)?.[0]?.replace(/[ _]/g,'-')??null;
  const videos=Array.from(document.querySelectorAll('video'));
  const sources=videos.map(v=>v.currentSrc||v.querySelector('source')?.src||'').filter(Boolean);
  const source=sources[0]??'';
  const kind=source.startsWith('blob:')?'blob':source.startsWith('mediasource:')?'media-source':/^https?:/i.test(source)?'http':'none';
  const url=new URL(location.href);const yt=/^(www\.|m\.)?youtube\.com$/i.test(url.hostname)||url.hostname==='youtu.be';
  const youtubeVideoId=yt?(url.hostname==='youtu.be'?url.pathname.split('/')[1]:url.searchParams.get('v')||url.pathname.match(/^\/(?:shorts|embed|live)\/([^/?]+)/)?.[1]||null):null;
  const video=videos[0]?{readyState:videos[0].readyState,duration:Number.isFinite(videos[0].duration)?videos[0].duration:null,width:videos[0].videoWidth,height:videos[0].videoHeight,currentTime:videos[0].currentTime,paused:videos[0].paused,error:videos[0].error?.code??null}:null;
  sendResponse({hostname:location.hostname,pageTitle:document.title,clipId,youtubeVideoId,videoCount:videos.length,videoAvailable:videos.some(v=>v.readyState>=1)||sources.length>0,videoKind:kind,video,note:'Compatibility content detector.'});
  return true;
});
