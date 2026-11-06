const DAY_NAMES = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
const TIME_REGIONS = [
    "00:00 - 02:59", "03:00 - 05:59", "06:00 - 08:59",
    "09:00 - 11:59", "12:00 - 14:59", "15:00 - 17:59",
    "18:00 - 20:59", "21:00 - 23:59"
];
const TIME_REGION_LABELS = [
    "00–03h", "03–06h", "06–09h", "09–12h",
    "12–15h", "15–18h", "18–21h", "21–24h"
];

const selector = document.getElementById("patient-selector");
const patientCards = document.getElementById("patient-list-items");
const histogramTab = document.getElementById("histogram-tab");
const heatmapTab = document.getElementById("heatmap-tab");

let activePatient = "";
let activeChart = "histogram";
let histogramData = [];
let heatmapData = [];

async function fetchJson(url) {
    const response = await fetch(url);
    if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
    return response.json();
}

function setLayout(title) {
    return {
        title: { text: title, font: { family: "IBM Plex Sans", size: 16, color: "#16181c" } },
        margin: { l: 65, r: 25, t: 55, b: 55 },
        paper_bgcolor: "#ffffff",
        plot_bgcolor: "#ffffff",
        font: { family: "IBM Plex Sans", color: "#16181c" },
        xaxis: { gridcolor: "#e3e5e8", linecolor: "#e3e5e8" },
        yaxis: { gridcolor: "#e3e5e8", linecolor: "#e3e5e8" }
    };
}

function renderHistogram() {
    const countsByDay = Array(7).fill(0);
    histogramData.forEach(row => {
        countsByDay[Number(row.day_of_week)] = Number(row.stress_counts);
    });

    Plotly.react("trendChart", [{
        x: DAY_NAMES,
        y: countsByDay,
        type: "bar",
        marker: {
            color: countsByDay.map(count => count === Math.max(...countsByDay) ? "#c0392b" : "#2b6f76"),
            line: { color: "#ffffff", width: 1 }
        },
        hovertemplate: "%{x}<br>%{y} stress events<extra></extra>"
    }], {
        ...setLayout("Patient stress frequency by day"),
        bargap: 0.18,
        yaxis: { title: "Stress events", rangemode: "tozero", gridcolor: "#e3e5e8", linecolor: "#e3e5e8", tickformat: "d" },
        xaxis: { title: "Day of week" }
    }, { responsive: true, displaylogo: false });

    const total = countsByDay.reduce((sum, count) => sum + count, 0);
    const peakIndex = countsByDay.indexOf(Math.max(...countsByDay));
    document.getElementById("stress-count").textContent = total.toLocaleString();
    document.getElementById("peak-day").textContent = total ? DAY_NAMES[peakIndex] : "--";
}

function renderHeatmap() {
    const counts = DAY_NAMES.map(() => TIME_REGIONS.map(() => 0));
    heatmapData.forEach(row => {
        const dayIndex = Number(row.day_of_week);
        const regionIndex = Number(row.time_region);
        if (counts[dayIndex] && regionIndex >= 0 && regionIndex < TIME_REGIONS.length) {
            counts[dayIndex][regionIndex] += Number(row.stress_counts);
        }
    });

    Plotly.react("trendChart", [{
        z: counts,
        x: TIME_REGION_LABELS,
        y: DAY_NAMES,
        type: "heatmap",
        xgap: 2,
        ygap: 2,
        zsmooth: false,
        showscale: true,
        text: counts.map(row => row.map(String)),
        texttemplate: "%{text}",
        colorscale: [
            [0, "#f2f4f5"], [0.25, "#b7d0d1"], [0.5, "#6d9fa3"],
            [0.75, "#2b6f76"], [1, "#c0392b"]
        ],
        hovertemplate: "%{y}<br>%{x}<br>%{z} stress events<extra></extra>",
        colorbar: { title: { text: "Events", font: { family: "IBM Plex Sans", size: 11 } } }
    }], {
        ...setLayout("Stress frequency by day and time region"),
        margin: { l: 100, r: 115, t: 55, b: 110 },
        xaxis: {
            title: "Time region",
            side: "bottom",
            tickangle: 0,
            tickfont: { size: 11 },
            constrain: "domain",
            automargin: true,
            showgrid: true,
            gridcolor: "#ffffff",
            gridwidth: 2
        },
        yaxis: {
            title: "Day of week",
            autorange: "reversed",
            tickfont: { size: 12 },
            automargin: true,
            showgrid: true,
            gridcolor: "#ffffff",
            gridwidth: 2
        }
    }, { responsive: true, displaylogo: false });
}

function activateChart(chart) {
    activeChart = chart;
    histogramTab.classList.toggle("active", chart === "histogram");
    heatmapTab.classList.toggle("active", chart === "heatmap");
    histogramTab.setAttribute("aria-selected", chart === "histogram");
    heatmapTab.setAttribute("aria-selected", chart === "heatmap");
    document.getElementById("chart-description").textContent =
        chart === "histogram" ? "Frequency by day of week" : "Day of week and 3-hour time regions";
    const chartContainer = document.querySelector(".chart-container");
    chartContainer.classList.toggle("heatmap-view", chart === "heatmap");
    chart === "histogram" ? renderHistogram() : renderHeatmap();
}

async function selectPatient(patientId) {
    if (!patientId) return;
    activePatient = patientId;
    selector.value = patientId;
    document.getElementById("patient-value").textContent = patientId;

    document.querySelectorAll(".patient-card").forEach(card => {
        card.classList.toggle("active", card.dataset.patient === patientId);
    });

    try {
        [histogramData, heatmapData] = await Promise.all([
            fetchJson(`/analysis/stress-histogram?patient_id=${encodeURIComponent(patientId)}`),
            fetchJson(`/analysis/stress-heatmap?patient_id=${encodeURIComponent(patientId)}`)
        ]);
        activateChart(activeChart);
    } catch (error) {
        console.error("Could not load trend data", error);
        Plotly.purge("trendChart");
    }
}

async function loadPatients() {
    try {
        const patients = await fetchJson("/patients");
        selector.innerHTML = "";
        patientCards.innerHTML = "";

        if (!patients.length) {
            selector.innerHTML = '<option value="">No patients found</option>';
            return;
        }

        patients.forEach(patientId => {
            const option = document.createElement("option");
            option.value = patientId;
            option.textContent = `Patient ${patientId}`;
            selector.appendChild(option);

            const card = document.createElement("button");
            card.type = "button";
            card.className = "patient-card";
            card.dataset.patient = patientId;
            card.innerHTML = `<strong>Patient ${patientId}</strong><p>Select trend data</p>`;
            card.addEventListener("click", () => selectPatient(patientId));
            patientCards.appendChild(card);
        });

        selector.disabled = false;
        await selectPatient(patients[0]);
    } catch (error) {
        selector.innerHTML = '<option value="">Unable to load patients</option>';
        console.error("Could not load patients", error);
    }
}

selector.addEventListener("change", event => selectPatient(event.target.value));
histogramTab.addEventListener("click", () => activateChart("histogram"));
heatmapTab.addEventListener("click", () => activateChart("heatmap"));

loadPatients();
