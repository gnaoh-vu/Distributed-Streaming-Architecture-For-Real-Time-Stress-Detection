        const dashboardState = {
            MAX_BUFFER_SIZE: 300,
            dataBuffer: [],
            isLive: true,
            recordStartTimestamp: 0,
            slider: null,
            btnToggleLive: null,
            canvas: null,
            ctx: null
        };

        dashboardState.canvas = document.getElementById('signalChart');
        dashboardState.ctx = dashboardState.canvas.getContext('2d');
        dashboardState.slider = document.getElementById('timeSlider');
        dashboardState.btnToggleLive = document.getElementById('btn-toggle-live');

        function resizeCanvas() {
            dashboardState.canvas.width = dashboardState.canvas.parentElement.clientWidth;
            dashboardState.canvas.height = dashboardState.canvas.parentElement.clientHeight;
        }

        function getSensorDataFromUI() {
            const isStress = dashboardState.elapsedSeconds >= 100 && dashboardState.elapsedSeconds <= 160;
            const baseEDA = isStress ? 8.0 : 2.0;
            const noise = (Math.random() - 0.5) * 0.8;
            const timestamp = Date.now()

            return {
                timestamp: timestamp,
                eda: parseFloat(Math.max(0.1, baseEDA + noise + Math.sin(dashboardState.recordStartTimestamp * 0.1) * 1.2).toFixed(2)),
                hr: Math.floor(isStress ? 110 + Math.random() * 10 : 70 + Math.random() * 5),
                acc: parseFloat((1 + (Math.random() - 0.5) * (isStress ? 0.35 : 0.15)).toFixed(2)),
                bvp: parseFloat(Math.max(0.1, (isStress ? 1.2 : 0.9) + (Math.random() - 0.5) * 0.25).toFixed(2)),
                temp: parseFloat((36.5 + (isStress ? 0.4 : 0) + (Math.random() - 0.5) * 0.3).toFixed(1)),
                ibi: 0.0
            };
        }

        function getTimelineSecondsFromIndex(index) {
            if (!dashboardState.dataBuffer.length) return 0;
            const targetIndex = Math.max(0, Math.min(index, dashboardState.dataBuffer.length - 1));
            const firstTimestamp = dashboardState.dataBuffer[0].timestamp;
            const targetPoint = dashboardState.dataBuffer[targetIndex];
            if (!targetPoint) return 0;
            return Math.max(0, Math.round((targetPoint.timestamp - firstTimestamp) / 1000));
        }

        function renderChart(viewEndIndex) {
            const { ctx, canvas, dataBuffer } = dashboardState;
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            if (dataBuffer.length < 2) return;

            const windowSize = 60;
            const endIndex = Math.min(viewEndIndex, dataBuffer.length - 1);
            const startIndex = Math.max(0, endIndex - windowSize);
            const visibleData = dataBuffer.slice(startIndex, endIndex + 1);

            const width = canvas.width;
            const height = canvas.height;
            const padding = 30;

            const edaValues = visibleData.map(d => d.eda);
            const minY = 0;
            const maxY = Math.max(12, Math.max(...edaValues) + 2);

            visibleData.forEach((pt, i) => {
                if (pt.isStress && i > 0) {
                    const x1 = padding + ((i - 1) / (windowSize - 1)) * (width - 2 * padding);
                    const x2 = padding + (i / (windowSize - 1)) * (width - 2 * padding);
                    ctx.fillStyle = 'rgba(239, 68, 68, 0.25)';
                    ctx.fillRect(x1, padding, x2 - x1, height - 2 * padding);
                }
            });

            ctx.strokeStyle = '#334155';
            ctx.lineWidth = 0.5;
            for (let i = 0; i <= 4; i++) {
                const y = padding + (i / 4) * (height - 2 * padding);
                ctx.beginPath();
                ctx.moveTo(padding, y);
                ctx.lineTo(width - padding, y);
                ctx.stroke();
            }

            ctx.strokeStyle = '#38bdf8';
            ctx.lineWidth = 2;
            ctx.beginPath();
            visibleData.forEach((pt, i) => {
                const x = padding + (i / (windowSize - 1)) * (width - 2 * padding);
                const y = height - padding - ((pt.eda - minY) / (maxY - minY)) * (height - 2 * padding);
                if (i === 0) ctx.moveTo(x, y);
                else ctx.lineTo(x, y);
            });
            ctx.stroke();

            const currentPt = dataBuffer[endIndex];
            if (currentPt) {
                document.getElementById('val-eda').innerText = `${currentPt.eda.toFixed(2)} µS`;
                document.getElementById('val-hr').innerText = `${currentPt.hr} BPM`;
                document.getElementById('val-bvp').innerText = currentPt.bvp.toFixed(2);
                document.getElementById('val-accelerometer').innerText = `${currentPt.accelerometer.toFixed(2)} g`;
                document.getElementById('val-temperature').innerText = `${currentPt.temperature.toFixed(1)} °C`;
                document.getElementById('val-ibi').innerText = `${currentPt.ibi} ms`;

                const stressElement = document.getElementById('val-stress');
                if (currentPt.isStress) {
                    stressElement.innerText = 'STRESS DETECTED';
                    stressElement.style.color = 'var(--accent-red)';
                } else {
                    stressElement.innerText = 'NORMAL';
                    stressElement.style.color = 'var(--accent-green)';
                }
                const elapsedSeconds = getTimelineSecondsFromIndex(endIndex);
                document.getElementById('time-display').innerText = `View Time: ${elapsedSeconds}s`;
            }
        }

        function updateSlider() {
            dashboardState.slider.max = dashboardState.dataBuffer.length - 1;
            if (dashboardState.isLive) {
                dashboardState.slider.value = dashboardState.dataBuffer.length - 1;
            }
            const currentSliderIndex = Number(dashboardState.slider.value || 0);
            document.getElementById('slider-time-label').innerText = `${getTimelineSecondsFromIndex(currentSliderIndex)}s`;
        }

        window.addEventListener('resize', resizeCanvas);
        resizeCanvas();

        dashboardState.slider.addEventListener('input', (e) => {
            dashboardState.isLive = false;
            dashboardState.btnToggleLive.innerText = 'GO LIVE';
            dashboardState.btnToggleLive.classList.remove('btn-live');
            const targetIndex = parseInt(e.target.value, 10);
            document.getElementById('slider-time-label').innerText = `${getTimelineSecondsFromIndex(targetIndex)}s`;
            renderChart(targetIndex);
        });

        dashboardState.btnToggleLive.addEventListener('click', () => {
            dashboardState.isLive = true;
            dashboardState.btnToggleLive.innerText = 'LIVE';
            dashboardState.btnToggleLive.classList.add('btn-live');
            dashboardState.slider.value = dashboardState.dataBuffer.length - 1;
            renderChart(dashboardState.dataBuffer.length - 1);
        });

        window.dashboardState = dashboardState;
        window.getSensorDataFromUI = getSensorDataFromUI;
        window.renderChart = renderChart;
        window.updateSlider = updateSlider;
