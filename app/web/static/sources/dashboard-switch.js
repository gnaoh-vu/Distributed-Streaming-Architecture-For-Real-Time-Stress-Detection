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
    }

    else {
	summaryDashboard.classList.remove('hidden')
	monitoringDashboard.classList.add('hidden')
	monitoringTab.classList.remove('active')
	summaryTab.classList.add('active')
    }
}

monitoringTab.onclick = () => {
    switchDashboard("monitoring")
}

summaryTab.onclick = () => {
    switchDashboard("summary")
}

