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
  const chatBox = document.getElementById('floating-chat');
  const toggleBtn = document.getElementById('chat-toggle');
  
  if (chatBox && toggleBtn) {
    chatBox.classList.toggle('minimized');
    toggleBtn.textContent = chatBox.classList.contains('minimized') ? '+' : '−';
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

function loadChatHistory(messages) {
  const chatMessages = document.getElementById('chat-messages');
  if (!chatMessages) return;
  
  // Clear existing messages
  chatMessages.innerHTML = '';
  
  // Load all messages from history
  messages.forEach(data => {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'chat-message';
    messageDiv.innerHTML = `
      <span class="chat-user">${data.user}:</span>
      <span class="chat-text">${data.message}</span>
      <span class="chat-time">${new Date(data.timestamp).toLocaleTimeString()}</span>
    `;
    chatMessages.appendChild(messageDiv);
  });
  
  // Scroll to bottom
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

function sendChatMessage(event) {
  if (event) event.preventDefault();
  
  const messageInput = document.getElementById('chat-input');
  const message = messageInput.value.trim();
  
  if (!message) return;
  
  if (typeof socket !== 'undefined') {
    // The backend will get user info from session, so we only send the message
    socket.emit('chat_message', {
      message: message
    });
  }
  
  messageInput.value = '';
}

function initializeUI() {
  console.log('Initializing UI for role:', window.userRole);
  
  initializeRoleBasedUI();
  
  if (typeof refreshQueueDisplay === 'function') {
    refreshQueueDisplay();
  }
  
  if (typeof setupAutoSearch === 'function') {
    setupAutoSearch();
  }
}

function addRoleIndicator(role) {
  const h1 = document.querySelector('h1');
  if (h1 && !document.querySelector('.role-indicator')) {
    const roleSpan = document.createElement('span');
    roleSpan.className = 'role-indicator';
    roleSpan.textContent = role.toUpperCase();
    h1.appendChild(roleSpan);
    
    // Always show a container for user info
    const userContainer = document.createElement('div');
    userContainer.style.cssText = `
      background: linear-gradient(135deg, #1db954, #1ed760);
      color: white;
      padding: 8px 16px;
      border-radius: 8px;
      font-size: 0.85em;
      font-weight: 500;
      margin: 10px 0;
      box-shadow: 0 2px 8px rgba(29, 185, 84, 0.3);
      display: flex;
      align-items: center;
      gap: 8px;
      text-align: center;
      justify-content: center;
    `;
    
    // Show display name if available, otherwise show generic welcome
    if (window.displayName && window.displayName !== 'Guest') {
      const nameSpan = document.createElement('span');
      nameSpan.innerHTML = `👋 Welcome, <strong>${window.displayName}</strong>!`;
      userContainer.appendChild(nameSpan);
    } else if (role === 'guest') {
      const nameSpan = document.createElement('span');
      nameSpan.innerHTML = '👋 Welcome, <strong>Guest</strong>!';
      userContainer.appendChild(nameSpan);
    }
    
    h1.parentNode.insertBefore(userContainer, h1.nextSibling);
  }
}

function removeRoleIndicator() {
  const existingIndicator = document.querySelector('.role-indicator');
  if (existingIndicator) {
    existingIndicator.remove();
  }
  
  // Also remove the user container
  const h1 = document.querySelector('h1');
  if (h1 && h1.nextElementSibling && h1.nextElementSibling.style.fontSize === '0.7em') {
    h1.nextElementSibling.remove();
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
window.addRoleIndicator = addRoleIndicator;
window.removeRoleIndicator = removeRoleIndicator;
