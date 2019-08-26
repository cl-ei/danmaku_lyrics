import time
import sys
import pygame
import logging
import requests
from threading import Thread
from pygame.constants import QUIT, KEYUP, K_LEFT, K_RIGHT


log_format = logging.Formatter("%(asctime)s [%(levelname)s]: %(message)s")
console = logging.StreamHandler(sys.stdout)
console.setFormatter(log_format)
console_logger = logging.getLogger("console")
console_logger.setLevel(logging.DEBUG)
console_logger.addHandler(console)
logging = console_logger


def executor(message, bili_jct, SESSDATA, room_id):
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
        "Cookie": f"bili_jct={bili_jct}; SESSDATA={SESSDATA};",
    }
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


class Core:
    def __init__(self, bili_jct, SESSDATA, room_id):
        self.bili_jct = bili_jct
        self.SESSDATA = SESSDATA
        self.room_id = room_id

        self.caption = "坏蛋！"
        self.icon_file = "source/icon.png"
        self.font_file = "source/ncsj.ttf"

        self.win_size = (1280, 720)
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
        with open("song.lrc") as f:
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

                    t = Thread(target=executor, args=(body, self.bili_jct, self.SESSDATA, self.room_id))
                    t.setDaemon(True)
                    t.start()
                    break

                scan_index += 1

            self.flush_surface(current_offset)

    def run(self):
        self.initialization()

        while True:
            self.wait_for_starting()
            self.send_lyrics()
