"""Hand Mouse Studio — local webcam control with a visible settings panel."""
import ctypes
from ctypes import wintypes
import json
from pathlib import Path
import queue
import threading
import time
import tkinter as tk
from tkinter import ttk

import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from PIL import Image, ImageTk
import pyautogui
from engine import Engine, Settings, observe

ROOT = Path(__file__).resolve().parent
BG, PANEL, TEXT, MUTED, ACCENT = '#101923','#192633','#e7f1f8','#9fb3c5','#48dbc1'
EDGES = [(0,1),(1,2),(2,3),(3,4),(0,5),(5,6),(6,7),(7,8),(5,9),(9,10),(10,11),(11,12),(9,13),(13,14),(14,15),(15,16),(13,17),(17,18),(18,19),(19,20),(0,17)]


class Desktop:
    def __init__(self):
        pyautogui.PAUSE = 0
        pyautogui.FAILSAFE = True
    def position(self): return tuple(pyautogui.position())
    def move(self,x,y): pyautogui.moveTo(x,y,_pause=False)
    def click(self,button):
        if button == 'double':
            pyautogui.doubleClick(interval=.09,_pause=False)
        else:
            pyautogui.click(button=button,_pause=False)
    def down(self): pyautogui.mouseDown(_pause=False)
    def up(self):
        # Cleanup must work even if the physical mouse is in a fail-safe corner.
        ctypes.windll.user32.mouse_event(0x0004,0,0,0,0)
    def wheel(self,units):
        pyautogui.failSafeCheck()
        ctypes.windll.user32.mouse_event(0x0800,0,0,ctypes.c_ulong(units & 0xffffffff),0)


def capture(stop, results):
    cap = None
    try:
        cap = cv2.VideoCapture(0,cv2.CAP_DSHOW)
        if not cap.isOpened():
            cap.release()
            cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            raise RuntimeError('Webcam unavailable. Close other camera apps and restart.')
        cap.set(cv2.CAP_PROP_FRAME_WIDTH,640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT,480)
        options = vision.HandLandmarkerOptions(base_options=python.BaseOptions(model_asset_path=str(ROOT/'hand_landmarker.task')),running_mode=vision.RunningMode.VIDEO,num_hands=1,min_hand_detection_confidence=.65,min_hand_presence_confidence=.65,min_tracking_confidence=.65)
        timestamp = -1
        with vision.HandLandmarker.create_from_options(options) as tracker:
            while not stop.is_set():
                ok,frame = cap.read()
                if not ok:
                    raise RuntimeError('Camera disconnected. Restart after checking camera access.')
                frame = cv2.flip(frame,1)
                rgb = cv2.cvtColor(frame,cv2.COLOR_BGR2RGB)
                now = time.perf_counter()
                timestamp = max(timestamp+1,int(now*1000))
                result = tracker.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB,data=rgb),timestamp)
                points = result.hand_landmarks[0] if result.hand_landmarks else None
                packet = (rgb,points,time.perf_counter(),None)
                if results.full():
                    try: results.get_nowait()
                    except queue.Empty: pass
                results.put_nowait(packet)
    except Exception as error:
        if results.full():
            try: results.get_nowait()
            except queue.Empty: pass
        results.put((None,None,time.perf_counter(),str(error)))
    finally:
        if cap is not None: cap.release()


class Studio:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title('Hand Mouse Studio')
        self.root.configure(bg=BG)
        self.root.geometry('1010x780')
        self.root.minsize(980,740)
        self.settings = Settings()
        try:
            saved = json.loads((ROOT/'settings.json').read_text())
            for key,lo,hi in [('pointer',1,7),('scroll',.5,5),('dwell',.5,2),('pinch_close',.2,.6)]:
                value = float(saved.get(key,getattr(self.settings,key)))
                if lo<=value<=hi: setattr(self.settings,key,value)
            if saved.get('click_mode') in ('Rest to click','Pinch'):
                self.settings.click_mode = saved['click_mode']
        except (OSError,ValueError,TypeError,AttributeError): pass
        self.engine = Engine(Desktop(),self.settings,tuple(pyautogui.size()))
        self.stop = threading.Event()
        self.results = queue.Queue(maxsize=1)
        self.last_frame = time.perf_counter()
        self.last_sample = None
        self.keys = {}
        self.closed = False
        self.save_job = None
        self.practice_count = 0
        self.build()
        self.overlay = tk.Toplevel(self.root)
        self.overlay.overrideredirect(True)
        self.overlay.attributes('-topmost',True)
        self.overlay.attributes('-transparentcolor','black')
        self.ring = tk.Canvas(self.overlay,width=58,height=58,bg='black',highlightthickness=0)
        self.ring.pack()
        self.overlay.update_idletasks()
        user32 = ctypes.windll.user32
        user32.GetParent.argtypes = [wintypes.HWND]
        user32.GetParent.restype = wintypes.HWND
        user32.GetWindowLongW.argtypes = [wintypes.HWND,ctypes.c_int]
        user32.SetWindowLongW.argtypes = [wintypes.HWND,ctypes.c_int,ctypes.c_long]
        hwnd = user32.GetParent(self.overlay.winfo_id())
        style = user32.GetWindowLongW(hwnd,-20)
        user32.SetWindowLongW(hwnd,-20,style|0x20|0x80000|0x08000000)
        self.overlay.withdraw()
        self.root.protocol('WM_DELETE_WINDOW',self.close)
        self.worker = threading.Thread(target=capture,args=(self.stop,self.results),daemon=True)
        self.worker.start()
        self.root.after(15,self.tick)
        print('STUDIO STARTED: window ready, camera initializing, paused; F8 starts/pauses, F10 quits.',flush=True)

    def label(self,parent,text,size=11,color=TEXT,**kwargs):
        widget = tk.Label(parent,text=text,font=('Segoe UI',size),fg=color,bg=parent['bg'],**kwargs)
        widget.pack(anchor='w',pady=4)
        return widget

    def button(self,parent,text,command):
        widget = tk.Button(parent,text=text,command=command,bg='#274354',fg=TEXT,activebackground=ACCENT,activeforeground=BG,relief='flat',font=('Segoe UI',11),padx=10,pady=8)
        widget.pack(fill='x',pady=4)
        return widget

    def build(self):
        head = tk.Frame(self.root,bg=BG)
        head.pack(fill='x',padx=20,pady=(12,4))
        self.label(head,'HAND MOUSE  /  STUDIO',20)
        self.label(head,'Small movements. Clear modes. Keep your elbow supported.',10,MUTED)
        body = tk.Frame(self.root,bg=BG)
        body.pack(fill='both',expand=True,padx=20)
        left = tk.Frame(body,bg=BG)
        left.pack(side='left',fill='both',expand=True,padx=(0,16))
        self.preview = tk.Label(left,bg=PANEL,text='Starting camera…',fg=TEXT,width=80,height=30)
        self.preview.pack()
        self.status = self.label(left,'Paused — press Start',12,ACCENT,wraplength=630)
        self.progress = ttk.Progressbar(left,maximum=1)
        self.progress.pack(fill='x',pady=5)
        self.practice = self.button(left,'Practice target — clicks: 0',self.practice_click)
        right = tk.Frame(body,bg=PANEL,padx=14,pady=8,width=280)
        right.pack(side='right',fill='y')
        self.start = self.button(right,'Start control  ·  F8',self.toggle)
        self.label(right,'CLICK METHOD',10,MUTED)
        self.mode = tk.StringVar(value=self.settings.click_mode)
        for mode in ('Rest to click','Pinch'):
            tk.Radiobutton(right,text=mode,variable=self.mode,value=mode,command=self.change_mode,bg=PANEL,fg=TEXT,selectcolor=BG,activebackground=PANEL,activeforeground=TEXT,font=('Segoe UI',11)).pack(anchor='w')
        self.slider(right,'Pointer sensitivity','pointer',1,7,.1)
        self.slider(right,'Scroll sensitivity','scroll',.5,5,.1)
        self.slider(right,'Rest time (seconds)','dwell',.5,2,.05)
        self.slider(right,'Pinch tolerance','pinch_close',.2,.6,.01)
        self.button(right,'Next rest: double click',lambda:self.action('double'))
        self.button(right,'Next rest: drag / drop',lambda:self.action('drag'))
        self.label(right,'Index: point / rest to click\n2 fingers: scroll strokes\nThumb + middle: right click\nFold fingers: rest / reposition\nF8: pause anywhere\nF10: quit anywhere',10,MUTED,justify='left')
        self.label(self.root,'Local webcam processing  •  Settings save automatically  •  Start paused',9,MUTED).pack_configure(padx=20)

    def slider(self,parent,title,key,lo,hi,step):
        self.label(parent,title,10,MUTED)
        control = tk.Scale(parent,from_=lo,to=hi,resolution=step,orient='horizontal',bg=PANEL,fg=TEXT,troughcolor=BG,highlightthickness=0,length=235)
        control.set(getattr(self.settings,key))
        control.configure(command=lambda value:self.setting(key,float(value)))
        control.pack(fill='x')

    def setting(self,key,value):
        setattr(self.settings,key,value)
        self.engine.mode_changed()
        self.schedule_save()

    def change_mode(self):
        self.settings.click_mode = self.mode.get()
        self.engine.mode_changed()
        self.engine.next_action = 'left'
        self.schedule_save()

    def action(self,name):
        self.mode.set('Rest to click')
        self.change_mode()
        self.engine.next_action = name
        self.engine.status = f'Next rest will {name} — point at your target'

    def practice_click(self):
        self.practice_count += 1
        self.practice.configure(text=f'Practice target — clicks: {self.practice_count}')

    def schedule_save(self):
        if self.save_job: self.root.after_cancel(self.save_job)
        self.save_job = self.root.after(250,self.save)

    def save(self):
        self.save_job = None
        try:
            temporary = ROOT/'settings.tmp'
            temporary.write_text(json.dumps(vars(self.settings),indent=2))
            temporary.replace(ROOT/'settings.json')
        except OSError as error:
            self.engine.status = f'Could not save settings: {error}'

    def toggle(self):
        self.engine.toggle()
        self.start.configure(text='Start control  ·  F8' if self.engine.paused else 'Pause control  ·  F8')

    def hotkey(self,key):
        down = bool(ctypes.windll.user32.GetAsyncKeyState(key)&0x8000)
        pressed = down and not self.keys.get(key,False)
        self.keys[key] = down
        return pressed

    def tick(self):
        if self.closed: return
        try:
            if self.hotkey(0x77): self.toggle()  # F8
            if self.hotkey(0x79):
                self.close()
                return
            try: packet = self.results.get_nowait()
            except queue.Empty: packet = None
            if packet:
                rgb,points,now,error = packet
                self.last_frame = time.perf_counter()
                if error:
                    self.engine.release()
                    self.engine.paused = True
                    self.engine.status = error
                    self.start.configure(text='Camera unavailable — restart app')
                    print('CAMERA ERROR: '+error,flush=True)
                else:
                    if self.last_sample is None:
                        print(f'CAMERA READY: {rgb.shape[1]}x{rgb.shape[0]}, hand inference working.',flush=True)
                    self.last_sample = now
                    hand = observe(points,rgb.shape[1]/rgb.shape[0]) if points else None
                    self.engine.update(hand,now)
                    h,w = rgb.shape[:2]
                    if points:
                        pixels = [(int(p.x*w),int(p.y*h)) for p in points]
                        for a,b in EDGES: cv2.line(rgb,pixels[a],pixels[b],(72,219,193),2)
                        for p in pixels: cv2.circle(rgb,p,3,(235,241,248),-1)
                    self.photo = ImageTk.PhotoImage(Image.fromarray(rgb))
                    self.preview.configure(image=self.photo,text='',width=640,height=480)
            elif time.perf_counter()-self.last_frame>.4:
                self.engine.update(None,time.perf_counter())
            self.status.configure(text=self.engine.status)
            self.progress['value'] = self.engine.progress
            if not self.engine.paused and self.engine.progress>0 and self.engine.pose in ('move','right'):
                x,y = pyautogui.position()
                self.overlay.geometry(f'58x58+{max(0,x-29)}+{max(0,y-29)}')
                self.ring.delete('all')
                self.ring.create_oval(4,4,54,54,outline='#405868',width=3)
                self.ring.create_arc(4,4,54,54,start=90,extent=-359*self.engine.progress,style='arc',outline=ACCENT,width=4)
                self.overlay.deiconify()
            else:
                self.overlay.withdraw()
        except pyautogui.FailSafeException:
            self.engine.release()
            self.engine.paused = True
            self.engine.status = 'Paused by screen-corner safety — F8 to resume'
            self.start.configure(text='Start control  ·  F8')
        except Exception as error:
            self.engine.release()
            self.engine.paused = True
            self.engine.status = f'Paused: {error}'
            print('CONTROL ERROR: '+repr(error),flush=True)
        self.root.after(15,self.tick)

    def close(self):
        if self.closed: return
        self.closed = True
        self.stop.set()
        self.engine.release()
        self.save()
        self.worker.join(timeout=1)
        self.root.destroy()
        print('STUDIO STOPPED: buttons released.',flush=True)


if __name__ == '__main__':
    app = Studio()
    app.root.mainloop()
