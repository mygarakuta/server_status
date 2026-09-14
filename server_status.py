# -*- coding: utf-8 -*-
"""
서버 상태 모니터 플러그인 (Server Status Home Widget)
-----------------------------------------------------
BookOasis 홈 대시보드에 CPU / 메모리 / 디스크 사용률과
시스템 가동시간을 카드 형태로 보여주는 "홈화면 전용" 위젯 플러그인입니다.

가이드 문서 §5-1 `home_widget` 계약을 사용하므로, 사용자가
[내 설정 > 홈 화면 플러그인 배치 모드]를 켜고 홈 화면 하단의
"+ 위젯 추가" 목록에서 직접 추가해야만 노출됩니다.
(사이드바 카테고리나 [플러그인] 공통 데스크 탭에는 노출되지 않습니다.)

v1.1.0: 플러그인 설정에서 "작은 화면(1칸)/큰 화면(2칸)"을 고를 수 있는
        WIDGET_SIZE 옵션을 추가했습니다. 큰 화면을 선택하면 grid에서
        2칸을 차지하며, 남는 공간에 스왑 사용률/네트워크 누적 트래픽
        카드가 추가로 표시됩니다.

설치 방법:
1. 이 폴더(server_status) 전체를 BookOasis의 `plugins/metadata/` 아래로 복사합니다.
2. (필요 시) requirements.txt가 자동으로 처리되어 psutil이 설치됩니다.
3. 서버를 재시작합니다.
4. [환경설정 > 플러그인 설정]에서 "서버 상태 모니터"를 활성화하고,
   필요하면 경고 임계치와 위젯 크기를 조정 후 저장합니다.
5. [내 설정 > 홈 화면 플러그인 배치 모드]를 켠 뒤, 홈 화면의
   "+ 위젯 추가" 목록에서 "홈 서버 자원 상태" 위젯을 추가합니다.
"""
import time
import json
from datetime import datetime, timedelta

try:
    import psutil
except ImportError:  # requirements.txt로 자동 설치되지만 방어적으로 처리
    psutil = None

from plugins.metadata.base import BaseMetadataProvider


class ServerStatusMetadataProvider(BaseMetadataProvider):
    # 네임스페이스 접두사(가이드 §1 "플러그인 ID 네이밍 규칙")를 본인 식별자로
    # 바꿔 쓰는 것을 권장합니다. 예: "yourname.server_status"
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
            "label": "홈 위젯 크기",
            "type": "select",
            "default": "small",
            "options": [
                {"value": "small", "label": "작은 화면 (1칸, CPU/메모리/디스크/가동시간)"},
                {"value": "large", "label": "큰 화면 (2칸, 스왑·네트워크 정보 추가)"},
            ],
        },
    ]

    # 자동 업데이트 기능은 사용하지 않음 (개인 배포 플러그인 전제)
    update_manifest = {"enabled": False}

    # ── 홈 대시보드 전용 위젯 매니페스트 ──
    # WIDGET_SIZE 설정값에 따라 grid 칸 수(size)와 노출 아이템 개수(limit)가
    # 달라져야 하므로 클래스 속성(dict)이 아니라 property로 선언합니다.
    # (코어는 위젯을 렌더링할 때 플러그인 인스턴스를 통해 이 값을 읽습니다.)
    @property
    def home_widget(self):
        is_large = self._get_widget_size() == "large"
        return {
            "title": "홈 서버 자원 상태",
            "subtitle": "CPU / 메모리 / 디스크" + (" / 스왑 / 네트워크" if is_large else ""),
            "icon": "fa-solid fa-server",
            "order": 55,          # 코어 3섹션(10/20/30)보다 뒤에 배치
            "limit": 6 if is_large else 4,
            "sessions": "all",    # general/adult/audiobook/video 전 세션 노출
            "layout": "grid",
            "size": 2 if is_large else 1,  # 작은 화면=1칸, 큰 화면=2칸
        }

    # ── 필수 계약: 이 플러그인은 검색/적용 기능을 쓰지 않음 ──
    def search(self, db_type, query):
        return {"success": True, "items": []}

    def apply(self, db_type, book_id, item_data):
        return False, "이 플러그인은 대시보드 전용이며 메타데이터 적용을 지원하지 않습니다."

    # ── 내부 헬퍼 ──
    def _get_widget_size(self):
        # 위젯 크기는 세션(일반/성인/오디오북/영상)과 무관하게 하나로
        # 통일해서 관리하는 편이 자연스러우므로 'general' 설정을 기준으로 삼습니다.
        cfg = self.get_plugin_config("general", default={})
        value = str(cfg.get("WIDGET_SIZE", "small")).strip().lower()
        return "large" if value == "large" else "small"

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

    def _collect_metrics(self, db_type, is_large):
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

        boot_ts = psutil.boot_time()
        uptime_seconds = time.time() - boot_ts

        items = [
            {
                "item_type": "metric",
                "metric": "CPU 사용률",
                "value": f"{cpu_usage:.1f}%",
                "description": f"{self._status_icon(cpu_usage, cfg['cpu'])} 경고 임계치 {cfg['cpu']:.0f}%",
            },
            {
                "item_type": "metric",
                "metric": "메모리 사용률",
                "value": f"{mem.percent:.1f}%",
                "description": (
                    f"{self._status_icon(mem.percent, cfg['mem'])} "
                    f"사용 {mem.used // (1024 ** 2):,}MB / 전체 {mem.total // (1024 ** 2):,}MB"
                ),
            },
            {
                "item_type": "metric",
                "metric": "디스크 사용률",
                "value": f"{disk_usage:.1f}%" if disk_usage is not None else "N/A",
                "description": (
                    f"{self._status_icon(disk_usage, cfg['disk'])} 경로 {cfg['disk_path']} "
                    f"(여유 {disk.free // (1024 ** 3):,}GB)"
                    if disk is not None
                    else f"경로 '{cfg['disk_path']}'를 확인할 수 없습니다."
                ),
            },
            {
                "item_type": "metric",
                "metric": "가동 시간",
                "value": self._format_uptime(uptime_seconds),
                "description": f"부팅: {datetime.fromtimestamp(boot_ts).strftime('%Y-%m-%d %H:%M:%S')}",
            },
        ]

        # 큰 화면(2칸)을 선택한 경우, 남는 공간에 스왑/네트워크 카드를 추가
        if is_large:
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
    def get_dashboard_data(self, db_type, limit=10):
        is_large = self._get_widget_size() == "large"
        cache_key = f"metrics:{db_type}:{'large' if is_large else 'small'}"

        # psutil은 로컬 측정이라 가볍지만, 홈 화면을 자주 여는 상황을
        # 대비해 짧은 TTL 캐시로 중복 측정을 줄인다 (가이드 §5-1 권장 사항).
        cached = self.cache_get(cache_key)
        if cached:
            try:
                return json.loads(cached)
            except Exception:
                pass

        result = self._collect_metrics(db_type, is_large)
        if result.get("success"):
            try:
                ttl = self._get_config(db_type)["cache_ttl"]
                self.cache_set(cache_key, json.dumps(result), ttl=max(ttl, 1))
            except Exception:
                pass
        return result
