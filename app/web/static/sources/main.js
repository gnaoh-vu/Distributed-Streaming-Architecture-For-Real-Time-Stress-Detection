import { establishWS } from './websocket.js'

const WINDOW_SECONDS = 300;
const MAX_BUFFER_SECONDS = 1000;

const state = {
    MAX_BUFFER_SECONDS,
    mode: 'monitoring',
    dataBuffer: [],
    predictions: [],
    selectedPatientId: null
};

async function getPatients() {
    try {
	const response = await fetch('http://signal-service:8000/patients');
	if (!response.ok) 
	    throw new Error(`Patient list request failed: ${response.status}`);
	const patients = await response.json();
	renderPatientCards(patients);
    } catch (error) {
	console.error('Unable to refresh patient list:', error);
    }
}

function connectPatient(patientId) {
    state.selectedPatientId = patientId;
    state.dataBuffer = [];
    state.predictions = [];
    document.getElementById('val-eda').innerText = '--';
    document.getElementById('val-ibi').innerText = '--';
    document.getElementById('val-stress').innerText = 'Waiting for prediction';
    document.getElementById('val-stress').style.color = 'var(--text-sub)';
    document.getElementById('time-display').innerText = 'Waiting for data';

    Plotly.purge(signalChart);
    if (typeof state.onPatientChange === 'function') {
	establishWS(patientId);
    }
}

function renderPatientCards(patients) {
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
		if (state.mode == 'monitoring') {
		    selector.value = id;
		    connectPatient(id);
		}
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

document.getElementById('patient-selector').addEventListener('change', event => {
    if (event.target.value && state.mode == 'monitoring') {
	connectPatient(event.target.value);
    }
});

getPatients();
window.setInterval(getPatients, 1000);
