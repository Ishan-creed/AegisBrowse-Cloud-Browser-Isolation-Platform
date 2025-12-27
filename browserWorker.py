import boto3
import psycopg2
import time
import subprocess
import os
import random
import asyncio
import websockets
from websockets.exceptions import ConnectionClosed
import io
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from PIL import Image

# AWS
boto3.setup_default_session(region_name="us-east-1")
SQS_URL = "https://sqs.us-east-1.amazonaws.com/321440756268/browser-session-queue"
sqs = boto3.client("sqs")

# Database
conn = psycopg2.connect(
    host="-",
    user="-",
    password="-",
    database="-"
)
conn.autocommit = True

WS_SERVER = "ws://127.0.0.1:8000/ws/push"

print("🚀 Cloud Browser Worker Ready (Concurrent Mode)")

# ---------------- STREAM ONE SESSION ----------------
async def stream_browser(sid, url):
    display = f":{random.randint(20,99)}"
    os.environ["DISPLAY"] = display

    xvfb = subprocess.Popen([
        "Xvfb", display,
        "-screen", "0", "1280x800x24",
        "-nolisten", "tcp"
    ])
    time.sleep(1)

    driver = None

    try:
        options = Options()
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")

        driver = webdriver.Chrome(options=options)
        driver.set_window_size(1280, 800)
        driver.get(url)

        cur = conn.cursor()
        cur.execute("UPDATE sessions SET status='streaming' WHERE id=%s", (sid,))

        ws = await websockets.connect(f"{WS_SERVER}/{sid}", max_size=10_000_000)
        print(f"🖥 Streaming {url} for session {sid}")

        while True:
            # DB kill-switch
            cur = conn.cursor()
            cur.execute("SELECT status FROM sessions WHERE id=%s", (sid,))
            status = cur.fetchone()[0]

            if status == "ended":
                print(f"🛑 Session {sid} ended by user")
                break

            png = driver.get_screenshot_as_png()
            img = Image.open(io.BytesIO(png)).resize((1280,800))

            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=55, optimize=True)

            try:
                await ws.send(buf.getvalue())
            except ConnectionClosed:
                print(f"🔌 Viewer disconnected for session {sid}")
                break

            await asyncio.sleep(0.08)  # ~12 FPS

    except Exception as e:
        print(f"❌ Session {sid} failed:", e)

    finally:
        try:
            if driver:
                driver.quit()
        except:
            pass

        xvfb.terminate()
        print(f"🧹 Chrome destroyed for session {sid}")


# ---------------- CONCURRENT SQS LOOP ----------------
async def main():
    active = set()

    while True:
        resp = sqs.receive_message(
            QueueUrl=SQS_URL,
            MaxNumberOfMessages=5,
            WaitTimeSeconds=5
        )

        if "Messages" in resp:
            for msg in resp["Messages"]:
                sid, url = msg["Body"].split("|")

                task = asyncio.create_task(stream_browser(sid, url))
                active.add(task)
                task.add_done_callback(active.discard)

                sqs.delete_message(
                    QueueUrl=SQS_URL,
                    ReceiptHandle=msg["ReceiptHandle"]
                )

        await asyncio.sleep(1)

asyncio.run(main())
