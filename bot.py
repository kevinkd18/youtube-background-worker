from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from PIL import Image
from concurrent.futures import ThreadPoolExecutor,as_completed
import threading,re,time,json,tempfile,asyncio,io,math,random,pickle,os,psutil,uuid
from telebot.async_telebot import AsyncTeleBot
from telebot import types
from datetime import datetime
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from matplotlib import patches

# Modern style configuration
plt.rcParams.update({
    'figure.facecolor': '#F0F2F6',
    'axes.facecolor': 'white',
    'axes.grid': True,
    'grid.alpha': 0.3,
    'grid.color': '#CCCCCC',
    'axes.spines.top': False,
    'axes.spines.right': False,
    'font.family': 'sans-serif',
    'axes.labelcolor': '#333333',
    'xtick.color': '#333333',
    'ytick.color': '#333333',
    'text.color': '#333333',
    'lines.linewidth': 2,
    'axes.titlesize': 14,
    'axes.titleweight': 'bold',
    'axes.labelsize': 11,
    'xtick.labelsize': 10,
    'ytick.labelsize': 10
})

extract_video_id=lambda url:(m.group(1)if(m:=re.search(r"(?:youtube\.com\/(?:[^\/]+\/.+\/|(?:v|e(?:mbed)?)|.*[?&]v=)|youtu\.be\/|youtube\.com\/shorts\/)([^\"&?\/\s]{11})",url))else None)

BOT_TOKEN=os.getenv("BOT_TOKEN","7693772906:AAHPxwVonJpa3lJPZlXB1yXXJwZ41FP6Lew")
CHAT_ID=os.getenv("CHAT_ID","898142325")
SAVE_FILE="bot_data.pkl"
bot=AsyncTeleBot(BOT_TOKEN)
selected_mode=None
videos_started=False
drivers=[];video_playing=False;video_urls=[];video_ids=[];driver_lock=threading.Lock()
event_loop=None
log_buffer=[]
cookie_data={}
video_links=[]
video_stats={}
start_timestamp=None
ads_skipped_count=0
temp_dirs=[]
stats_lock=threading.Lock()
driver_creation_lock=threading.Lock()

def save_data():
    try:
        data={'cookie_data':cookie_data,'video_links':video_links,'selected_mode':selected_mode}
        with open(SAVE_FILE,'wb')as f:
            pickle.dump(data,f)
        print("✅ Data saved")
    except Exception as e:
        print(f"❌ Save error: {e}")

def load_data():
    global cookie_data,video_links,selected_mode
    try:
        if os.path.exists(SAVE_FILE):
            with open(SAVE_FILE,'rb')as f:
                data=pickle.load(f)
            cookie_data=data.get('cookie_data',{})
            video_links=data.get('video_links',[])
            selected_mode=data.get('selected_mode')
            print(f"✅ Restored: {len(cookie_data)} accounts, {len(video_links)} links")
            return True
        return False
    except Exception as e:
        print(f"❌ Load error: {e}")
        return False

def get_main_keyboard():
    markup=types.ReplyKeyboardMarkup(resize_keyboard=True,row_width=2)
    markup.add(
        types.KeyboardButton('📋 JSON'),
        types.KeyboardButton('🔗 Links'),
        types.KeyboardButton('▶️ Start'),
        types.KeyboardButton('⏹️ Stop'),
        types.KeyboardButton('📸 Grid'),
        types.KeyboardButton('📊 Simple'),
        types.KeyboardButton('📈 Detailed'),
        types.KeyboardButton('🖼️ Single')
    )
    return markup

def log(msg,to_telegram=True):
    print(msg)
    if to_telegram and event_loop and not event_loop.is_closed():
        asyncio.run_coroutine_threadsafe(bot.send_message(CHAT_ID,msg,reply_markup=get_main_keyboard()),event_loop)

def load_cookies(d,cookie_name):
    try:
        if cookie_name not in cookie_data:
            print(f"   ⚠️ Cookie not found: {cookie_name}")
            return False
        cookies=cookie_data[cookie_name]
        for c in cookies:
            try:
                ck={'name':c['name'],'value':c['value'],'domain':('.'+c['domain']if not c['domain'].startswith('.')else c['domain']),'path':c.get('path','/')}
                if'expirationDate'in c:ck['expiry']=int(c['expirationDate'])
                if c.get('secure'):ck['secure']=True
                if c.get('httpOnly'):ck['httpOnly']=True
                if'sameSite'in c and c['sameSite']:ck['sameSite']='None'if c['sameSite'].lower()=='no_restriction'else c['sameSite'].capitalize()
                d.add_cookie(ck)
            except:pass
        return True
    except Exception as e:
        print(f"   ❌ Cookie load error: {e}")
        return False

def create_driver(mode,profile_index):
    with driver_creation_lock:
        o=Options()
        # Render uses chromium-browser
        o.binary_location='/usr/bin/chromium'
        
        unique_id=f"{profile_index}_{int(time.time()*1000000)}_{uuid.uuid4().hex[:12]}"
        temp_dir=tempfile.TemporaryDirectory(prefix=f'ytbot_{unique_id}_')
        temp_dirs.append(temp_dir)
        
        # Optimized for Render's environment
        args=['--headless=new','--no-sandbox','--disable-dev-shm-usage','--mute-audio',f'--user-data-dir={temp_dir.name}','--disable-blink-features=AutomationControlled','--disable-gpu','--disable-extensions','--disable-logging','--disable-software-rasterizer','--no-first-run','--no-default-browser-check','--disable-popup-blocking','--autoplay-policy=no-user-gesture-required','--disable-background-networking','--disable-background-timer-throttling','--disable-backgrounding-occluded-windows','--disable-breakpad','--disable-component-extensions-with-background-pages','--disable-features=TranslateUI','--disable-ipc-flooding-protection','--disable-renderer-backgrounding','--disable-sync','--force-color-profile=srgb','--metrics-recording-only','--safebrowsing-disable-auto-update','--single-process','--disable-setuid-sandbox']
        
        if mode==1:args.extend(['--window-size=1280,720','--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'])
        else:args.extend(['--window-size=412,915','--user-agent=Mozilla/5.0 (Linux; Android 13; SM-S911B) AppleWebKit/537.36'])
        
        [o.add_argument(a)for a in args]
        o.add_experimental_option("excludeSwitches",["enable-automation","enable-logging"]);o.add_experimental_option('useAutomationExtension',False)
        o.add_experimental_option("prefs",{"profile.default_content_setting_values.media_stream_mic":1,"profile.default_content_setting_values.media_stream_camera":1,"profile.default_content_setting_values.notifications":1})
        o.page_load_strategy='eager'
        
        try:
            d=webdriver.Chrome(options=o)
            d.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument',{'source':'Object.defineProperty(navigator,"webdriver",{get:()=>undefined});'})
            time.sleep(0.2)
            return d
        except Exception as e:
            print(f"Driver creation error: {e}")
            try:temp_dir.cleanup()
            except:pass
            raise

def monitor_and_maintain_video(d,index,vid):
    global ads_skipped_count
    loop_count=0
    local_ads_skipped=0
    
    while video_playing:
        try:
            result=d.execute_script("""
                var v=document.querySelector('video');
                var stats={playing:false,ended:false,adSkipped:false,currentTime:0,duration:0};
                if(v){
                    stats.currentTime=v.currentTime;
                    stats.duration=v.duration;
                    stats.ended=v.ended;
                    v.muted=true;
                    if(v.paused||v.ended){
                        v.currentTime=0;
                        v.play().then(()=>{}).catch(e=>{setTimeout(()=>v.play(),200);});
                    }else{
                        stats.playing=true;
                    }
                }
                var skipBtn=document.querySelector('.ytp-ad-skip-button, .ytp-skip-ad-button, button[aria-label*="Skip"], .ytp-ad-skip-button-modern, .ytp-ad-overlay-close-button');
                if(skipBtn&&skipBtn.offsetParent!==null){skipBtn.click();stats.adSkipped=true;}
                var playBtn=document.querySelector('.ytp-play-button[aria-label*="Play"]');
                if(playBtn)playBtn.click();
                return stats;
            """)
            
            if result:
                curr_time=result.get('currentTime',0)
                duration=result.get('duration',0)
                
                if result.get('ended')or(duration>0 and curr_time>=duration-0.5):
                    loop_count+=1
                    with stats_lock:
                        video_stats[vid]['loops']=loop_count
                
                if result.get('adSkipped'):
                    local_ads_skipped+=1
                    ads_skipped_count+=1
                    with stats_lock:
                        video_stats[vid]['ads_skipped']=local_ads_skipped
                
                with stats_lock:
                    video_stats[vid]['current_time']=curr_time
                    video_stats[vid]['duration']=duration
                    video_stats[vid]['status']='▶️ Playing'if result.get('playing')else'⏸️ Paused'
            
            time.sleep(0.7)
        except Exception as e:
            print(f"Monitor error for {vid}: {e}")
            time.sleep(1)

def play_video(index,url,mode,cookie_name,profile_index):
    global drivers,video_urls,video_ids,log_buffer,video_stats
    vid=extract_video_id(url)
    if not vid:return None
    
    with stats_lock:
        video_stats[vid]={'loops':0,'ads_skipped':0,'current_time':0,'duration':0,'status':'⏳ Loading','cookie':cookie_name,'start_time':datetime.now().strftime('%H:%M:%S')}
    
    print(f"{'🖥️' if mode==1 else '📱'} Browser {index+1} starting...")
    
    try:
        d=create_driver(mode,profile_index)
    except Exception as e:
        print(f"Failed to create driver for browser {index+1}: {e}")
        with stats_lock:
            video_stats[vid]['status']='❌ Driver Error'
        return False
    
    try:
        d.get("https://www.youtube.com"if mode==1 else"https://m.youtube.com");time.sleep(0.3);d.delete_all_cookies()
        
        if load_cookies(d,cookie_name):print(f"   ✅ Cookies loaded")
        
        d.refresh();time.sleep(1);d.get(url);time.sleep(4)
        
        try:
            WebDriverWait(d,15).until(EC.presence_of_element_located((By.TAG_NAME,"video")))
            
            for attempt in range(3):
                d.execute_script("""
                    var v=document.querySelector('video');
                    if(v){
                        v.muted=true;v.loop=false;v.autoplay=true;
                        v.play().then(()=>{
                            v.addEventListener('ended',function(){this.currentTime=0;this.play();});
                        }).catch(e=>{setTimeout(()=>v.play(),300);});
                    }
                    var playBtn=document.querySelector('.ytp-large-play-button, .ytp-play-button');
                    if(playBtn)playBtn.click();
                """)
                time.sleep(0.5)
            
            with driver_lock:
                drivers.append(d);video_ids.append(vid);video_urls.append(url)
            
            with stats_lock:
                video_stats[vid]['status']='▶️ Playing'
            
            print(f"   ▶️ Playing - Browser {index+1}")
            threading.Thread(target=monitor_and_maintain_video,args=(d,index,vid),daemon=True).start()
            return True
        except Exception as e:
            print(f"Video load timeout for browser {index+1}: {e}")
            d.quit()
            with stats_lock:
                video_stats[vid]['status']='❌ Timeout'
            return False
    except Exception as e:
        print(f"Error in play_video for browser {index+1}: {e}")
        try:d.quit()
        except:pass
        with stats_lock:
            video_stats[vid]['status']='❌ Error'
        return False

async def capture_grid_only(mode):
    if not drivers:
        await bot.send_message(CHAT_ID,"❌ No browsers!",reply_markup=get_main_keyboard())
        return
    
    msg=await bot.send_message(CHAT_ID,f"📸 Capturing {len(drivers)} screenshots...",reply_markup=get_main_keyboard())
    screenshot_data=[]
    
    def take_ss(i,d):
        try:
            d.execute_script("var v=document.querySelector('video');if(v)v.pause();")
            png=d.get_screenshot_as_png()
            d.execute_script("var v=document.querySelector('video');if(v)v.play();")
            return png
        except Exception as e:
            print(f"Screenshot error {i}: {e}")
            return None
    
    with ThreadPoolExecutor(max_workers=len(drivers))as e:
        futures=[e.submit(take_ss,i,d)for i,d in enumerate(drivers)]
        screenshot_data=[f.result()for f in as_completed(futures)if f.result()]
    
    if len(screenshot_data)>=1:
        cols=math.ceil(math.sqrt(len(screenshot_data)))
        rows=math.ceil(len(screenshot_data)/cols)
        
        images=[Image.open(io.BytesIO(img_bytes))for img_bytes in screenshot_data]
        
        for i,img in enumerate(images):
            img.thumbnail((640,360),Image.Resampling.LANCZOS)
            images[i]=img
        
        w,h=640,360
        grid=Image.new('RGB',(w*cols,h*rows),(0,0,0))
        
        for idx,img in enumerate(images):
            x=(idx%cols)*w;y=(idx//cols)*h
            grid.paste(img,(x,y))
        
        grid_buffer=io.BytesIO()
        grid.save(grid_buffer,format='PNG',optimize=True,quality=85)
        grid_data=grid_buffer.getvalue()
        
        await bot.delete_message(CHAT_ID,msg.message_id)
        await bot.send_photo(CHAT_ID,grid_data,caption=f"🖼️ Grid - {len(screenshot_data)} Videos\n{'Desktop' if mode==1 else 'Mobile'}",reply_markup=get_main_keyboard())
    else:
        await bot.edit_message_text("❌ Failed",CHAT_ID,msg.message_id,reply_markup=get_main_keyboard())

def generate_status_graphs():
    try:
        fig=plt.figure(figsize=(15,12))
        fig.patch.set_facecolor('#F0F2F6')
        
        colors={'primary':'#2196F3','secondary':'#FF4081','success':'#4CAF50','warning':'#FFC107','danger':'#F44336','neutral':'#607D8B'}
        
        gs=plt.GridSpec(3,2,figure=fig,hspace=0.3,wspace=0.2)
        
        ax1=fig.add_subplot(gs[0,:])
        video_names=[v[:8]for v in video_ids]
        
        with stats_lock:
            loops=[video_stats.get(v,{}).get('loops',0)for v in video_ids]
            ads=[video_stats.get(v,{}).get('ads_skipped',0)for v in video_ids]
        
        x=range(len(video_names))
        ax1.plot(x,loops,marker='o',color=colors['primary'],linewidth=2,label='Loops')
        ax1.plot(x,ads,marker='s',color=colors['secondary'],linewidth=2,label='Ads Skipped')
        
        ax1.fill_between(x,loops,alpha=0.2,color=colors['primary'])
        ax1.fill_between(x,ads,alpha=0.2,color=colors['secondary'])
        
        ax1.set_title('Performance Overview',pad=20)
        ax1.set_xticks(x)
        ax1.set_xticklabels(video_names,rotation=45,ha='right')
        ax1.legend(loc='upper right')
        
        ax2=fig.add_subplot(gs[1,0])
        status_counts={}
        with stats_lock:
            for vid in video_ids:
                status=video_stats.get(vid,{}).get('status','Unknown')
                status_counts[status]=status_counts.get(status,0)+1
        
        status_colors=[colors['success'],colors['warning'],colors['danger'],colors['neutral']]
        wedges,texts,autotexts=ax2.pie(status_counts.values(),labels=status_counts.keys(),colors=status_colors,autopct='%1.1f%%',pctdistance=0.85,wedgeprops=dict(width=0.5))
        ax2.set_title('Video Status Distribution',pad=20)
        
        ax3=fig.add_subplot(gs[1,1])
        cpu_percent=psutil.cpu_percent(interval=0.1)
        memory_percent=psutil.virtual_memory().percent
        ax3.text(0.5,0.5,f'CPU: {cpu_percent}%\nRAM: {memory_percent}%',ha='center',va='center',fontsize=14)
        ax3.set_title('System Resources',pad=20)
        ax3.axis('off')
        
        ax4=fig.add_subplot(gs[2,:])
        timeline=range(len(video_ids))
        performance_score=[(l+a)/2 for l,a in zip(loops,ads)]
        
        ax4.fill_between(timeline,performance_score,alpha=0.3,color=colors['success'])
        ax4.plot(timeline,performance_score,color=colors['success'],linewidth=2)
        
        ax4.set_title('Performance Timeline',pad=20)
        ax4.set_xlabel('Video Sequence')
        ax4.set_ylabel('Performance Score')
        
        buf=io.BytesIO()
        plt.savefig(buf,format='png',dpi=100,bbox_inches='tight')
        buf.seek(0)
        plt.close()
        
        return buf.getvalue()
    except Exception as e:
        print(f"Graph error: {e}")
        return None

def parse_links(text):
    links=[]
    text=text.replace('"','').replace("'",'').replace('[','').replace(']','').replace('(','').replace(')','')
    url_pattern=r'https?://(?:www\.)?(?:youtube\.com|youtu\.be)[^\s,]*'
    found_urls=re.findall(url_pattern,text)
    for url in found_urls:
        url=url.strip().rstrip(',').rstrip(';')
        if url and extract_video_id(url):
            links.append(url)
    return links

async def telegram_listener():
    global selected_mode,video_playing,videos_started,video_links,start_timestamp
    
    @bot.message_handler(commands=['start'])
    async def start(message):
        restored=load_data()
        text="🎯 Multi-Account YouTube Player\n\n"
        if restored:
            text+=f"✅ Restored:\n📁 {len(cookie_data)} accounts\n🔗 {len(video_links)} links\n\n"
        text+="Use buttons:"
        await bot.send_message(message.chat.id,text,reply_markup=get_main_keyboard())
    
    @bot.message_handler(func=lambda m:m.text=='📋 JSON')
    async def manage_json(message):
        if cookie_data:
            text=f"📋 Accounts ({len(cookie_data)}):\n\n"
            for i,name in enumerate(cookie_data.keys(),1):
                text+=f"{i}. {name}\n"
            text+="\n📤 Upload\n🗑️ /remove <#>"
        else:
            text="📋 No JSON\n\n📤 Upload files"
        await bot.send_message(message.chat.id,text,reply_markup=get_main_keyboard())
    
    @bot.message_handler(func=lambda m:m.text=='🔗 Links')
    async def manage_links(message):
        if video_links:
            text=f"🔗 Links ({len(video_links)}):\n\n"
            for i,link in enumerate(video_links[:10],1):
                vid=extract_video_id(link)
                text+=f"{i}. {vid}\n"
            if len(video_links)>10:text+=f"...+{len(video_links)-10} more\n"
            text+="\n📝 Send\n🗑️ /clearlinks"
        else:
            text="🔗 No links\n\n📝 Send YouTube URLs"
        await bot.send_message(message.chat.id,text,reply_markup=get_main_keyboard())
    
    @bot.message_handler(func=lambda m:m.text=='▶️ Start')
    async def start_videos(message):
        global videos_started,video_playing
        if videos_started:
            await bot.send_message(message.chat.id,"⚠️ Running!",reply_markup=get_main_keyboard())
            return
        if not cookie_data or not video_links:
            await bot.send_message(message.chat.id,"⚠️ Need JSON & links!",reply_markup=get_main_keyboard())
            return
        
        markup=types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton('🖥️ Desktop',callback_data='mode_desktop'),
            types.InlineKeyboardButton('📱 Mobile',callback_data='mode_mobile')
        )
        await bot.send_message(message.chat.id,"Mode:",reply_markup=markup)
    
    @bot.callback_query_handler(func=lambda c:c.data.startswith('mode_'))
    async def mode_callback(call):
        global selected_mode,videos_started,video_playing,start_timestamp
        selected_mode=1 if call.data=='mode_desktop'else 2
        videos_started=True
        video_playing=True
        start_timestamp=datetime.now()
        save_data()
        await bot.answer_callback_query(call.id)
        await bot.delete_message(call.message.chat.id,call.message.message_id)
        await bot.send_message(call.message.chat.id,f"✅ {'Desktop' if selected_mode==1 else 'Mobile'}\n\n⏳ Loading...",reply_markup=get_main_keyboard())
        asyncio.create_task(start_video_loading())
    
    @bot.message_handler(func=lambda m:m.text=='⏹️ Stop')
    async def stop_videos(message):
        global video_playing,videos_started,drivers,video_stats,temp_dirs
        if not videos_started:
            await bot.send_message(message.chat.id,"⚠️ Not running!",reply_markup=get_main_keyboard())
            return
        video_playing=False
        await bot.send_message(message.chat.id,"🛑 Stopping...",reply_markup=get_main_keyboard())
        
        for d in drivers:
            try:d.quit()
            except:pass
        
        drivers.clear();video_ids.clear();video_urls.clear();video_stats.clear()
        
        for td in temp_dirs:
            try:td.cleanup()
            except:pass
        temp_dirs.clear()
        
        videos_started=False
        await bot.send_message(message.chat.id,"✅ Stopped & cleaned",reply_markup=get_main_keyboard())
    
    @bot.message_handler(func=lambda m:m.text=='📸 Grid')
    async def grid_screenshot(message):
        if not drivers:
            await bot.send_message(message.chat.id,"❌ No videos!",reply_markup=get_main_keyboard())
            return
        await capture_grid_only(selected_mode)
    
    @bot.message_handler(func=lambda m:m.text=='📊 Simple')
    async def simple_status(message):
        if not videos_started:
            await bot.send_message(message.chat.id,"⚠️ Not running!",reply_markup=get_main_keyboard())
            return
        
        runtime=str(datetime.now()-start_timestamp).split('.')[0]if start_timestamp else"N/A"
        
        with stats_lock:
            total_loops=sum([v.get('loops',0)for v in video_stats.values()])
        
        text=f"📊 QUICK STATUS\n\n"
        text+=f"⏱️ Runtime: {runtime}\n"
        text+=f"👥 Accounts: {len(cookie_data)}\n"
        text+=f"📹 Active: {len(drivers)}/{len(video_links)}\n"
        text+=f"🖥️ Mode: {'Desktop' if selected_mode==1 else 'Mobile'}\n"
        text+=f"🎯 Total Ads: {ads_skipped_count}\n"
        text+=f"🔄 Total Loops: {total_loops}\n"
        text+=f"💻 CPU: {psutil.cpu_percent(interval=0.1)}%\n"
        text+=f"🧠 RAM: {psutil.virtual_memory().percent}%"
        
        await bot.send_message(message.chat.id,text,reply_markup=get_main_keyboard())
    
    @bot.message_handler(func=lambda m:m.text=='📈 Detailed')
    async def detailed_status(message):
        if not videos_started:
            await bot.send_message(message.chat.id,"⚠️ Not running!",reply_markup=get_main_keyboard())
            return
        
        runtime=str(datetime.now()-start_timestamp).split('.')[0]if start_timestamp else"N/A"
        
        with stats_lock:
            total_loops=sum([v.get('loops',0)for v in video_stats.values()])
        
        cpu_percent=psutil.cpu_percent()
        memory=psutil.virtual_memory()
        
        active_videos=len(drivers)
        total_videos=len(video_links)
        success_rate=(active_videos/total_videos*100)if total_videos>0 else 0
        
        text="╔════ 📊 DETAILED ANALYTICS ═══╗\n\n"
        text+="🎯 SYSTEM OVERVIEW\n"
        text+="┌─────────────────────────┐\n"
        text+=f"│ ⏱️ Runtime: {runtime}\n"
        text+=f"│ 💻 CPU: {cpu_percent}%\n"
        text+=f"│ 🧠 RAM: {memory.percent}%\n"
        text+=f"│ 🌡️ Load: {'Low 🟢' if cpu_percent<50 else 'Medium 🟡' if cpu_percent<80 else 'High 🔴'}\n"
        text+="└─────────────────────────┘\n\n"
        
        text+="📊 PERFORMANCE METRICS\n"
        text+="┌─────────────────────────┐\n"
        text+=f"│ 👥 Active Accounts: {len(cookie_data)}\n"
        text+=f"│ 📹 Videos: {active_videos}/{total_videos}\n"
        text+=f"│ ✨ Success Rate: {success_rate:.1f}%\n"
        text+=f"│ 🎯 Ads Skipped: {ads_skipped_count}\n"
        text+=f"│ 🔄 Total Loops: {total_loops}\n"
        text+="└─────────────────────────┘\n\n"
        
        text+="🎥 VIDEO DETAILS\n"
        text+="┌────────────────────────────────┐\n"
        
        with stats_lock:
            for i,vid in enumerate(video_ids[:10],1):
                stats=video_stats.get(vid,{})
                status=stats.get('status','Unknown')
                status_emoji='▶️' if 'Playing' in status else '⏸️' if 'Paused' in status else '⚠️'
                
                current_time=stats.get('current_time',0)
                duration=stats.get('duration',1)
                progress=int((current_time/duration)*10)if duration>0 else 0
                progress_bar=''.join(['█' if i<=progress else '░' for i in range(10)])
                progress_percent=int((current_time/duration)*100)if duration>0 else 0
                
                text+=f"│ {i}. {vid[:8]}... {status_emoji}\n"
                text+=f"│ ┌────────────────────────┐\n"
                text+=f"│ │ 🔄 Loops: {stats.get('loops',0):2} | 🎯 Ads: {stats.get('ads_skipped',0):3}\n"
                text+=f"│ │ ⏳ [{progress_bar}] {progress_percent:3}%\n"
                text+=f"│ └────────────────────────┘\n"
        
        if len(video_ids)>10:
            text+=f"│ + {len(video_ids)-10} more videos...\n"
        
        text+="└────────────────────────────┘"
        
        await bot.send_message(message.chat.id,text,reply_markup=get_main_keyboard())
        
        try:
            graph_data=generate_status_graphs()
            if graph_data:
                await bot.send_photo(message.chat.id,graph_data,caption="📊 Visual Dashboard",reply_markup=get_main_keyboard())
        except Exception as e:
            print(f"Graph sending error: {e}")
    
    @bot.message_handler(func=lambda m:m.text=='🖼️ Single')
    async def single_ss(message):
        if not drivers:
            await bot.send_message(message.chat.id,"❌ No videos!",reply_markup=get_main_keyboard())
            return
        
        markup=types.InlineKeyboardMarkup(row_width=4)
        buttons=[types.InlineKeyboardButton(f"#{i+1}",callback_data=f"ss_{i}")for i in range(len(drivers))]
        markup.add(*buttons)
        await bot.send_message(message.chat.id,f"Select ({len(drivers)}):",reply_markup=markup)
    
    @bot.callback_query_handler(func=lambda c:c.data.startswith('ss_'))
    async def single_ss_callback(call):
        idx=int(call.data.split('_')[1])
        if idx<len(drivers):
            await bot.answer_callback_query(call.id)
            await bot.delete_message(call.message.chat.id,call.message.message_id)
            msg=await bot.send_message(call.message.chat.id,f"📸 Capturing #{idx+1}...",reply_markup=get_main_keyboard())
            try:
                d=drivers[idx]
                vid=video_ids[idx]
                url=video_urls[idx]
                
                with stats_lock:
                    stats=video_stats.get(vid,{})
                
                d.execute_script("var v=document.querySelector('video');if(v)v.pause();")
                png=d.get_screenshot_as_png()
                d.execute_script("var v=document.querySelector('video');if(v)v.play();")
                
                img=Image.open(io.BytesIO(png))
                img.thumbnail((1280,720),Image.Resampling.LANCZOS)
                img_buffer=io.BytesIO()
                img.save(img_buffer,format='PNG',optimize=True,quality=85)
                img_data=img_buffer.getvalue()
                
                caption=f"📸 Video #{idx+1}: {vid}\n"
                caption+=f"📊 Status: {stats.get('status','Unknown')}\n"
                caption+=f"🔄 Loops: {stats.get('loops',0)}\n"
                caption+=f"🎯 Ads: {stats.get('ads_skipped',0)}"
                
                await bot.delete_message(call.message.chat.id,msg.message_id)
                await bot.send_photo(call.message.chat.id,img_data,caption=caption,reply_markup=get_main_keyboard())
            except Exception as e:
                await bot.edit_message_text(f"❌ {e}",call.message.chat.id,msg.message_id,reply_markup=get_main_keyboard())
    
    @bot.message_handler(content_types=['document'])
    async def handle_json_files(message):
        global cookie_data
        try:
            file_info=await bot.get_file(message.document.file_id)
            downloaded=await bot.download_file(file_info.file_path)
            filename=message.document.file_name
            
            if not filename.endswith('.json'):
                await bot.send_message(message.chat.id,"⚠️ Only JSON!",reply_markup=get_main_keyboard())
                return
            
            cookies=json.loads(downloaded)
            cookie_data[filename]=cookies
            save_data()
            
            await bot.send_message(message.chat.id,f"✅ {filename}\n📁 Total: {len(cookie_data)}",reply_markup=get_main_keyboard())
        except Exception as e:
            await bot.send_message(message.chat.id,f"❌ {e}",reply_markup=get_main_keyboard())
    
    @bot.message_handler(func=lambda m:m.text and'youtube'in m.text.lower())
    async def handle_links(message):
        global video_links
        if videos_started:
            await bot.send_message(message.chat.id,"⚠️ Stop first!",reply_markup=get_main_keyboard())
            return
        
        parsed_links=parse_links(message.text)
        added=len(parsed_links)
        video_links.extend(parsed_links)
        
        save_data()
        await bot.send_message(message.chat.id,f"✅ +{added}\n📹 Total: {len(video_links)}",reply_markup=get_main_keyboard())
    
    @bot.message_handler(commands=['clearlinks'])
    async def clear_links(message):
        global video_links
        video_links.clear()
        save_data()
        await bot.send_message(message.chat.id,"✅ Cleared",reply_markup=get_main_keyboard())
    
    @bot.message_handler(commands=['remove'])
    async def remove_json(message):
        global cookie_data
        try:
            num=int(message.text.split()[1])-1
            names=list(cookie_data.keys())
            if 0<=num<len(names):
                removed=names[num]
                del cookie_data[removed]
                save_data()
                await bot.send_message(message.chat.id,f"✅ Removed: {removed}",reply_markup=get_main_keyboard())
            else:
                await bot.send_message(message.chat.id,"⚠️ Invalid",reply_markup=get_main_keyboard())
        except:
            await bot.send_message(message.chat.id,"⚠️ /remove <#>",reply_markup=get_main_keyboard())
    
    while True:
        try:
            await bot.infinity_polling(timeout=180,request_timeout=180,skip_pending=True)
        except Exception as e:
            print(f"Polling error: {e}")
            await asyncio.sleep(5)

async def start_video_loading():
    try:
        start_time=time.time()
        tasks=[]
        cookie_names=list(cookie_data.keys())
        
        for i,url in enumerate(video_links):
            cookie_name=random.choice(cookie_names)
            profile_index=i+1
            tasks.append((i,url,selected_mode,cookie_name,profile_index))
        
        # Limit workers for Render's free tier
        max_workers=min(2,len(tasks))
        
        with ThreadPoolExecutor(max_workers=max_workers)as e:
            futures=[e.submit(play_video,*task)for task in tasks]
            results=[]
            for f in as_completed(futures):
                try:
                    results.append(f.result())
                except Exception as ex:
                    print(f"Task exception: {ex}")
                    results.append(False)
        
        elapsed=time.time()-start_time
        success_count=sum(1 for r in results if r)
        await bot.send_message(CHAT_ID,f"✅ {success_count}/{len(video_links)} loaded\n⏱️ {elapsed:.1f}s",reply_markup=get_main_keyboard())
    except Exception as e:
        print(f"Loading error: {e}")
        await bot.send_message(CHAT_ID,f"❌ Loading error: {e}",reply_markup=get_main_keyboard())

async def main():
    global event_loop
    event_loop=asyncio.get_event_loop()
    
    print("="*60);print("🎯 YouTube Player on Render");print("="*60)
    
    load_data()
    
    text="🚀 Started on Render!\n\n"
    if cookie_data or video_links:
        text+=f"✅ Restored:\n📁 {len(cookie_data)}\n🔗 {len(video_links)}\n\n"
    text+="/start"
    
    await bot.send_message(CHAT_ID,text,reply_markup=get_main_keyboard())
    await telegram_listener()

if __name__=="__main__":
    asyncio.run(main())
