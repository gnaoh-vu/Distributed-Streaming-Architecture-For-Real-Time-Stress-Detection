const numeric = value => {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : 0;
};

const selector = document.getElementById("patient-selector");
const plotConfig = { responsive: true, displaylogo: false };
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
        bargap: 0.48,
        yaxis: { title: "Dysregulated (%)", rangemode: "tozero", ticksuffix: "%", gridcolor: "#eceef0" },
        yaxis2: {
            title: "Severity",
            overlaying: "y",
            side: "right",
            showgrid: false,
            rangemode: "tozero"
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
    const weeks = rows.map(row => shortDate(row.window_start));
    Plotly.react("loadChart", ["EDA", "IBI", "HRV"].map((name, index) => ({
        x: weeks,
        y: rows.map(row => numeric(row[[ "eda_improv", "ibi_improv", "hrv_improv"][index]]) * 100),
        type: "bar",
        name,
        marker: { color: ["#2b6f76", "#a9720d", "#a3486b"][index] },
        hovertemplate: `%{x}<br>${name} %{y:.1f}%<extra></extra>`
    })), {
        ...baseLayout,
        barmode: "group",
        bargap: 0.18,
        bargroupgap: 0.06,
        yaxis: {
            title: "Change (%)",
            zeroline: true,
            zerolinecolor: "#81868e",
            ticksuffix: "%",
            gridcolor: "#eceef0"
        },
        legend: { orientation: "h", x: 0, y: 1.12 }
    }, plotConfig);
}

function renderRecovery(rows) {
    const values = rows.map(row => numeric(row.number_consecutive_abnormal_windows)).filter(Boolean);
    const distribution = {};
    values.forEach(value => { distribution[value] = (distribution[value] || 0) + 1; });
    const lengths = Object.keys(distribution).map(Number).sort((a, b) => a - b);
    Plotly.react("recoveryChart", [{
        x: lengths,
        y: lengths.map(length => distribution[length]),
        type: "bar",
        marker: { color: "#2b6f76", opacity: 0.92 },
        hovertemplate: "%{x} consecutive window(s)<br>%{y} episode(s)<extra></extra>"
    }], {
        ...baseLayout,
        bargap: 0.28,
        xaxis: {
            title: "Consecutive abnormal windows",
            dtick: 1,
            gridcolor: "#eceef0",
            linecolor: "#dde0e3"
        },
        yaxis: {
            title: "Episodes",
            rangemode: "tozero",
            dtick: 1,
            gridcolor: "#eceef0",
            linecolor: "#dde0e3"
        },
        annotations: lengths.length ? [] : [{
            text: "No abnormal episodes",
            showarrow: false,
            x: 0.5,
            y: 0.5,
            xref: "paper",
            yref: "paper"
        }]
    }, plotConfig);

    if (!values.length) {
        document.getElementById("median-recovery").textContent = "--";
        return;
    }
    const sorted = [...values].sort((a, b) => a - b);
    const middle = Math.floor(sorted.length / 2);
    const median = sorted.length % 2
        ? sorted[middle]
        : (sorted[middle - 1] + sorted[middle]) / 2;
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
        renderStressLoad(load);
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
