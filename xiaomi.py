"""Minimalni Xiaomi cloud klijent (MIoT) za citanje podataka s preciscaca.

Logika logina i RC4 enkripcije prati poznati open-source Xiaomi cloud
tokens extractor. Token se kesira u TOKEN_FILE da se ne loguje svaki put.
"""
import base64
import hashlib
import json
import os
import random
import string
import time

import requests
from Crypto.Cipher import ARC4

UA = ("Android-7.1.1-1.0.0-ONEPLUS A3010-136-"
      + "".join(random.choice("ABCDEF") for _ in range(13))
      + " APP/xiaomi.smarthome APPV/62830")
SERVERS = ["de", "i2", "ru", "sg", "us", "cn"]


class XiaomiError(Exception):
    pass


def _strip(text):
    return json.loads(text.replace("&&&START&&&", ""))


class XiaomiCloud:
    def __init__(self, username, password, token_file=None,
                 pass_token=None, user_id=None, device_id=None):
        self.username = username or user_id
        self.password = password
        self.pass_token = pass_token
        self.pt_user_id = user_id
        self.token_file = token_file
        self.s = requests.Session()
        self.device_id = device_id or "".join(random.choice(string.ascii_letters) for _ in range(16))
        self.user_id = None
        self.ssecurity = None
        self.service_token = None

    # ---------- token cache ----------
    def load_token(self):
        if not self.token_file or not os.path.exists(self.token_file):
            return False
        try:
            with open(self.token_file) as f:
                t = json.load(f)
            if t.get("username") != self.username:
                return False
            self.user_id = t["user_id"]
            self.ssecurity = t["ssecurity"]
            self.service_token = t["service_token"]
            return True
        except Exception:
            return False

    def save_token(self):
        if not self.token_file:
            return
        with open(self.token_file, "w") as f:
            json.dump({"username": self.username, "user_id": self.user_id,
                       "ssecurity": self.ssecurity,
                       "service_token": self.service_token}, f)

    # ---------- login ----------
    def login(self):
        if self.pass_token and self.pt_user_id:
            return self.login_pass_token()
        return self.login_password()

    def login_pass_token(self):
        """Login preko passToken cookieja iz browsera (bez lozinke i bez 2FA)."""
        s = requests.Session()
        s.headers.update({"User-Agent": UA})
        for dom in ("account.xiaomi.com", ".xiaomi.com"):
            s.cookies.set("passToken", self.pass_token, domain=dom)
            s.cookies.set("userId", str(self.pt_user_id), domain=dom)
            s.cookies.set("deviceId", self.device_id, domain=dom)
            s.cookies.set("sdkVersion", "accountsdk-18.8.15", domain=dom)
        r = s.get("https://account.xiaomi.com/pass/serviceLogin?sid=xiaomiio&_json=true", timeout=20)
        j = _strip(r.text)
        if not j.get("ssecurity") or not j.get("location"):
            raise XiaomiError("passToken login nije uspio (istekao ili pogresan?) code=%s desc=%s"
                              % (j.get("code"), j.get("desc")))
        self.ssecurity = j["ssecurity"]
        self.user_id = str(j.get("userId") or self.pt_user_id)
        r = s.get(j["location"], timeout=20)
        token = r.cookies.get("serviceToken") or s.cookies.get("serviceToken")
        if not token:
            raise XiaomiError("passToken login: nema serviceToken")
        self.service_token = token
        print("[xiaomi] login preko passToken ok")
        self.save_token()

    def login_password(self):
        self.s = requests.Session()
        self.s.headers.update({"User-Agent": UA,
                               "Content-Type": "application/x-www-form-urlencoded"})
        self.s.cookies.set("sdkVersion", "accountsdk-18.8.15", domain="mi.com")
        self.s.cookies.set("sdkVersion", "accountsdk-18.8.15", domain="xiaomi.com")
        self.s.cookies.set("deviceId", self.device_id, domain="mi.com")
        self.s.cookies.set("deviceId", self.device_id, domain="xiaomi.com")

        r = self.s.get("https://account.xiaomi.com/pass/serviceLogin?sid=xiaomiio&_json=true",
                       cookies={"userId": self.username}, timeout=20)
        sign = _strip(r.text).get("_sign")
        if not sign:
            raise XiaomiError("login korak 1: nema _sign")

        data = {
            "sid": "xiaomiio",
            "hash": hashlib.md5(self.password.encode()).hexdigest().upper(),
            "callback": "https://sts.api.io.mi.com/sts",
            "qs": "%3Fsid%3Dxiaomiio%26_json%3Dtrue",
            "user": self.username,
            "_sign": sign,
            "_json": "true",
        }
        r = self.s.post("https://account.xiaomi.com/pass/serviceLoginAuth2",
                        data=data, timeout=20)
        j = _strip(r.text)
        if j.get("notificationUrl"):
            raise XiaomiError("Xiaomi trazi dodatnu verifikaciju (2FA): "
                              + j["notificationUrl"])
        if "ssecurity" not in j or not j.get("location"):
            raise XiaomiError("login korak 2 nije uspio (pogresan user/lozinka?) code=%s desc=%s"
                              % (j.get("code"), j.get("desc")))
        self.ssecurity = j["ssecurity"]
        self.user_id = str(j["userId"])

        r = self.s.get(j["location"], timeout=20)
        token = r.cookies.get("serviceToken") or self.s.cookies.get("serviceToken")
        if not token:
            raise XiaomiError("login korak 3: nema serviceToken")
        self.service_token = token
        self.save_token()

    # ---------- RC4 potpisani zahtjevi ----------
    @staticmethod
    def _nonce():
        rnd = os.urandom(8)
        t = int(time.time() / 60).to_bytes(4, "big")
        return base64.b64encode(rnd + t).decode()

    def _signed_nonce(self, nonce):
        h = hashlib.sha256(base64.b64decode(self.ssecurity) + base64.b64decode(nonce))
        return base64.b64encode(h.digest()).decode()

    @staticmethod
    def _rc4(key_b64, payload):
        c = ARC4.new(base64.b64decode(key_b64))
        c.encrypt(bytes(1024))
        return c

    def _enc(self, key, text):
        return base64.b64encode(self._rc4(key, None).encrypt(text.encode())).decode()

    def _dec(self, key, text):
        return self._rc4(key, None).decrypt(base64.b64decode(text))

    @staticmethod
    def _sig(url, method, signed_nonce, params):
        parts = [method.upper(), url.split("com")[1].replace("/app/", "/")]
        for k, v in params.items():
            parts.append(f"{k}={v}")
        parts.append(signed_nonce)
        return base64.b64encode(hashlib.sha1("&".join(parts).encode()).digest()).decode()

    def _call(self, server, path, payload):
        prefix = "" if server == "cn" else server + "."
        url = f"https://{prefix}api.io.mi.com/app{path}"
        nonce = self._nonce()
        sn = self._signed_nonce(nonce)
        params = {"data": json.dumps(payload)}
        params["rc4_hash__"] = self._sig(url, "POST", sn, params)
        params = {k: self._enc(sn, v) for k, v in params.items()}
        params["signature"] = self._sig(url, "POST", sn, params)
        params["ssecurity"] = self.ssecurity
        params["_nonce"] = nonce
        headers = {
            "Accept-Encoding": "identity",
            "User-Agent": UA,
            "Content-Type": "application/x-www-form-urlencoded",
            "x-xiaomi-protocal-flag-cli": "PROTOCAL-HTTP2",
            "MIOT-ENCRYPT-ALGORITHM": "ENCRYPT-RC4",
        }
        cookies = {
            "userId": str(self.user_id),
            "yetAnotherServiceToken": self.service_token,
            "serviceToken": self.service_token,
            "locale": "en_GB",
            "timezone": "GMT+01:00",
            "is_daylight": "0",
            "dst_offset": "0",
            "channel": "MI_APP_STORE",
        }
        r = requests.post(url, data=params, headers=headers, cookies=cookies, timeout=20)
        if r.status_code in (401, 403):
            raise PermissionError("token istekao")
        r.raise_for_status()
        return json.loads(self._dec(sn, r.text))

    def get_props(self, did, pairs, server=None):
        """pairs: lista (siid, piid). Vraca dict {(siid,piid): value}."""
        if not self.load_token():
            self.login()
        payload = {"params": [{"did": str(did), "siid": s, "piid": p} for s, p in pairs]}
        servers = [server] if server else SERVERS
        last = None
        for attempt in range(2):
            for srv in servers:
                try:
                    res = self._call(srv, "/miotspec/prop/get", payload)
                except PermissionError:
                    last = "token"
                    break
                except Exception as e:  # mrezne greske, pogresan server
                    last = e
                    continue
                if res.get("code") == 0:
                    out = {}
                    for item in res.get("result", []):
                        if item.get("code") == 0:
                            out[(item["siid"], item["piid"])] = item.get("value")
                    if out:
                        print(f"[xiaomi] server={srv} ok, {len(out)} vrijednosti")
                        return out, srv
                last = res
            if attempt == 0:
                print(f"[xiaomi] ponovni login ({last})")
                self.login()
        raise XiaomiError(f"nije uspjelo citanje: {last}")
