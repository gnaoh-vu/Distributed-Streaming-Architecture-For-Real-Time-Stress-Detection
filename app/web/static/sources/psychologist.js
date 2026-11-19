const numeric = value => {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : 0;
};

const selector = document.getElementById("patient-selector");
const plotConfig = { responsive: true, displaylogo: false };
let stressLoadRows = [];
let activeSignal = "eda";
const baseLayout = {
    paper_bgcolor: "#ffffff",
    plot_bgcolor: "#ffffff",
    font: { family: "IBM Plex Sans", color: "#171a1d" },
    margin: { l: 58, r: 18, t: 18, b: 48 },
    xaxis: {
        gridcolor: "#eceef0",
        linecolor: "#dde0e3",
        tickfont: { size: 10 }
    },
    yaxis: {
        gridcolor: "#eceef0",
        linecolor: "#dde0e3",
        tickfont: { size: 10 }
    },
    hoverlabel: { bgcolor: "#171a1d", font: { family: "IBM Plex Sans", color: "#ffffff" } }
};

async function fetchJson(url) {
    const response = await fetch(url);
    if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
    return response.json();
}

function shortDate(value) {
    if (!value) return "--";
    const date = new Date(value);
    return Number.isNaN(date.getTime())
        ? String(value).slice(0, 10)
        : date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function renderAns(rows) {
    rows.sort((a, b) => String(a.week_start).localeCompare(String(b.week_start)));
    Plotly.react("ansChart", [{
        x: rows.map(row => shortDate(row.week_start)),
        y: rows.map(row => numeric(row.dysregulation_ratio) * 100),
        type: "bar",
        marker: { color: "#2b6f76", line: { width: 0 } },
        hovertemplate: "%{x}<br>%{y:.1f}% dysregulated<extra></extra>"
    }, {
        x: rows.map(row => shortDate(row.week_start)),
        y: rows.map(row => numeric(row.weekly_dysregulation_severity)),
        type: "scatter",
        mode: "lines+markers",
        yaxis: "y2",
        line: { color: "#a3486b", width: 2 },
        marker: { color: "#ffffff", line: { color: "#a3486b", width: 2 }, size: 7 },
        hovertemplate: "%{x}<br>Severity %{y:.2f}<extra></extra>"
    }], {
        ...baseLayout,
        margin: { l: 68, r: 82, t: 38, b: 55 },
        bargap: 0.48,
        yaxis: { title: "Dysregulated (%)", rangemode: "tozero", ticksuffix: "%", gridcolor: "#eceef0" },
        yaxis2: {
            title: { text: "Severity", standoff: 14 },
            overlaying: "y",
            side: "right",
            showgrid: false,
            rangemode: "tozero",
            automargin: true
        },
        legend: { orientation: "h", x: 0, y: 1.12 },
        annotations: rows.length ? [] : [{
            text: "No ANS observations",
            showarrow: false,
            x: 0.5,
            y: 0.5,
            xref: "paper",
            yref: "paper"
        }]
    }, plotConfig);

    document.getElementById("weeks-observed").textContent = rows.length || "--";
    const latest = rows[rows.length - 1];
    document.getElementById("latest-ans").textContent = latest
        ? `${(numeric(latest.dysregulation_ratio) * 100).toFixed(1)}%`
        : "--";
}

function renderStressLoad(rows) {
    rows.sort((a, b) => String(a.window_start).localeCompare(String(b.window_start)));
    const signals = [
        { id: "eda", name: "EDA AUC", field: "auc_eda", color: "#2b6f76" },
        { id: "ibi", name: "IBI AUC", field: "auc_ibi", color: "#a9720d" },
        { id: "hrv", name: "HRV AUC", field: "auc_hrv", color: "#a3486b" }
    ];
    const hasAucFields = rows.length > 0 && signals.every(signal =>
        Object.prototype.hasOwnProperty.call(rows[0], signal.field)
    );

    if (!hasAucFields) {
        Plotly.react("loadChart", [], {
            ...baseLayout,
            annotations: [{
                text: rows.length
                    ? "AUC output fields unavailable; rerun the updated stress-load analysis"
                    : "No weekly stress-load observations",
                showarrow: false,
                x: 0.5,
                y: 0.5,
                xref: "paper",
                yref: "paper"
            }]
        }, plotConfig);
        return;
    }

    const signal = signals.find(item => item.id === activeSignal) || signals[0];
    Plotly.react("loadChart", [{
        x: rows.map(row => row.window_start),
        y: rows.map(row => numeric(row[signal.field])),
        type: "scatter",
        mode: "lines+markers",
        line: { color: signal.color, width: 2 },
        marker: { size: 6, color: signal.color },
        connectgaps: false,
        hovertemplate: `%{x|%b %d, %Y}<br>${signal.name}: %{y:.3g}<extra></extra>`
    }], {
        ...baseLayout,
        margin: { l: 72, r: 24, t: 20, b: 58 },
        yaxis: {
            title: signal.name,
            rangemode: "tozero",
            gridcolor: "#eceef0",
            automargin: true
        },
        xaxis: {
            type: "date",
            tickformat: "%b %d",
            title: "Week",
            gridcolor: "#eceef0"
        },
    }, plotConfig);
}

function activateSignal(signalId) {
    activeSignal = signalId;
    document.querySelectorAll(".signal-tab").forEach(tab => {
        const active = tab.dataset.signal === signalId;
        tab.classList.toggle("active", active);
        tab.setAttribute("aria-selected", String(active));
    });
    renderStressLoad(stressLoadRows);
}

function renderRecovery(rows) {
    const episodes = rows
        .map(row => ({
            start: row.region_start,
            windows: numeric(row.number_consecutive_abnormal_windows)
        }))
        .filter(episode => episode.windows > 0)
        .sort((a, b) => String(a.start).localeCompare(String(b.start)));
    const values = episodes.map(episode => episode.windows);
    const sorted = [...values].sort((a, b) => a - b);
    const middle = Math.floor(sorted.length / 2);
    const median = sorted.length
        ? (sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2)
        : null;
    const dates = episodes.map(episode => episode.start);

    Plotly.react("recoveryChart", [{
        x: dates,
        y: values,
        type: "scatter",
        mode: "markers",
        marker: {
            size: 11,
            color: values.map(value => value > median ? "#a3486b" : "#2b6f76"),
            line: { color: "#ffffff", width: 1.5 }
        },
        customdata: values.map((value, index) => [index + 1, value * 2.5 + 2.5]),
        hovertemplate: "Episode %{customdata[0]}<br>%{x|%b %d, %Y}<br>%{y} consecutive abnormal windows<br>About %{customdata[1]:.1f} min of overlapping window coverage<extra></extra>"
    }], {
        ...baseLayout,
        margin: { l: 68, r: 24, t: 18, b: 55 },
        xaxis: {
            ...baseLayout.xaxis,
            type: "date",
            title: "Episode start date",
            tickformat: "%b %d"
        },
        yaxis: {
            title: "Consecutive abnormal windows",
            rangemode: "tozero",
            dtick: 1,
            gridcolor: "#eceef0",
            linecolor: "#dde0e3"
        },
        shapes: median === null ? [] : [{
            type: "line",
            xref: "paper",
            x0: 0,
            x1: 1,
            y0: median,
            y1: median,
            line: { color: "#a9720d", width: 1.5, dash: "dash" }
        }],
        annotations: median === null ? [{
            text: "No abnormal-window episodes to display",
            showarrow: false,
            x: 0.5,
            y: 0.5,
            xref: "paper",
            yref: "paper"
        }] : []
    }, plotConfig);

    if (!episodes.length) {
        document.getElementById("median-recovery").textContent = "--";
        return;
    }
    document.getElementById("median-recovery").textContent =
        `${Number.isInteger(median) ? median : median.toFixed(1)} windows`;
}

async function loadPatient(patientId) {
    if (!patientId) return;
    document.getElementById("selected-patient").textContent = patientId;
    selector.value = patientId;

    try {
        const [ans, load, recovery] = await Promise.all([
            fetchJson(`/specialist-analysis/ans?patient_id=${encodeURIComponent(patientId)}`),
            fetchJson(`/specialist-analysis/stress_load?patient_id=${encodeURIComponent(patientId)}`),
            fetchJson(`/specialist-analysis/recovery_speed?patient_id=${encodeURIComponent(patientId)}`)
        ]);
        renderAns(ans);
        stressLoadRows = load;
        renderStressLoad(stressLoadRows);
        renderRecovery(recovery);
    } catch (error) {
        console.error("Could not load specialist analysis", error);
    }
}

async function loadPatients() {
    try {
        const patients = await fetchJson("/patients");
        selector.innerHTML = "";
        if (!patients.length) {
            selector.innerHTML = '<option value="">No patients found</option>';
            return;
        }
        patients.forEach(patientId => {
            const option = document.createElement("option");
            option.value = patientId;
            option.textContent = `Patient ${patientId}`;
            selector.appendChild(option);
        });
        selector.disabled = false;
        await loadPatient(String(patients[0]));
    } catch (error) {
        selector.innerHTML = '<option value="">Unable to load patients</option>';
        console.error(error);
    }
}

selector.addEventListener("change", event => loadPatient(event.target.value));
document.querySelectorAll(".signal-tab").forEach(tab => {
    tab.addEventListener("click", () => activateSignal(tab.dataset.signal));
});
document.querySelectorAll(".section-link").forEach(button => {
    button.addEventListener("click", () => {
        document.querySelectorAll(".section-link").forEach(item => item.classList.remove("active"));
        button.classList.add("active");
        document.getElementById(button.dataset.target).scrollIntoView({ behavior: "smooth", block: "start" });
    });
});
document.getElementById("review-date").textContent =
    new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(new Date());

loadPatients();
