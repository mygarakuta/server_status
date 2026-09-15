# -*- coding: utf-8 -*-
"""
서버 상태 모니터 플러그인 (Server Status Home Widget)
-----------------------------------------------------
BookOasis 홈 대시보드에 CPU / 메모리 / 디스크 사용률과
시스템 가동시간을 카드 형태로 보여주는 "홈화면 전용" 위젯 플러그인입니다.

── 버전 이력 (겪었던 로딩/검증 실패와 그 해결) ──────────────────────
v1.x : home_widget을 @property로 구현 → 코어가 클래스 레벨에서 dict를
       기대하고 접근하다가 property 객체를 만나 예외 발생 → 플러그인
       전체 로딩 실패(설정 화면도 사라짐). "매니페스트 계약은 항상
       고정 dict여야 한다"는 교훈을 얻고 되돌림.
v2.0~2.2 : "작은 화면/큰 화면"을 아예 별도 id의 두 클래스(플러그인)로
       분리 → 설치 검증기가 "폴더당 플러그인 1개, id는 폴더명과 일치
       해야 함"을 요구해 거부됨.
v3.0 (현재) : 단일 플러그인(id = 폴더명 = "server_status")으로 되돌리고,
       "작은 화면/큰 화면"은 위젯의 정적 매니페스트(home_widget, 항상
       고정 dict)가 아니라 **설정(config_schema)의 WIDGET_SIZE 값에
       따라 get_dashboard_data()가 반환하는 카드 개수**로 구현했다.
       home_widget 자체는 완전히 고정된 dict이므로 클래스 레벨 접근도
       안전하고, get_dashboard_data()는 원래도 매 요청마다 호출되는
       메서드라 여기서 설정을 읽어 분기하는 것은 안전한 정석 패턴이다.
       (참고: 그리드에서 실제 차지하는 칸 수(size)는 위젯 렌더링 이전
       단계에서 고정되어야 하므로 1칸으로 유지되며, "큰 화면"을 선택해도
       칸 수 자체는 늘어나지 않고 카드 개수/정보량만 늘어난다.)

설치 방법:
1. 이 폴더(server_status) 전체를 BookOasis의 `plugins/metadata/` 아래로
   복사합니다. **폴더명이 반드시 `server_status`여야 합니다** (클래스의
   `id`와 정확히 일치해야 검증을 통과합니다).
2. (필요 시) requirements.txt가 자동으로 처리되어 psutil이 설치됩니다.
3. 서버를 재시작합니다.
4. [환경설정 > 플러그인 설정]에서 "서버 상태 모니터"를 활성화하고,
   경고 임계치와 "홈 위젯 표시 정보량"(작은 화면/큰 화면)을 조정 후
   저장합니다.
5. [내 설정 > 홈 화면 플러그인 배치 모드]를 켠 뒤, 홈 화면의
   "+ 위젯 추가" 목록에서 "홈 서버 자원 상태" 위젯을 추가합니다.
"""
import time
import json
from datetime import datetime

try:
    import psutil
except ImportError:  # requirements.txt로 자동 설치되지만 방어적으로 처리
    psutil = None

from plugins.metadata.base import BaseMetadataProvider


class ServerStatusMetadataProvider(BaseMetadataProvider):
    # id는 반드시 이 플러그인 폴더명("server_status")과 일치해야 합니다.
    id = "server_status"
    name = "서버 상태 모니터"
    is_searchable = False

    config_schema = [
        {"key": "CPU_WARN", "label": "CPU 경고 임계치(%)", "type": "number", "default": 80},
        {"key": "MEM_WARN", "label": "메모리 경고 임계치(%)", "type": "number", "default": 80},
        {"key": "DISK_WARN", "label": "디스크 경고 임계치(%)", "type": "number", "default": 90},
        {"key": "DISK_PATH", "label": "디스크 확인 경로", "type": "text", "default": "/"},
        {"key": "CACHE_TTL_SEC", "label": "측정값 캐시 시간(초)", "type": "number", "default": 5},
        {
            "key": "WIDGET_SIZE",
            "label": "홈 위젯 표시 정보량",
            "type": "select",
            "default": "small",
            "options": [
                {"value": "small", "label": "small (CPU/메모리/디스크를 한 카드에 통합 표시)"},
                {"value": "general", "label": "general (CPU/메모리/디스크 + 가동시간/스왑/네트워크를 개별 카드로 표시)"},
            ],
        },
    ]

    # 자동 업데이트 기능은 사용하지 않음 (개인 배포 플러그인 전제)
    update_manifest = {"enabled": False}

    # ── 홈 대시보드 전용 위젯 매니페스트 (반드시 고정 dict) ──
    # 그리드 칸 수(size)는 위젯 등록 시점에 고정되어야 안전하므로 1로
    # 유지한다. "큰 화면" 설정은 실제 칸 수가 아니라 카드 개수(정보량)를
    # 늘리는 방식으로 구현되어 있다 (get_dashboard_data 참고).
    home_widget = {
        "title": "홈 서버 자원 상태",
        "subtitle": "",
        "icon": "fa-solid fa-server",
        "order": 55,
        "limit": 6,   # WIDGET_SIZE=general일 때 최대 6개까지 나오므로 넉넉히 지정
        "sessions": "all",
        "layout": "grid",
        "size": 1,
    }

    # ── 필수 계약: 검색/적용 기능은 사용하지 않음 ──
    def search(self, db_type, query):
        return {"success": True, "items": []}

    def apply(self, db_type, book_id, item_data):
        return False, "이 플러그인은 대시보드 전용이며 메타데이터 적용을 지원하지 않습니다."

    # ── 내부 헬퍼 ──
    def _get_widget_size(self, db_type):
        cfg = self.get_plugin_config(db_type, default={})
        value = str(cfg.get("WIDGET_SIZE", "small")).strip().lower()
        # "small"이 아니면 전부 "general"(개별 카드) 모드로 취급한다.
        # (예전 버전에 저장된 "large" 값과도 자연스럽게 호환된다.)
        return "small" if value == "small" else "general"

    def _get_config(self, db_type):
        cfg = self.get_plugin_config(db_type, default={})

        def _num(key, default):
            try:
                return float(cfg.get(key, default))
            except (TypeError, ValueError):
                return default

        return {
            "cpu": _num("CPU_WARN", 80),
            "mem": _num("MEM_WARN", 80),
            "disk": _num("DISK_WARN", 90),
            "disk_path": cfg.get("DISK_PATH") or "/",
            "cache_ttl": int(_num("CACHE_TTL_SEC", 5)),
        }

    @staticmethod
    def _format_uptime(seconds):
        total = int(seconds)
        days, rem = divmod(total, 86400)
        hours, rem = divmod(rem, 3600)
        minutes, _ = divmod(rem, 60)
        parts = []
        if days:
            parts.append(f"{days}일")
        if hours or days:
            parts.append(f"{hours}시간")
        parts.append(f"{minutes}분")
        return " ".join(parts)

    @staticmethod
    def _format_bytes(num_bytes):
        value = float(num_bytes)
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if value < 1024.0:
                return f"{value:.1f}{unit}"
            value /= 1024.0
        return f"{value:.1f}PB"

    @staticmethod
    def _status_icon(value, warn):
        if value is None:
            return "❔"
        if value >= warn:
            return "🔴"
        if value >= warn * 0.85:
            return "🟡"
        return "🟢"

    @staticmethod
    def _gauge(percent, width=10):
        """유니코드 막대 문자로 텍스트 안에 표시하는 간이 게이지 바.
        실제 CSS 프로그레스 바는 아니지만(홈 위젯 metric 카드는 텍스트만
        지원), 옆에 붙이면 시각적으로 비슷한 효과를 준다."""
        if percent is None:
            return "▱" * width
        try:
            pct = max(0.0, min(100.0, float(percent)))
        except (TypeError, ValueError):
            return "▱" * width
        filled = max(0, min(width, int(round(pct / 100.0 * width))))
        return "▰" * filled + "▱" * (width - filled)

    def _collect_metrics(self, db_type, mode):
        if psutil is None:
            return {"success": False, "error": "psutil 모듈이 설치되어 있지 않습니다."}

        cfg = self._get_config(db_type)

        # cpu_percent는 interval을 주면 그 시간만큼 블로킹되므로 짧게만 사용
        cpu_usage = psutil.cpu_percent(interval=0.3)
        mem = psutil.virtual_memory()

        try:
            disk = psutil.disk_usage(cfg["disk_path"])
            disk_usage = disk.percent
        except Exception:
            disk = None
            disk_usage = None

        if mode == "small":
            # small: CPU/메모리/디스크 현황을 하나의 리스트(카드 1개)로 통합 표시.
            # 각 줄에 유니코드 게이지 바를 붙여 스크린샷과 비슷한 느낌을 낸다.
            # 라벨/설명 텍스트는 넣지 않고 값(게이지 바 3줄)만 표시한다.
            cpu_line = f"CPU  {cpu_usage:>3.0f}% {self._gauge(cpu_usage)}"
            mem_line = f"MEM  {mem.percent:>3.0f}% {self._gauge(mem.percent)}"
            disk_line = (
                f"DISK {disk_usage:>3.0f}% {self._gauge(disk_usage)}"
                if disk_usage is not None
                else "DISK  N/A"
            )
            combined_value = "\n".join([cpu_line, mem_line, disk_line])
            items = [
                {
                    "item_type": "metric",
                    "metric": "",
                    "value": combined_value,
                    "description": "",
                },
            ]
            return {"success": True, "items": items}

        # general: CPU/메모리/디스크를 각각 개별 리스트(카드)로 표시
        items = [
            {
                "item_type": "metric",
                "metric": "CPU 사용률",
                "value": f"{cpu_usage:.0f}% {self._gauge(cpu_usage)}",
                "description": f"{self._status_icon(cpu_usage, cfg['cpu'])} 경고 임계치 {cfg['cpu']:.0f}%",
            },
            {
                "item_type": "metric",
                "metric": "메모리 사용률",
                "value": f"{mem.percent:.0f}% {self._gauge(mem.percent)}",
                "description": (
                    f"{self._status_icon(mem.percent, cfg['mem'])} "
                    f"사용 {mem.used // (1024 ** 2):,}MB / 전체 {mem.total // (1024 ** 2):,}MB"
                ),
            },
            {
                "item_type": "metric",
                "metric": "디스크 사용률",
                "value": (
                    f"{disk_usage:.0f}% {self._gauge(disk_usage)}"
                    if disk_usage is not None else "N/A"
                ),
                "description": (
                    f"{self._status_icon(disk_usage, cfg['disk'])} 경로 {cfg['disk_path']} "
                    f"(여유 {disk.free // (1024 ** 3):,}GB)"
                    if disk is not None
                    else f"경로 '{cfg['disk_path']}'를 확인할 수 없습니다."
                ),
            },
        ]

        # 가동시간/스왑/네트워크도 각각 개별 카드로 추가
        boot_ts = psutil.boot_time()
        uptime_seconds = time.time() - boot_ts
        items.append({
            "item_type": "metric",
            "metric": "가동 시간",
            "value": self._format_uptime(uptime_seconds),
            "description": f"부팅: {datetime.fromtimestamp(boot_ts).strftime('%Y-%m-%d %H:%M:%S')}",
        })

        try:
            swap = psutil.swap_memory()
            swap_desc = (
                f"사용 {swap.used // (1024 ** 2):,}MB / 전체 {swap.total // (1024 ** 2):,}MB"
                if swap.total > 0 else "스왑 미설정"
            )
            items.append({
                "item_type": "metric",
                "metric": "스왑 사용률",
                "value": f"{swap.percent:.1f}%" if swap.total > 0 else "N/A",
                "description": swap_desc,
            })
        except Exception:
            pass

        try:
            net = psutil.net_io_counters()
            items.append({
                "item_type": "metric",
                "metric": "네트워크 누적 트래픽",
                "value": f"↑{self._format_bytes(net.bytes_sent)} / ↓{self._format_bytes(net.bytes_recv)}",
                "description": "서버 부팅 이후 누적 송신/수신량",
            })
        except Exception:
            pass

        return {"success": True, "items": items}

    # ── 공통 계약: home_widget이 재사용하는 표준 메서드 ──
    # 매니페스트(home_widget)는 고정 dict로 유지하고, 실제 "small(통합)/
    # general(개별)" 분기는 이 메서드 내부에서 설정을 읽어 처리한다
    # (요청마다 호출되므로 설정을 반영하기에 안전한 지점이다).
    def get_dashboard_data(self, db_type, limit=10):
        mode = self._get_widget_size(db_type)  # "small" 또는 "general"
        cache_key = f"metrics:{db_type}:{mode}"

        # psutil은 로컬 측정이라 가볍지만, 홈 화면을 자주 여는 상황을
        # 대비해 짧은 TTL 캐시로 중복 측정을 줄인다 (가이드 §5-1 권장 사항).
        cached = self.cache_get(cache_key)
        if cached:
            try:
                return json.loads(cached)
            except Exception:
                pass

        result = self._collect_metrics(db_type, mode)
        if result.get("success"):
            try:
                ttl = self._get_config(db_type)["cache_ttl"]
                self.cache_set(cache_key, json.dumps(result), ttl=max(ttl, 1))
            except Exception:
                pass
        return result
