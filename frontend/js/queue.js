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

function extractSongTitleFromTrackName(trackName) {
  if (!trackName) return 'Unknown Track';
  
  // Try to extract song title from common formats:
  // "Artist - Track Name"
  // "Artist — Track Name" (em dash)
  // "Artist: Track Name"
  if (trackName.includes(' - ')) {
    const parts = trackName.split(' - ');
    return parts.length > 1 ? parts.slice(1).join(' - ').trim() : trackName;
  } else if (trackName.includes(' — ')) {
    const parts = trackName.split(' — ');
    return parts.length > 1 ? parts.slice(1).join(' — ').trim() : trackName;
  } else if (trackName.includes(': ')) {
    const parts = trackName.split(': ');
    return parts.length > 1 ? parts.slice(1).join(': ').trim() : trackName;
  }
  
  // If no separator found, return the whole track name
  return trackName;
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
              ${window.userRole === 'host' ? `<button onclick="showAddToPlaylistModal('${trackId}', '${extractSongTitleFromTrackName(item.track_name || '').replace(/'/g, "\\'")}', '${extractArtistFromTrackName(item.track_name || '').replace(/'/g, "\\'")}', '${(item.track_album || '').replace(/'/g, "\\'")}', ${item.track_duration || 0})" style="background-color: #9b59b6; margin: 0 5px; color: white; border: none; padding: 4px 8px; border-radius: 4px; cursor: pointer;">📋 Add to Playlist</button>` : ''}
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
  // Check if socket is connected
  if (typeof socket === 'undefined' || !socket.connected) {
    console.error('Socket not connected, cannot vote');
    alert('Connection lost. Please refresh the page and try again.');
    return;
  }

  console.log(`Voting for track: ${trackUri}, vote: ${voteType}`);
  
  // Generate a unique client vote ID for tracking
  const clientVoteId = Math.random().toString(36).substr(2, 8);
  
  // Add the green glow animation only
  if (buttonElement) {
    // Add the green glow animation
    buttonElement.classList.add('just-voted');
    
    // Remove the animation class after it completes (0.3s)
    setTimeout(() => {
      buttonElement.classList.remove('just-voted');
    }, 300);
  }
  
  // Emit vote via Socket.IO
  socket.emit('vote_add', {
    track_uri: trackUri,
    vote: voteType,
    client_vote_id: clientVoteId
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

function updateVoteDisplay(data) {
  const trackUri = data.track_uri;
  const upVotes = data.up_votes;
  const downVotes = data.down_votes;
  const netScore = upVotes - downVotes;
  
  // Create safe ID for selectors (same logic as in queue display)
  const safeTrackId = trackUri.replace(/[^a-zA-Z0-9]/g, '_');
  
  // Update vote counts quietly without any animations
  const upElement = document.getElementById(`up-${safeTrackId}`);
  const downElement = document.getElementById(`down-${safeTrackId}`);
  const scoreElement = document.getElementById(`score-${safeTrackId}`);
  
  if (upElement) {
    upElement.textContent = upVotes;
  }
  
  if (downElement) {
    downElement.textContent = downVotes;
  }
  
  if (scoreElement) {
    scoreElement.textContent = `Score: ${netScore}`;
    
    // Update score color based on value
    if (netScore > 0) {
      scoreElement.style.color = '#1db954'; // Green for positive
    } else if (netScore < 0) {
      scoreElement.style.color = '#e74c3c'; // Red for negative
    } else {
      scoreElement.style.color = '#95a5a6'; // Gray for neutral
    }
  }
}

function reorderQueueByVotes() {
  const queueContainer = document.getElementById("queue");
  if (!queueContainer) return;
  
  const queueItems = Array.from(queueContainer.children);
  if (queueItems.length === 0) return;
  
  // Store original positions and heights
  const originalData = new Map();
  queueItems.forEach((item, index) => {
    const trackUri = item.getAttribute('data-track-uri');
    const rect = item.getBoundingClientRect();
    originalData.set(trackUri, {
      index: index,
      top: rect.top,
      height: rect.height
    });
  });
  
  // Sort queue items by vote score (up votes - down votes), then by timestamp
  queueItems.sort((a, b) => {
    const scoreA = parseInt(a.querySelector('.vote-score')?.textContent?.replace('Score: ', '') || '0');
    const scoreB = parseInt(b.querySelector('.vote-score')?.textContent?.replace('Score: ', '') || '0');
    
    // Sort by score (descending), then by timestamp (ascending) for tie-breaking
    if (scoreB !== scoreA) {
      return scoreB - scoreA; // Higher score first
    }
    
    // If scores are equal, maintain original order (timestamp)
    const timestampA = parseInt(a.getAttribute('data-timestamp') || '0');
    const timestampB = parseInt(b.getAttribute('data-timestamp') || '0');
    return timestampA - timestampB;
  });
  
  // Reorder DOM elements first
  queueContainer.innerHTML = '';
  queueItems.forEach((item, index) => {
    // Highlight the first track (next to play)
    if (index === 0) {
      item.classList.add('next-to-play');
    } else {
      item.classList.remove('next-to-play');
    }
    queueContainer.appendChild(item);
  });
  
  // Calculate movements and animate
  queueItems.forEach((item, newIndex) => {
    const trackUri = item.getAttribute('data-track-uri');
    const originalInfo = originalData.get(trackUri);
    
    if (originalInfo && originalInfo.index !== newIndex) {
      // Calculate the distance this item needs to move
      const oldIndex = originalInfo.index;
      const itemsToMove = newIndex - oldIndex;
      
      // Calculate actual pixel distance based on average item height
      const avgItemHeight = queueItems.reduce((sum, itm) => sum + itm.offsetHeight, 0) / queueItems.length;
      const pixelDistance = itemsToMove * (avgItemHeight + 8); // +8 for margin
      
      // Set initial position to where it came from
      item.style.transform = `translateY(${-pixelDistance}px)`;
      item.style.transition = 'none';
      
      // Add visual highlight based on movement direction
      if (itemsToMove < 0) {
        // Moving up
        item.classList.add('moving-up');
        item.style.background = 'rgba(29, 185, 84, 0.1)';
        item.style.boxShadow = '0 4px 12px rgba(29, 185, 84, 0.3)';
      } else {
        // Moving down  
        item.classList.add('moving-down');
        item.style.background = 'rgba(255, 165, 0, 0.1)';
        item.style.boxShadow = '0 4px 12px rgba(255, 165, 0, 0.3)';
      }
      
      // Force reflow then animate to final position
      item.offsetHeight;
      
      // Animate to final position
      item.style.transition = 'all 0.8s cubic-bezier(0.4, 0.0, 0.2, 1)';
      item.style.transform = 'translateY(0)';
      
      // Clean up after animation
      setTimeout(() => {
        item.classList.remove('moving-up', 'moving-down');
        item.style.background = '';
        item.style.boxShadow = '';
        item.style.transform = '';
        item.style.transition = '';
      }, 800);
    }
  });
  
  console.log('Queue reordered by votes with position-based animations');
}

// Export functions
window.loadQueue = loadQueue;
window.updateQueueDisplay = updateQueueDisplay;
window.updateQueueCount = updateQueueCount;
window.refreshQueueDisplay = refreshQueueDisplay;
window.voteTrack = voteTrack;
window.updateVoteDisplay = updateVoteDisplay;
window.clearQueue = clearQueue;
window.queueTrack = queueTrack;
window.extractArtistFromTrackName = extractArtistFromTrackName;
window.extractSongTitleFromTrackName = extractSongTitleFromTrackName;
window.reorderQueueByVotes = reorderQueueByVotes;
