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
        updateHeaderStats();
        
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

        // metadata preview (example: fieldboundary or device)
        let metaPreview = '';
        if (msg.metadata) {
            // Prüfe ob metadata ein Objekt ist
            if (typeof msg.metadata === 'object' && msg.metadata !== null) {
                if (msg.metadata.fieldboundary) metaPreview = msg.metadata.fieldboundary;
                else if (msg.metadata.device) metaPreview = msg.metadata.device;
                else {
                    const keys = Object.keys(msg.metadata);
                    if (keys.length) metaPreview = `${keys[0]}: ${msg.metadata[keys[0]]}`;
                }
            } else {
                // Es ist ein String
                metaPreview = String(msg.metadata).substring(0, 50); // Erste 50 Zeichen
            }
        }

        item.innerHTML = `
            <div class="message-preview">
                <div class="topic">${topicPreview}</div>
                <div class="meta-preview">${metaPreview}</div>
            </div>
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


function updateHeaderStats() {
    const timeElement = document.querySelector('.global-time');
    const countElement = document.querySelector('.message-count');

    timeElement.textContent =
        new Date().toLocaleTimeString('de-DE');

    if (mqttMessages.length) {
        const latest = mqttMessages[0];

        countElement.textContent =
            `${mqttMessages.length} Messages | Last: ${
                new Date(latest.timestamp).toLocaleTimeString('de-DE')
            }`;
    } else {
        countElement.textContent = 'No Messages';
    }
}


function updateDetailView(index) {
    const msg = mqttMessages[index];
    if (!msg) {
        console.error('Message not found at index:', index);
        return;
    }

    const detailHeader = document.querySelector('.detail-header h2');
    const detailContent = document.querySelector('.detail-content');
    const detailTime = document.querySelector('.detail-time');

    const timestamp = new Date(msg.timestamp);
    const timeString = timestamp.toLocaleString('de-DE');

    detailHeader.textContent = msg.topic || '-';
    detailTime.textContent = timeString;

    let payloadStr = typeof msg.payload === 'string' 
        ? msg.payload 
        : JSON.stringify(msg.payload, null, 2);

    // Metadata rendering - mit Typprüfung
    let metadataHtml = '<div class="metadata-empty">—</div>';
    
    if (msg.metadata) {
        if (typeof msg.metadata === 'object' && msg.metadata !== null) {
            if (Object.keys(msg.metadata).length > 0) {
                metadataHtml = '<ul class="metadata-list">';
                for (const [k, v] of Object.entries(msg.metadata)) {
                    const displayValue = typeof v === 'object' ? JSON.stringify(v) : v;
                    metadataHtml += `<li><strong>${k}:</strong> ${displayValue}</li>`;
                }
                metadataHtml += '</ul>';
            }
        } else {
            metadataHtml = `<div class="metadata-string">${msg.metadata}</div>`;
        }
    }

    detailContent.innerHTML = `
        <div class="detail-section">
            <h3>Information</h3>
            <div class="detail-metadata">
                <div><strong>Topic:</strong> ${msg.topic}</div>
                <div><strong>QoS:</strong> ${msg.qos}</div>
                <div><strong>Timestamp:</strong> ${timeString}</div>
            </div>
        </div>
        
        <div class="detail-section">
            <h3>Payload</h3>
            <div class="detail-metadata">
                <pre id="payload-pre"></pre>
            </div>
        </div>
        
        <div class="detail-section">
            <h3>Metadata</h3>
            <div class="detail-metadata">
                ${metadataHtml}
            </div>
        </div>
    `;
    
    // Payload als plain text setzen (nicht als HTML) 
    const preElement = detailContent.querySelector('#payload-pre');
    preElement.textContent = payloadStr;
}