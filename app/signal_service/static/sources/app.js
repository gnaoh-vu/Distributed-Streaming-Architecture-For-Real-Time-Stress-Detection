(function () {
    const WINDOW_SECONDS = 300;
    const MAX_BUFFER_SECONDS = 1000;
    
    const state = {
        MAX_BUFFER_SECONDS,
        dataBuffer: [],
        predictions: [],
        isLive: true,
        slider: document.getElementById('timeSlider'),
        btnToggleLive: document.getElementById('btn-toggle-live'),
        chart: document.getElementById('signalChart'),
        selectedPatientId: null,
        onPatientChange: null
    };

    function formatStatus(prediction) {
        if (!prediction || Number(prediction.label) < 0) {
            return { text: 'Waiting for prediction', className: 'pending', stress: null };
        }
        const stress = Number(prediction.label) === 1;
        return {
            text: stress ? 'STRESS DETECTED' : 'NORMAL',
            className: stress ? 'stress' : 'normal',
            stress
        };
    }

    function getTimelineSeconds(point) {
        if (!state.dataBuffer.length || !point) return 0;
        return Math.max(0, Math.round(point.timestamp - state.dataBuffer[0].timestamp));
    }

    function updateMetricValues(point, prediction) {
        if (!point) return;
        document.getElementById('val-eda').innerText = `${point.eda.toFixed(2)} µS`;
        document.getElementById('val-ibi').innerText =
            point.ibi !== null ? `${point.ibi.toFixed(0)} ms` : '--';

        const statusElement = document.getElementById('val-stress');
        const status = formatStatus(prediction);
        statusElement.innerText = status.text;
        statusElement.style.color = status.stress === null
            ? 'var(--text-sub)'
            : status.stress ? 'var(--accent-red)' : 'var(--accent-green)';
    }

    function renderChart(viewEndIndex) {
        const { chart, dataBuffer } = state;
        if (!chart || dataBuffer.length === 0) return;

        const endIndex = Math.max(0, Math.min(viewEndIndex, dataBuffer.length - 1));
        const endTimestamp = dataBuffer[endIndex].timestamp;
        const startTimestamp = Math.max(
            dataBuffer[0].timestamp,
            endTimestamp - WINDOW_SECONDS
        );
        const visibleData = dataBuffer.filter(point =>
            point.timestamp >= startTimestamp && point.timestamp <= endTimestamp
        );
        const predictionShapes = state.predictions
            .filter(prediction =>
                Number(prediction.start) <= endTimestamp &&
                Number(prediction.end) >= startTimestamp
            )
            .map(prediction => {
                const stress = Number(prediction.label) === 1;
                return {
                    type: 'rect',
                    xref: 'x',
                    yref: 'paper',
                    x0: Math.max(Number(prediction.start), startTimestamp),
                    x1: Math.min(Number(prediction.end), endTimestamp),
                    y0: 0,
                    y1: 1,
                    fillcolor: stress ? 'rgba(192, 57, 43, 0.16)' : 'rgba(47, 125, 79, 0.10)',
                    line: {
                        color: stress ? 'rgba(192, 57, 43, 0.45)' : 'rgba(47, 125, 79, 0.35)',
                        width: 1
                    }
                };
            });

        const firstTimestamp = state.dataBuffer[0].timestamp;
        const tickCount = 5;
        const tickValues = Array.from({ length: tickCount }, (_, index) =>
            startTimestamp + (endTimestamp - startTimestamp) * index / (tickCount - 1)
        );
        const currentPrediction = state.isLive
            ? state.predictions[state.predictions.length - 1]
            : state.predictions
                .filter(prediction =>
                    Number(prediction.start) <= endTimestamp &&
                    Number(prediction.end) >= endTimestamp
                )
                .sort((left, right) => Number(right.end) - Number(left.end))[0];

        Plotly.react(chart, [{
            x: visibleData.map(point => point.timestamp),
            y: visibleData.map(point => point.eda),
            type: 'scatter',
            mode: 'lines',
            line: { color: '#2b6f76', width: 2 },
            hovertemplate: 'Time %{customdata}s<br>EDA %{y:.2f} µS<extra></extra>',
            customdata: visibleData.map(point => getTimelineSeconds(point))
        }], {
            margin: { t: 12, r: 18, b: 38, l: 48 },
            paper_bgcolor: '#ffffff',
            plot_bgcolor: '#ffffff',
            font: { family: 'IBM Plex Mono, monospace', color: '#16181c', size: 11 },
            xaxis: {
                title: 'Time',
                gridcolor: '#e3e5e8',
                zeroline: false,
                range: [startTimestamp, endTimestamp],
                tickvals: tickValues,
                ticktext: tickValues.map(value => `${Math.round(value - firstTimestamp)}s`)
            },
            yaxis: { title: 'EDA (µS)', gridcolor: '#e3e5e8', zeroline: false, rangemode: 'tozero' },
            shapes: [
                ...predictionShapes,
                {
                    type: 'line',
                    x0: endTimestamp,
                    x1: endTimestamp,
                    y0: 0,
                    y1: 1,
                    yref: 'paper',
                    line: { color: '#16181c', dash: 'dot' }
                }
            ],
            showlegend: false
        }, { responsive: true, displaylogo: false });

        updateMetricValues(dataBuffer[endIndex], currentPrediction);
        const elapsedSeconds = getTimelineSeconds(dataBuffer[endIndex]);
        const timeDisplay = document.getElementById('time-display');
        if (timeDisplay) timeDisplay.innerText = `View Time: ${elapsedSeconds}s`;
    }

    function updateSlider() {
        if (!state.slider) return;
        const lastIndex = Math.max(0, state.dataBuffer.length - 1);
        state.slider.max = lastIndex;
        state.slider.disabled = state.dataBuffer.length === 0;
        if (state.isLive) state.slider.value = lastIndex;

        const currentIndex = Number(state.slider.value || 0);
        const point = state.dataBuffer[currentIndex];
        const label = document.getElementById('slider-time-label');
        if (label) label.innerText = `${getTimelineSeconds(point)}s`;
    }

    function resetPatient(patientId) {
        state.selectedPatientId = patientId;
        state.dataBuffer = [];
        state.predictions = [];
        state.isLive = true;
        state.slider.value = 0;
        state.slider.max = 0;
        state.slider.disabled = true;
        state.btnToggleLive.innerText = 'LIVE';
        state.btnToggleLive.classList.add('btn-live');
        document.getElementById('val-eda').innerText = '--';
        document.getElementById('val-ibi').innerText = '--';
        document.getElementById('val-stress').innerText = 'Waiting for prediction';
        document.getElementById('val-stress').style.color = 'var(--text-sub)';
        document.getElementById('time-display').innerText = 'Waiting for data';
        Plotly.purge(state.chart);
        if (typeof state.onPatientChange === 'function') state.onPatientChange(patientId);
    }

    function updatePatientCards(patients) {
        const selector = document.getElementById('patient-selector');
        const list = document.getElementById('patient-list-items');
        patients.forEach(patient => {
            const id = String(patient.id);
            const status = formatStatus(patient.latest_prediction);
            let option = Array.from(selector.options).find(item => item.value === id);
            if (!option) {
                option = document.createElement('option');
                option.value = id;
                selector.append(option);
            }
            option.textContent = `${id} — ${status.text}`;

            let card = Array.from(list.children).find(item => item.dataset.patientId === id);
            if (!card) {
                card = document.createElement('button');
                card.type = 'button';
                card.className = 'patient-card';
                card.dataset.patientId = id;
                card.innerHTML = '<strong></strong><p></p>';
                card.addEventListener('click', () => {
                    selector.value = id;
                    resetPatient(id);
                });
                list.append(card);
            }
            card.classList.remove('active', 'stress', 'normal', 'pending');
            card.classList.add(status.className);
            if (id === state.selectedPatientId) card.classList.add('active');
            card.querySelector('strong').textContent = patient.name || `Patient ${id}`;
            card.querySelector('p').textContent = `Status: ${status.text}`;
        });

        const availableIds = new Set(patients.map(patient => String(patient.id)));
        Array.from(selector.options).forEach(option => {
            if (option.value && !availableIds.has(option.value)) option.remove();
        });
        Array.from(list.children).forEach(card => {
            if (!availableIds.has(card.dataset.patientId)) card.remove();
        });
        selector.disabled = patients.length === 0;
        if (!state.selectedPatientId && patients.length > 0) {
            selector.value = String(patients[0].id);
            resetPatient(selector.value);
        } else if (state.selectedPatientId && !availableIds.has(state.selectedPatientId)) {
            resetPatient(patients.length > 0 ? String(patients[0].id) : null);
        }
    }

    window.addEventListener('resize', () => {
        if (state.chart && state.chart.data) Plotly.Plots.resize(state.chart);
    });

    state.slider.addEventListener('input', event => {
        state.isLive = false;
        state.btnToggleLive.innerText = 'GO LIVE';
        state.btnToggleLive.classList.remove('btn-live');
        const targetIndex = Number.parseInt(event.target.value, 10);
        const label = document.getElementById('slider-time-label');
        if (label) label.innerText = `${getTimelineSeconds(state.dataBuffer[targetIndex])}s`;
        renderChart(targetIndex);
    });

    state.btnToggleLive.addEventListener('click', () => {
        state.isLive = true;
        state.btnToggleLive.innerText = 'LIVE';
        state.btnToggleLive.classList.add('btn-live');
        state.slider.value = Math.max(0, state.dataBuffer.length - 1);
        renderChart(state.dataBuffer.length - 1);
    });

    document.getElementById('patient-selector').addEventListener('change', event => {
        if (event.target.value) resetPatient(event.target.value);
    });

    window.dashboardState = state;
    window.renderChart = renderChart;
    window.updateSlider = updateSlider;
    window.resetPatient = resetPatient;
    window.updatePatientCards = updatePatientCards;
})();
