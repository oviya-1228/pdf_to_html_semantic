let currentTaskId = null;
let pollInterval = null;

async function uploadPDF() {
    const fileInput = document.getElementById('pdf-upload');
    const file = fileInput.files[0];
    const statusText = document.getElementById('status-text');
    const uploadBtn = document.getElementById('upload-btn');

    if (!file) {
        alert("Please select a file first.");
        return;
    }

    uploadBtn.disabled = true;
    statusText.innerText = "Uploading...";

    // Clear previous views
    document.getElementById('pdf-container').innerHTML = '';
    document.getElementById('html-preview').src = 'about:blank';
    document.getElementById('json-view').innerText = '';

    // Render PDF locally immediately for UX
    renderPDFLocal(file);

    const formData = new FormData();
    formData.append('file', file);

    try {
        const response = await fetch('/upload', {
            method: 'POST',
            body: formData
        });

        if (!response.ok) throw new Error("Upload failed");

        const result = await response.json();
        currentTaskId = result.task_id;
        statusText.innerText = `Processing... (ID: ${currentTaskId})`;

        // Start polling
        if (pollInterval) clearInterval(pollInterval);
        pollInterval = setInterval(checkStatus, 2000);

    } catch (e) {
        statusText.innerText = "Error: " + e.message;
        uploadBtn.disabled = false;
    }
}

async function checkStatus() {
    if (!currentTaskId) return;

    try {
        const response = await fetch(`/status/${currentTaskId}`);
        const data = await response.json();
        const statusText = document.getElementById('status-text');

        if (data.status === 'completed') {
            clearInterval(pollInterval);
            statusText.innerText = "Done!";
            document.getElementById('upload-btn').disabled = false;

            // Load Results
            loadResults();
        } else if (data.status === 'failed') {
            clearInterval(pollInterval);
            statusText.innerText = "Failed: " + (data.error || "Unknown error");
            document.getElementById('upload-btn').disabled = false;
        } else {
            statusText.innerText = `Processing... (${data.step || data.status})`;
        }
    } catch (e) {
        console.error("Polling error", e);
    }
}

function loadResults() {
    // Load HTML
    const iframe = document.getElementById('html-preview');
    iframe.src = `/results/${currentTaskId}/html`;

    // Load JSON
    fetch(`/results/${currentTaskId}/json`)
        .then(res => res.json())
        .then(data => {
            document.getElementById('json-view').innerText = JSON.stringify(data, null, 2);
        });
}

function renderPDFLocal(file) {
    const reader = new FileReader();
    reader.onload = function (e) {
        const typedarray = new Uint8Array(e.target.result);

        pdfjsLib.getDocument(typedarray).promise.then(function (pdf) {
            const container = document.getElementById('pdf-container');
            container.innerHTML = ''; // Clear

            for (let pageNum = 1; pageNum <= pdf.numPages; pageNum++) {
                pdf.getPage(pageNum).then(function (page) {
                    const scale = 1.0;
                    const viewport = page.getViewport({ scale: scale });

                    const canvas = document.createElement('canvas');
                    const context = canvas.getContext('2d');
                    canvas.height = viewport.height;
                    canvas.width = viewport.width;

                    const renderContext = {
                        canvasContext: context,
                        viewport: viewport
                    };

                    container.appendChild(canvas);

                    page.render(renderContext);
                });
            }
        });
    };
    reader.readAsArrayBuffer(file);
}
