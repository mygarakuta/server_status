# -*- coding: utf-8 -*-
"""
서버 상태 모니터 플러그인 (Server Status Home Widget)
-----------------------------------------------------
BookOasis 홈 대시보드에 CPU / 메모리 / 디스크(/ 스왑) 사용률을
Zabbix 스타일 반원형 게이지(색상 존 + 바늘 + 중앙 값)로 보여주는
"홈화면 전용" 위젯 플러그인입니다. Load average / Uptime / Network처럼
0~100% 스케일이 아닌 값은 게이지 대신 텍스트 행으로 표시합니다.

── 버전 이력 ──────────────────────────────────────────────
v1.x  : home_widget을 @property로 구현 → 클래스 레벨 접근 실패로 전체
        로딩 실패. → 매니페스트는 항상 고정 dict여야 한다는 교훈.
v2.x  : "작은/큰 화면"을 별도 id의 두 클래스로 분리 → "폴더당 플러그인
        1개, id=폴더명" 규칙 위반으로 설치 거부.
v3.x  : 단일 플러그인(id=폴더명)으로 복귀, WIDGET_SIZE 설정으로 small/
        general 두 모드를 get_dashboard_data() 내부에서 분기. 진행률은
        유니코드 막대 문자(▰▱)로 근사.
v4.0~4.3 : dashboard.html/css/js(Shadow DOM 격리, 완전한 CSS 허용)로
        진짜 CSS 프로그레스 바 + 카드 배경/라운드 적용.
v5.0 (현재) : 프로그레스 바를 Zabbix 스타일 SVG 반원형 게이지(초록/
        노랑/빨강 색상 존 + 바늘 + 중앙 퍼센트 텍스트)로 교체했다.
        SVG 좌표 계산은 Python(math.cos/sin)에서 미리 완성해 문자열로
        반환하고, dashboard.js는 그 결과를 그대로 삽입만 한다 — 값은
        전부 숫자 연산 결과라 사용자 입력이 섞이지 않으므로 innerHTML
        삽입이 안전하다(라벨 등 텍스트는 여전히 textContent만 사용).

설치 방법:
1. 이 폴더(server_status) 전체를 BookOasis의 `plugins/metadata/` 아래로
   복사합니다. **폴더명은 반드시 `server_status`여야 합니다.**
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
2. 서버를 재시작합니다. (dashboard.html/css/js 지원은 코어 1.1.1+ 필요)
3. [환경설정 > 플러그인 설정]에서 "유메미루"를 활성화하고, 경고 임계치와
   표시 방식(small/general)을 조정 후 저장합니다.
4. [내 설정 > 홈 화면 플러그인 배치 모드]를 켠 뒤, 홈 화면의
   "+ 위젯 추가" 목록에서 "홈 서버 자원 상태" 위젯을 추가합니다.
"""
import os
import math
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
    name = "유메미루"
    is_searchable = False

    config_schema = [
        {"key": "CPU_WARN", "label": "CPU 경고 임계치(%)", "type": "number", "default": 80},
        {"key": "MEM_WARN", "label": "메모리 경고 임계치(%)", "type": "number", "default": 80},
        {"key": "DISK_WARN", "label": "디스크 경고 임계치(%)", "type": "number", "default": 90},
        {"key": "DISK_PATH", "label": "디스크 확인 경로", "type": "text", "default": "/"},
        {"key": "CACHE_TTL_SEC", "label": "측정값 캐시 시간(초)", "type": "number", "default": 5},
        {
            "key": "WIDGET_SIZE",
            "label": "표시 방식",
            "type": "select",
            "default": "small",
            "options": [
                {"value": "small", "label": "small (CPU/메모리/디스크 게이지만)"},
                {"value": "general", "label": "general (위 게이지 + 스왑 게이지 + 로드애버리지/가동시간/네트워크)"},
            ],
        },
    ]

    # 자동 업데이트 기능은 사용하지 않음 (개인 배포 플러그인 전제)
    update_manifest = {"enabled": False}

    # ── 홈 대시보드 전용 위젯 매니페스트 (반드시 고정 dict) ──
    home_widget = {
        "title": "홈 서버 자원 상태",
        "subtitle": "",
        "icon": "fa-solid fa-server",
        "order": 55,
        "limit": 10,
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
        # "small"이 아니면 전부 "general"(상세) 모드로 취급한다.
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
    def _gauge_point(percent, radius, cx=100, cy=100):
        """반원(왼쪽=0%, 위쪽=50%, 오른쪽=100%) 위의 좌표를 계산한다."""
        angle_deg = 180.0 - (percent / 100.0) * 180.0
        theta = math.radians(angle_deg)
        return cx + radius * math.cos(theta), cy - radius * math.sin(theta)

    @classmethod
    def _gauge_arc_path(cls, p_start, p_end, radius, cx=100, cy=100):
        x1, y1 = cls._gauge_point(p_start, radius, cx, cy)
        x2, y2 = cls._gauge_point(p_end, radius, cx, cy)
        return f"M {x1:.2f} {y1:.2f} A {radius} {radius} 0 0 1 {x2:.2f} {y2:.2f}"

    @classmethod
    def _gauge_svg(cls, value, warn):
        """Zabbix 스타일 반원형 게이지 SVG 마크업을 생성한다.
        value/warn은 전부 숫자 연산 결과이므로(사용자 입력 없음),
        결과 문자열을 dashboard.js에서 innerHTML로 그대로 삽입해도 안전하다."""
        value = 0.0 if value is None else max(0.0, min(100.0, float(value)))
        warn = max(1.0, min(99.0, float(warn) if warn else 80.0))

        zones = [
            (0.0, warn * 0.85, "#22c55e"),   # 초록
            (warn * 0.85, warn, "#eab308"),  # 노랑
            (warn, 100.0, "#ef4444"),        # 빨강
        ]
        radius = 78
        stroke_w = 14
        zone_svg = "".join(
            f'<path d="{cls._gauge_arc_path(a, b, radius)}" stroke="{color}" '
            f'stroke-width="{stroke_w}" fill="none"/>'
            for a, b, color in zones if b > a
        )

        needle_x, needle_y = cls._gauge_point(value, radius - 12)

        return (
            '<svg viewBox="0 0 200 118" class="ss-gauge-svg" xmlns="http://www.w3.org/2000/svg">'
            f'{zone_svg}'
            f'<line x1="100" y1="100" x2="{needle_x:.2f}" y2="{needle_y:.2f}" class="ss-gauge-needle"/>'
            '<circle cx="100" cy="100" r="6" class="ss-gauge-hub"/>'
            f'<text x="100" y="80" text-anchor="middle" class="ss-gauge-value">{value:.2f}%</text>'
            '<text x="16" y="112" text-anchor="start" class="ss-gauge-minmax">0%</text>'
            '<text x="184" y="112" text-anchor="end" class="ss-gauge-minmax">100%</text>'
            '</svg>'
        )

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

        gauges = [
            {"kind": "gauge", "label": "CPU usage", "svg": self._gauge_svg(cpu_usage, cfg["cpu"])},
            {"kind": "gauge", "label": "RAM usage", "svg": self._gauge_svg(mem.percent, cfg["mem"])},
            {
                "kind": "gauge",
                "label": f"{cfg['disk_path']} disk",
                "svg": self._gauge_svg(disk_usage, cfg["disk"]) if disk is not None else None,
            },
        ]
        gauges = [g for g in gauges if g.get("svg")]

        texts = []

        if mode == "general":
            # 스왑도 게이지로 (임계치는 별도 설정 없이 80% 고정 사용)
            try:
                swap = psutil.swap_memory()
                if swap.total > 0:
                    gauges.append({
                        "kind": "gauge",
                        "label": "Swap usage",
                        "svg": self._gauge_svg(swap.percent, 80.0),
                    })
            except Exception:
                pass

            # 로드 애버리지는 유닉스 계열에서만 지원 (Windows에는 없음)
            if hasattr(os, "getloadavg"):
                try:
                    load1, load5, load15 = os.getloadavg()
                    texts.append({
                        "kind": "text",
                        "icon": "fa-solid fa-gauge-high",
                        "label": "Load average",
                        "value_text": f"{load1:.2f}, {load5:.2f}, {load15:.2f}",
                    })
                except Exception:
                    pass

            boot_ts = psutil.boot_time()
            uptime_seconds = time.time() - boot_ts
            texts.append({
                "kind": "text",
                "icon": "fa-solid fa-clock",
                "label": "Uptime",
                "value_text": (
                    f"{self._format_uptime(uptime_seconds)} "
                    f"(부팅: {datetime.fromtimestamp(boot_ts).strftime('%Y-%m-%d %H:%M')})"
                ),
            })

            try:
                net = psutil.net_io_counters()
                texts.append({
                    "kind": "text",
                    "icon": "fa-solid fa-network-wired",
                    "label": "Network (누적)",
                    "value_text": f"↑{self._format_bytes(net.bytes_sent)} / ↓{self._format_bytes(net.bytes_recv)}",
                })
            except Exception:
                pass

        # 코어 계약({'success': True, 'items': [...]})을 지키기 위해 게이지와
        # 텍스트 행을 하나의 items 리스트로 합친다. dashboard.js가 각
        # 아이템의 'kind' 값으로 게이지 그리드 / 텍스트 목록에 나눠 배치한다.
        return {"success": True, "items": gauges + texts}

    # ── 공통 계약: home_widget이 재사용하는 표준 메서드 ──
    def get_dashboard_data(self, db_type, limit=10):
        mode = self._get_widget_size(db_type)  # "small" 또는 "general"
        cache_key = f"metrics:{db_type}:{mode}:v5"

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
