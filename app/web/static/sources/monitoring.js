import { getTimelineSeconds, formatStatus } from './utils.js'
import * as constants from './constants.js'
import { state } from './main.js'

const signalChart = document.getElementById('signalChart')

function renderMetricValues(point, prediction) {
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
    const { dataBuffer } = state;
    console.log(dataBuffer)

    if (!signalChart || dataBuffer.length === 0) return;

    const endIndex = Math.max(0, Math.min(viewEndIndex, dataBuffer.length - 1));
    const endTimestamp = dataBuffer[endIndex].timestamp;
    const startTimestamp = Math.max(
	dataBuffer[0].timestamp,
	endTimestamp - constants.WINDOW_SECONDS
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

    Plotly.react(signalChart, [{
	x: visibleData.map(point => point.timestamp),
	y: visibleData.map(point => point.eda),
	type: 'scatter',
	mode: 'lines',
	line: { color: '#2b6f76', width: 2 },
	hovertemplate: 'Time %{customdata}s<br>EDA %{y:.2f} µS<extra></extra>',
	customdata: visibleData.map(point => getTimelineSeconds(point, firstTimestamp))
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


    const elapsedSeconds = getTimelineSeconds(dataBuffer[endIndex], firstTimestamp);
    document.getElementById('time-display').innerText = `View Time: ${elapsedSeconds}s`;
}

window.addEventListener('resize', () => {
    if (signalChart && signalChart.data) Plotly.Plots.resize(signalChart);
});

export { renderChart, renderMetricValues }
