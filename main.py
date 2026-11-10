import requests, base64, string, random, time, ssl
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from requests.adapters import HTTPAdapter
from urllib3.util.ssl_ import create_urllib3_context
import urllib3
urllib3.disable_warnings()

# ============ НАСТРОЙКИ ============
IP        = "10.18.3.124"
USER      = "admin"
PASSWORDS = ["158103Msi", "admin"]   # пробуем по порядку
ZONE      = 8
STATUS    = 2                       # 0=выкл, 1=вкл, 2=24H

FIXED_KEY = b"rBd3mQ68jfEGo3K3"
IV        = b"0000000000000000"
# ===================================


# --- TLS-адаптер для старых прошивок ---
class LegacyTLS(HTTPAdapter):
    def init_poolmanager(self, *a, **kw):
        ctx = create_urllib3_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        try: ctx.set_ciphers("DEFAULT@SECLEVEL=1")
        except: pass
        try: ctx.minimum_version = ssl.TLSVersion.TLSv1
        except: pass
        kw["ssl_context"] = ctx
        return super().init_poolmanager(*a, **kw)


def aes_cbc_b64(key: bytes, data: str) -> str:
    return base64.b64encode(
        AES.new(key, AES.MODE_CBC, IV).encrypt(pad(data.encode(), 16))
    ).decode()


def Et(n: int) -> str:
    return "".join(random.choice(string.ascii_letters + string.digits) for _ in range(n))


def make_session(token: str, aes_key: str) -> str:
    ts = str(int(time.time() * 1000))
    return token + aes_cbc_b64(aes_key.encode(), ts + Et(64) + "akuvox")


def try_login(password: str):
    """Возвращает (session, token, aes_key) или None, если пароль не подошёл."""
    s = requests.Session()
    s.verify = False
    s.mount("https://", LegacyTLS())

    try:
        pwd1 = aes_cbc_b64(FIXED_KEY, FIXED_KEY.decode() + password)
        r = s.post(f"https://{IP}/web", json={
            "target": "login", "action": "set",
            "data": {"password": pwd1},
            "session": "", "web": "1"
        }, timeout=10)
        j = r.json()
        if j.get("retcode") != 0:
            print(f"  set отказал: {j.get('retcode')} {j.get('message')}")
            return None

        pwd2 = aes_cbc_b64(FIXED_KEY, j["data"]["encrypt"])
        r = s.post(f"https://{IP}/web", json={
            "target": "login", "action": "login",
            "data": {"userName": USER, "password": pwd2},
            "session": "", "web": "1"
        }, timeout=10)
        j = r.json()
        if j.get("retcode") != 0:
            print(f"  login отказал: {j.get('retcode')} {j.get('message')}")
            return None

        return s, j["data"]["token"], j["data"]["aesKey"]

    except Exception as e:
        print(f"  ошибка: {e}")
        return None


def send_config(s, token, aes_key, action, items):
    r = s.post(f"https://{IP}/web", json={
        "target": "config", "action": action,
        "configData": {"item": items},
        "session": make_session(token, aes_key), "web": "1"
    }, headers={"Cookie": f"token={token}"}, timeout=10)
    return r.json()


def status_key_id(zone: int) -> int:
    return 11 + (zone - 1) * 32


if __name__ == "__main__":
    # --- логин с fallback ---
    auth = None
    for pwd in PASSWORDS:
        print(f"Пробую пароль '{pwd}'...")
        auth = try_login(pwd)
        if auth:
            print(f"✅ Подошёл '{pwd}'")
            break

    if not auth:
        print("❌ Ни один пароль не подошёл")
        exit(1)

    s, token, aes_key = auth

    # --- читаем ДО ---
    key = f"AlarmStatus0{ZONE}"
    item = f"{key}&54&{status_key_id(ZONE)}"

    before = send_config(s, token, aes_key, "info", [item])
    print(f"ДО:    {before}")

    # --- меняем ---
    edit = send_config(s, token, aes_key, "edit", [f"{STATUS}&54&{status_key_id(ZONE)}"])
    print(f"EDIT:  {edit}")

    # --- читаем ПОСЛЕ ---
    after = send_config(s, token, aes_key, "info", [item])
    print(f"ПОСЛЕ: {after}")

    val = after.get("data", {}).get(key)
    if val == str(STATUS):
        print(f"✅ Зона {ZONE}: статус = {val}")
    else:
        print(f"❌ Не применилось. Сейчас: {val}")