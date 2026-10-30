import time
import subprocess
from pathlib import Path
from datetime import datetime

import pyautogui
import pytesseract

from PIL import Image
from pytesseract import Output


# ============================================================
# 1. 기본 설정
# ============================================================

# 실제 Chrome 실행 파일 경로
CHROME_PATH = (
    r"C:\Program Files\Google\Chrome\Application\chrome.exe"
)

# 접속할 사이트
#URL = "https://ui.tradingforaliving.co.kr/"
URL = "https://mkospi.com/"

# 찾고 클릭할 버튼 글자
# 실제 사이트 화면에 표시된 글자에 맞게 수정한다.
BUTTON_TEXT = "주간선물"

# 캡처 이미지 저장 폴더
IMAGE_DIR = Path("tfl_capture_data/images")
IMAGE_DIR.mkdir(parents=True, exist_ok=True)

# OCR 텍스트 저장 폴더
TEXT_DIR = Path("tfl_capture_data/text")
TEXT_DIR.mkdir(parents=True, exist_ok=True)

# Tesseract OCR 실행 파일 경로
pytesseract.pytesseract.tesseract_cmd = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe"
)

# PyAutoGUI의 마우스 이동 안전장치
pyautogui.FAILSAFE = True


# ============================================================
# 2. 현재 시각 생성
# ============================================================

def get_timestamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


# ============================================================
# 3. Windows 새 가상 데스크톱 생성
# ============================================================

def create_virtual_desktop():

    print("새 Windows 가상 데스크톱을 생성한다.")

    # Win + Ctrl + D
    pyautogui.hotkey("win", "ctrl", "d")

    time.sleep(3)

    print("가상 데스크톱 생성 단축키를 실행했다.")


# ============================================================
# 4. 일반 Chrome 실행
# ============================================================

def open_normal_chrome():

    chrome = Path(CHROME_PATH)

    if not chrome.exists():
        raise FileNotFoundError(
            f"Chrome 실행 파일을 찾을 수 없다: {chrome}"
        )

    print("일반 Chrome을 실행한다.")

    # Playwright를 사용하지 않고 일반 Chrome을 실행한다.
    subprocess.Popen([
        str(chrome),
        "--new-window",
        URL
    ])

    # 브라우저와 사이트가 표시될 때까지 대기한다.
    time.sleep(10)

    print("Chrome 실행을 요청했다.")


# ============================================================
# 5. 현재 화면 캡처
# ============================================================

def capture_screen():

    timestamp = get_timestamp()

    image_path = IMAGE_DIR / f"screen_{timestamp}.png"

    # 현재 화면을 캡처한다.
    image = pyautogui.screenshot()

    image.save(image_path)

    print("화면 캡처:", image_path)

    return image, image_path


# ============================================================
# 6. OCR로 화면의 글자와 위치 찾기
# ============================================================

def find_button_position(image, target_text):

    print(f"버튼 글자를 찾는다: {target_text}")

    # 이미지에서 글자와 위치를 추출한다.
    result = pytesseract.image_to_data(
        image,
        lang="kor+eng",
        config="--psm 11",
        output_type=Output.DICT
    )

    # OCR 결과를 파일로 저장한다.
    timestamp = get_timestamp()

    text_path = TEXT_DIR / f"ocr_positions_{timestamp}.txt"

    matches = []

    # OCR이 읽은 각 단어를 검사한다.
    for i, word in enumerate(result["text"]):

        word = word.strip()

        if not word:
            continue

        x = result["left"][i]
        y = result["top"][i]
        width = result["width"][i]
        height = result["height"][i]

        confidence = float(result["conf"][i])

        # OCR 인식 결과를 기록한다.
        with open(text_path, "a", encoding="utf-8") as f:
            f.write(
                f"글자={word}, "
                f"좌표=({x}, {y}), "
                f"크기=({width}, {height}), "
                f"신뢰도={confidence}\n"
            )

        # 찾을 글자가 포함된 OCR 단어를 후보로 추가한다.
        if target_text in word and confidence >= 50:
            matches.append(
                (x, y, width, height, word, confidence)
            )

    if not matches:

        print("버튼 글자를 찾지 못했다.")
        print("OCR 결과 파일을 확인해야 한다.")

        return None

    # 같은 글자가 여러 곳에서 발견되면
    # 임의로 첫 번째 항목을 클릭하지 않는다.
    if len(matches) > 1:

        print("같은 글자가 여러 곳에서 발견되었다.")
        print("안전을 위해 클릭하지 않는다.")

        for match in matches:
            print(match)

        return None

    x, y, width, height, word, confidence = matches[0]

    # 글자 영역 중앙 좌표
    center_x = x + width // 2
    center_y = y + height // 2

    print("인식된 글자:", word)
    print("클릭 후보 좌표:", center_x, center_y)
    print("OCR 신뢰도:", confidence)

    return center_x, center_y


# ============================================================
# 7. 버튼 클릭
# ============================================================

def click_button(target_text):

    # 현재 화면 캡처
    image, _ = capture_screen()

    # OCR로 버튼 위치 찾기
    position = find_button_position(
        image,
        target_text
    )

    if position is None:
        print("버튼 위치를 확정할 수 없어 클릭하지 않는다.")
        return False

    x, y = position

    # 클릭 직전 사용자 확인을 위한 대기
    print(f"3초 후 좌표 ({x}, {y})를 클릭한다.")
    time.sleep(3)

    # 마우스 이동
    pyautogui.moveTo(
        x,
        y,
        duration=0.5
    )

    # 마우스 클릭
    pyautogui.click()

    print(f"클릭 완료: {target_text}")

    # 버튼 클릭 후 화면 갱신 대기
    time.sleep(3)

    # 클릭 후 화면 캡처
    after_image, after_path = capture_screen()

    print("클릭 후 화면 저장:", after_path)

    return True


# ============================================================
# 8. 전체 작업
# ============================================================

def capture_page():

    print("=" * 60)
    print("일반 Chrome 화면 인식 및 자동 클릭")
    print("=" * 60)

    # 1. 새 가상 데스크톱 생성
    create_virtual_desktop()

    # 2. 일반 Chrome 실행
    open_normal_chrome()

    # 3. 화면에서 버튼을 찾아 클릭
    success = click_button(BUTTON_TEXT)

    if success:
        print("버튼 클릭 작업이 완료되었다.")
    else:
        print("버튼 클릭 작업이 완료되지 않았다.")


# ============================================================
# 9. 프로그램 시작
# ============================================================

if __name__ == "__main__":

    try:
        capture_page()

    except KeyboardInterrupt:
        print("사용자가 프로그램을 중단했다.")

    except Exception as e:
        print("오류가 발생했다:", e)