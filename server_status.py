# -*- coding: utf-8 -*-
"""
서버 상태 모니터 플러그인 (Server Status Home Widget)
-----------------------------------------------------
BookOasis 홈 대시보드에 CPU / 메모리 / 디스크 사용률을 아이콘 + 라벨 +
값 + 진행률 바 형태로 보여주는 "홈화면 전용" 위젯 플러그인입니다.

── 버전 이력 ──────────────────────────────────────────────
v1.x  : home_widget을 @property로 구현 → 클래스 레벨 접근 실패로 전체
        로딩 실패. → 매니페스트는 항상 고정 dict여야 한다는 교훈.
v2.x  : "작은/큰 화면"을 별도 id의 두 클래스로 분리 → "폴더당 플러그인
        1개, id=폴더명" 규칙 위반으로 설치 거부.
v3.x  : 단일 플러그인(id=폴더명)으로 복귀, WIDGET_SIZE 설정으로 small/
        general 두 모드를 get_dashboard_data() 내부에서 분기. 진행률
        바는 item_type:"metric" 카드가 텍스트만 지원해 유니코드 막대
        문자(▰▱)로 근사.
v4.0 (현재) : 플러그인 가이드가 `dashboard.html`/`dashboard.css`/
        `dashboard.js`(Shadow DOM 격리 렌더링, 완전한 CSS 허용)를
        지원하게 되어, 진짜 CSS 프로그레스 바로 교체했다. 이제
        get_dashboard_data()는 core의 "metric" 스키마가 아니라
        dashboard.js가 이해하는 자유 형식 아이템
        (icon/label/value_text/percent/status)을 반환한다.

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
2. 서버를 재시작합니다. (dashboard.html/css/js를 지원하는 코어 1.1.1+
   필요 — 그보다 낮은 버전에서는 이 파일들이 무시되고 기존 텍스트
   카드로 자동 폴백됩니다.)
3. [환경설정 > 플러그인 설정]에서 "서버 상태 모니터"를 활성화하고,
   경고 임계치와 표시 방식(small/general)을 조정 후 저장합니다.
4. [내 설정 > 홈 화면 플러그인 배치 모드]를 켠 뒤, 홈 화면의
   "+ 위젯 추가" 목록에서 "홈 서버 자원 상태" 위젯을 추가합니다.
"""
import os
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
                {"value": "small", "label": "small (CPU/메모리/디스크만)"},
                {"value": "general", "label": "general (CPU/로드애버리지/메모리/디스크/가동시간/스왑/네트워크)"},
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
        # "small"이 아니면 전부 "general"(개별/상세) 모드로 취급한다.
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
    def _status_level(value, warn):
        """진행률 바 색상을 위한 상태 문자열 (dashboard.js가 해석)."""
        if value is None:
            return None
        if value >= warn:
            return "danger"
        if value >= warn * 0.85:
            return "warn"
        return None

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

        items = [
            {
                "icon": "fa-solid fa-microchip",
                "label": "CPU usage",
                "value_text": f"{cpu_usage:.2f}%",
                "percent": cpu_usage,
                "status": self._status_level(cpu_usage, cfg["cpu"]),
            },
        ]

        # 로드 애버리지는 유닉스 계열에서만 지원 (Windows에는 없음)
        if mode == "general" and hasattr(os, "getloadavg"):
            try:
                load1, load5, load15 = os.getloadavg()
                items.append({
                    "icon": "fa-solid fa-gauge-high",
                    "label": "Load average",
                    "value_text": f"{load1:.2f}, {load5:.2f}, {load15:.2f}",
                    "percent": None,
                })
            except Exception:
                pass

        items.append({
            "icon": "fa-solid fa-memory",
            "label": "RAM usage",
            "value_text": f"{mem.percent:.2f}%",
            "percent": mem.percent,
            "status": self._status_level(mem.percent, cfg["mem"]),
            "group_start": True,
        })

        items.append({
            "icon": "fa-solid fa-hard-drive",
            "label": f"{cfg['disk_path']} HD space",
            "value_text": f"{disk_usage:.2f}%" if disk is not None else "확인 불가",
            "percent": disk_usage,
            "status": self._status_level(disk_usage, cfg["disk"]),
        })

        if mode == "general":
            boot_ts = psutil.boot_time()
            uptime_seconds = time.time() - boot_ts
            items.append({
                "icon": "fa-solid fa-clock",
                "label": "Uptime",
                "value_text": f"{self._format_uptime(uptime_seconds)} (부팅: {datetime.fromtimestamp(boot_ts).strftime('%Y-%m-%d %H:%M')})",
                "percent": None,
                "group_start": True,
            })

            try:
                swap = psutil.swap_memory()
                if swap.total > 0:
                    items.append({
                        "icon": "fa-solid fa-database",
                        "label": "Swap usage",
                        "value_text": f"{swap.percent:.2f}%",
                        "percent": swap.percent,
                    })
            except Exception:
                pass

            try:
                net = psutil.net_io_counters()
                items.append({
                    "icon": "fa-solid fa-network-wired",
                    "label": "Network (누적)",
                    "value_text": f"↑{self._format_bytes(net.bytes_sent)} / ↓{self._format_bytes(net.bytes_recv)}",
                    "percent": None,
                })
            except Exception:
                pass

        return {"success": True, "items": items}

    # ── 공통 계약: home_widget이 재사용하는 표준 메서드 ──
    def get_dashboard_data(self, db_type, limit=10):
        mode = self._get_widget_size(db_type)  # "small" 또는 "general"
        cache_key = f"metrics:{db_type}:{mode}:v4"

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
