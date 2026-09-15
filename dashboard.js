// server_status 홈 위젯 렌더러
// new Function('pluginId', 'shadowRoot', 'items', <이 파일 내용>) 형태로 실행되므로
// pluginId / shadowRoot / items 세 변수가 이미 스코프에 존재한다.

var container = shadowRoot.getElementById('ss-widget') || shadowRoot.querySelector('.ss-widget');
if (!container) {
    // 예상치 못한 마크업이면 조용히 종료 (Shadow DOM 안이라 앱 전체에 영향 없음)
} else {
    container.innerHTML = '';

    if (!items || items.length === 0) {
        var empty = document.createElement('div');
        empty.className = 'ss-empty';
        empty.textContent = '표시할 자원 정보가 없습니다.';
        container.appendChild(empty);
    } else {
        items.forEach(function (item, idx) {
            var row = document.createElement('div');
            row.className = 'ss-row';
            if (item.group_start && idx > 0) {
                row.className += ' ss-group-start';
            }

            var top = document.createElement('div');
            top.className = 'ss-row-top';

            var labelWrap = document.createElement('div');
            labelWrap.className = 'ss-row-label';

            if (item.icon) {
                var icon = document.createElement('i');
                // item.icon은 플러그인 코드가 만든 고정 문자열이라 안전하지만,
                // 방어적으로 className만 사용하고 innerHTML은 쓰지 않는다.
                icon.className = item.icon + ' ss-row-icon';
                labelWrap.appendChild(icon);
            }

            var labelText = document.createElement('span');
            labelText.textContent = item.label || '';
            labelWrap.appendChild(labelText);

            var valueText = document.createElement('span');
            valueText.className = 'ss-row-value';
            valueText.textContent = item.value_text || '';

            top.appendChild(labelWrap);
            top.appendChild(valueText);
            row.appendChild(top);

            if (typeof item.percent === 'number' && !isNaN(item.percent)) {
                var track = document.createElement('div');
                track.className = 'ss-bar-track';

                var fill = document.createElement('div');
                fill.className = 'ss-bar-fill';
                if (item.status === 'danger') {
                    fill.className += ' ss-danger';
                } else if (item.status === 'warn') {
                    fill.className += ' ss-warn';
                }

                var pct = Math.max(0, Math.min(100, item.percent));
                fill.style.width = pct + '%';

                track.appendChild(fill);
                row.appendChild(track);
            }

            container.appendChild(row);
        });
    }
}
