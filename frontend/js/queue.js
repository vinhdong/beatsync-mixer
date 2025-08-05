/**
 * Queue Management Module
 */

let queueCount = 0;
let voteData = {};

// Helper function to extract artist from track name
function extractArtistFromTrackName(trackName) {
  if (!trackName) return 'Unknown Artist';
  
  // Try to extract artist from common formats:
  // "Artist - Track Name"
  // "Artist — Track Name" (em dash)
  // "Artist: Track Name"
  if (trackName.includes(' - ')) {
    return trackName.split(' - ')[0].trim();
  } else if (trackName.includes(' — ')) {
    return trackName.split(' — ')[0].trim();
  } else if (trackName.includes(': ')) {
    return trackName.split(': ')[0].trim();
  }
  
  // If no separator found, return Unknown Artist
  return 'Unknown Artist';
}

async function loadQueue() {
  try {
    const response = await fetch('/queue');
    const data = await response.json();
    queueCount = data.count || 0;
    updateQueueDisplay();
    console.log('Queue loaded, count:', queueCount);
  } catch (err) {
    console.error('Error loading queue:', err);
  }
}

function updateQueueDisplay() {
  const queueCountElement = document.querySelector('.queue-count');
  const queueIndicator = document.querySelector('.queue-indicator');
  
  if (queueCountElement) {
    queueCountElement.textContent = queueCount;
  }
  
  if (queueIndicator) {
    queueIndicator.style.display = queueCount > 0 ? 'inline' : 'none';
  }
}

function updateQueueCount() {
  queueCount++;
  updateQueueDisplay();
}

async function refreshQueueDisplay() {
  try {
    const response = await fetch('/queue/');
    const data = await response.json();
    
    queueCount = data.count || 0;
    updateQueueDisplay();
    
    const queueList = document.getElementById('queue');
    if (queueList && data.queue) {
      queueList.innerHTML = '';
      data.queue.forEach(item => {
        const li = document.createElement('li');
        const trackId = item.track_uri;
        const safeTrackId = trackId.replace(/[^a-zA-Z0-9]/g, '_');
        const timestamp = new Date(item.timestamp || Date.now()).getTime();
        
        li.setAttribute('data-track-uri', trackId);
        li.setAttribute('data-timestamp', timestamp);
        li.className = 'queue-item';
        li.style.position = 'relative';
        li.innerHTML = `
          <div>
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
              <span style="font-weight: bold;">${item.track_name || item.track_uri}</span>
              <span class="vote-score" id="score-${safeTrackId}" style="background-color: #333; padding: 2px 8px; border-radius: 12px; font-size: 12px; color: #1db954;">Score: ${item.vote_score || 0}</span>
            </div>
            <small style="color: #666;">Added: ${new Date(item.timestamp || Date.now()).toLocaleTimeString()}</small>
            <div class="vote-buttons">
              <button class="vote-btn" onclick="voteTrack('${trackId}', 'up', this)">👍</button>
              <span class="vote-count" id="up-${safeTrackId}">${item.upvotes || 0}</span>
              <button class="vote-btn" onclick="voteTrack('${trackId}', 'down', this)">👎</button>
              <span class="vote-count" id="down-${safeTrackId}">${item.downvotes || 0}</span>
              ${window.userRole === 'host' ? `<button onclick="playTrackFromQueue('${trackId}')" style="background-color: #1db954; margin: 0 5px;">▶️ Play</button>` : ''}
              ${window.userRole === 'host' ? `<button onclick="showAddToPlaylistModal('${trackId}', '${(item.track_name || 'Unknown Track').replace(/'/g, "\\'")}', '${extractArtistFromTrackName(item.track_name || '').replace(/'/g, "\\'")}', '${(item.track_album || '').replace(/'/g, "\\'")}', ${item.track_duration || 0})" style="background-color: #9b59b6; margin: 0 5px; color: white; border: none; padding: 4px 8px; border-radius: 4px; cursor: pointer;">📋 Add to Playlist</button>` : ''}
              <button class="recommendations-btn" onclick="loadRecs('${trackId}', '${safeTrackId}')">See Similar Tracks</button>
            </div>
            <div id="recs-${safeTrackId}" class="recommendations-list"></div>
          </div>
        `;
        queueList.appendChild(li);
      });
    }
    
    console.log('Queue refreshed, count:', queueCount);
  } catch (error) {
    console.error('Error refreshing queue:', error);
  }
}

function voteTrack(trackUri, voteType, buttonElement) {
  fetch('/vote', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      track_uri: trackUri,
      vote_type: voteType
    })
  })
  .then(response => response.json())
  .then(data => {
    if (data.error) {
      alert(data.error);
    } else {
      console.log('Vote submitted:', data);
      
      if (buttonElement) {
        buttonElement.disabled = true;
        buttonElement.textContent = voteType === 'up' ? '👍 Voted' : '👎 Voted';
      }
    }
  })
  .catch(error => {
    console.error('Error voting:', error);
    alert('Failed to submit vote');
  });
}

async function clearQueue() {
  if (!confirm('Are you sure you want to clear the entire queue?')) {
    return;
  }
  
  try {
    const response = await fetch('/queue/clear', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      }
    });
    
    const data = await response.json();
    
    if (response.ok) {
      console.log('Queue cleared successfully:', data.message);
      showNotification(`✅ ${data.message}`, 'success');
      queueCount = 0;
      updateQueueDisplay();
      
      if (typeof loadQueue === 'function') {
        loadQueue();
      }
    } else {
      console.error('Failed to clear queue:', data.error);
      showNotification(`❌ ${data.error}`, 'error');
    }
  } catch (error) {
    console.error('Error clearing queue:', error);
    showNotification('❌ Failed to clear queue', 'error');
  }
}

function queueTrack(trackUri, trackName) {
  fetch('/queue/add', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      track_uri: trackUri,
      track_name: trackName
    })
  })
  .then(response => response.json())
  .then(data => {
    if (data.error) {
      alert(data.error);
    } else {
      console.log('Track queued:', data);
      showNotification(`✅ Added "${trackName}" to queue`, 'success');
      
      if (typeof loadQueue === 'function') {
        loadQueue();
      }
    }
  })
  .catch(error => {
    console.error('Error queueing track:', error);
    alert('Failed to queue track');
  });
}

// Export functions
window.loadQueue = loadQueue;
window.updateQueueDisplay = updateQueueDisplay;
window.updateQueueCount = updateQueueCount;
window.refreshQueueDisplay = refreshQueueDisplay;
window.voteTrack = voteTrack;
window.clearQueue = clearQueue;
window.queueTrack = queueTrack;
window.extractArtistFromTrackName = extractArtistFromTrackName;
