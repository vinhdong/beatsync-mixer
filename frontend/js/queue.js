/**
 * Queue Management Module
 */

let queueCount = 0;
let voteData = {};

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
    
    const queueList = document.getElementById('queue-list');
    if (queueList && data.queue) {
      queueList.innerHTML = '';
      data.queue.forEach(item => {
        const li = document.createElement('li');
        li.textContent = item.track_name;
        li.setAttribute('data-track-uri', item.track_uri);
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
