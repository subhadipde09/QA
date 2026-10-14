export type Detection = {hostname:string;pageTitle:string;clipId:string|null;youtubeVideoId:string|null;videoCount:number;videoAvailable:boolean;videoKind:'http'|'blob'|'media-source'|'none';video:{readyState:number;duration:number|null;width:number;height:number;currentTime:number;paused:boolean;error:number|null}|null;note:string};

// This self-contained function is injected only after the user opens the popup
// (activeTab permission), so it reads the current page without a persistent
// content script or an all-sites host permission.
export function readPageContext():Detection {
  const text=`${location.pathname} ${document.title} ${document.body?.innerText?.slice(0,12000)??''} ${Array.from(document.querySelectorAll('a[href]')).map(a=>(a as HTMLAnchorElement).pathname).join(' ')}`;
  const found=text.match(/\bCLIP[-_ ]?\d{2,}\b/i)?.[0]?.replace(/[ _]/g,'-')??null;
  const videos=Array.from(document.querySelectorAll('video'));
  const sources=videos.map(v=>v.currentSrc||v.querySelector('source')?.src||'').filter(Boolean);
  const source=sources[0]??'';
  const kind:Detection['videoKind']=source.startsWith('blob:')?'blob':source.startsWith('mediasource:')?'media-source':/^https?:/i.test(source)?'http':'none';
  const parsed=new URL(location.href);const yt=/^(www\.|m\.)?youtube\.com$/i.test(parsed.hostname)||parsed.hostname==='youtu.be';
  const youtubeVideoId=yt?(parsed.hostname==='youtu.be'?parsed.pathname.split('/')[1]:parsed.searchParams.get('v')||parsed.pathname.match(/^\/(?:shorts|embed|live)\/([^/?]+)/)?.[1]||null):null;
  const current=videos.filter(v=>v.readyState>0).sort((a,b)=>b.videoWidth*b.videoHeight-a.videoWidth*a.videoHeight)[0]||videos[0];
  const video=current?{readyState:current.readyState,duration:Number.isFinite(current.duration)?current.duration:null,width:current.videoWidth,height:current.videoHeight,currentTime:current.currentTime,paused:current.paused,error:current.error?.code??null}:null;
  return {hostname:location.hostname,pageTitle:document.title,clipId:found,youtubeVideoId,videoCount:videos.length,videoAvailable:videos.some(v=>v.readyState>=1)||sources.length>0,videoKind:kind,video,note:kind==='blob'||kind==='media-source'?'Player uses a browser-only media source. Browser metadata can be inspected, but the local service cannot download or decode its stream.':sources.length?'A video element is present; its URL is intentionally not shared with the local backend.':'No accessible video source was detected.'};
}
