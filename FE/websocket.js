(function () {
    const patientId = 'Part101C';
    const ws = new WebSocket(`ws://localhost:3000/ws/patients/${patientId}`);
    let sendTimer = null;

    function ensureDashboardReady() {
        if (!window.dashboardState || typeof window.getSensorDataFromUI !== 'function' || typeof window.renderChart !== 'function' || typeof window.updateSlider !== 'function') {
            return false;
        }
        return true;
    }

    ws.onopen = () => {
        console.log('WebSocket Connected successfully to FastAPI');

        sendTimer = setInterval(() => {
            if (ws.readyState !== WebSocket.OPEN || !ensureDashboardReady()) {
                return;
            }

            const state = window.dashboardState;
            state.recordStartTimestamp += 1;
            const sensorData = window.getSensorDataFromUI();
            ws.send(JSON.stringify(sensorData));
        }, 1000);
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

        if (!payload.metrics || !payload.prediction || typeof payload.prediction.is_stress !== 'boolean') {
            console.error('Unexpected WebSocket response:', payload);
            return;
        }

        const state = window.dashboardState;
        const { metrics, prediction } = payload;

        const newPoint = {
            timestamp: metrics.timestamp,
            eda: metrics.eda,
            hr: metrics.hr,
            bvp: metrics.bvp,
            accelerometer: metrics.acc,
            temperature: metrics.temp,
            ibi: metrics.ibi,
            isStress: prediction.is_stress,
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
        if (sendTimer !== null) {
            clearInterval(sendTimer);
            sendTimer = null;
        }
        console.warn('WebSocket Connection Closed');
    };
})();
