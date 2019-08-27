import sys
import rsa
import json
import time
import base64
import pygame
import logging
import hashlib
import asyncio
import aiohttp
import requests
import traceback
import configparser
from urllib import parse
from threading import Thread
from pygame.constants import QUIT, KEYUP, K_LEFT, K_RIGHT


log_format = logging.Formatter("%(asctime)s [%(levelname)s]: %(message)s")
console = logging.StreamHandler(sys.stdout)
console.setFormatter(log_format)
console_logger = logging.getLogger("console")
console_logger.setLevel(logging.DEBUG)
console_logger.addHandler(console)
logging = console_logger


def executor(message, cookie, room_id):
    req_url = "https://api.live.bilibili.com/msg/send"
    headers = {
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;"
            "q=0.9,image/webp,image/apng,*/*;q=0.8"
        ),
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_0) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/70.0.3538.110 Safari/537.36"
        ),
        "Cookie": cookie,
    }

    bili_jct = ""
    for kv in cookie.split(";"):
        if "bili_jct" in kv:
            bili_jct = kv.split("=")[1]
            break

    data = {
        "color": 0xffffff,
        "fontsize": 25,
        "mode": 1,
        "msg": message,
        "rnd": int(time.time()),
        "roomid": room_id,
        "bubble": 0,
        "csrf_token": bili_jct,
        "csrf": bili_jct,
    }
    try:
        r = requests.post(url=req_url, headers=headers, data=data)
        print(r.status_code, r.content.decode("utf-8"))
    except Exception as e:
        print(f"Exception: {e}")


class CookieFetcher:
    appkey = "1d8b6e7d45233436"
    actionKey = "appkey"
    build = "520001"
    device = "android"
    mobi_app = "android"
    platform = "android"
    app_secret = "560c52ccd288fed045859ed18bffd973"
    refresh_token = ""
    access_key = ""
    cookie = ""
    csrf = ""
    uid = ""

    pc_headers = {
        "Accept-Language": "zh-CN,zh;q=0.9",
        "accept-encoding": "gzip, deflate",
        "Accept": "application/json, text/plain, */*",
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_3) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/62.0.3202.94 Safari/537.36"
        ),
    }
    app_headers = {
        "User-Agent": "bili-universal/6570 CFNetwork/894 Darwin/17.4.0",
        "Accept-encoding": "gzip",
        "Buvid": "000ce0b9b9b4e342ad4f421bcae5e0ce",
        "Display-ID": "146771405-1521008435",
        "Accept-Language": "zh-CN",
        "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
        "Connection": "keep-alive",
    }

    @classmethod
    def calc_sign(cls, text):
        text = f'{text}{cls.app_secret}'
        return hashlib.md5(text.encode('utf-8')).hexdigest()

    @classmethod
    async def _request(cls, method, url, params=None, data=None, headers=None, timeout=5):
        client_session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout))
        try:
            async with client_session as session:
                if method.lower() == "get":
                    async with session.get(url, params=params, data=data, headers=headers) as resp:
                        status_code = resp.status
                        content = await resp.text()
                        return status_code, content

                else:
                    async with session.post(url, data=data, params=params, headers=headers) as resp:
                        status_code = resp.status
                        content = await resp.text()
                        return status_code, content
        except Exception as e:
            return 5000, f"Error happend: {e}\n {traceback.format_exc()}"

    @classmethod
    async def fetch_key(cls):
        url = 'https://passport.bilibili.com/api/oauth2/getKey'

        sign = cls.calc_sign(f'appkey={cls.appkey}')
        data = {'appkey': cls.appkey, 'sign': sign}

        status_code, content = await cls._request("post", url=url, data=data)
        if status_code != 200:
            return False, content

        try:
            json_response = json.loads(content)
        except Exception as e:
            return False, f"Not json response! {e}"

        if json_response["code"] != 0:
            return False, json_response.get("message", "unknown error!")

        return True, json_response

    @classmethod
    async def post_login_req(cls, url_name, url_password, captcha=''):
        temp_params = (
            f'actionKey={cls.actionKey}'
            f'&appkey={cls.appkey}'
            f'&build={cls.build}'
            f'&captcha={captcha}'
            f'&device={cls.device}'
            f'&mobi_app={cls.mobi_app}'
            f'&password={url_password}'
            f'&platform={cls.platform}'
            f'&username={url_name}'
        )
        sign = cls.calc_sign(temp_params)
        payload = f'{temp_params}&sign={sign}'
        url = "https://passport.bilibili.com/api/v2/oauth2/login"

        content = ""
        for _ in range(10):
            status_code, content = await cls._request('POST', url, params=payload)
            if status_code == 200 and content:
                break
            await asyncio.sleep(4)
        else:
            return False, f"Try too many times! last content: {content}"

        try:
            json_response = json.loads(content)
        except Exception as e:
            return False, f"Not json response! {e}"

        return True, json_response

    @classmethod
    async def get_cookie(cls, account, password):
        flag, json_rsp = await cls.fetch_key()
        if not flag:
            return False

        key = json_rsp['data']['key']
        hash_ = str(json_rsp['data']['hash'])

        pubkey = rsa.PublicKey.load_pkcs1_openssl_pem(key.encode())
        hashed_password = base64.b64encode(rsa.encrypt((hash_ + password).encode('utf-8'), pubkey))
        url_password = parse.quote_plus(hashed_password)
        url_name = parse.quote_plus(account)

        flag, json_rsp = await cls.post_login_req(url_name, url_password)
        if not flag:
            return False, json_rsp

        if json_rsp["code"] != 0:
            return False, json_rsp.get("message", "unknown error in login!")

        cookies = json_rsp["data"]["cookie_info"]["cookies"]
        result = []
        for c in cookies:
            result.append(f"{c['name']}={c['value']}; ")

        return True, "".join(result).strip()


class Core:
    def __init__(self):
        self.cookie = None
        self.room_id = None

        self.caption = "坏蛋！"
        self.icon_file = "source/icon.png"
        self.font_file = "source/ncsj.ttf"
        self.cookie_file = "source/cookie.dat"

        self.win_size = (960, 720)
        self.font_size = 22
        self.lines = self.win_size[1] // self.font_size

        self.screen = None
        self.clock = None
        self.font = None

        self.buff = []
        self.need_update = True
        self.lyric_content = []

    def initialization(self):
        pygame.init()
        pygame.display.set_caption(self.caption)
        pygame.display.set_icon(pygame.image.load(self.icon_file))
        self.screen = pygame.display.set_mode(self.win_size)
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(self.font_file, self.font_size)

    def print(self, message):
        if len(self.buff) >= self.lines:
            self.buff.pop(0)
        self.buff.append(message)
        self.need_update = True

    def flush_surface(self, offset=None):
        self.clock.tick(30)

        if not self.need_update and not offset:
            return

        self.screen.fill((30, 30, 30))

        y_offset = 0
        for line in self.buff:
            context = self.font.render(line, True, (222, 100, 70))
            self.screen.blit(context, (0, y_offset))
            y_offset += self.font_size

        if offset:
            context = self.font.render(f"当前时间：{offset//60:.0f}分{offset%60:.2f}", True, (222, 100, 180))
            self.screen.blit(context, (self.win_size[0] - 400, 0))

        pygame.display.update()
        self.need_update = False

    def wait_for_starting(self):
        lyric_content = []
        with open("song.lrc", "r", encoding="utf-8") as f:
            for l in f.readlines():
                if len(l) < 8:
                    continue

                header, body = l[1:9], l[10:]
                minute, sec = header.split(":")
                try:
                    offset = int(minute)*60 + float(sec)
                except ValueError:
                    continue

                self.print(l)
                lyric_content.append((offset, body.strip()))

        self.lyric_content = lyric_content
        self.print("-" * 80)
        self.print("按Enter键开始发送歌词。")
        self.print("中途如需停止，请按ESC键!")
        self.print("")

        while True:
            for event in pygame.event.get():
                if event.type == QUIT:
                    exit()

                if event.type == KEYUP and event.key == 13:  # enter
                    self.print("已经启动，现在开始发送歌词...")
                    return

            self.flush_surface()

    def send_lyrics(self):
        start_time = time.time()
        index = 0
        while True:
            for event in pygame.event.get():
                if event.type == QUIT:
                    exit()

                if event.type == KEYUP:
                    if event.key == K_LEFT:
                        self.print("歌词后退1秒！")
                        start_time += 1

                    if event.key == K_RIGHT:
                        self.print("歌词前进1秒！")
                        start_time -= 1

                    if event.key == 13:
                        self.print("")

                    if event.key == 27:
                        return

            current_offset = time.time() - start_time
            scan_index = index
            for offset, body in self.lyric_content[index:]:
                if offset > current_offset:
                    break

                if offset <= current_offset and current_offset - offset <= 0.1:
                    index = scan_index
                    self.print(f"[{offset//60:2.0f}:{offset%60:.2f}]{body}")
                    print(body, self.lyric_content[scan_index], index, scan_index)
                    index += 1

                    t = Thread(target=executor, args=(body, self.cookie, self.room_id))
                    t.setDaemon(True)
                    t.start()
                    break

                scan_index += 1

            self.flush_surface(current_offset)

    def load_account_config(self):
        # login
        config = configparser.ConfigParser()
        config.read("config.yml")
        account = config["账号信息"]["账号"]
        password = config["账号信息"]["密码"]
        self.room_id = config["房间号"]["房间号"]

        try:
            with open(self.cookie_file, "rb") as f:
                cached_data = f.read()
            cookie = json.loads(cached_data.decode("utf-8"))
        except Exception as e:
            logging.info(f"未发现缓存过的cookie，现在需要登陆. e: {e}")
            cookie = None

        if cookie:
            req_url = f"https://api.live.bilibili.com/sign/doSign"
            headers = {
                "Accept": (
                    "text/html,application/xhtml+xml,application/xml;"
                    "q=0.9,image/webp,image/apng,*/*;q=0.8"
                ),
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_0) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/70.0.3538.110 Safari/537.36"
                ),
                "Cookie": cookie,
            }
            try:
                r = requests.get(url=req_url, headers=headers)
                if r.status_code != 200:
                    raise Exception("登录失败")

                result = json.loads(r.content.decode("utf-8"))
                if result["code"] == -401:
                    raise Exception("登陆过期！")

                self.cookie = cookie
                return
            except Exception as e:
                logging.error(f"检查cookie时发现已失效： {e}")

        loop = asyncio.get_event_loop()
        flag, cookie = loop.run_until_complete(CookieFetcher.get_cookie(account, password))
        loop.close()
        if flag:
            with open(self.cookie_file, "wb") as f:
                f.write(json.dumps(cookie).encode("utf-8"))
            logging.info(f"账号登陆成功！")
            self.cookie = cookie
            return

        # Invalid Account
        self.print("账号错误，无法登陆bilibili！")
        while True:
            for event in pygame.event.get():
                if event.type == QUIT:
                    exit()
            self.flush_surface()

    def run(self):
        self.initialization()
        self.load_account_config()

        while True:
            self.wait_for_starting()
            self.send_lyrics()
