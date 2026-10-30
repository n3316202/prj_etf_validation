# ============================================================
# 파일명: mkospi_two_chrome.py
#
# 목적:
#   1. 새 Windows 가상 데스크톱 생성(선택 사항)
#   2. 일반 Chrome 창 2개 실행
#   3. 주간선물 / 야간선물 탭 각각 선택
#   4. 접근성 트리에서 갱신 시각, 현재가, 등락폭, 등락률 추출
#   5. 콘솔에 일정 간격으로 출력
#
# 설치:
#   python -m pip install pywinauto pywin32 pyautogui
#
# 참고:
#   Windows 가상 데스크톱에서 비활성 데스크톱의 창을
#   UI Automation으로 읽는 것은 Windows 환경에 따라 제한될 수 있습니다.
# ============================================================

import os
import re
import subprocess
import time
from datetime import datetime
from pathlib import Path

import pyautogui
from pywinauto import Desktop


# ============================================================
# 1. 사용자 설정
# ============================================================

URL = "https://mkospi.com/"

REFRESH_SECONDS = 10       # 시세 조회 간격(초)
PAGE_LOAD_WAIT = 12        # 페이지 로딩 대기(초)
BUTTON_WAIT = 3            # 탭 선택 후 대기(초)
WINDOW_TIMEOUT = 60        # Chrome 창 검색 제한 시간(초)

CREATE_NEW_DESKTOP = True  # 새 가상 데스크톱 생성 여부

LOCAL_APP_DATA = Path(os.environ.get("LOCALAPPDATA", str(Path.home())))
PROFILE_BASE = LOCAL_APP_DATA / "mkospi_two_chrome_profiles"
DEBUG_DIR = Path(__file__).resolve().parent / "mkospi_debug"
DEBUG_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# 2. Chrome 설치 경로 찾기
# ============================================================

def find_chrome():
    possible_paths = [
        Path(os.environ.get("PROGRAMFILES", r"C:\Program Files"))
        / "Google" / "Chrome" / "Application" / "chrome.exe",

        Path(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"))
        / "Google" / "Chrome" / "Application" / "chrome.exe",

        LOCAL_APP_DATA / "Google" / "Chrome" / "Application" / "chrome.exe",
    ]

    for path in possible_paths:
        if path.exists():
            return path

    raise FileNotFoundError(
        "Chrome 실행 파일을 찾지 못했습니다. Chrome 설치 경로를 확인하세요."
    )


# ============================================================
# 3. 새 가상 데스크톱 만들기
# ============================================================

def create_new_desktop():
    print("\n[1단계] 새 Windows 가상 데스크톱 생성")
    pyautogui.hotkey("win", "ctrl", "d")
    time.sleep(3)
    print("새 데스크톱 생성 단축키를 실행했습니다.")


# ============================================================
# 4. 현재 Chrome 창 핸들 수집
#    중요: Chrome 프로세스 PID와 창 PID가 다를 수 있으므로
#    프로세스 PID만으로 창을 찾지 않습니다.
# ============================================================

def get_chrome_windows(backend="win32"):
    found = []

    try:
        desktop = Desktop(backend=backend)

        for window in desktop.windows(visible_only=False):
            try:
                class_name = window.class_name()
                title = window.window_text()
                hwnd = window.handle

                if class_name == "Chrome_WidgetWin_1":
                    found.append({
                        "handle": hwnd,
                        "title": title,
                        "pid": window.process_id(),
                        "class_name": class_name,
                    })
            except Exception:
                continue

    except Exception as error:
        print(f"[진단] {backend} 창 검색 오류: {error!r}")

    return found


def print_chrome_windows():
    print("\n[진단] 현재 검색되는 Chrome 창")

    for backend in ("win32", "uia"):
        print(f"\n  Backend = {backend}")
        windows = get_chrome_windows(backend)

        if not windows:
            print("    Chrome 창을 찾지 못했습니다.")
            continue

        for item in windows:
            print(
                f"    HWND={item['handle']} | "
                f"PID={item['pid']} | "
                f"제목={item['title']!r}"
            )


# ============================================================
# 5. Chrome 실행
# ============================================================

def launch_chrome(session_name, chrome_path):
    print(f"\n[{session_name}] Chrome 실행")

    profile_dir = PROFILE_BASE / session_name
    profile_dir.mkdir(parents=True, exist_ok=True)

    args = [
        str(chrome_path),
        "--force-renderer-accessibility",
        f"--user-data-dir={profile_dir}",
        "--no-first-run",
        "--no-default-browser-check",
        "--new-window",
        URL,
    ]

    # Chrome 실행 직전 창 목록을 기록합니다.
    old_handles = {
        item["handle"] for item in get_chrome_windows("win32")
    }

    process = subprocess.Popen(args)

    print(f"[{session_name}] 실행 요청 PID: {process.pid}")
    print(f"[{session_name}] 프로필: {profile_dir}")

    return {
        "process": process,
        "old_handles": old_handles,
        "profile_dir": profile_dir,
        "session_name": session_name,
    }


# ============================================================
# 6. 실행 직후 새로 나타난 Chrome 창 찾기
#    창 핸들 변화를 우선 사용하므로 PID가 달라도 찾을 수 있습니다.
# ============================================================

def find_new_chrome_window(launch_info, timeout=WINDOW_TIMEOUT):
    session_name = launch_info["session_name"]
    old_handles = launch_info["old_handles"]
    started = time.time()

    print(f"\n[{session_name}] 새 Chrome 창 검색")

    while time.time() - started < timeout:
        windows = get_chrome_windows("win32")

        # 이번 실행 전에는 없었던 Chrome 창을 찾습니다.
        new_windows = [
            item for item in windows
            if item["handle"] not in old_handles
        ]

        # 새 창이 여러 개면 제목이 있는 창을 우선합니다.
        new_windows.sort(
            key=lambda item: bool(item["title"]),
            reverse=True
        )

        if new_windows:
            selected = new_windows[0]

            print(
                f"[성공] 창 발견: HWND={selected['handle']} | "
                f"PID={selected['pid']} | "
                f"제목={selected['title']!r}"
            )

            # UIA 백엔드로 같은 HWND를 연결합니다.
            try:
                uia_window = Desktop(backend="uia").window(
                    handle=selected["handle"]
                )

                # 접근 가능한 창인지 가볍게 확인합니다.
                _ = uia_window.window_text()
                return uia_window

            except Exception as error:
                print(
                    "[경고] Win32 창은 찾았지만 UIA 연결에 실패했습니다:",
                    repr(error)
                )

        time.sleep(1)

    print(f"[실패] {session_name} 새 Chrome 창을 찾지 못했습니다.")
    print_chrome_windows()
    return None


# ============================================================
# 7. UI Automation 요소 이름/종류 읽기
# ============================================================

def control_name(control):
    try:
        return control.window_text().strip()
    except Exception:
        return ""


def control_type(control):
    try:
        return control.element_info.control_type
    except Exception:
        return ""


# ============================================================
# 8. 선물 탭 찾기 및 선택
# ============================================================

def select_session(window, session_name):
    """
    탭을 이름으로 찾아 select()를 먼저 시도하고,
    지원하지 않으면 invoke()를 시도합니다.
    마우스 클릭이나 click_input()은 사용하지 않습니다.
    """

    print(f"\n[{session_name}] 탭 선택")

    try:
        controls = window.descendants()
    except Exception as error:
        print(f"[실패] 접근성 요소를 읽지 못했습니다: {error!r}")
        return False

    matches = []

    for control in controls:
        name = control_name(control)
        ctype = control_type(control)

        if name == session_name:
            print(f"발견: {name} / 종류: {ctype}")
            matches.append(control)

    if not matches:
        print(f"[실패] '{session_name}' 요소를 찾지 못했습니다.")
        save_accessibility_tree(window, f"{session_name}_탭검색실패")
        return False

    # TabItem을 먼저 시도합니다.
    matches.sort(key=lambda item: control_type(item) != "TabItem")

    for control in matches:
        ctype = control_type(control)

        if ctype == "TabItem":
            try:
                control.select()
                time.sleep(BUTTON_WAIT)
                print(f"[성공] '{session_name}' 탭 선택 요청 완료(select)")
                return True
            except Exception as error:
                print(f"TabItem select() 실패: {error!r}")

        try:
            control.select()
            time.sleep(BUTTON_WAIT)
            print(f"[성공] '{session_name}' 선택 요청 완료(select)")
            return True
        except Exception as error:
            print(f"select() 실패: {error!r}")

        try:
            control.invoke()
            time.sleep(BUTTON_WAIT)
            print(f"[성공] '{session_name}' 선택 요청 완료(invoke)")
            return True
        except Exception as error:
            print(f"invoke() 실패: {error!r}")

    print(
        f"[실패] '{session_name}' 탭을 UI Automation으로 선택할 수 없습니다."
    )
    save_accessibility_tree(window, f"{session_name}_탭선택실패")
    return False


# ============================================================
# 9. Chrome 접근성 트리 읽기 및 디버그 파일 저장
# ============================================================

def read_page_text(window):
    result = []

    try:
        for control in window.descendants():
            name = control_name(control)
            if name:
                result.append(name)
    except Exception as error:
        print(f"[경고] 페이지 접근성 정보 읽기 실패: {error!r}")

    return result


def save_accessibility_tree(window, filename):
    texts = read_page_text(window)
    path = DEBUG_DIR / f"{filename}.txt"

    with open(path, "w", encoding="utf-8") as file:
        for index, text in enumerate(texts):
            file.write(f"{index:04d}: {text}\n")

    print(f"[진단 파일 저장] {path}")


# ============================================================
# 10. 선물 가격 정보 추출
# ============================================================

def extract_futures_info(texts, session_name):
    title = f"코스피200 {session_name}"

    title_index = None

    for index, text in enumerate(texts):
        if text.strip() == title:
            title_index = index
            break

    if title_index is None:
        return {
            "session": session_name,
            "update_time": None,
            "price": None,
            "direction": None,
            "change": None,
            "change_percent": None,
            "error": f"'{title}' 제목을 찾지 못했습니다.",
        }

    section = texts[title_index + 1:title_index + 20]

    update_index = None
    for index, text in enumerate(section):
        if "갱신" in text:
            update_index = index
            break

    if update_index is None:
        return {
            "session": session_name,
            "update_time": None,
            "price": None,
            "direction": None,
            "change": None,
            "change_percent": None,
            "error": "갱신 시각을 찾지 못했습니다.",
        }

    update_text = section[update_index]
    update_time = update_text.replace("갱신", "").strip()

    def value_after(offset):
        position = update_index + offset
        return section[position].strip() if position < len(section) else None

    price = value_after(1)
    direction = value_after(2)
    change = value_after(3)
    change_percent = value_after(4)

    # 접근성 트리에서 값이 합쳐져 나오는 경우는 별도 진단이 필요합니다.
    if price is None or not re.fullmatch(
        r"\d[\d,]*(?:\.\d+)?",
        price.replace(" ", "")
    ):
        return {
            "session": session_name,
            "update_time": update_time,
            "price": price,
            "direction": direction,
            "change": change,
            "change_percent": change_percent,
            "error": "현재가 형식이 예상과 다릅니다. 디버그 파일을 확인하세요.",
        }

    return {
        "session": session_name,
        "update_time": update_time,
        "price": price,
        "direction": direction,
        "change": change,
        "change_percent": change_percent,
        "error": None,
    }


# ============================================================
# 11. 조회 및 콘솔 출력
# ============================================================

def read_session_price(window, session_name):
    texts = read_page_text(window)

    debug_path = DEBUG_DIR / f"{session_name}.txt"
    with open(debug_path, "w", encoding="utf-8") as file:
        for index, text in enumerate(texts):
            file.write(f"{index:04d}: {text}\n")

    return extract_futures_info(texts, session_name)


def print_session_info(info):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print(f"[{now}] {info['session']}")

    if info["error"]:
        print("  조회 오류 :", info["error"])
        return

    print("  갱신 시각 :", info["update_time"])
    print("  현재가     :", info["price"])
    print("  방향       :", info["direction"])
    print("  등락폭     :", info["change"])
    print("  등락률     :", info["change_percent"])


# ============================================================
# 12. 메인 실행
# ============================================================

def main():
    print("=" * 70)
    print("코스피200 주간선물 / 야간선물 모니터")
    print("=" * 70)

    if CREATE_NEW_DESKTOP:
        create_new_desktop()

    chrome_path = find_chrome()
    print("\nChrome 경로:", chrome_path)

    # 주간선물 Chrome을 실행하고, 새 창이 생길 때까지 찾습니다.
    day_launch = launch_chrome("주간선물", chrome_path)
    day_window = find_new_chrome_window(day_launch)

    if day_window is None:
        print("\n주간선물 Chrome 창을 찾지 못해 종료합니다.")
        return

    # 주간선물 창을 찾은 후 야간선물 Chrome을 실행합니다.
    night_launch = launch_chrome("야간선물", chrome_path)
    night_window = find_new_chrome_window(night_launch)

    if night_window is None:
        print("\n야간선물 Chrome 창을 찾지 못해 종료합니다.")
        return

    print(f"\n페이지 로딩을 {PAGE_LOAD_WAIT}초 기다립니다.")
    time.sleep(PAGE_LOAD_WAIT)

    print("\n사이트가 열렸는지 확인하세요.")
    print("로그인이 필요하다면 각 Chrome 창에서 로그인하세요.")
    input("준비가 끝나면 Enter를 누르세요...")

    day_ok = select_session(day_window, "주간선물")
    night_ok = select_session(night_window, "야간선물")

    if not day_ok or not night_ok:
        print("\n탭 선택에 실패했습니다.")
        print(f"진단 파일 위치: {DEBUG_DIR.resolve()}")
        return

    print("\n가격 모니터링을 시작합니다.")
    print(f"조회 간격: {REFRESH_SECONDS}초")
    print("종료하려면 Ctrl+C를 누르세요.")

    try:
        while True:
            print("\n" + "=" * 70)
            day_info = read_session_price(day_window, "주간선물")
            print_session_info(day_info)

            print("-" * 70)

            night_info = read_session_price(night_window, "야간선물")
            print_session_info(night_info)

            print("=" * 70)
            time.sleep(REFRESH_SECONDS)

    except KeyboardInterrupt:
        print("\n사용자가 모니터링을 종료했습니다.")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print("\n프로그램 실행 중 오류가 발생했습니다.")
        print(type(error).__name__, ":", error)
    finally:
        input("\nEnter 키를 누르면 종료합니다...")
