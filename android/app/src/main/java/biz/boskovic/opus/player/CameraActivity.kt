package biz.boskovic.opus.player

import android.annotation.SuppressLint
import android.graphics.Color
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.KeyEvent
import android.view.ViewGroup
import android.webkit.RenderProcessGoneDetail
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.activity.ComponentActivity
import androidx.activity.OnBackPressedCallback
import biz.boskovic.opus.core.Opus
import org.json.JSONObject

/** A television-first wall of every camera DIDA exposes to this OPUS box.
 *
 * The browser receives only OPUS proxy paths. Camera addresses and DIDA's
 * machine credential stay on the servers, while the shared Player cookie keeps
 * this surface within the paired box session. */
class CameraActivity : ComponentActivity() {
    private var web: WebView? = null
    private val keys = Handler(Looper.getMainLooper())
    private var centerDown = false
    private var centerLong = false
    private val centerLongPress = Runnable {
        if (!centerDown) return@Runnable
        triggerCenterLongPress()
    }

    @SuppressLint("SetJavaScriptEnabled", "MissingOnRenderProcessGone")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        web = object : WebView(this) {
            override fun dispatchKeyEvent(event: KeyEvent): Boolean =
                when {
                    handleCenter(event) -> true
                    handleArrow(event) -> true
                    else -> super.dispatchKeyEvent(event)
                }
        }.apply {
            setBackgroundColor(Color.BLACK)
            settings.javaScriptEnabled = true
            settings.domStorageEnabled = false
            webViewClient = object : WebViewClient() {
                override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean =
                    !Opus.ours(request.url)

                override fun onRenderProcessGone(view: WebView, detail: RenderProcessGoneDetail): Boolean {
                    (view.parent as? ViewGroup)?.removeView(view)
                    view.destroy()
                    finish()
                    return true
                }
            }
            loadDataWithBaseURL(Opus.url("/"), page(), "text/html", "utf-8", null)
        }
        setContentView(web, ViewGroup.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            ViewGroup.LayoutParams.MATCH_PARENT,
        ))
        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                val page = web
                if (page == null) {
                    finish()
                    return
                }
                page.evaluateJavascript("window.leaveCameraView && window.leaveCameraView()") { handled ->
                    if (handled != "true") {
                        isEnabled = false
                        onBackPressedDispatcher.onBackPressed()
                    }
                }
            }
        })
    }

    override fun onDestroy() {
        keys.removeCallbacks(centerLongPress)
        web?.apply {
            stopLoading()
            loadUrl("about:blank")
            destroy()
        }
        web = null
        super.onDestroy()
    }

    private fun handleCenter(event: KeyEvent): Boolean {
        if (event.keyCode != KeyEvent.KEYCODE_DPAD_CENTER &&
            event.keyCode != KeyEvent.KEYCODE_ENTER) {
            return false
        }
        if (event.action == KeyEvent.ACTION_DOWN && !centerDown) {
            centerDown = true
            centerLong = false
            keys.postDelayed(centerLongPress, LONG_PRESS_MS)
            if (event.isLongPress || event.repeatCount > 0) triggerCenterLongPress()
        } else if (event.action == KeyEvent.ACTION_DOWN && !centerLong && event.repeatCount > 0) {
            triggerCenterLongPress()
        } else if (event.action == KeyEvent.ACTION_UP) {
            keys.removeCallbacks(centerLongPress)
            if (centerDown && !centerLong) {
                web?.evaluateJavascript("window.pressFocused && window.pressFocused()", null)
            }
            centerDown = false
            centerLong = false
        }
        return true
    }

    private fun triggerCenterLongPress() {
        if (!centerDown || centerLong) return
        keys.removeCallbacks(centerLongPress)
        centerLong = true
        web?.evaluateJavascript("window.longPressFocused && window.longPressFocused()", null)
    }

    /** Some Android TV WebViews consume DPAD arrows for their own scrolling.
     * Forward them explicitly so the wall remains browsable with every Shield
     * remote and gamepad, while the page still owns the actual focus logic. */
    private fun handleArrow(event: KeyEvent): Boolean {
        val direction = when (event.keyCode) {
            KeyEvent.KEYCODE_DPAD_LEFT -> "left"
            KeyEvent.KEYCODE_DPAD_RIGHT -> "right"
            KeyEvent.KEYCODE_DPAD_UP -> "up"
            KeyEvent.KEYCODE_DPAD_DOWN -> "down"
            else -> return false
        }
        if (event.action == KeyEvent.ACTION_DOWN) {
            web?.evaluateJavascript("window.moveFocus && window.moveFocus('$direction')", null)
        }
        return true
    }

    private fun page(): String {
        val empty = JSONObject.quote(getString(R.string.cameras_empty))
        val unavailable = JSONObject.quote(getString(R.string.cameras_unavailable))
        val moveBefore = htmlLabel(getString(R.string.cameras_move_before))
        val moveAfter = htmlLabel(getString(R.string.cameras_move_after))
        val cancel = htmlLabel(getString(R.string.cameras_cancel))
        val orderFailed = JSONObject.quote(getString(R.string.cameras_order_failed))
        val streamFailed = JSONObject.quote(getString(R.string.cameras_stream_failed))
        val codecUnsupported = JSONObject.quote(getString(R.string.cameras_codec_unsupported))
        return """
            <!doctype html>
            <html><head><meta name="viewport" content="width=device-width,initial-scale=1">
            <style>
              *{box-sizing:border-box}html,body{margin:0;width:100%;height:100%;overflow:hidden;background:#071011;color:#eef4f4;font-family:system-ui,sans-serif}
              #grid{width:100%;height:100%;display:flex;flex-flow:row wrap;gap:8px;padding:10px;align-content:stretch}
              .cam{position:relative;display:block;flex:1 1 calc(25% - 8px);margin:0;padding:0;border:2px solid #314043;border-radius:12px;overflow:hidden;background:#181f20;color:inherit;min-width:0;appearance:none;-webkit-appearance:none}
              .cam.featured{flex-basis:calc(50% - 8px)}
              .cam:focus,.cam.selected{outline:0;border-color:#f3b56b!important;box-shadow:inset 0 0 0 4px #f3b56b,0 0 0 3px #39b7b4,0 8px 24px rgba(0,0,0,.78);filter:brightness(1.1);z-index:2}
              .cam img{display:block;width:100%;height:100%;object-fit:cover;background:#101617}
              .cam.off img,img:not([src]){visibility:hidden}
              .name{position:absolute;left:0;right:0;bottom:0;padding:24px 12px 9px;text-align:left;font-size:15px;font-weight:650;background:linear-gradient(transparent,rgba(0,0,0,.82));text-shadow:0 1px 4px #000}
              .site{color:#8fa5aa;font-size:11px;font-weight:500;margin-left:7px}
              #message{position:fixed;inset:0;display:grid;place-items:center;color:#8fa5aa;font-size:22px}
              #solo{position:fixed;inset:0;z-index:10;background:#000}#solo[hidden]{display:none}
              #solo img,#solo video{position:absolute;inset:0;width:100%;height:100%;object-fit:contain;background:transparent}
              #solo video,#solo #stream{opacity:0}#solo.live video,#solo.live #stream{opacity:1}
              #solo .name{padding:40px 24px 18px;font-size:20px}#solo .site{font-size:14px}
              #status{position:absolute;top:18px;left:50%;transform:translateX(-50%);padding:9px 16px;border-radius:10px;background:rgba(0,0,0,.72);color:#f3b56b;font-size:16px}#status:empty{display:none}
              #menu[hidden]{display:none}#menu{position:fixed;inset:0;z-index:20;display:grid;place-items:center;background:rgba(0,0,0,.6)}
              .menu-card{min-width:360px;padding:22px;border:1px solid #496064;border-radius:16px;background:#152022;box-shadow:0 18px 70px #000}
              #menu-title{margin:0 0 14px;font-size:20px}.action{display:block;width:100%;margin:7px 0;padding:13px 16px;border:1px solid #43575a;border-radius:10px;background:#202d2f;color:#eef4f4;text-align:left;font-size:17px}.action:focus{outline:3px solid #39b7b4}.action:disabled{display:none}
            </style></head><body><main id="grid"></main><div id="message"></div>
            <section id="solo" hidden><img id="poster" alt=""><video id="video" muted playsinline></video><img id="stream" alt=""><span class="name" id="solo-name"></span><div id="status"></div></section>
            <div id="menu" hidden><section class="menu-card"><h2 id="menu-title"></h2>
              <button class="action" id="before">$moveBefore</button>
              <button class="action" id="after">$moveAfter</button>
              <button class="action" id="cancel">$cancel</button>
            </section></div>
            <script>
              const grid=document.getElementById('grid'),message=document.getElementById('message'),menu=document.getElementById('menu');
              const before=document.getElementById('before'),after=document.getElementById('after'),cancel=document.getElementById('cancel'),menuTitle=document.getElementById('menu-title');
              const solo=document.getElementById('solo'),poster=document.getElementById('poster'),video=document.getElementById('video'),stream=document.getElementById('stream'),soloName=document.getElementById('solo-name'),status=document.getElementById('status');
              let cameras=[],timer,refreshCursor=0,generation=0,soloIndex=-1,menuIndex=-1,holdTimer=0,suppressClickUntil=0,live=null;
              function base(camera){return '/api/launcher/cameras/'+encodeURIComponent(camera.id)}
              function cards(){return Array.from(grid.querySelectorAll('.cam'))}
              function loadSnapshot(index,cycle){
                const card=cards()[index],camera=cameras[index];if(!card||!camera)return;const img=card.querySelector('img'),probe=new Image();
                probe.onload=()=>{if(cycle!==generation)return;img.src=probe.src;card.classList.remove('off')};
                probe.onerror=()=>{if(cycle===generation&&!img.getAttribute('src'))card.classList.add('off')};probe.src=base(camera)+'/snapshot?w=640&v='+Date.now();
              }
              function startGridUpdates(first){
                clearInterval(timer);const cycle=++generation;
                if(first>=0)loadSnapshot(first,cycle);
                else cameras.forEach((camera,index)=>setTimeout(()=>loadSnapshot(index,cycle),index*350));
                refreshCursor=0;timer=setInterval(()=>{if(soloIndex>=0||!cameras.length)return;loadSnapshot(refreshCursor,cycle);refreshCursor=(refreshCursor+1)%cameras.length},1200);
              }
              function markSelected(card){cards().forEach(item=>item.classList.toggle('selected',item===card))}
              function focusCard(index){const list=cards();if(list[index]){list[index].focus();markSelected(list[index])}}
              function show(items,focusIndex){
                cameras=items;grid.replaceChildren();message.textContent=items.length?'':$empty;
                const units=items.reduce((sum,camera)=>sum+(isFeatured(camera)?2:1),0),rows=Math.max(1,Math.ceil(units/4));
                items.forEach((camera,index)=>{
                  const card=document.createElement('button');card.className='cam';card.type='button';
                  if(isFeatured(camera))card.classList.add('featured');
                  card.style.height='calc((100% - '+((rows-1)*8)+'px) / '+rows+')';card.dataset.index=String(index);
                  const img=document.createElement('img');img.alt='';
                  card.append(img,label(camera));card.onclick=()=>{if(Date.now()<suppressClickUntil)return;enterSolo(index)};
                  card.onfocus=()=>markSelected(card);
                  card.onpointerdown=()=>{clearTimeout(holdTimer);holdTimer=setTimeout(()=>openMenu(index),650)};
                  card.onpointerup=card.onpointercancel=card.onpointerleave=()=>clearTimeout(holdTimer);
                  grid.append(card)
                });
                startGridUpdates(-1);setTimeout(()=>focusCard(Math.max(0,focusIndex||0)),0);
              }
              function label(camera,into){
                const name=into||document.createElement('span');name.className='name';name.textContent=camera.name;
                if(camera.site){const site=document.createElement('span');site.className='site';site.textContent=camera.site;name.append(site)}
                return name;
              }
              function isFeatured(camera){return Number(camera.span&&camera.span.c||1)>1||/\bgate\b/i.test(camera.name||'')}
              // The camera's own H.264/H.265 as fragmented MP4 over one long GET into
              // MediaSource: full resolution with no transcode, the same transport the
              // NVR's web player uses. The live edge is chased so latency cannot pile up.
              function playMp4(camera){
                let closed=false,abort=null,objectUrl=null,retry=0,backoff=1000;
                const onPlaying=()=>{solo.classList.add('live');status.textContent='';backoff=1000};
                video.addEventListener('playing',onPlaying);
                function teardown(){if(abort){abort.abort();abort=null}if(objectUrl){URL.revokeObjectURL(objectUrl);objectUrl=null}}
                function again(){if(closed||retry)return;teardown();status.textContent=$streamFailed;const wait=backoff;backoff=Math.min(backoff*2,30000);retry=setTimeout(()=>{retry=0;start()},wait)}
                async function start(){
                  const ms=new MediaSource(),queue=[];let sb=null,mime=null,seeked=false;
                  objectUrl=URL.createObjectURL(ms);video.src=objectUrl;
                  function edge(){
                    if(!sb||!sb.buffered.length||video.readyState<1)return;const end=sb.buffered.end(sb.buffered.length-1);
                    if(!seeked){seeked=true;video.currentTime=Math.max(end-0.5,sb.buffered.start(0));return}
                    const drift=end-video.currentTime;
                    if(drift>2){video.currentTime=end-0.5;video.playbackRate=1}else if(drift>1.2)video.playbackRate=1.1;else if(video.playbackRate!==1)video.playbackRate=1;
                  }
                  function trim(){if(!sb||sb.updating||!sb.buffered.length)return;const a=sb.buffered.start(0),b=sb.buffered.end(sb.buffered.length-1);if(b-a>10)sb.remove(a,b-5)}
                  function flush(){
                    if(!sb||sb.updating||!queue.length)return;
                    try{sb.appendBuffer(queue[0]);queue.shift()}catch(error){if(error.name==='QuotaExceededError')trim();else{again();return}}
                    edge();
                  }
                  function setup(){
                    if(sb||ms.readyState!=='open'||!mime)return;
                    if(!MediaSource.isTypeSupported(mime)){closed=true;teardown();status.textContent=$codecUnsupported+' ('+mime.replace(/^.*codecs=/,'')+')';return}
                    sb=ms.addSourceBuffer(mime);sb.mode='segments';sb.addEventListener('updateend',()=>{trim();flush()});flush();video.play().catch(()=>{});
                  }
                  ms.addEventListener('sourceopen',setup,{once:true});
                  abort=new AbortController();const signal=abort.signal;
                  try{
                    const response=await fetch(base(camera)+'/mp4',{signal,cache:'no-store'});
                    if(!response.ok||!response.body){again();return}
                    mime=response.headers.get('content-type')||'video/mp4; codecs="avc1.640029"';setup();
                    const reader=response.body.getReader();
                    while(!closed){const {done,value}=await reader.read();if(done){again();return}if(value&&value.length){queue.push(value);flush()}}
                  }catch(error){if(!closed&&error.name!=='AbortError')again()}
                }
                start();
                return{close(){closed=true;clearTimeout(retry);teardown();video.removeEventListener('playing',onPlaying);video.removeAttribute('src');video.load()}};
              }
              function playMjpeg(camera){
                stream.onload=()=>{solo.classList.add('live');status.textContent=''};
                stream.onerror=()=>{solo.classList.remove('live');status.textContent=$streamFailed};
                stream.src=base(camera)+'/mjpeg?v='+Date.now();
                return{close(){stream.onload=stream.onerror=null;stream.removeAttribute('src')}};
              }
              function stopLive(){if(live){live.close();live=null}solo.classList.remove('live');status.textContent=''}
              function enterSolo(index){
                stopLive();soloIndex=index;const camera=cameras[index],tile=cards()[index].querySelector('img');
                const frame=tile.getAttribute('src');if(frame)poster.src=frame;else poster.removeAttribute('src');
                label(camera,soloName);solo.hidden=false;focusCard(index);
                if(camera.live==='mp4')live=playMp4(camera);else if(camera.live==='mjpeg')live=playMjpeg(camera);else status.textContent=$streamFailed;
              }
              function exitSolo(){if(soloIndex<0)return false;const previous=soloIndex;stopLive();soloIndex=-1;solo.hidden=true;startGridUpdates(previous);focusCard(previous);return true}
              function moveSolo(by){if(!cameras.length)return;enterSolo((soloIndex+by+cameras.length)%cameras.length)}
              function nearest(direction){
                const active=document.activeElement,all=cards();if(!active||!all.includes(active)){focusCard(0);return}
                const here=active.getBoundingClientRect(),hx=(here.left+here.right)/2,hy=(here.top+here.bottom)/2;
                let best=null,bestScore=Infinity;
                all.forEach(candidate=>{if(candidate===active)return;const r=candidate.getBoundingClientRect(),x=(r.left+r.right)/2,y=(r.top+r.bottom)/2,dx=x-hx,dy=y-hy;
                  const primary=direction==='left'?-dx:direction==='right'?dx:direction==='up'?-dy:dy;
                  if(primary<=4)return;const secondary=direction==='left'||direction==='right'?Math.abs(dy):Math.abs(dx),score=primary+secondary*2.5;
                  if(score<bestScore){best=candidate;bestScore=score}
                });if(best)best.focus();
              }
              function moveFocus(direction){
                if(!menu.hidden){
                  const actions=[before,after,cancel].filter(button=>!button.disabled);
                  const current=actions.indexOf(document.activeElement),next=actions[(current+1)%actions.length];
                  if(direction==='up'||direction==='left')actions[(current-1+actions.length)%actions.length].focus();
                  else if(direction==='down'||direction==='right')next.focus();
                  return;
                }
                if(soloIndex>=0){if(direction==='left'||direction==='up')moveSolo(-1);else moveSolo(1);return}
                nearest(direction);
              }
              function openMenu(index){
                if(soloIndex>=0)return;suppressClickUntil=Date.now()+800;menuIndex=index;menuTitle.textContent=cameras[index].name;
                before.disabled=index===0;after.disabled=index===cameras.length-1;menu.hidden=false;(before.disabled?after:before).focus();
              }
              function closeMenu(){if(menu.hidden)return false;menu.hidden=true;const index=menuIndex;menuIndex=-1;focusCard(index);return true}
              async function moveCamera(by){
                const from=menuIndex,to=Math.max(0,Math.min(cameras.length-1,from+by));if(from<0||from===to){closeMenu();return}
                const previous=cameras.slice(),next=cameras.slice();next.splice(to,0,next.splice(from,1)[0]);menu.hidden=true;menuIndex=-1;show(next,to);
                try{const response=await fetch('/api/launcher/cameras/order',{method:'PUT',headers:{'content-type':'application/json'},body:JSON.stringify({order:next.map(camera=>camera.id)})});if(!response.ok)throw Error(response.status)}
                catch(error){show(previous,from);message.textContent=$orderFailed;setTimeout(()=>{if(cameras.length)message.textContent=''},2400)}
              }
              before.onclick=()=>moveCamera(-1);after.onclick=()=>moveCamera(1);cancel.onclick=closeMenu;
              document.addEventListener('keydown',event=>{
                if(!menu.hidden)return;
                if(event.key.startsWith('Arrow')){event.preventDefault();if(soloIndex>=0){if(event.key==='ArrowLeft'||event.key==='ArrowUp')moveSolo(-1);else moveSolo(1)}else nearest(event.key.slice(5).toLowerCase());return}
                if((event.key==='Enter'||event.key===' ')&&soloIndex<0&&event.repeat){event.preventDefault();const active=document.activeElement,index=cards().indexOf(active);if(index>=0)openMenu(index)}
              });
              document.addEventListener('keyup',event=>{if((event.key==='Enter'||event.key===' ')&&!menu.hidden){event.preventDefault();suppressClickUntil=Date.now()+600}});
              window.longPressFocused=()=>{if(!menu.hidden||soloIndex>=0)return false;const index=cards().indexOf(document.activeElement);if(index<0)return false;openMenu(index);return true};
              window.pressFocused=()=>{if(!menu.hidden){document.activeElement.click();return true}if(soloIndex>=0)return exitSolo();const index=cards().indexOf(document.activeElement);if(index<0)return false;enterSolo(index);return true};
              window.moveFocus=moveFocus;
              window.leaveCameraView=()=>closeMenu()||exitSolo();
              fetch('/api/launcher/cameras',{cache:'no-store'}).then(r=>{if(!r.ok)throw Error(r.status);return r.json()}).then(data=>show(data.cameras||[])).catch(()=>message.textContent=$unavailable);
            </script></body></html>
        """.trimIndent()
    }

    private fun htmlLabel(value: String): String = value
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\"", "&quot;")

    companion object {
        private const val LONG_PRESS_MS = 600L
    }
}
