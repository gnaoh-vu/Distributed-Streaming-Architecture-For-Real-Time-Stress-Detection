import { renderChart, renderMetricValues} from './monitoring.js'
import * as constants from './constants.js'
import { state } from './main.js'

let websocket = null;
let lastPatientId = null;
let latestIbiTimestamp = null;
let latestIbiMilliseconds = null;
let seenSensorTimestamps = new Set();
let seenPredictionRanges = new Set();

function appendSensorMessage(message) {
    const messageTimestamp = Number(message.timestamp);

    if (!Number.isFinite(messageTimestamp) || seenSensorTimestamps.has(messageTimestamp)) return;
    seenSensorTimestamps.add(messageTimestamp);

    if (seenSensorTimestamps.size > 1200) {
	seenSensorTimestamps = new Set(
	    Array.from(seenSensorTimestamps).sort((left, right) => left - right).slice(-1000)
	);
    }

    const ibiValues = Array.isArray(message.ibi) ? message.ibi : [];

    ibiValues.forEach(value => {
	const timestamp = Number(value);
	if (!Number.isFinite(timestamp)) return;
	if (latestIbiTimestamp !== null && timestamp > latestIbiTimestamp) {
	    latestIbiMilliseconds = (timestamp - latestIbiTimestamp) * 1000;
	}
	if (latestIbiTimestamp === null || timestamp > latestIbiTimestamp) {
	    latestIbiTimestamp = timestamp;
	}
    });

    const edaValues = Array.isArray(message.eda) ? message.eda : [];
    const sampleRate = 4;

    edaValues.forEach((value, index) => {
	const eda = Number(value);
	if (!Number.isFinite(eda)) return;
	state.dataBuffer.push({
	    timestamp: messageTimestamp,
	    eda,
	    ibi: latestIbiMilliseconds
	});
    });

    const latestTimestamp = state.dataBuffer.length
	? state.dataBuffer[state.dataBuffer.length - 1].timestamp
	: messageTimestamp;

    const earliestTimestamp = latestTimestamp - constants.MAX_BUFFER_SECONDS;
    state.dataBuffer = state.dataBuffer.filter(point => point.timestamp >= earliestTimestamp);
}

function appendPrediction(prediction) {
    const start = Number(prediction.start);
    const end = Number(prediction.end);

    if (!Number.isFinite(start) || !Number.isFinite(end)) return;

    const key = `${start}:${end}`;
    if (seenPredictionRanges.has(key)) return;

    seenPredictionRanges.add(key);

    if (seenPredictionRanges.size > 16) {
	seenPredictionRanges = new Set(Array.from(seenPredictionRanges).slice(-8));
    }

    state.predictions.push({
	...prediction,
	start,
	end,
	label: Number(prediction.label)
    });

    state.predictions.sort((left, right) => left.start - right.start);

    if (state.predictions.length > 4) {
	state.predictions.shift();
    }
}

function receiveSnapshot(event) {
    let snapshot;

    try {
	snapshot = JSON.parse(event.data);
    } catch (error) {
	console.error('Invalid patient snapshot from WebSocket:', error);
	return;
    }

    if (!snapshot || !Array.isArray(snapshot.sensors) || !Array.isArray(snapshot.predictions)) {
	console.error('Unexpected patient snapshot from WebSocket:', snapshot);
	return;
    }

    snapshot.sensors.forEach(appendSensorMessage);
    snapshot.predictions.forEach(appendPrediction);

    state.dataBuffer.sort((left, right) => left.timestamp - right.timestamp);
    state.predictions = state.predictions.filter(prediction =>
	!state.dataBuffer.length || prediction.end >= state.dataBuffer[0].timestamp - 300
    );

    if (state.dataBuffer.length) {
	const endIndex = state.dataBuffer.length - 1

	renderChart(endIndex);
	renderMetricValues(
	    state.dataBuffer[endIndex], 
	    state.predictions[state.predictions.length - 1]
	);
    }
}

function establishWS(patientId) {
    if (websocket) {
	websocket.onclose = null;
	websocket.close();
	websocket = null;
    }

    lastPatientId = patientId;
    latestIbiTimestamp = null;
    latestIbiMilliseconds = null;
    seenSensorTimestamps = new Set();
    seenPredictionRanges = new Set();
    if (patientId === null || patientId === undefined || patientId === '') return;

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    websocket = new WebSocket(
	`${protocol}//localhost:8001/ws/patients/${encodeURIComponent(patientId)}`
    );

    websocket.onopen = () => { console.log('connected') }
    websocket.onmessage = receiveSnapshot;
    websocket.onerror = error => console.error('Patient WebSocket error:', error);
    websocket.onclose = () => {
	if (lastPatientId === patientId) { console.log('disconnected') } 
    };
}

export { establishWS }
