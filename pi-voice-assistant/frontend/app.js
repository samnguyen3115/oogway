const statusText = document.getElementById('status-text');
const chatContainer = document.getElementById('chat-container');
const recordBtn = document.getElementById('record-btn');

// Hide the record button! We are now 100% hands-free from the backend.
recordBtn.style.display = 'none';

// WebSocket connection to the backend
let socket;

function connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws`;
    
    console.log("Connecting to WebSocket:", wsUrl);
    socket = new WebSocket(wsUrl);

    socket.onopen = () => {
        console.log("WebSocket connected.");
        statusText.innerText = "System Active & Listening...";
        statusText.style.color = "#58a6ff";
    };

    socket.onmessage = (event) => {
        const data = JSON.parse(event.data);
        console.log("Received data:", data);

        if (data.transcription) {
            addMessage(data.transcription, 'user');
        }

        if (data.ai_text) {
            addMessage(data.ai_text, 'ai');
        }

        updateStatus(data.state);
    };

    socket.onclose = () => {
        console.log("WebSocket disconnected. Retrying in 3 seconds...");
        statusText.innerText = "Server Disconnected. Retrying...";
        statusText.style.color = "#f85149";
        setTimeout(connectWebSocket, 3000);
    };

    socket.onerror = (error) => {
        console.error("WebSocket error:", error);
    };
}

function updateStatus(state) {
    if (state === "AWAKE") {
        statusText.innerText = "Active: Go ahead and ask!";
        statusText.style.color = "#f85149";
    } else if (state === "THINKING") {
        statusText.innerText = "Processing Your Request...";
        statusText.style.color = "#a371f7";
    } else {
        statusText.innerText = "System Active & Listening (Say 'Hey')...";
        statusText.style.color = "#58a6ff";
    }
}

function addMessage(text, sender) {
    // Basic filter for empty or system messages
    if(!text || text.includes("(Sleeping")) return;
    
    const msgDiv = document.createElement('div');
    msgDiv.classList.add('message', sender);
    msgDiv.innerText = text;
    chatContainer.appendChild(msgDiv);
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

// Start connection on page load
connectWebSocket();
