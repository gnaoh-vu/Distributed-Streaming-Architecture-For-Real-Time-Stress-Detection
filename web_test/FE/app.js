(function () {
    const dashboardState = {
        MAX_BUFFER_SIZE: 1000,
        dataBuffer: [],
        isLive: true,
        slider: null,
        btnToggleLive: null,
        chart: null
    };

    dashboardState.chart = document.getElementById('signalChart');
    dashboardState.slider = document.getElementById('timeSlider');
    dashboardState.btnToggleLive = document.getElementById('btn-toggle-live');

    function resizeChart() {
        if (dashboardState.chart && dashboardState.chart.data) {
            Plotly.Plots.resize(dashboardState.chart);
        }
    }

    function getTimelineSecondsFromIndex(index) {
        if (!dashboardState.dataBuffer.length) return 0;
        const targetIndex = Math.max(0, Math.min(index, dashboardState.dataBuffer.length - 1));
        const firstTimestamp = dashboardState.dataBuffer[0].timestamp;
        const targetPoint = dashboardState.dataBuffer[targetIndex];
        if (!targetPoint) return 0;
        return Math.max(0, Math.round(targetPoint.timestamp - firstTimestamp));
    }

    function renderChart(viewEndIndex) {
        const { chart, dataBuffer } = dashboardState;
        if (dataBuffer.length < 2 || !chart) return;

        const endIndex = Math.min(viewEndIndex, dataBuffer.length - 1);
        const startIndex = Math.max(0, endIndex - 60);
        const visibleData = dataBuffer.slice(startIndex, endIndex + 1);
        const xValues = visibleData.map((_, index) => index + startIndex);
        const stressRegions = [];
        let regionStart = null;

        visibleData.forEach((point, index) => {
            if (point.isStress && regionStart === null) regionStart = index + startIndex;
            if ((!point.isStress || index === visibleData.length - 1) && regionStart !== null) {
                stressRegions.push({
                    type: 'rect',
                    xref: 'x',
                    yref: 'paper',
                    x0: regionStart,
                    x1: index + startIndex,
                    y0: 0,
                    y1: 1,
                    fillcolor: 'rgba(192, 57, 43, 0.12)',
                    line: { width: 0 }
                });
                regionStart = null;
            }
        });

        Plotly.react(chart, [{
            x: xValues,
            y: visibleData.map(point => point.eda),
            type: 'scatter',
            mode: 'lines',
            line: { color: '#2b6f76', width: 2 },
            hovertemplate: 'Sample %{x}<br>EDA %{y:.2f} µS<extra></extra>'
        }], {
            margin: { t: 12, r: 18, b: 38, l: 48 },
            paper_bgcolor: '#ffffff',
            plot_bgcolor: '#ffffff',
            font: { family: 'IBM Plex Mono, monospace', color: '#16181c', size: 11 },
            xaxis: { title: 'Time', gridcolor: '#e3e5e8', zeroline: false },
            yaxis: { title: 'EDA (µS)', gridcolor: '#e3e5e8', zeroline: false, rangemode: 'tozero' },
            shapes: [
                ...stressRegions,
                { type: 'line', x0: endIndex, x1: endIndex, y0: 0, y1: 1, yref: 'paper', line: { color: '#c0392b', dash: 'dot' } }
            ],
            showlegend: false
        }, { responsive: true, displaylogo: false });

        const currentPt = dataBuffer[endIndex];
        if (currentPt) {
            document.getElementById('val-eda').innerText = `${currentPt.eda.toFixed(2)} µS`;

            document.getElementById('val-hr').innerText = currentPt.hr !== null ? `${currentPt.hr} BPM` : '--';
            document.getElementById('val-bvp').innerText = currentPt.bvp !== null ? currentPt.bvp.toFixed(2) : '--';
            document.getElementById('val-accelerometer').innerText = currentPt.accelerometer !== null ? `${currentPt.accelerometer.toFixed(2)} g` : '--';
            document.getElementById('val-temperature').innerText = currentPt.temperature !== null ? `${currentPt.temperature.toFixed(1)} °C` : '--';
            document.getElementById('val-ibi').innerText = currentPt.ibi !== null ? `${currentPt.ibi} ms` : '--';

            const stressElement = document.getElementById('val-stress');
            if (stressElement) {
                const confPercent = (currentPt.confidence * 100).toFixed(0);
                console.log(confPercent)
                if (currentPt.isStress) {
                    stressElement.innerText = `STRESS DETECTED (${confPercent}%)`;
                    stressElement.style.color = 'var(--accent-red)';
                } else {
                    stressElement.innerText = `NORMAL (${confPercent}%)`;
                    stressElement.style.color = 'var(--accent-green)';
                }
            }

            const elapsedSeconds = getTimelineSecondsFromIndex(endIndex);
            const timeDisplay = document.getElementById('time-display');
            if (timeDisplay) {
                timeDisplay.innerText = `View Time: ${elapsedSeconds}s`;
            }
            console.log(currentPt.isStress)
            
            
        }
    }

    function updateSlider() {
        if (!dashboardState.slider) return;
        dashboardState.slider.max = dashboardState.dataBuffer.length - 1;
        if (dashboardState.isLive) {
            dashboardState.slider.value = dashboardState.dataBuffer.length - 1;
        }
        const currentSliderIndex = Number(dashboardState.slider.value || 0);
        const label = document.getElementById('slider-time-label');
        if (label) {
            label.innerText = `${getTimelineSecondsFromIndex(currentSliderIndex)}s`;
        }
    }

    window.addEventListener('resize', resizeChart);

    if (dashboardState.slider) {
        dashboardState.slider.addEventListener('input', (e) => {
            dashboardState.isLive = false;
            if (dashboardState.btnToggleLive) {
                dashboardState.btnToggleLive.innerText = 'GO LIVE';
                dashboardState.btnToggleLive.classList.remove('btn-live');
            }
            const targetIndex = parseInt(e.target.value, 10);
            const label = document.getElementById('slider-time-label');
            if (label) {
                label.innerText = `${getTimelineSecondsFromIndex(targetIndex)}s`;
            }
            renderChart(targetIndex);
        });
    }

    if (dashboardState.btnToggleLive) {
        dashboardState.btnToggleLive.addEventListener('click', () => {
            dashboardState.isLive = true;
            dashboardState.btnToggleLive.innerText = 'LIVE';
            dashboardState.btnToggleLive.classList.add('btn-live');
            if (dashboardState.slider) {
                dashboardState.slider.value = dashboardState.dataBuffer.length - 1;
            }
            renderChart(dashboardState.dataBuffer.length - 1);
        });
    }


    window.dashboardState = dashboardState;
    window.renderChart = renderChart;
    window.updateSlider = updateSlider;
})();