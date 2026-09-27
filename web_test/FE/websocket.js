(function () {
    const WS_URL = 'ws://localhost:3000/ws/predict';
    let ws = null;

    function ensureDashboardReady() {
        return (
            window.dashboardState &&
            typeof window.renderChart === 'function' &&
            typeof window.updateSlider === 'function'
        );
    }

    function connectWebSocket() {
        ws = new WebSocket(WS_URL)
        ws.onopen = () => {
            console.log('WebSocket Connected');
        };

        ws.onmessage = (event) => {
            if (!ensureDashboardReady()) {
                return;
            }

            let payload;
            try {
                payload = JSON.parse(event.data);
            } catch (error) {
                console.error('Invalid WebSocket response:', error);
                return;
            }

            if (!payload.metrics || !payload.prediction) {
                console.error('Unexpected WebSocket response:', payload);
                return;
            }

            const state = window.dashboardState;
            const { metrics, prediction } = payload;

            const newPoint = {
                timestamp: metrics.timestamp,
                eda: metrics.eda,
                hr: metrics.hr ?? null,
                bvp: metrics.bvp ?? null,
                accelerometer: metrics.acc ?? null,
                temperature: metrics.temp ?? null,
                ibi: metrics.ibi ?? null,
                isStress: Boolean(prediction.is_stress),
                confidence: prediction.confidence
            };

            state.dataBuffer.push(newPoint);

            if (state.dataBuffer.length > state.MAX_BUFFER_SIZE) {
                state.dataBuffer.shift();
            }

            state.slider.disabled = false;
            window.updateSlider();

            if (state.isLive) {
                window.renderChart(state.dataBuffer.length - 1);
            }
        };
        ws.onerror = (error) => {
            console.error('WebSocket Error:', error);
        };

        ws.onclose = () => {
            console.warn('WebSocket Connection Closed');
        };
    }
    connectWebSocket()
})();
