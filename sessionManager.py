from fastapi import FastAPI, Form, WebSocket
from fastapi.responses import HTMLResponse, RedirectResponse
import boto3, uuid, psycopg2

boto3.setup_default_session(region_name="us-east-1")

SQS_URL = "https://sqs.us-east-1.amazonaws.com/321440756268/browser-session-queue"

conn = psycopg2.connect(
    host="-",
    user="-",
    password="-",
    database="-"
)
conn.autocommit = True

sqs = boto3.client("sqs")
app = FastAPI()

# live websocket viewers
live_viewers = {}

# last frame per session
frame_buffers = {}

# ---------------- HOME ----------------
@app.get("/", response_class=HTMLResponse)
def home():
    return """
<html>
<body style="margin:0;background:#020617;font-family:Inter;color:white;display:flex;justify-content:center;align-items:center;height:100vh">
<form action="/open" method="post" style="background:rgba(15,23,42,.9);padding:40px;border-radius:20px">
<h2>Secure Cloud Browser</h2>
<input name="url" placeholder="https://example.com" style="width:100%;padding:12px;border-radius:10px;margin-top:10px">
<button style="width:100%;margin-top:15px;padding:12px;background:#38bdf8;border:none;border-radius:10px">Launch</button>
</form>
</body>
</html>
"""

# ---------------- OPEN ----------------
@app.post("/open")
def open_url(url: str = Form(...)):
    sid = str(uuid.uuid4())
    cur = conn.cursor()
    cur.execute("INSERT INTO sessions (id,url,status,started_at) VALUES (%s,%s,'connecting',NOW())", (sid,url))
    sqs.send_message(QueueUrl=SQS_URL, MessageBody=f"{sid}|{url}")
    return RedirectResponse(f"/view/{sid}",302)

# ---------------- DISPOSE ----------------
@app.post("/dispose/{sid}")
def dispose_session(sid: str):
    cur = conn.cursor()
    cur.execute("UPDATE sessions SET status='ended', ended_at=NOW() WHERE id=%s", (sid,))
    return {"status": "disposed"}

# ---------------- VIEW ----------------
@app.get("/view/{sid}", response_class=HTMLResponse)
def view(sid:str):
    html = """
<html>
<style>
body{margin:0;background:black;color:white;font-family:Inter;display:flex}
#left{width:260px;background:rgba(2,6,23,.95);backdrop-filter:blur(20px);padding:20px}
#right{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center}
#top{height:50px;background:#020617;color:#38bdf8;width:100%;display:flex;align-items:center;padding-left:20px}
#canvas{box-shadow:0 0 40px #38bdf8;display:none;max-width:100%;max-height:100%}
.stat{margin-top:10px;color:#94a3b8}
#loader{text-align:center;color:#38bdf8}
#bar{width:300px;height:6px;background:#020617;border-radius:10px;overflow:hidden;margin-top:10px}
#fill{height:100%;width:0%;background:#38bdf8;animation:load 2s infinite}
@keyframes load{0%{width:0}100%{width:100%}}
#kill{margin-top:20px;width:100%;padding:10px;border:none;border-radius:10px;background:#ef4444;color:white;font-weight:bold;cursor:pointer}
</style>

<div id="left">
<h3>🔐 Session</h3>
<div class="stat">ID: SESSION_ID</div>
<div class="stat">Isolation: Container VM</div>
<div class="stat">Engine: Chromium</div>
<div class="stat">Threat: <span style="color:#22c55e">Low</span></div>
<div class="stat">FPS: <span id="fps">0</span></div>
<div class="stat">Status: <span id="status">Connecting</span></div>
<button id="kill">Dispose Session</button>
</div>

<div id="right">
<div id="top">Secure Cloud Browser</div>

<div id="loader">
<h2>Launching secure session…</h2>
<div id="bar"><div id="fill"></div></div>
</div>

<canvas id="canvas"></canvas>
</div>

<script>
const ws=new WebSocket("ws://"+location.host+"/ws/view/SESSION_ID");
ws.binaryType="blob";

const canvas=document.getElementById("canvas");
const ctx=canvas.getContext("2d");
const fps=document.getElementById("fps");
const status=document.getElementById("status");
const loader=document.getElementById("loader");

document.getElementById("kill").onclick = ()=>{
  fetch("/dispose/SESSION_ID", {method:"POST"});
  status.innerText="Disposed";
};

let last=Date.now(),frames=0;

ws.onmessage=e=>{
 const img=new Image();
 img.onload=()=>{
  loader.style.display="none";
  canvas.style.display="block";
  canvas.width=img.width;
  canvas.height=img.height;
  ctx.drawImage(img,0,0);

  frames++;
  if(Date.now()-last>1000){
    fps.innerText=frames;
    frames=0;
    last=Date.now();
    status.innerText="Streaming";
  }
 }
 img.src=URL.createObjectURL(e.data);
}
</script>
</html>
"""
    return html.replace("SESSION_ID", sid)

# ---------------- VIEW SOCKET ----------------
@app.websocket("/ws/view/{sid}")
async def ws_view(ws:WebSocket,sid:str):
    await ws.accept()
    live_viewers[sid]=ws

    # send latest frame if worker already streaming
    if sid in frame_buffers and frame_buffers[sid]:
        await ws.send_bytes(frame_buffers[sid])

    try:
        while True:
            await ws.receive_text()
    except:
        live_viewers.pop(sid,None)
        cur = conn.cursor()
        cur.execute("UPDATE sessions SET status='ended', ended_at=NOW() WHERE id=%s", (sid,))

# ---------------- PUSH SOCKET ----------------
@app.websocket("/ws/push/{sid}")
async def ws_push(ws:WebSocket,sid:str):
    await ws.accept()
    frame_buffers[sid] = None

    try:
        while True:
            data = await ws.receive_bytes()
            frame_buffers[sid] = data

            if sid in live_viewers:
                await live_viewers[sid].send_bytes(data)
    except:
        frame_buffers.pop(sid,None)
