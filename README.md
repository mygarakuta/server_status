# 서버 상태 모니터 (server_status)

BookOasis 홈 대시보드에 **CPU / 메모리 / 디스크 사용률**을 아이콘 +
라벨 + 값 + 진행률 바 형태로 보여주는 홈화면 전용(`home_widget`)
플러그인입니다.

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

**v4.0 (현재) — `dashboard.html`/`dashboard.css`/`dashboard.js` 도입**
플러그인 가이드가 업데이트되어 `home_widget`에 완전한 커스텀 CSS/이미지를
쓸 수 있게 되었습니다(위젯별 **Shadow DOM 격리** 렌더링, 코어 1.1.1+).
이제 진짜 CSS 프로그레스 바로 교체했습니다.

- `dashboard.html`: 빈 컨테이너(`<div id="ss-widget">`)만 두고
- `dashboard.js`: `get_dashboard_data()`가 반환한 아이템 배열을 받아
  아이콘 + 라벨 + 값(우측 정렬) 한 줄과, 그 아래 진행률 바를 동적으로
  그립니다.
- `dashboard.css`: 앱 테마 CSS 변수(`--app-text-primary`, `--app-accent`
  등)를 사용해 테마 변경에도 자동으로 어울리도록 스타일링했습니다.

`get_dashboard_data()`가 반환하는 아이템은 더 이상 core의 `metric`
스키마(`metric`/`value`/`description`)를 따르지 않고, `dashboard.js`가
직접 해석하는 자유 형식입니다:

```json
{
  "icon": "fa-solid fa-microchip",
  "label": "CPU usage",
  "value_text": "16.16% of 4 CPUs",
  "percent": 16.16,
  "status": null
}
```

- `icon`: Font Awesome 클래스 문자열
- `label` / `value_text`: 좌우로 배치되는 텍스트
- `percent`: 있으면 그 값만큼 채워진 진행률 바를 그리고, 없으면(`null`)
  바 없이 텍스트 줄만 표시 (예: Load average, Uptime, Network)
- `status`: `"danger"`(빨강) / `"warn"`(주황) / 그 외(테마 강조색)
- `group_start`: 다음 시각적 그룹의 시작임을 표시해 위쪽에 약간 더 여백을 둠

`small` 모드는 CPU/RAM/Disk 3개 행(모두 바 포함)만, `general` 모드는
여기에 Load average(유닉스 계열만)/Uptime/Swap/Network까지 추가로
보여줍니다.

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
   `get_dashboard_data()`가 반환한 값이 대신 기존 화이트리스트
   텍스트 렌더러로 표시되어 값이 다소 어색하게 나올 수 있습니다.
   이 경우 코어를 업그레이드하거나, 이전 버전(v3.x)을 사용하십시오.)
3. [환경설정 ⚙️ > 플러그인 설정]에서 "서버 상태 모니터"를 **활성화**합니다.
4. 필요하면 아래 설정값을 조정 후 저장합니다.
   - `CPU_WARN` / `MEM_WARN` / `DISK_WARN`: 경고 임계치(%) — 초과 시
     바 색상이 빨강(`danger`), 85% 이상 근접 시 주황(`warn`)으로 표시됩니다.
   - `DISK_PATH`: 사용률을 확인할 디스크 경로 (기본값 `/`)
   - `CACHE_TTL_SEC`: 캐시 유지 시간(초, 기본 5초)
   - `WIDGET_SIZE` (표시 방식): `small` / `general`
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
- `dashboard.js`는 `textContent`만 사용해 라벨/값 텍스트를 그리므로
  (`innerHTML` 미사용), 값에 이상한 문자가 섞여도 XSS로 이어지지
  않습니다. `icon`은 플러그인 코드가 만든 고정 문자열만 `className`에
  넣습니다.

## 배운 점 (플러그인 개발자를 위한 메모)

1. `home_widget` 등 매니페스트 계약은 **항상 고정 dict**로 선언하고,
   설정에 따라 달라지는 부분은 `get_dashboard_data()` 내부에서 처리하십시오.
2. 필수 필드/메서드(`is_searchable`, `config_schema`, `search`, `apply`)는
   **실제 플러그인 클래스 본문에 리터럴로 직접** 선언하십시오.
3. **한 폴더 = 한 플러그인**, 클래스 `id`는 **폴더명과 정확히 일치**해야
   합니다.
4. 완전한 CSS/레이아웃이 필요한 홈 위젯은 `dashboard.html`/`css`/`js`를
   사용하십시오. 이 경우 `get_dashboard_data()`의 아이템 스키마는 코어의
   `metric` 규격에 얽매이지 않고, `dashboard.js`가 이해하는 자유
   형식으로 설계해도 됩니다 — 렌더링을 플러그인이 전부 책임지기 때문입니다.
