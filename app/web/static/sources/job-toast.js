(() => {
    const trendServiceUrl = "http://localhost:8002";
    const storageKey = "stress-insight-analysis-job";
    const toastRegion = document.getElementById("job-toast-region");
    const runButton = document.querySelector("[data-run-analyses]");
    let activeToastTimer;
    let activeToast;
    let activeToastKind;
    let activeToastHeading;
    let activeToastDetail;
    let trackedJobId;

    function showToast(kind, title, message, dismissAfter) {
        window.clearTimeout(activeToastTimer);

        if (!activeToast || activeToastKind !== kind) {
            const toast = document.createElement("div");
            toast.className = `job-toast job-toast-${kind}`;
            toast.setAttribute("role", kind === "error" ? "alert" : "status");

            const icon = document.createElement("span");
            icon.className = "job-toast-icon";
            icon.setAttribute("aria-hidden", "true");
            if (kind === "loading") {
                const spinner = document.createElement("span");
                spinner.className = "job-toast-spinner";
                icon.appendChild(spinner);
            } else {
                icon.textContent = kind === "success" ? "✓" : "!";
            }

            const content = document.createElement("span");
            content.className = "job-toast-message";
            activeToastHeading = document.createElement("strong");
            activeToastDetail = document.createElement("span");
            content.append(activeToastHeading, activeToastDetail);
            toast.append(icon, content);
            toastRegion.replaceChildren(toast);
            activeToast = toast;
            activeToastKind = kind;
        }

        activeToastHeading.textContent = title;
        activeToastDetail.textContent = message;

        if (dismissAfter) {
            const toast = activeToast;
            activeToastTimer = window.setTimeout(() => {
                if (activeToast !== toast) return;
                toast.remove();
                activeToast = undefined;
                activeToastKind = undefined;
                activeToastHeading = undefined;
                activeToastDetail = undefined;
            }, dismissAfter);
        }
    }

    async function requestJson(path, options) {
        const response = await fetch(`${trendServiceUrl}${path}`, options);
        const payload = await response.json().catch(() => ({}));
        if (!response.ok) {
            const error = new Error(payload.detail || `${response.status} ${response.statusText}`);
            error.status = response.status;
            throw error;
        }
        return payload;
    }

    function setButtonRunning(running) {
        if (!runButton) return;
        runButton.disabled = running;
        runButton.textContent = running ? "Analyses running…" : "Run Analyses";
    }

    function pause(milliseconds) {
        return new Promise(resolve => window.setTimeout(resolve, milliseconds));
    }

    async function monitorJob(jobId) {
        if (trackedJobId === jobId) return;
        
        trackedJobId = jobId;
        setButtonRunning(true);
        showToast("loading", "Analyses in progress", "You can keep viewing this dashboard or switch to real-time monitoring.", 0);

        while (localStorage.getItem(storageKey) === jobId) {
            let job;
            try {
                job = await requestJson(`/run-analyses/${encodeURIComponent(jobId)}`);
            } catch (error) {
                if (error.status === 404) {
                    localStorage.removeItem(storageKey);
                    setButtonRunning(false);
                    showToast("error", "Analysis status unavailable", error.message, 9000);
                    break;
                }
                showToast("loading", "Analyses in progress", "Connection interrupted; checking the batch status again.", 0);
                await pause(3500);
                continue;
            }

            if (job.status === "queued" || job.status === "running") {
                const current = job.current_analysis
                    ? `Running ${job.current_analysis.replace(/_/g, " ")} analysis…`
                    : "Preparing the analysis batch…";
                showToast("loading", "Analyses in progress", `${current} You can continue browsing.`, 0);
                await pause(1800);
                continue;
            }

            localStorage.removeItem(storageKey);
            setButtonRunning(false);
            if (job.status === "completed") {
                showToast("success", "Analyses complete", "The updated analysis results are ready.", 8000);
                window.dispatchEvent(new CustomEvent("analysis-jobs-completed"));
            } else {
                showToast("error", "Analysis batch failed", job.error || "One or more Spark jobs did not complete successfully.", 10000);
            }
            break;
        }

        trackedJobId = undefined;
    }

    async function startJobBatch() {
        const existingJobId = localStorage.getItem(storageKey);

        if (existingJobId) {
            if (existingJobId === "submitting") {
                resumeSubmission();
            } else {
                monitorJob(existingJobId);
            }
            return;
        }

        setButtonRunning(true);
        localStorage.setItem(storageKey, "submitting");
        showToast("loading", "Submitting analyses", "Your existing results remain available while Spark runs.", 0);

        try {
            const job = await requestJson("/run-analyses", { method: "POST" });
            localStorage.setItem(storageKey, job.job_id);
            monitorJob(job.job_id);
        } catch (error) {
            localStorage.removeItem(storageKey);
            setButtonRunning(false);
            showToast("error", "Could not start analyses", error.message, 10000);
        }
    }

    async function resumeSubmission() {
        for (let attempt = 0; attempt < 6; attempt += 1) {
            try {
                const job = await requestJson("/run-analyses/active");
                localStorage.setItem(storageKey, job.job_id);
                monitorJob(job.job_id);
                return;
            } catch (error) {
                if (error.status !== 404) {
                    localStorage.removeItem(storageKey);
                    setButtonRunning(false);
                    showToast("error", "Could not check analysis status", error.message, 10000);
                    return;
                }
                await pause(500);
            }
        }

        localStorage.removeItem(storageKey);
        setButtonRunning(false);
        showToast("error", "Analysis batch not found", "The submission did not start or its status is no longer available.", 10000);
    }

    if (runButton) {
        runButton.addEventListener("click", startJobBatch);
    }

    const existingJobId = localStorage.getItem(storageKey);
    if (existingJobId) {
        if (existingJobId === "submitting") {
            setButtonRunning(true);
            showToast("loading", "Submitting analyses", "Checking the batch status…", 0);
            resumeSubmission();
        } else {
            monitorJob(existingJobId);
        }
    }
})();
