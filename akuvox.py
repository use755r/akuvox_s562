# akuvox.py
import base64, string, random, time, ssl
import requests
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from requests.adapters import HTTPAdapter
from urllib3.util.ssl_ import create_urllib3_context
import urllib3
urllib3.disable_warnings()

FIXED_KEY = b"rBd3mQ68jfEGo3K3"
IV        = b"0000000000000000"


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


def _aes(key, data):
    return base64.b64encode(
        AES.new(key, AES.MODE_CBC, IV).encrypt(pad(data.encode(), 16))
    ).decode()


def _Et(n):
    return "".join(random.choice(string.ascii_letters + string.digits) for _ in range(n))


def _session(token, aes_key):
    ts = str(int(time.time() * 1000))
    return token + _aes(aes_key.encode(), ts + _Et(64) + "akuvox")


def _try_login(ip, user, password):
    print(f"  [login] {ip} user={user} password={'*' * len(password)}")
    s = requests.Session()
    s.verify = False
    s.mount("https://", LegacyTLS())
    try:
        print(f"  [login] -> set")
        r = s.post(f"https://{ip}/web", json={
            "target": "login", "action": "set",
            "data": {"password": _aes(FIXED_KEY, FIXED_KEY.decode() + password)},
            "session": "", "web": "1"
        }, timeout=10).json()
        print(f"  [login] <- set retcode={r.get('retcode')} msg={r.get('message')}")
        if r.get("retcode") != 0: return None

        print(f"  [login] -> login")
        r = s.post(f"https://{ip}/web", json={
            "target": "login", "action": "login",
            "data": {"userName": user, "password": _aes(FIXED_KEY, r["data"]["encrypt"])},
            "session": "", "web": "1"
        }, timeout=10).json()
        print(f"  [login] <- login retcode={r.get('retcode')} msg={r.get('message')}")
        if r.get("retcode") != 0: return None
        print(f"  [login] OK token={r['data']['token']} aesKey={r['data']['aesKey']}")
        return s, r["data"]["token"], r["data"]["aesKey"]
    except Exception as e:
        print(f"  [login] ошибка: {e}")
        return None


def _send(s, ip, token, aes_key, action, items):
    print(f"  [config] -> {action} {items}")
    r = s.post(f"https://{ip}/web", json={
        "target": "config", "action": action,
        "configData": {"item": items},
        "session": _session(token, aes_key), "web": "1"
    }, headers={"Cookie": f"token={token}"}, timeout=10).json()
    print(f"  [config] <- {action} retcode={r.get('retcode')} data={r.get('data')}")
    return r


def _key_id(zone):
    return 11 + (zone - 1) * 32


def set_zone_status(ip, zone, status, user="admin",
                    passwords=("158103Msi", "admin")):
    """status: 0=выкл, 1=вкл, 2=24H"""
    print(f"[zone] set_zone_status ip={ip} zone={zone} status={status}")
    auth = None
    for pwd in passwords:
        auth = _try_login(ip, user, pwd)
        if auth: break
    if not auth:
        print(f"[zone] ❌ auth failed")
        return {"ok": False, "ip": ip, "zone": zone, "status": status,
                "error": "auth failed"}

    s, token, aes_key = auth
    item = f"{status}&54&{_key_id(zone)}"
    r = _send(s, ip, token, aes_key, "edit", [item])
    ok = r.get("retcode") == 0
    print(f"[zone] {'✅' if ok else '❌'} zone={zone} status={status}")
    return {"ok": ok, "ip": ip, "zone": zone,
            "status": status, "response": r}


def open_door(ip, user="admin", password="158103Msi", door=1, timeout=5):
    """Открыть дверь через FCGI (обычный HTTP)."""
    url = (f"http://{ip}/fcgi/do"
           f"?action=OpenDoor&UserName={user}&Password={password}&DoorNum={door}")
    print(f"[door] -> GET {url}")
    try:
        r = requests.get(url, timeout=timeout)
        print(f"[door] <- {r.status_code} {r.text[:100]!r}")
        return {"ok": r.status_code == 200, "ip": ip, "door": door,
                "status_code": r.status_code, "text": r.text[:200]}
    except Exception as e:
        print(f"[door] ошибка: {e}")
        return {"ok": False, "ip": ip, "door": door, "error": str(e)}