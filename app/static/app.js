const form = document.getElementById("analysis-form");
const results = document.getElementById("results");
const statusPill = document.getElementById("status-pill");
const submitButton = form.querySelector("button[type='submit']");
const resumeFileInput = document.getElementById("resume-file");
const resumeTextArea = document.getElementById("resume-text");
const jobDescFileInput = document.getElementById("job-desc-file");
const jobTextArea = document.getElementById("job-text");
const contextFileInput = document.getElementById("context-file");
const supplementalTextArea = document.getElementById("supplemental-text");

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function setStatus(state, text) {
  statusPill.className = `status-pill ${state}`;
  statusPill.textContent = text;
}

function renderList(items, emptyLabel, chipClass = "") {
  if (!items.length) {
    return `<p class="text-block">${escapeHtml(emptyLabel)}</p>`;
  }

  return `<div class="chips">${items
    .map((item) => `<span class="chip ${chipClass}">${escapeHtml(item)}</span>`)
    .join("")}</div>`;
}

function renderResults(payload) {
  const analysis = payload.analysis || {};
  const improvements = payload.improvements || {};
  const explanations = improvements.explanations || [];
  const rewrittenBullets = improvements.rewritten_bullets || [];

  results.classList.remove("empty-state");
  results.innerHTML = `
    <div class="card">
      <h3>Fit metrics</h3>
      <div class="metric-row">
        <div class="metric">
          <span class="label">Alignment score</span>
          <span class="value">${Math.round((analysis.alignment_score || 0) * 100)}%</span>
        </div>
      </div>
    </div>

    <div class="card">
      <h3>Matched skills</h3>
      ${renderList(analysis.matched_skills || [], "No direct overlaps were found yet.")}
    </div>

    <div class="card">
      <h3>Missing skills</h3>
      ${renderList(analysis.missing_skills || [], "No notable gaps were detected.", "missing")}
    </div>

    <div class="card">
      <h3>Starter rewrite summary</h3>
      <p class="text-block">${escapeHtml(improvements.rewritten_summary || "No rewrite summary was returned.")}</p>
    </div>

    <div class="card">
      <h3>Rewritten bullets</h3>
      ${renderList(rewrittenBullets, "No rewritten bullets were returned yet.")}
    </div>

    <div class="card">
      <h3>Notes</h3>
      ${explanations.length
        ? `<ul>${explanations.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`
        : '<p class="text-block">No notes were returned.</p>'}
    </div>
  `;

  setStatus("success", "Analysis complete");
}

function renderError(message) {
  results.classList.add("empty-state");
  results.innerHTML = `<p class="text-block error-message">${escapeHtml(message)}</p>`;
  setStatus("error", "Request failed");
}

resumeFileInput.addEventListener("change", () => {
  const file = resumeFileInput.files && resumeFileInput.files[0];

  if (!file) {
    return;
  }

  setStatus("idle", `Selected ${file.name}`);
});

jobDescFileInput.addEventListener("change", () => {
  const file = jobDescFileInput.files && jobDescFileInput.files[0];

  if (!file) {
    return;
  }

  setStatus("idle", `Selected ${file.name}`);
});

contextFileInput.addEventListener("change", () => {
  const file = contextFileInput.files && contextFileInput.files[0];

  if (!file) {
    return;
  }

  setStatus("idle", `Selected ${file.name}`);
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();

  const payload = new FormData();
  payload.append("resume_text", resumeTextArea.value.trim());
  payload.append("job_description_text", jobTextArea.value.trim());
  payload.append("supplemental_text", supplementalTextArea.value.trim());

  const resumeFile = resumeFileInput.files && resumeFileInput.files[0];
  const jobDescriptionFile = jobDescFileInput.files && jobDescFileInput.files[0];
  const supplementalFile = contextFileInput.files && contextFileInput.files[0];

  if (resumeFile) payload.append("resume_file", resumeFile);
  if (jobDescriptionFile) payload.append("job_description_file", jobDescriptionFile);
  if (supplementalFile) payload.append("supplemental_file", supplementalFile);

  submitButton.disabled = true;
  setStatus("loading", "Analyzing...");

  try {
    const response = await fetch("/analyze-upload", {
      method: "POST",
      body: payload,
    });

    const data = await response.json();

    if (!response.ok) {
      const message = data.detail || `Backend returned ${response.status}`;
      throw new Error(message);
    }

    renderResults(data);
  } catch (error) {
    renderError(`Unable to run the analysis. ${error.message}`);
  } finally {
    submitButton.disabled = false;
  }
});
