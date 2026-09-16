// server_status 홈 위젯 렌더러
// new Function('pluginId', 'shadowRoot', 'items', <이 파일 내용>) 형태로 실행되므로
// pluginId / shadowRoot / items 세 변수가 이미 스코프에 존재한다.
//
// items의 각 원소는 서버(server_status.py)가 만든 자유 형식 아이템으로,
// 'kind'가 "gauge"면 SVG 반원형 게이지, "text"면 아이콘+라벨+값 한 줄로 렌더링한다.
// 'svg' 필드는 서버가 숫자 연산만으로 만든 문자열(사용자 입력 없음)이라
// innerHTML로 그대로 삽입해도 안전하다. 라벨/값 텍스트는 항상 textContent로만 넣는다.

var gaugeGrid = shadowRoot.getElementById('ss-gauge-grid');
var textList = shadowRoot.getElementById('ss-text-list');

if (gaugeGrid) {
    gaugeGrid.innerHTML = '';
}
if (textList) {
    textList.innerHTML = '';
}

var gaugeItems = (items || []).filter(function (item) { return item && item.kind === 'gauge'; });
var textItems = (items || []).filter(function (item) { return item && item.kind === 'text'; });

if (gaugeGrid) {
    if (gaugeItems.length === 0) {
        gaugeGrid.style.display = 'none';
    } else {
        gaugeGrid.style.display = '';
        gaugeItems.forEach(function (item) {
            var card = document.createElement('div');
            card.className = 'ss-gauge-card';

            var svgWrap = document.createElement('div');
            svgWrap.className = 'ss-gauge-svg-wrap';
            // item.svg는 서버가 숫자만으로 조립한 SVG 문자열이라 안전하다.
            svgWrap.innerHTML = item.svg || '';

            var label = document.createElement('div');
            label.className = 'ss-gauge-label';
            label.textContent = item.label || '';

            card.appendChild(svgWrap);
            card.appendChild(label);
            gaugeGrid.appendChild(card);
        });
    }
}

if (textList) {
    if (textItems.length === 0) {
        textList.style.display = 'none';
    } else {
        textList.style.display = '';
        textItems.forEach(function (item) {
            var row = document.createElement('div');
            row.className = 'ss-text-row';

            var labelWrap = document.createElement('div');
            labelWrap.className = 'ss-text-label';

            if (item.icon) {
                var icon = document.createElement('i');
                icon.className = item.icon + ' ss-text-icon';
                labelWrap.appendChild(icon);
            }

            var labelText = document.createElement('span');
            labelText.textContent = item.label || '';
            labelWrap.appendChild(labelText);

            var valueText = document.createElement('span');
            valueText.className = 'ss-text-value';
            valueText.textContent = item.value_text || '';

            row.appendChild(labelWrap);
            row.appendChild(valueText);
            textList.appendChild(row);
        });
    }
}
