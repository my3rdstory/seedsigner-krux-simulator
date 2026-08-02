# BTC Inspector: SeedSigner + Krux Windows Simulator Panel

SeedSigner 데스크톱 에뮬레이터와 Krux Amigo 시뮬레이터를 하나의 Windows 창에 나란히 띄워, 같은 입력을 서로 다른 오픈소스 구현에 독립적으로 넣어 보는 교육용 검증 도구입니다. 기본 배치는 왼쪽 SeedSigner, 오른쪽 Krux입니다.

## 반드시 읽어야 할 주의 사항

> 이 저장소는 Windows 전용 교육용·검증용 시뮬레이터입니다. 실제 Bitcoin 지갑을 만들거나 실제 자산을 보관하는 용도로 사용하지 마십시오.

> 이 저장소의 통합 레이어와 일부 원본 파일은 에이전틱 코딩을 사용해 수정되었습니다. 변경 사항이 원본 프로젝트의 보안 모델, 하드웨어 동작, 암호학적 가정을 그대로 보존한다고 보장할 수 없습니다. 코드를 직접 검토하고 테스트용 데이터만 사용하십시오.

> 실제 니모닉, 패스프레이즈, 개인 키, QR 코드, 지갑 백업을 화면 녹화, 화면 공유, 로그 또는 온라인 환경에 입력하지 마십시오. 샘플 주사위 값과 테스트용 니모닉만 사용하십시오.

> 두 앱의 결과가 같다는 것은 동일한 입력에 대해 두 구현의 계산 결과가 일치했다는 뜻일 뿐입니다. 주사위가 충분히 무작위였다는 사실, 장치와 소프트웨어 전체의 안전성, 실제 지갑의 보안을 증명하지 않습니다.

이 프로젝트는 SeedSigner와 Krux의 원본 코드 및 각 프로젝트의 라이선스 파일을 함께 포함합니다.

- SeedSigner: https://github.com/SeedSigner/seedsigner
- Krux: https://github.com/selfcustody/krux

원본 프로젝트의 저작권과 라이선스 조건을 유지하십시오.

## 목적

하드웨어 지갑에서 주사위 결과를 입력해 니모닉을 만들 때, 한 장치의 화면만 확인하고 끝내는 실수를 줄이는 것이 목적입니다.

1. 두 앱을 동시에 실행합니다.
2. 한 앱에 원본 주사위 목록을 입력합니다.
3. 다른 앱에 같은 원본 목록을 다시 입력합니다.
4. 한 앱의 니모닉을 다른 앱에 복사하지 않고, 두 결과의 단어 순서와 마스터 핑거프린트를 비교합니다.

두 시뮬레이터는 각각 별도의 Python 프로세스로 실행됩니다. 상위 패널은 두 창을 배치하고 입력을 전달하는 역할을 합니다.

## 제공 기능

- 하나의 Tkinter 패널에 SeedSigner를 왼쪽, Krux를 오른쪽으로 표시
- 패널의 마지막 위치와 크기 복원
- 각 앱의 Close App / Open App으로 한쪽만 닫았다가 다시 열기
- SeedSigner 하드웨어 버튼을 마우스, 화살표, Enter, Space, 숫자 키로 조작
- Krux Amigo 시뮬레이터의 터치스크린을 마우스로 조작
- 앱을 최대화하지 않고 저장된 원래 창 크기로 실행
- SeedSigner와 Krux의 설정을 다음 실행에서도 유지
- Windows 웹캠을 앱별 환경 변수로 선택
- 두 앱이 동시에 웹캠을 열지 않도록 프로세스 간 파일 잠금 제공
- 시작 오류와 실행 로그를 logs에 저장
- Krux의 Pygame 터치 이벤트에 실제 마우스 이벤트 좌표 전달
- Windows용 SeedSigner 디스플레이, 입력, 카메라 에뮬레이션
- Windows용 pyzbar 호환성 폴백

## 실행 환경

상위 실행기는 Windows 10/11과 PowerShell을 전제로 작성되었습니다. Linux, macOS, 순수 WSL에서는 launch-both.bat, Win32 창 배치, Tkinter/Pygame 임베딩, Windows 웹캠 잠금이 그대로 동작하지 않습니다.

권장 환경:

- Windows 10 또는 Windows 11
- PowerShell 5.1 이상 또는 PowerShell 7
- Python 3.12 계열
- Git
- Krux 의존성 설치를 위한 Poetry
- GUI 세션이 열려 있는 데스크톱

SeedSigner는 Python 3.10 이상을 요구합니다. Krux의 현재 pyproject.toml은 Python 3.12.3 계열을 요구합니다.

## 디렉터리 구조

    btc-inspector/
    |-- control_panel.py             # 두 앱을 한 창에 배치하는 상위 패널
    |-- launch-both.bat              # 일반 사용자를 위한 Windows 실행 진입점
    |-- launch-both.ps1              # 두 시뮬레이터를 독립 창으로 실행하는 보조 스크립트
    |-- webcam_capture.py             # OpenCV 웹캠 어댑터와 단일 점유 잠금
    |-- panel-state.json              # 패널의 마지막 위치와 크기
    |-- logs/                         # 실행 중 생성되는 로그
    |-- seedsigner/                   # SeedSigner 원본 코드와 Windows 에뮬레이터
    +-- krux/                         # Krux 원본 코드와 Amigo 시뮬레이터

## 설치

모든 명령은 저장소 루트에서 PowerShell로 실행합니다.

### 1. SeedSigner 가상환경

    py -3.12 -m venv .\seedsigner\.venv
    .\seedsigner\.venv\Scripts\python.exe -m pip install --upgrade pip
    .\seedsigner\.venv\Scripts\python.exe -m pip install -r .\seedsigner\requirements.txt

requirements.txt에는 Windows 데스크톱 카메라와 QR 테스트에 필요한 opencv-python이 포함되어 있습니다. 네트워크가 제한된 환경에서는 Git URL 의존성인 SeedSigner의 pyzbar 포크도 준비해야 합니다.

### 2. Krux 가상환경

Krux는 Poetry로 관리합니다. simulator extra를 설치하면 Pygame, Pillow, OpenCV 등 시뮬레이터 의존성이 함께 설치됩니다.

    py -3.12 -m pip install --upgrade poetry
    Set-Location .\krux
    poetry config virtualenvs.in-project true --local
    poetry install --extras simulator
    Set-Location ..

설치 후 다음 두 파일이 존재해야 합니다.

    Test-Path .\seedsigner\.venv\Scripts\pythonw.exe
    Test-Path .\krux\.venv\Scripts\pythonw.exe

둘 다 True여야 launch-both.bat가 정상적으로 앱을 시작할 수 있습니다.

## 실행

가장 일반적인 실행 방법:

    .\launch-both.bat

실행 흐름:

    launch-both.bat
        |
        +-- seedsigner\.venv\Scripts\pythonw.exe control_panel.py
                |
                |-- seedsigner\.venv\Scripts\pythonw.exe
                |      seedsigner\desktop_emulator.py
                |
                +-- krux\.venv\Scripts\pythonw.exe
                       krux\simulator\simulator.py --device maixpy_amigo --sd

control_panel.py는 중복 패널을 막기 위해 Windows named mutex를 사용합니다. 이미 패널이 실행 중이면 새 패널을 만들지 않고 기존 창을 표시합니다. 패널 창을 닫으면 두 시뮬레이터도 함께 종료됩니다.

launch-both.ps1는 패널 없이 두 앱을 독립 창으로 띄우는 진단용 실행기입니다. 일반적인 교차 검증에는 launch-both.bat를 사용하십시오.

## 화면과 입력 조작

### 패널

- SeedSigner 또는 Krux 헤더를 클릭하면 키보드 입력을 전달할 앱이 바뀝니다.
- Ctrl+Left와 Ctrl+Right로 선택 앱을 바꿀 수 있습니다.
- Tab으로 선택 앱을 전환할 수 있습니다.
- 패널의 Close App은 해당 앱만 닫습니다.
- Open App으로 닫힌 앱만 다시 시작할 수 있습니다.
- 패널 창 자체를 닫으면 두 앱이 함께 종료됩니다.

### SeedSigner

SeedSigner는 실제 하드웨어의 입력 대기와 디스플레이를 Windows Tkinter 창으로 흉내 냅니다.

- 화면 위 버튼을 마우스로 클릭
- Up, Down, Left, Right로 방향 이동
- Enter 또는 Space로 선택
- 1, 2, 3으로 세 하드웨어 버튼 입력

SeedSigner의 화면 입력은 desktop_emulator.py의 INPUT_QUEUE로 들어가고, 시뮬레이터 코드가 사용하는 하드웨어 모듈로 전달됩니다. 화면 렌더링은 DISPLAY_QUEUE를 통해 Tkinter 이미지로 갱신됩니다.

### Krux

Krux는 Amigo 시뮬레이터를 기반으로 하며 화면의 터치 영역을 마우스로 클릭합니다. simulator.py에서 Pygame MOUSEBUTTONDOWN의 실제 이벤트 좌표를 터치 드라이버에 전달하도록 수정했습니다. 빠른 마우스 클릭에서도 버튼을 놓친 위치를 다시 읽는 경쟁 조건을 줄이기 위한 수정입니다.

## 설정 저장

앱 설정은 실행 중 변경한 뒤 다음 실행에서도 유지됩니다.

| 대상 | 저장 위치 |
| --- | --- |
| 패널 위치와 크기 | panel-state.json |
| SeedSigner 시뮬레이터 설정 | seedsigner/simulator-data/settings.json |
| Krux 내부 플래시 설정 | krux/simulator/flash/settings.json |
| Krux 에뮬레이트 SD 카드 | krux/simulator/sd/ |

시뮬레이터 설정과 SD 카드에는 테스트 데이터가 남을 수 있습니다. 실제 지갑 정보나 실제 니모닉을 입력하지 마십시오.

SeedSigner와 Krux의 언어 설정은 각 앱의 설정 화면에서 변경합니다. 패널이 언어를 강제로 바꾸지는 않습니다. 번역 범위와 니모닉 단어 목록은 앱별 설정이므로 다음 항목을 두 앱에서 별도로 확인해야 합니다.

- 12단어 또는 24단어 선택
- BIP39 단어 목록
- 패스프레이즈 사용 여부
- 네트워크
- 파생 경로와 지갑 정책

## 웹캠 사용

카메라 기능을 사용할 때 webcam_capture.py가 %TEMP%\btc-inspector-webcam.lock 파일 잠금을 사용합니다. 한 앱이 카메라를 점유하는 동안 다른 앱이 열기를 시도하면 WebcamError가 발생합니다. 현재 카메라 화면을 종료한 뒤 다시 시도하십시오.

기본 장치 번호는 0입니다.

    # 두 앱이 공통으로 사용할 기본 장치
    $env:BTC_INSPECTOR_CAMERA_INDEX = "0"

    # 앱별 설정이 공통 설정에 우선합니다
    $env:SEEDSIGNER_CAMERA_INDEX = "0"
    $env:KRUX_CAMERA_INDEX = "1"

    # 0부터 7까지 순서대로 찾아 첫 번째 사용 가능한 카메라 선택
    $env:BTC_INSPECTOR_CAMERA_INDEX = "auto"

웹캠이 없는 경우 카메라 기능을 사용하지 않으면 주사위 입력, 니모닉 계산, 설정 저장 기능은 계속 사용할 수 있습니다.

## 샘플 주사위 검증

아래 목록은 교육용 테스트 데이터입니다. 실제 지갑의 주사위 결과나 실제 시드를 사용하지 마십시오.

    1 ~ 10회
    33466
    36351

    11 ~ 20회
    36254
    62164

    21 ~ 30회
    11156
    11532

    31 ~ 40회
    44145
    54243

    41 ~ 50회
    34564
    14614

두 앱을 비교할 때는 한 앱의 화면 결과에서 값을 복사하지 말고 원본 목록에서 각각 다시 입력하십시오. 50개 입력 후 니모닉 단어 수, 단어 순서, 마스터 핑거프린트 전체를 직접 비교합니다. 결과가 다르면 성공으로 처리하지 말고 입력 개수, 순서, 단어 목록, 패스프레이즈, 파생 설정을 처음부터 재확인합니다.

## 코드 설명

### control_panel.py

상위 Tkinter 애플리케이션입니다.

- Simulator: 앱 프로세스, 실행 상태, 로그 핸들을 관리합니다.
- ApplicationPane: 앱 헤더, 상태 표시, Close App/Open App 버튼, 호스트 프레임을 관리합니다.
- CombinedWindow: 저장된 geometry를 복원하고 두 pane을 좌우로 배치합니다.
- Win32 SetWindowLongPtrW와 SetWindowPos로 각 native window를 호스트 영역에 배치합니다. Tkinter와 SDL/Pygame의 마우스 처리를 보존하는 것이 목적입니다.
- panel-state.json에는 패널의 x, y, width, height만 저장합니다.

### launch-both.bat와 launch-both.ps1

launch-both.bat는 SeedSigner 가상환경의 pythonw.exe로 상위 패널을 시작합니다. 실제 앱 프로세스의 생성, 제목, 로그 리다이렉션, 위치 계산은 control_panel.py가 담당합니다.

launch-both.ps1는 두 앱을 별도 native window로 실행하고 주 모니터 작업 영역의 좌우에 배치합니다. 패널 임베딩 문제를 분리해서 진단할 때 사용합니다.

### webcam_capture.py

OpenCV와 앱별 환경 변수 사이의 공통 어댑터입니다.

- _CameraLease: 파일 잠금으로 웹캠 단일 점유를 보장합니다.
- open_webcam: 0부터 7 또는 auto 장치 검색을 수행합니다.
- WebcamStream: 연속 프레임 카메라 API에 맞춘 백그라운드 읽기 클래스입니다.
- WebcamStill: 단일 프레임을 사용하는 화면을 위한 클래스입니다.
- frame_to_image: OpenCV 프레임을 SeedSigner 화면용 PIL 이미지로 변환합니다.

### seedsigner/desktop_emulator.py

원본 SeedSigner 하드웨어 의존성을 Windows GUI로 대체하는 진입점입니다.

- Tkinter 창과 디스플레이를 제공합니다.
- 하드웨어 버튼 대기 API를 queue.Queue 기반 입력으로 대체합니다.
- 화면 클릭을 실제 하드웨어 버튼 의미로 매핑합니다.
- webcam_capture.py로 카메라 스트림과 단일 프레임 입력을 제공합니다.
- --geometry, --title, --start-hidden 옵션으로 상위 패널의 창 생명주기와 배치를 지원합니다.

### krux/simulator/simulator.py

Krux의 Pygame 기반 Amigo 시뮬레이터입니다.

- flash 디렉터리를 자동 생성해 설정 저장 위치를 에뮬레이트합니다.
- KRUX_SIMULATOR_TITLE로 패널이 인스턴스별 창을 찾게 합니다.
- KRUX_SIMULATOR_START_HIDDEN=1로 시작 순간의 별도 창 노출을 줄입니다.
- MOUSEBUTTONDOWN 이벤트 좌표를 터치 드라이버에 전달합니다.
- Pygame 화면을 상위 패널에서 사용할 수 있도록 resizable 창을 사용합니다.

### 원본 코드에 적용한 주요 수정

SeedSigner:

- desktop_emulator.py: Windows Tkinter 화면, 입력 큐, 카메라 어댑터, 창 옵션을 추가했습니다.
- requirements.txt: opencv-python을 추가했습니다.
- src/seedsigner/models/decode_qr.py: Windows pyzbar wheel에서 binary 인자를 지원하지 않을 때의 제한적 폴백을 추가했습니다.

Krux:

- simulator/kruxsim/mocks/sensor.py: 직접 VideoCapture(0) 대신 공통 웹캠 잠금 어댑터를 사용합니다.
- simulator/kruxsim/mocks/touchscreen_common.py: 현재 마우스 상태를 다시 읽지 않고 이벤트 당시 좌표를 사용합니다.
- simulator/simulator.py: 플래시 저장소 생성, 창 제목, 숨김 시작, resizable 창, 터치 좌표 전달을 추가했습니다.

## 로그와 문제 해결

앱이 시작되지 않으면 다음 파일을 확인하십시오.

    logs/control-panel.log
    logs/seedsigner-error.log
    logs/seedsigner-output.log
    logs/krux-error.log
    logs/krux-output.log

### Required file is missing

다음 두 파일이 없으면 가상환경을 다시 만들거나 설치 위치를 확인합니다.

    seedsigner/.venv/Scripts/pythonw.exe
    krux/.venv/Scripts/pythonw.exe

### Krux 창이 시작되지 않음

Krux의 .venv가 Python 3.12.3 계열인지, poetry install --extras simulator가 완료됐는지 확인합니다. logs/krux-error.log에서 Pygame, Pillow, OpenCV, pyzbar import 오류를 확인합니다.

### SeedSigner QR 또는 카메라가 동작하지 않음

SeedSigner 가상환경에 opencv-python이 설치됐는지 확인합니다. Windows 카메라 권한과 다른 프로그램의 카메라 점유 여부도 확인합니다. Krux 카메라 화면을 종료해 파일 잠금을 해제한 뒤 다시 시도합니다.

### 앱 화면이 잠깐 별도 창으로 보임

패널은 Krux에 KRUX_SIMULATOR_START_HIDDEN=1을 전달하고 SeedSigner 화면을 패널 호스트에 배치합니다. 이전 패널이나 앱 프로세스가 남아 있으면 중복 창이 생길 수 있습니다. 패널을 정상 종료하고 logs를 확인한 뒤 다시 실행하십시오.

### 설정을 초기화해야 함

앱을 종료한 뒤 해당 런타임 파일을 백업하고 삭제하면 다음 실행에서 기본값으로 다시 만들어집니다.

    seedsigner/simulator-data/settings.json
    krux/simulator/flash/settings.json
    krux/simulator/sd/
    panel-state.json

이 파일에는 테스트 데이터가 남을 수 있으므로 실제 비밀값을 넣지 마십시오.

## 테스트와 검증

루트 어댑터의 문법 검사:

    python -m py_compile .\control_panel.py .\webcam_capture.py

SeedSigner 테스트:

    Set-Location .\seedsigner
    .\.venv\Scripts\python.exe -m pytest
    Set-Location ..

Krux 테스트:

    Set-Location .\krux
    poetry run pytest --cache-clear ./tests
    Set-Location ..

GUI 스모크 테스트:

1. launch-both.bat 실행 후 한 창 안에 두 앱이 좌우로 보이는지 확인합니다.
2. 패널을 이동하거나 크기를 바꾼 뒤 종료하고 다시 실행해 geometry가 복원되는지 확인합니다.
3. 한쪽의 Close App을 눌러도 다른 앱과 패널이 남는지 확인합니다.
4. Open App으로 닫힌 앱이 같은 pane에 다시 나타나는지 확인합니다.
5. SeedSigner의 화면 버튼과 Krux의 Amigo 터치 영역을 마우스로 조작합니다.
6. 두 앱의 설정 화면에서 바꾼 언어와 설정이 재실행 후 유지되는지 확인합니다.
7. 한 앱이 카메라 점유 중일 때 다른 앱이 명확한 사용 중 오류를 표시하는지 확인합니다.

## Git 초기화와 배포 주의

루트 저장소는 통합 레이어와 문서를 관리하기 위한 별도 저장소입니다. seedsigner와 krux 디렉터리 안에는 원본 프로젝트의 .git 메타데이터가 보존되어 있을 수 있습니다. 원본 변경 이력을 보존하기 위한 조치입니다.

루트 저장소를 초기화하는 명령:

    git init -b main
    git config core.quotepath false
    git status

커밋 작성자 정보는 각 개발자의 로컬 Git 설정으로 관리하며, 공개 문서나 소스에 개인 계정 정보를 기록하지 마십시오.

내부에 또 다른 .git이 있는 디렉터리를 루트에서 바로 git add하면 Git이 embedded repository 또는 gitlink로 처리할 수 있습니다. 소스 전체를 하나의 저장소로 배포할지, 두 원본 프로젝트를 submodule로 관리할지 결정한 뒤 추가하십시오. 원본 메타데이터를 무심코 삭제하거나 원본 변경 사항을 덮어쓰지 마십시오.

## 라이선스와 책임

이 통합 저장소의 실행 스크립트와 문서는 별도 라이선스를 명시하지 않는 한 교육용 참고 자료로 제공됩니다. 포함된 SeedSigner와 Krux 소스는 각 디렉터리의 원본 LICENSE.md와 저작권 고지를 따릅니다.

이 프로젝트는 금융 조언, 지갑 보안 인증, 난수 품질 인증, 하드웨어 보증을 제공하지 않습니다. 실제 사용 전에는 원본 프로젝트의 공식 문서, 릴리스, 서명, 해시, 보안 공지를 직접 확인하고 이 통합본과 원본의 차이를 검토하십시오.
