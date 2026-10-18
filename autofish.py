"""마인크래프트 자바 에디션 자동 낚시 (Windows).

자막 영역을 mss 로 캡처하고 OpenCV 템플릿 매칭으로 "Fishing Bobber splashes" 자막을 감지한다.

    python autofish.py              # 저장된 영역/템플릿이 없으면 설정부터 진행
    python autofish.py --setup      # 영역 + 템플릿 다시 지정
    python autofish.py --region     # 영역만 다시 지정
    python autofish.py --template   # 템플릿만 다시 캡처
"""
import ctypes
import sys


def set_dpi_awareness():
    """좌표가 실제 픽셀과 어긋나지 않도록, 다른 라이브러리를 import 하기 전에 호출."""
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PROCESS_PER_MONITOR_DPI_AWARE
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


set_dpi_awareness()

import argparse  # noqa: E402
import json  # noqa: E402
import logging  # noqa: E402
import random  # noqa: E402
import threading  # noqa: E402
import time  # noqa: E402
from pathlib import Path  # noqa: E402

import cv2  # noqa: E402
import keyboard  # noqa: E402
import mss  # noqa: E402
import numpy as np  # noqa: E402

from clicker import make_right_click  # noqa: E402

# mss 10.x 부터 mss.mss 는 deprecated, mss.MSS 사용
new_mss = getattr(mss, "MSS", None) or mss.mss

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.json"
REGION_PATH = BASE_DIR / "region.json"
TEMPLATE_PATH = BASE_DIR / "template.png"

DEFAULT_CONFIG = {
    "match_threshold": 0.8,
    "reaction_delay": [0.2, 0.6],
    "recast_delay": [1.0, 2.0],
    "bite_timeout": 30,
    "cast_grace": 3.5,
    "scan_interval": 0.05,
    "log_interval": 1.0,
    "click_backend": "pyautogui",
    "click_hold": [0.04, 0.09],
    "toggle_key": "f8",
    "capture_key": "f9",
    "quit_key": "f10",
    "monitor_index": 1,
    "binarize": False,
    "binarize_level": 180,
}

log = logging.getLogger("autofish")


# ---------------------------------------------------------------- 설정 파일

def load_config():
    cfg = dict(DEFAULT_CONFIG)
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, encoding="utf-8") as f:
            cfg.update(json.load(f))
    else:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_CONFIG, f, indent=2, ensure_ascii=False)
        log.info("기본 설정 파일을 만들었습니다: %s", CONFIG_PATH.name)
    return cfg


def load_region():
    if not REGION_PATH.exists():
        return None
    with open(REGION_PATH, encoding="utf-8") as f:
        return json.load(f)


def load_template():
    if not TEMPLATE_PATH.exists():
        return None
    # cv2.imread 는 한글 경로를 못 읽어서 imdecode 사용
    data = np.fromfile(str(TEMPLATE_PATH), dtype=np.uint8)
    return cv2.imdecode(data, cv2.IMREAD_COLOR)


def save_template(img):
    ok, buf = cv2.imencode(".png", img)
    if not ok:
        raise RuntimeError("템플릿 PNG 인코딩 실패")
    buf.tofile(str(TEMPLATE_PATH))


# ---------------------------------------------------------------- 이미지 처리

def grab_bgr(sct, region):
    """mss 는 BGRA 를 돌려주므로 알파 채널을 버린다."""
    return np.ascontiguousarray(np.array(sct.grab(region))[:, :, :3])


def preprocess(img_bgr, cfg):
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    if cfg["binarize"]:
        _, gray = cv2.threshold(gray, cfg["binarize_level"], 255, cv2.THRESH_BINARY)
    return gray


def match_score(frame_gray, tmpl_gray):
    result = cv2.matchTemplate(frame_gray, tmpl_gray, cv2.TM_CCOEFF_NORMED)
    # 단색 구간(빈 화면, 이진화 후 전부 검정 등)은 OpenCV 가 1.0 을 돌려주므로 0 으로 처리
    th, tw = tmpl_gray.shape[:2]
    ii, ii2 = cv2.integral2(frame_gray, sdepth=cv2.CV_64F, sqdepth=cv2.CV_64F)
    s = ii[th:, tw:] - ii[:-th, tw:] - ii[th:, :-tw] + ii[:-th, :-tw]
    s2 = ii2[th:, tw:] - ii2[:-th, tw:] - ii2[th:, :-tw] + ii2[:-th, :-tw]
    n = th * tw
    var = s2 / n - (s / n) ** 2
    result[var < 1.0] = 0
    result = np.nan_to_num(result, nan=0.0, posinf=0.0, neginf=0.0)
    return float(result.max())


def select_roi(title, img):
    """드래그로 사각형을 지정. 선택 없이 Enter 를 누르면 None."""
    cv2.namedWindow(title, cv2.WINDOW_NORMAL)
    try:
        cv2.setWindowProperty(title, cv2.WND_PROP_TOPMOST, 1)
    except cv2.error:
        pass
    x, y, w, h = cv2.selectROI(title, img, showCrosshair=False, fromCenter=False)
    cv2.destroyWindow(title)
    cv2.waitKey(1)
    if w == 0 or h == 0:
        return None
    return int(x), int(y), int(w), int(h)


# ---------------------------------------------------------------- 최초 설정

def setup_region(cfg):
    key = cfg["capture_key"].upper()
    print()
    print("=== ① 자막 영역 지정 ===")
    print("1. 마인크래프트에서 설정 > 접근성 > '자막 표시'를 켜세요.")
    print("2. 낚싯대를 던져 오른쪽 아래에 자막이 보이게 하세요.")
    print(f"3. 게임 화면에서 {key} 를 누르면 화면이 캡처됩니다.")
    print("   → 뜨는 창에서 자막 상자가 나타나는 범위를 넉넉하게 드래그하고 Enter.")
    print("     (자막이 여러 줄 쌓일 수 있으니 위아래로 여유 있게)")
    keyboard.wait(cfg["capture_key"])

    with new_mss() as sct:
        mon = sct.monitors[cfg["monitor_index"]]
        shot = grab_bgr(sct, mon)

    while True:
        roi = select_roi("Drag subtitle area, then Enter", shot)
        if roi:
            break
        print("선택된 영역이 없습니다. 다시 드래그하세요.")

    x, y, w, h = roi
    region = {"left": mon["left"] + x, "top": mon["top"] + y, "width": w, "height": h}
    with open(REGION_PATH, "w", encoding="utf-8") as f:
        json.dump(region, f, indent=2)
    log.info("자막 영역 저장: %s", region)
    return region


def setup_template(cfg, region):
    key = cfg["capture_key"].upper()
    print()
    print("=== ② 입질 자막 템플릿 캡처 ===")
    print("1. 낚싯대를 던지고 기다리세요.")
    print(f"2. 'Fishing Bobber splashes' 자막이 뜬 순간 {key} 를 누르세요. (자막은 몇 초간 남아 있음)")
    print("3. 뜨는 창에서 'Fishing Bobber splashes' 글자 부분만 딱 맞게 드래그하고 Enter.")
    print("   (좌우의 < > 화살표는 방향에 따라 바뀌므로 빼는 게 좋습니다)")

    with new_mss() as sct:
        while True:
            keyboard.wait(cfg["capture_key"])
            shot = grab_bgr(sct, region)
            roi = select_roi("Drag 'Fishing Bobber splashes' text, then Enter", shot)
            if roi:
                break
            print(f"선택된 영역이 없습니다. 자막이 다시 뜨면 {key} 를 누르세요.")

    x, y, w, h = roi
    tmpl = shot[y:y + h, x:x + w].copy()
    save_template(tmpl)
    log.info("템플릿 저장: %s (%dx%d)", TEMPLATE_PATH.name, w, h)
    return tmpl


# ---------------------------------------------------------------- 낚시 루프

class AutoFisher:
    def __init__(self, cfg, region, template_bgr):
        self.cfg = cfg
        self.region = region
        self.tmpl = preprocess(template_bgr, cfg)
        th, tw = self.tmpl.shape[:2]
        if th > region["height"] or tw > region["width"]:
            raise SystemExit("템플릿이 자막 영역보다 큽니다. --setup 으로 다시 지정하세요.")
        if self.tmpl.std() < 1.0:
            raise SystemExit("템플릿이 단색이라 매칭할 수 없습니다. --template 으로 글자 부분을 다시 캡처하세요.")

        self.right_click = make_right_click(cfg["click_backend"], cfg["click_hold"])
        self.running = threading.Event()
        self.quit = threading.Event()

    # 핫키 콜백 (keyboard 스레드에서 호출됨)
    def toggle(self):
        if self.running.is_set():
            self.running.clear()
            log.info("■ 정지 (%s)", self.cfg["toggle_key"].upper())
        else:
            self.running.set()
            log.info("▶ 시작 (%s)", self.cfg["toggle_key"].upper())

    def stop_all(self):
        log.info("종료 (%s)", self.cfg["quit_key"].upper())
        self.running.clear()
        self.quit.set()

    def sleep(self, seconds):
        """정지/종료되면 바로 깨어나는 sleep. 계속 실행 중이면 True."""
        end = time.monotonic() + seconds
        while True:
            if not self.running.is_set() or self.quit.is_set():
                return False
            remaining = end - time.monotonic()
            if remaining <= 0:
                return True
            time.sleep(min(0.02, remaining))

    def cast(self):
        self.right_click()
        log.info("투척")

    def reel_and_recast(self, reason):
        self.right_click()
        log.info("회수 (%s)", reason)
        delay = random.uniform(*self.cfg["recast_delay"])
        if not self.sleep(delay):
            return False
        self.cast()
        return True

    def run(self):
        cfg = self.cfg
        keyboard.add_hotkey(cfg["toggle_key"], self.toggle)
        keyboard.add_hotkey(cfg["quit_key"], self.stop_all)
        log.info(
            "준비 완료. 마인크래프트에서 낚싯대를 들고 %s 로 시작/정지, %s 로 종료.",
            cfg["toggle_key"].upper(), cfg["quit_key"].upper(),
        )
        log.info(
            "임계값=%.2f, 반응지연=%s, 재투척지연=%s, 타임아웃=%ss, 클릭=%s",
            cfg["match_threshold"], cfg["reaction_delay"], cfg["recast_delay"],
            cfg["bite_timeout"], cfg["click_backend"],
        )

        with new_mss() as sct:  # mss 는 스레드마다 따로 만들어야 하므로 여기서 생성
            while not self.quit.is_set():
                if not self.running.wait(0.1):
                    continue
                self._session(sct)

        keyboard.unhook_all_hotkeys()

    def _session(self, sct):
        """F8 로 시작된 한 번의 실행. 정지되면 반환."""
        cfg = self.cfg
        self.cast()
        last_cast = time.monotonic()
        last_log = last_cast
        peak = 0.0
        catches = 0

        while self.running.is_set() and not self.quit.is_set():
            now = time.monotonic()
            score = match_score(preprocess(grab_bgr(sct, self.region), cfg), self.tmpl)
            peak = max(peak, score)

            if now - last_log >= cfg["log_interval"]:
                log.info("매칭 점수 최대 %.3f (대기 %.1fs)", peak, now - last_cast)
                peak = 0.0
                last_log = now

            # 재투척 직후에는 이전 입질 자막이 아직 남아 있으므로 무시
            in_grace = now - last_cast < cfg["cast_grace"]

            if score >= cfg["match_threshold"] and not in_grace:
                delay = random.uniform(*cfg["reaction_delay"])
                log.info("입질 감지! 점수 %.3f → %.2fs 후 회수", score, delay)
                if not self.sleep(delay):
                    break
                if not self.reel_and_recast("입질"):
                    break
                catches += 1
                log.info("누적 %d회", catches)
                last_cast = last_log = time.monotonic()
                peak = 0.0
                continue

            if now - last_cast >= cfg["bite_timeout"]:
                log.info("%ss 동안 입질 없음 → 재투척", cfg["bite_timeout"])
                if not self.reel_and_recast("타임아웃"):
                    break
                last_cast = last_log = time.monotonic()
                peak = 0.0
                continue

            if not self.sleep(cfg["scan_interval"]):
                break


# ---------------------------------------------------------------- 진입점

def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s.%(msecs)03d  %(message)s",
        datefmt="%H:%M:%S",
    )
    parser = argparse.ArgumentParser(description="Minecraft 자동 낚시")
    parser.add_argument("--setup", action="store_true", help="영역과 템플릿을 모두 다시 지정")
    parser.add_argument("--region", action="store_true", help="자막 영역만 다시 지정")
    parser.add_argument("--template", action="store_true", help="템플릿만 다시 캡처")
    args = parser.parse_args()

    cfg = load_config()

    region = None if (args.setup or args.region) else load_region()
    if region is None:
        region = setup_region(cfg)
        args.template = True  # 영역이 바뀌면 템플릿도 새로 캡처해야 함

    template = None if (args.setup or args.template) else load_template()
    if template is None:
        template = setup_template(cfg, region)

    try:
        AutoFisher(cfg, region, template).run()
    except KeyboardInterrupt:
        log.info("Ctrl+C 로 종료")


if __name__ == "__main__":
    main()
