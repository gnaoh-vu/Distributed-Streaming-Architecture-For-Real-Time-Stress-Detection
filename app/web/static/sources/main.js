import { establishWS } from './websocket.js'
import { renderChart } from './monitoring.js'
import { getPatientSummary } from './summary.js'

import { formatStatus } from './utils.js'
import * as constants from './constants.js'

const state = {
    mode: 'monitoring',
    dataBuffer: [],
    predictions: [],
    selectedPatientId: null
};

const monitoringTab = document.querySelector('#monitoring-tab')
const summaryTab = document.querySelector('#summary-tab')

const monitoringDashboard = document.querySelector('.monitoring')
const summaryDashboard = document.querySelector('.summary')

function switchDashboard(tab) {
    if (tab == 'monitoring') {
	monitoringDashboard.classList.remove('hidden')
	summaryDashboard.classList.add('hidden')
	monitoringTab.classList.add('active')
	summaryTab.classList.remove('active')
	connectPatient(state.selectedPatientId)
    }

    else {
	summaryDashboard.classList.remove('hidden')
	monitoringDashboard.classList.add('hidden')
	monitoringTab.classList.remove('active')
	summaryTab.classList.add('active')
	getPatientSummary(state.selectedPatientId)
    }

    state.mode = tab
}

monitoringTab.onclick = () => {
    switchDashboard("monitoring")
}

summaryTab.onclick = () => {
    switchDashboard("summary")
}


async function getPatients() {
    try {
	const response = await fetch('http://localhost:8001/patients');
	if (!response.ok) 
	    throw new Error(`Patient list request failed: ${response.status}`);
	const patients = await response.json();
	renderPatientCards(patients);
    } catch (error) {
	console.error('Unable to refresh patient list:', error);
    }
}

function connectPatient(patientId) {
    state.dataBuffer = [];
    state.predictions = [];
    document.getElementById('val-eda').innerText = '--';
    document.getElementById('val-ibi').innerText = '--';
    document.getElementById('val-stress').innerText = 'Waiting for prediction';
    document.getElementById('val-stress').style.color = 'var(--text-sub)';
    document.getElementById('time-display').innerText = 'Waiting for data';

    Plotly.purge(signalChart);
    establishWS(patientId);
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
		selector.value = id;
		state.selectedPatientId = id;
		if (state.mode == 'monitoring') { connectPatient(id); } 
		else { getPatientSummary(id) }
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
	selector.value = String(patients[0].id)
	state.selectedPatientId = selector.value;
	establishWS(selector.value);
    } else if (state.selectedPatientId && !availableIds.has(state.selectedPatientId)) {
	establishWS(patients.length > 0 ? String(patients[0].id) : null);
    }
}

document.getElementById('patient-selector').addEventListener('change', event => {
    const patientId = event.target.value

    if (patientId) {
	if (state.mode == 'monitoring') connectPatient(patientId);
	else getPatientSummary(patientId)
    }
});

getPatients();
// window.setInterval(getPatients, 1000);

export { state }
