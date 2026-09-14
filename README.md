# 서버 상태 모니터 (server_status)

BookOasis 홈 대시보드에 **CPU / 메모리 / 디스크 사용률**과 **가동 시간**을
카드로 보여주는 홈화면 전용(`home_widget`) 플러그인입니다.

## 왜 `home_widget`인가?

가이드 문서 §5-1에 따라 `home_widget`은 `dashboard_widget`([플러그인] 공통
데스크 탭)과 달리, 사용자가 실제로 처음 접속했을 때 보는 **홈 화면**에 카드로
꽂힙니다. 다만 아래 두 조건을 모두 만족해야 화면에 보입니다.

1. 사용자가 [내 설정 > 홈 화면 플러그인 배치 모드]를 켰을 것
2. 그 사용자가 홈 화면 하단 "+ 위젯 추가" 목록에서 이 위젯을 직접 추가했을 것

즉 "설치 = 즉시 노출"이 아니라 "설치 = 카탈로그 등장"이라는 점에 유의하십시오.
반대로 말하면, 배치 모드를 켜지 않은 다른 사용자의 홈 화면에는 전혀 영향이
없습니다.

## 설치

1. 이 폴더(`server_status`)를 통째로 BookOasis의 `plugins/metadata/` 아래에
   복사합니다.
   ```
   plugins/metadata/
     server_status/
       __init__.py
       server_status.py
       VERSION
       requirements.txt
       README.md
   ```
2. 서버를 재시작합니다. (`requirements.txt`의 `psutil`이 플러그인 전용
   `libs/`에 자동 격리 설치됩니다 — 코어가 이미 `psutil`을 쓰고 있다면
   충돌 없이 그대로 재사용됩니다.)
3. [환경설정 ⚙️ > 플러그인 설정]에서 "서버 상태 모니터"를 **활성화**합니다.
4. 필요하면 아래 설정값을 조정 후 저장합니다.
   - `CPU_WARN` / `MEM_WARN` / `DISK_WARN`: 각 자원의 경고 임계치(%)
     — 초과 시 카드 설명에 🔴, 85% 이상 근접 시 🟡, 그 외 🟢로 표시됩니다.
   - `DISK_PATH`: 사용률을 확인할 디스크 경로 (기본값 `/`)
   - `CACHE_TTL_SEC`: 홈 화면을 자주 열 때 psutil 재측정을 줄이기 위한
     캐시 유지 시간(초, 기본 5초)
5. [내 설정 > 홈 화면 플러그인 배치 모드]를 켭니다.
6. 홈 화면 하단의 "+ 위젯 추가" 목록에서 "서버 상태" 위젯을 추가합니다.
   `layout: grid`, `size: 1`로 선언되어 있어 다른 grid 위젯과 함께 카드
   형태로 한 행에 나란히 배치됩니다.

## 동작 방식

- 별도의 `index.html`/`style.css`/`script.js` 없이, 코어가 기본 제공하는
  `item_type: "metric"` 카드 렌더러를 그대로 사용합니다
  (가이드의 `get_dashboard_data()` 아이템 공용 스키마 참고).
- `get_dashboard_data(db_type, limit=10)`가 `home_widget`과
  ([플러그인] 공통 데스크에 노출하고 싶다면) `dashboard_widget` 양쪽에서
  공용으로 재사용 가능한 표준 계약 메서드입니다. 이 플러그인은 홈화면
  전용 요구사항에 맞춰 `home_widget`만 선언했습니다.
- 매 홈 화면 로드마다 `psutil`을 재호출하는 대신, 플러그인 전용 Redis
  캐시(`self.cache_get`/`self.cache_set`)로 짧게(기본 5초) 결과를
  재사용해 서버 부담을 줄입니다.
- CPU 사용률은 `psutil.cpu_percent(interval=0.3)`로 측정하며, 이 0.3초는
  요청 처리 스레드 안에서만 짧게 블로킹됩니다(캐시로 인해 실제 호출
  빈도는 `CACHE_TTL_SEC`당 최대 1회).

## 커스터마이즈 아이디어

- Top 프로세스 5개를 `item_type: "metric"` 카드 하나로 요약해서 추가
- `run_context_menu_action` 없이도, 이 플러그인은 홈 위젯 전용이라
  도서 컨텍스트 메뉴 연동은 포함하지 않았습니다. 필요하면 가이드 §6을
  참고해 "지금 자원 상태 새로고침" 같은 RPC 액션을 추가할 수 있습니다.
- 네트워크 트래픽, 스캔 큐 상태(`/api/system/status`와 유사한 정보)를
  같은 카드 세트에 추가로 붙이는 것도 가능합니다.
