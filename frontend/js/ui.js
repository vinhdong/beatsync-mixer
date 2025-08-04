/**
 * UI Utilities and Notifications Module
 */

function showNotification(message, type = 'info') {
  const notification = document.createElement('div');
  notification.style.cssText = `
    position: fixed;
    top: 20px;
    right: 20px;
    padding: 15px 20px;
    border-radius: 8px;
    color: white;
    font-weight: bold;
    z-index: 1000;
    transition: all 0.3s ease;
    max-width: 300px;
    word-wrap: break-word;
  `;
  
  if (type === 'success') {
    notification.style.backgroundColor = '#27ae60';
  } else if (type === 'error') {
    notification.style.backgroundColor = '#e74c3c';
  } else {
    notification.style.backgroundColor = '#3498db';
  }
  
  notification.textContent = message;
  document.body.appendChild(notification);
  
  setTimeout(() => {
    notification.style.opacity = '0';
    notification.style.transform = 'translateX(100%)';
    setTimeout(() => {
      if (document.body.contains(notification)) {
        document.body.removeChild(notification);
      }
    }, 300);
  }, 3000);
}

function updateConnectionStatus(status) {
  const statusElement = document.querySelector('.connection-status');
  if (statusElement) {
    statusElement.textContent = status;
    statusElement.className = `connection-status ${status.toLowerCase()}`;
  }
}

function updateNowPlaying(track) {
  const nowPlayingElement = document.querySelector('.now-playing');
  const trackNameElement = document.querySelector('.track-name');
  const artistNameElement = document.querySelector('.artist-name');
  
  if (nowPlayingElement && track) {
    nowPlayingElement.style.display = 'block';
    
    if (trackNameElement) {
      trackNameElement.textContent = track.name || 'Unknown Track';
    }
    
    if (artistNameElement) {
      artistNameElement.textContent = track.artists || 'Unknown Artist';
    }
  }
}

function updatePlayPauseButton(playing) {
  const playPauseBtn = document.getElementById('play-pause-btn');
  if (playPauseBtn) {
    playPauseBtn.textContent = playing ? '⏸️' : '▶️';
    playPauseBtn.setAttribute('aria-label', playing ? 'Pause' : 'Play');
  }
}

function enablePlaybackControls(enabled) {
  const controls = ['play-pause-btn', 'next-btn', 'prev-btn', 'volume-slider'];
  controls.forEach(id => {
    const element = document.getElementById(id);
    if (element) {
      element.disabled = !enabled;
      element.style.opacity = enabled ? '1' : '0.5';
    }
  });
}

function formatTime(ms) {
  if (!ms) return '0:00';
  const totalSeconds = Math.floor(ms / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${seconds.toString().padStart(2, '0')}`;
}

function updateProgress(position, trackDuration) {
  const progressBar = document.querySelector('.progress-bar');
  const currentTimeElement = document.querySelector('.current-time');
  const totalTimeElement = document.querySelector('.total-time');
  
  if (progressBar && trackDuration) {
    const percentage = (position / trackDuration) * 100;
    progressBar.style.width = `${Math.min(percentage, 100)}%`;
  }
  
  if (currentTimeElement) {
    currentTimeElement.textContent = formatTime(position);
  }
  
  if (totalTimeElement) {
    totalTimeElement.textContent = formatTime(trackDuration);
  }
}

function toggleChat() {
  const chatSection = document.getElementById('chat-section');
  const toggleBtn = document.getElementById('chat-toggle-btn');
  
  if (chatSection && toggleBtn) {
    const isVisible = chatSection.style.display !== 'none';
    chatSection.style.display = isVisible ? 'none' : 'block';
    toggleBtn.textContent = isVisible ? 'Show Chat' : 'Hide Chat';
  }
}

function displayChatMessage(data) {
  const chatMessages = document.getElementById('chat-messages');
  if (!chatMessages) return;
  
  const messageDiv = document.createElement('div');
  messageDiv.className = 'chat-message';
  messageDiv.innerHTML = `
    <span class="chat-user">${data.user}:</span>
    <span class="chat-text">${data.message}</span>
    <span class="chat-time">${new Date(data.timestamp).toLocaleTimeString()}</span>
  `;
  
  chatMessages.appendChild(messageDiv);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

function sendChatMessage(event) {
  if (event) event.preventDefault();
  
  const messageInput = document.getElementById('chat-input');
  const message = messageInput.value.trim();
  
  if (!message) return;
  
  if (typeof socket !== 'undefined') {
    socket.emit('chat_message', {
      message: message,
      user: window.displayName || 'Anonymous'
    });
  }
  
  messageInput.value = '';
}

function initializeUI() {
  console.log('Initializing UI for role:', window.userRole);
  
  initializeRoleBasedUI();
  
  if (typeof loadQueue === 'function') {
    loadQueue();
  }
  
  if (typeof setupAutoSearch === 'function') {
    setupAutoSearch();
  }
}

// Export functions
window.showNotification = showNotification;
window.updateConnectionStatus = updateConnectionStatus;
window.updateNowPlaying = updateNowPlaying;
window.updatePlayPauseButton = updatePlayPauseButton;
window.enablePlaybackControls = enablePlaybackControls;
window.formatTime = formatTime;
window.updateProgress = updateProgress;
window.toggleChat = toggleChat;
window.displayChatMessage = displayChatMessage;
window.sendChatMessage = sendChatMessage;
window.initializeUI = initializeUI;
