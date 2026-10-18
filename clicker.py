"""클릭 백엔드 분리 모듈.

config.json 의 "click_backend" 값만 바꾸면 pyautogui <-> pydirectinput 전환이 됩니다.
다른 라이브러리를 쓰고 싶으면 _BACKENDS 에 (mouseDown, mouseUp) 를 돌려주는 함수를 추가하세요.
"""
import random
import time


def _pyautogui():
    import pyautogui

    pyautogui.PAUSE = 0  # 호출마다 붙는 기본 0.1초 지연 제거
    return (
        lambda: pyautogui.mouseDown(button="right"),
        lambda: pyautogui.mouseUp(button="right"),
    )


def _pydirectinput():
    import pydirectinput

    pydirectinput.PAUSE = 0
    return (
        lambda: pydirectinput.mouseDown(button="right"),
        lambda: pydirectinput.mouseUp(button="right"),
    )


_BACKENDS = {
    "pyautogui": _pyautogui,
    "pydirectinput": _pydirectinput,
}


def make_right_click(backend="pyautogui", hold_range=(0.04, 0.09)):
    """우클릭 함수를 만들어 돌려준다. 누르고 있는 시간도 약간 랜덤."""
    if backend not in _BACKENDS:
        raise ValueError(f"알 수 없는 click_backend: {backend!r} (가능: {', '.join(_BACKENDS)})")
    down, up = _BACKENDS[backend]()

    def right_click():
        down()
        time.sleep(random.uniform(*hold_range))
        up()

    return right_click
