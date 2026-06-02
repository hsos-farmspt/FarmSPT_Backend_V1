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