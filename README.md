# 서버 상태 모니터 (server_status)

BookOasis 홈 대시보드에 **CPU / 메모리 / 디스크(/ 스왑) 사용률**을
Zabbix 스타일 반원형 게이지(색상 존 + 바늘 + 중앙 퍼센트 텍스트)로
보여주는 홈화면 전용(`home_widget`) 플러그인입니다. Load average /
Uptime / Network처럼 0~100% 스케일이 아닌 값은 텍스트 행으로 별도
표시합니다.

## ⚠️ 버전 변경 이력

**v1.x — 설정 화면 자체가 사라지는 문제**
`home_widget`을 `@property`로 구현했다가 클래스 레벨 접근 실패로 플러그인
전체 로딩이 실패했습니다. → 매니페스트는 항상 고정 dict로 선언해야 합니다.

**v2.0~2.2 — 설치 검증기가 필드/폴더 규칙으로 거부**
"작은/큰 화면"을 별도 id의 두 클래스(두 플러그인)로 분리했다가, mixin
상속·외부 상수 참조 방식 모두 검증기가 인식하지 못했고, 무엇보다
**"폴더당 플러그인 1개, id는 폴더명과 일치"** 규칙과 맞지 않아 거부되었습니다.

**v3.x — 단일 플러그인 + 유니코드 게이지 바**
`id = 폴더명("server_status")`인 단일 플러그인으로 되돌리고, `small`
(통합 1줄)/`general`(개별 카드) 두 모드를 설정으로 고를 수 있게 했습니다.
당시 가이드는 `home_widget`의 `item_type:"metric"` 카드가 순수 텍스트만
지원해서, 진행률 바를 `▰▱` 유니코드 문자로 흉내 냈습니다.

**v4.0~4.2 — `dashboard.html`/`dashboard.css`/`dashboard.js` 도입**
플러그인 가이드가 업데이트되어 `home_widget`에 완전한 커스텀 CSS/이미지를
쓸 수 있게 되었습니다(위젯별 **Shadow DOM 격리** 렌더링, 코어 1.1.1+).
처음에는 텍스트 진행률 바로 교체했다가, 부가 상세 정보(`"of 4 CPUs"`,
`"(13.35 GiB of 31.09 GiB)"`)를 빼고 퍼센트만 남겨 줄바꿈 문제를
줄였습니다.

**v4.3 — 카드 배경 + 라운드 처리로 시인성 개선**
코어 기본 위젯("현재 읽는 중" 등)처럼 배경색과 둥근 모서리를 넣어
배경과 구분되도록 했습니다.

**v4.4 — 위젯 상단 어트리뷰션 이름 변경**
홈 위젯 상단에 자동으로 붙는 "제공: ..." 표시가 플러그인 클래스의
`name` 속성을 그대로 사용하는 것으로 확인되어, `"서버 상태 모니터"`
→ `"유메미루"`로 변경했습니다. 화면에는 "제공: 유메미루"로 표시됩니다.

**v5.0 (현재) — Zabbix 스타일 SVG 반원형 게이지로 전면 교체**
프로그레스 바 대신 Zabbix 대시보드 스타일의 반원형 게이지(초록/노랑/
빨강 색상 존 + 바늘 + 중앙 퍼센트 텍스트)로 바꿨습니다.

- `_gauge_svg(value, warn)`가 Python(`math.cos`/`math.sin`)으로 SVG
  좌표를 전부 계산해 완성된 `<svg>...</svg>` 문자열을 반환합니다.
  값/경고 임계치는 전부 숫자 연산 결과이므로, `dashboard.js`가 이
  문자열을 `innerHTML`로 그대로 삽입해도 안전합니다(라벨 등 텍스트는
  여전히 `textContent`만 사용).
- 색상 존 경계는 기존 임계치 설정을 그대로 재사용합니다: 초록
  `0 ~ warn×0.85`, 노랑 `warn×0.85 ~ warn`, 빨강 `warn ~ 100`.
- **CPU / RAM / Disk(/ Swap)** 처럼 0~100% 스케일이 있는 항목만
  게이지로 그리고, **Load average / Uptime / Network**처럼 자연스러운
  0~100% 최대치가 없는 항목은 계속 텍스트 행으로 표시합니다(게이지로
  억지로 표현하면 오해를 부를 수 있어 제외했습니다).
- 코어 계약(`{'success': True, 'items': [...]}`)을 지키기 위해 게이지와
  텍스트 항목을 하나의 `items` 배열에 담고, 각 원소의 `kind` 필드
  (`"gauge"` / `"text"`)로 `dashboard.js`가 게이지 그리드/텍스트
  목록에 나눠 렌더링합니다.
- 게이지 카드는 `grid-template-columns: repeat(auto-fit, minmax(110px,
  1fr))`로 배치되어, 위젯 폭이 넓으면 여러 개가 한 줄에, 좁으면 자동
  으로 줄바꿈됩니다.

`small` 모드는 CPU/RAM/Disk/Swap 게이지 4개(스왑이 있는 서버 기준),
`general` 모드는 여기에 Load average(유닉스 계열만)/Uptime/Network
텍스트 행까지 추가로 보여줍니다.

**v5.1 (현재) — 기본(small) 모드에 Swap 게이지 포함**
스크린샷 레퍼런스처럼 평상시(=`small` 모드)에도 CPU/RAM/Disk 3개가
아니라 **CPU/RAM/Disk/Swap 4개 게이지**가 항상 보이도록 수정했습니다.
`general` 모드와의 차이는 이제 게이지 개수가 아니라, 텍스트 행(Load
average/Uptime/Network)의 유무뿐입니다. 스왑이 아예 없는 서버(예:
스왑 미설정 컨테이너)에서는 이전처럼 스왑 게이지가 자동으로 생략됩니다
(psutil이 보고하는 스왑 총량이 0이면 게이지를 만들지 않음).

### 아이템 스키마 (v5.0 기준)

`get_dashboard_data()`가 반환하는 최상위 구조는 여전히 코어 계약대로
`{'success': True, 'items': [...]}`이지만(`items` 필드만 꺼내
`dashboard.js`에 넘겨주므로 이 키는 반드시 유지해야 함), 배열 안
아이템 자체는 core의 `metric` 스키마가 아니라 `dashboard.js`가
직접 해석하는 자유 형식입니다. 두 종류가 있습니다.

```json
{"kind": "gauge", "label": "CPU usage", "svg": "<svg>...</svg>"}
```
```json
{"kind": "text", "icon": "fa-solid fa-clock", "label": "Uptime", "value_text": "1일 2시간 (부팅: ...)"}
```

- `kind: "gauge"`: `svg` 필드에 완성된 `<svg>` 마크업 문자열이 들어
  있고, `dashboard.js`가 그대로 `innerHTML`로 삽입합니다.
- `kind: "text"`: `icon`(Font Awesome 클래스) + `label` + `value_text`
  한 줄을 렌더링합니다.

## 설치

1. 이 폴더(`server_status`)를 통째로 BookOasis의 `plugins/metadata/`
   아래에 복사합니다. **폴더명은 반드시 `server_status`여야 합니다.**
   ```
   plugins/metadata/
     server_status/
       __init__.py
       server_status.py
       VERSION
       requirements.txt
       README.md
       dashboard.html
       dashboard.css
       dashboard.js
   ```
2. 서버를 재시작합니다. (`dashboard.html`/`css`/`js` 지원은 코어
   1.1.1+ 필요 — 이보다 낮은 버전에서는 이 파일들이 조용히 무시되고,
   `get_dashboard_data()`가 반환한 값이 기존 화이트리스트 텍스트
   렌더러로 표시되어 값이 다소 어색하게 나올 수 있습니다. 이 경우
   코어를 업그레이드하거나, 이전 버전(v3.x)을 사용하십시오.)
3. [환경설정 ⚙️ > 플러그인 설정]에서 "유메미루"를 **활성화**합니다.
4. 필요하면 아래 설정값을 조정 후 저장합니다.
   - `CPU_WARN` / `MEM_WARN` / `DISK_WARN`: 경고 임계치(%) — 게이지의
     초록/노랑/빨강 색상 존 경계로 그대로 사용됩니다.
   - `DISK_PATH`: 사용률을 확인할 디스크 경로 (기본값 `/`)
   - `CACHE_TTL_SEC`: 캐시 유지 시간(초, 기본 5초)
   - `WIDGET_SIZE` (표시 방식):
     - `small` (기본값): CPU/RAM/Disk/Swap 게이지 4개만
     - `general`: 위 게이지 4개 + Load average/Uptime/Network 텍스트 행
5. [내 설정 > 홈 화면 플러그인 배치 모드]를 켭니다.
6. 홈 화면 하단의 "+ 위젯 추가" 목록에서 "홈 서버 자원 상태" 위젯을
   추가합니다.

## 동작 방식

- 매 홈 화면 로드마다 `psutil`을 재호출하는 대신, 플러그인 전용 Redis
  캐시(`self.cache_get`/`self.cache_set`)로 짧게(기본 5초) 결과를
  재사용합니다. 캐시 키에 `small`/`general` 구분을 넣어 모드를 바꿔도
  섞이지 않게 했습니다.
- CPU 사용률은 `psutil.cpu_percent(interval=0.3)`로 측정하며, 캐시
  덕분에 실제 호출 빈도는 `CACHE_TTL_SEC`당 최대 1회입니다.
- 게이지 SVG는 Python에서 숫자 연산으로만 완성되므로(외부/사용자
  입력 없음) `dashboard.js`가 `innerHTML`로 삽입해도 안전합니다.
  라벨/값 텍스트는 항상 `textContent`로만 넣어 XSS를 원천 차단합니다.
  `icon`도 플러그인 코드가 만든 고정 문자열만 `className`에 넣습니다.

## 배운 점 (플러그인 개발자를 위한 메모)

1. `home_widget` 등 매니페스트 계약은 **항상 고정 dict**로 선언하고,
   설정에 따라 달라지는 부분은 `get_dashboard_data()` 내부에서 처리하십시오.
2. 필수 필드/메서드(`is_searchable`, `config_schema`, `search`, `apply`)는
   **실제 플러그인 클래스 본문에 리터럴로 직접** 선언하십시오.
3. **한 폴더 = 한 플러그인**, 클래스 `id`는 **폴더명과 정확히 일치**해야
   합니다.
4. 완전한 CSS/레이아웃이 필요한 홈 위젯은 `dashboard.html`/`css`/`js`를
   사용하십시오. `get_dashboard_data()`는 여전히
   `{'success': True, 'items': [...]}` 최상위 형태를 지켜야 하지만,
   `items` 배열 안 각 원소의 구조는 core의 `metric` 규격에 얽매이지
   않고 `dashboard.js`가 이해하는 자유 형식으로 설계해도 됩니다 —
   렌더링을 플러그인이 전부 책임지기 때문입니다.
5. SVG처럼 복잡한 좌표 계산이 필요한 그래픽은 JS보다 Python에서 미리
   완성된 문자열로 만들어 반환하는 편이 검증(단위 테스트)하기 쉽고,
   값이 순수 숫자 연산 결과라면 `innerHTML` 삽입도 안전합니다.
