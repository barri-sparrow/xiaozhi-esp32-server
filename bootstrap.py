import os, time, pathlib, subprocess, signal, urllib.request
import pymysql
import yaml

os.chdir("/opt/xiaozhi-esp32-server")
storage = pathlib.Path("/var/data")
storage.mkdir(exist_ok=True)
data = pathlib.Path("data")
if not data.is_symlink():
    import shutil
    if data.exists():
        shutil.rmtree(data)
    (storage / "data").mkdir(exist_ok=True)
    data.symlink_to(storage / "data", target_is_directory=True)
model = storage / "model.pt"
model.parent.mkdir(parents=True, exist_ok=True)
if not model.exists():
    print("Downloading SenseVoiceSmall model", flush=True)
    urllib.request.urlretrieve(
        "https://huggingface.co/FunAudioLLM/SenseVoiceSmall/resolve/main/model.pt",
        str(model) + ".part")
    pathlib.Path(str(model) + ".part").replace(model)

target = pathlib.Path("models/SenseVoiceSmall/model.pt")
target.parent.mkdir(parents=True, exist_ok=True)
if not target.is_symlink():
    if target.exists():
        target.unlink()
    target.symlink_to(model)
secret = None
for attempt in range(180):
    try:
        with pymysql.connect(host=os.environ["DB_HOST"], user="xiaozhi",
                password=os.environ["DB_PASSWORD"], database="xiaozhi_esp32_server",
                connect_timeout=10, read_timeout=10) as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT param_value FROM sys_params WHERE param_code=%s", ("server.secret",))
                row = cursor.fetchone()
                if row and row[0]:
                    secret = row[0]
                    break
    except pymysql.MySQLError:
        pass
    print("Waiting for manager database initialization", flush=True)
    time.sleep(10)
if not secret:
    raise RuntimeError("Manager did not initialize server.secret")
base = "https://" + os.environ["RENDER_EXTERNAL_HOSTNAME"]
config = {
    "server": {"ip": "0.0.0.0", "port": 8000, "http_port": 8003,
        "websocket": base.replace("https://", "wss://") + "/xiaozhi/v1/",
        "vision_explain": base + "/mcp/vision/explain"},
    "manager-api": {"url": "http://" + os.environ["MANAGER_HOST"] + ":8002/xiaozhi", "secret": secret},
    "prompt_template": "agent-base-prompt.txt",
}
pathlib.Path("data").mkdir(exist_ok=True)
with open("data/.config.yaml", "w", encoding="utf-8") as file:
    yaml.safe_dump(config, file, allow_unicode=True)
app = subprocess.Popen(["python", "app.py"])
proxy = subprocess.Popen(["nginx", "-g", "daemon off;"])
def stop(*_):
    app.terminate()
    proxy.terminate()
signal.signal(signal.SIGTERM, stop)
signal.signal(signal.SIGINT, stop)
try:
    while app.poll() is None and proxy.poll() is None:
        time.sleep(1)
finally:
    stop()
    for process in (app, proxy):
        try:
            process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            process.kill()
raise SystemExit(app.returncode or proxy.returncode or 1)
