document.querySelectorAll('.message-item').forEach(item => {
    item.addEventListener('click', function() {
        // Remove active class from all items
        document.querySelectorAll('.message-item').forEach(i => i.classList.remove('active'));
        
        // Add active class to clicked item
        this.classList.add('active');
        
        // Update detail content (Placeholder-Logik)
        const messageId = this.dataset.id;
        updateDetailView(messageId, this.textContent);
    });
});

function updateDetailView(id, title) {
    const detailHeader = document.querySelector('.detail-header h2');
    const detailContent = document.querySelector('.detail-content');
    
    detailHeader.textContent = title.split('\n')[0];
    
    // Placeholder-Inhalte
    detailContent.innerHTML = `
        <p>Lorem ipsum dolor sit amet, consectetur adipiscing elit. 
        Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. 
        Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris 
        nisi ut aliquip ex ea commodo consequat.</p>
        
        <div class="detail-metadata">
            <div><strong>Message ID:</strong> ${id}</div>
            <div><strong>Topic:</strong> farm/sensor/temperature</div>
            <div><strong>Payload:</strong> {"temp": 25.5, "humidity": 65}</div>
            <div><strong>Fieldboundary:</strong> Hansen_Feld A</div>
            <div><strong>Timestamp:</strong> 2026-06-02T10:${30 + parseInt(id)}:00Z</div>
        </div>
    `;
}

let mqttMessages = [];

// Beim Laden die Messages einmalig laden
document.addEventListener('DOMContentLoaded', function() {
    loadMessages();
    // Dann alle 2 Sekunden neu laden
    setInterval(loadMessages, 2000);
});

async function loadMessages() {
    try {
        const response = await fetch('/api/mqtt-get-messages/');
        if (!response.ok) {
            console.error('Fehler beim Laden der Messages:', response.statusText);
            return;
        }
        
        mqttMessages = await response.json();
        renderMessageList();
        
        // Wenn mindestens eine Message vorhanden, zeige die erste
        if (mqttMessages.length > 0 && !document.querySelector('.message-item.active')) {
            document.querySelector('.message-item')?.click();
        }
    } catch (error) {
        console.error('Fehler beim Abrufen der Messages:', error);
    }
}

function renderMessageList() {
    const messageList = document.querySelector('.message-list');
    messageList.innerHTML = '';
    
    mqttMessages.forEach((msg, index) => {
        const item = document.createElement('div');
        item.className = 'message-item' + (index === 0 ? ' active' : '');
        item.dataset.id = index;
        
        const timestamp = new Date(msg.timestamp);
        const timeString = timestamp.toLocaleTimeString('de-DE');
        const topicPreview = msg.topic || 'Unknown';
        
        item.innerHTML = `
            <div class="message-preview">${topicPreview}</div>
            <div class="message-time">${timeString}</div>
        `;
        
        item.addEventListener('click', function() {
            document.querySelectorAll('.message-item').forEach(i => i.classList.remove('active'));
            this.classList.add('active');
            updateDetailView(parseInt(this.dataset.id));
        });
        
        messageList.appendChild(item);
    });
}

function updateDetailView(index) {
    const msg = mqttMessages[index];
    if (!msg) return;
    
    const detailHeader = document.querySelector('.detail-header h2');
    const detailContent = document.querySelector('.detail-content');
    const detailTime = document.querySelector('.detail-time');
    
    const timestamp = new Date(msg.timestamp);
    const timeString = timestamp.toLocaleString('de-DE');
    
    detailHeader.textContent = msg.topic;
    detailTime.textContent = timeString;
    
    // Payload formatieren - kann String oder JSON sein
    let payloadStr;
    if (typeof msg.payload === 'string') {
        payloadStr = msg.payload;
    } else {
        payloadStr = JSON.stringify(msg.payload, null, 2);
    }
    
    detailContent.innerHTML = `
        <div class="detail-metadata">
            <div><strong>Topic:</strong> ${msg.topic}</div>
            <div><strong>Payload:</strong> <pre>${payloadStr}</pre></div>
            <div><strong>QoS:</strong> ${msg.qos}</div>
            <div><strong>Timestamp:</strong> ${timeString}</div>
        </div>
    `;
}