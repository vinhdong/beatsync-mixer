// Immediate role initialization - run before any other code
(function() {
  // Check if user role is injected from server
  const role = window.userRole;
  const loginDiv = document.getElementById('login');
  
  console.log('Immediate initialization - Role:', role, 'Login div exists:', !!loginDiv);
  
  // If no role is defined or it's undefined, this means we weren't properly authenticated
  if (!role || role === 'undefined' || role === '' || role === 'null') {
    console.log('No valid role found, checking if we should redirect');
    
    // If we're on the main page but have no role, redirect to role selection
    if (window.location.pathname === '/' || window.location.pathname === '/index.html') {
      console.log('On main page but no valid role, redirecting to role selection');
      window.location.href = '/select-role?error=session_lost';
      return;
    }
    
    // Otherwise, show login interface
    if (loginDiv) {
      loginDiv.style.display = 'block';
      loginDiv.style.visibility = 'visible';
      console.log('Login div shown for unauthenticated user');
    }
    
  } else if (role && role !== 'guest' && loginDiv) {
    // Hide login for authenticated users immediately
    loginDiv.style.display = 'none';
    loginDiv.style.visibility = 'hidden';
    console.log('Login div hidden for authenticated user with role:', role);
    
    // Apply immediate role-based UI changes
    const clearQueueBtn = document.getElementById('clear-queue-btn');
    if (role === 'host' && clearQueueBtn) {
      clearQueueBtn.style.display = 'inline-block';
      console.log('Clear queue button shown for host');
    } else if (role === 'listener' && clearQueueBtn) {
      clearQueueBtn.style.display = 'none';
      console.log('Clear queue button hidden for listener');
    }
    
  } else if (!role && loginDiv) {
    // Show login for unauthenticated users
    loginDiv.style.display = 'block';
    loginDiv.style.visibility = 'visible';
    console.log('Login div shown for unauthenticated user');
  }
})();

// Socket initialization and global variables
const socket = io();
let queueCount = 0;
let currentUser = 'User_' + Math.random().toString(36).substr(2, 9); // Generate random user ID
let voteData = {}; // Store vote counts for tracks
let socketConnected = false; // Track socket connection status

// Track socket connection details
const socketId = Math.random().toString(36).substr(2, 8);
console.log(`[SOCKET ${socketId}] Socket created for role:`, window.userRole);

// Socket connection events
socket.on('connect', function() {
  console.log(`[SOCKET ${socketId}] Socket.IO connected`);
  socketConnected = true;
});

socket.on('disconnect', function() {
  console.log(`[SOCKET ${socketId}] Socket.IO disconnected`);
  socketConnected = false;
});

socket.on('error', function(error) {
  console.error('Socket.IO error:', error);
  
  // Show user-friendly error message
  if (error.message) {
    alert('Error: ' + error.message);
  }
  
  // If authentication error, fetch session info for debugging
  if (error.message && error.message.includes('Authentication')) {
    fetch('/session-info')
      .then(response => response.json())
      .then(sessionData => {
        console.log('Session data after auth error:', sessionData);
      })
      .catch(err => console.error('Failed to fetch session info after error:', err));
  }
});

// Playback state events from host
socket.on("playback_started", data => {
  console.log('Playback started:', data);
  
  // Update UI to show something is playing
  if (data.track_uri) {
    // Find the track in the queue and highlight it as playing
    const trackElements = document.querySelectorAll(`li[data-track-uri="${data.track_uri}"]`);
    trackElements.forEach(el => {
      el.style.background = 'rgba(29, 185, 84, 0.2)';
      el.style.border = '2px solid #1db954';
      
      // Add playing indicator
      const playingIndicator = el.querySelector('.playing-indicator');
      if (!playingIndicator) {
        const indicator = document.createElement('span');
        indicator.className = 'playing-indicator';
        indicator.innerHTML = ' 🎵 Playing';
        indicator.style.color = '#1db954';
        indicator.style.fontWeight = 'bold';
        el.appendChild(indicator);
      }
    });
  }
  
  // Show notification for listeners
  if (window.userRole === 'listener') {
    const trackName = data.track_name || 'Unknown Track';
    const notification = document.createElement('div');
    notification.style.cssText = `
      position: fixed;
      top: 20px;
      right: 20px;
      background: #1db954;
      color: white;
      padding: 12px 20px;
      border-radius: 8px;
      z-index: 1000;
      font-weight: bold;
      max-width: 300px;
    `;
    notification.textContent = `🎵 Now Playing: ${trackName}`;
    document.body.appendChild(notification);
    
    setTimeout(() => {
      if (notification.parentNode) {
        notification.parentNode.removeChild(notification);
      }
    }, 5000);
  }
});

socket.on("playback_paused", data => {
  console.log('Playback paused:', data);
  
  // Remove playing indicators from all tracks
  const playingIndicators = document.querySelectorAll('.playing-indicator');
  playingIndicators.forEach(indicator => indicator.remove());
  
  // Remove highlight from all tracks
  const trackElements = document.querySelectorAll('li[data-track-uri]');
  trackElements.forEach(el => {
    el.style.background = '';
    el.style.border = '';
  });
  
  // Show notification for listeners
  if (window.userRole === 'listener') {
    const notification = document.createElement('div');
    notification.style.cssText = `
      position: fixed;
      top: 20px;
      right: 20px;
      background: #666;
      color: white;
      padding: 12px 20px;
      border-radius: 8px;
      z-index: 1000;
      font-weight: bold;
    `;
    notification.textContent = '⏸️ Host paused the music';
    document.body.appendChild(notification);
    
    setTimeout(() => {
      if (notification.parentNode) {
        notification.parentNode.removeChild(notification);
      }
    }, 3000);
  }
});

// Playlists became available from host
socket.on("playlists_available", data => {
  console.log('Playlists available from host:', data);
  
  // Show notification for listeners
  if (window.userRole === 'listener') {
    const notification = document.createElement('div');
    notification.style.cssText = `
      position: fixed;
      top: 20px;
      right: 20px;
      background: #1db954;
      color: white;
      padding: 12px 20px;
      border-radius: 8px;
      z-index: 1000;
      font-weight: bold;
    `;
    notification.textContent = `🎵 ${data.host_name} shared ${data.playlist_count} playlists!`;
    document.body.appendChild(notification);
    
    // Auto-reload playlists for listeners
    setTimeout(() => {
      loadPlaylists();
    }, 1000);
    
    setTimeout(() => {
      if (notification.parentNode) {
        notification.parentNode.removeChild(notification);
      }
    }, 5000);
  }
});

// Socket event handlers for queue and voting
socket.on("queue_updated", data => {
  const li = document.createElement("li");
  const trackId = data.track_uri;
  const safeTrackId = trackId.replace(/[^a-zA-Z0-9]/g, '_');
  const timestamp = new Date(data.timestamp || Date.now()).getTime();
  
  li.setAttribute('data-track-uri', trackId);
  li.setAttribute('data-timestamp', timestamp);
  li.className = 'queue-item';
  li.style.position = 'relative';
  li.innerHTML = `
    <div>
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
        <span style="font-weight: bold;">${data.track_name || data.track_uri}</span>
        <span class="vote-score" id="score-${safeTrackId}" style="background-color: #333; padding: 2px 8px; border-radius: 12px; font-size: 12px; color: #1db954;">Score: 0</span>
      </div>
      <small style="color: #666;">Added: ${new Date(data.timestamp || Date.now()).toLocaleTimeString()}</small>
      <div class="vote-buttons">
        <button class="vote-btn" onclick="voteTrack('${trackId}', 'up', this)">👍</button>
        <span class="vote-count" id="up-${safeTrackId}">0</span>
        <button class="vote-btn" onclick="voteTrack('${trackId}', 'down', this)">👎</button>
        <span class="vote-count" id="down-${safeTrackId}">0</span>
        ${window.userRole === 'host' ? `<button onclick="playTrackFromQueue('${trackId}')" style="background-color: #1db954; margin: 0 5px;">▶️ Play</button>` : ''}
        <button class="recommendations-btn" onclick="loadRecs('${trackId}', '${safeTrackId}')">See Similar Tracks</button>
      </div>
      <div id="recs-${safeTrackId}" class="recommendations-list"></div>
    </div>
  `;
  document.getElementById("queue").appendChild(li);
  queueCount++;
  updateQueueDisplay();
  
  // Initialize vote data for this track if not exists
  if (!voteData[trackId]) {
    voteData[trackId] = { up: 0, down: 0 };
  }
});

socket.on("vote_updated", data => {
  const trackId = data.track_uri;
  const safeId = trackId.replace(/[^a-zA-Z0-9]/g, '_');
  const upElement = document.getElementById(`up-${safeId}`);
  const downElement = document.getElementById(`down-${safeId}`);
  const scoreElement = document.getElementById(`score-${safeId}`);
  
  if (upElement) upElement.textContent = data.up_votes;
  if (downElement) downElement.textContent = data.down_votes;
  
  // Update score display with enhanced styling
  const netScore = data.up_votes - data.down_votes;
  if (scoreElement) {
    scoreElement.textContent = `Score: ${netScore >= 0 ? '+' : ''}${netScore}`;
    
    // Color code the score with background
    if (netScore > 0) {
      scoreElement.style.color = '#1db954'; // Green for positive
      scoreElement.style.backgroundColor = 'rgba(29, 185, 84, 0.1)';
    } else if (netScore < 0) {
      scoreElement.style.color = '#e74c3c'; // Red for negative
      scoreElement.style.backgroundColor = 'rgba(231, 76, 60, 0.1)';
    } else {
      scoreElement.style.color = '#666'; // Gray for neutral
      scoreElement.style.backgroundColor = '#333';
    }
  }
  
  voteData[trackId] = {
    up: data.up_votes,
    down: data.down_votes
  };
  
  // Reorder the queue based on updated votes
  reorderQueueByVotes();
});

socket.on("chat_message", data => {
  const chatMessages = document.getElementById("chat-messages");
  const messageDiv = document.createElement("div");
  messageDiv.className = "chat-message";
  messageDiv.innerHTML = `
    <span class="chat-user">${data.user}:</span> 
    ${data.message}
    <span class="chat-time">${new Date(data.timestamp || Date.now()).toLocaleTimeString()}</span>
  `;
  chatMessages.appendChild(messageDiv);
  chatMessages.scrollTop = chatMessages.scrollHeight;
});

socket.on("queue_cleared", () => {
  document.getElementById("queue").innerHTML = '';
  queueCount = 0;
  voteData = {};
  updateQueueDisplay();
});

// Spotify Web Playback SDK variables
let player = null;
let deviceId = null;
let currentTrack = null;
let isPlaying = false;
let accessToken = null;
let currentTrackUri = null;
let currentPosition = 0;
let duration = 0;
let progressInterval = null;

// Track end detection using progress tracking
let trackEndCheckInterval = null;

// Continue as guest function
function continueAsGuest() {
  // Hide the login section
  const loginDiv = document.getElementById('login');
  if (loginDiv) {
    loginDiv.style.display = 'none';
  }
  
  // Set role to guest and initialize UI
  window.userRole = 'guest';
  window.userId = 'guest_' + Math.random().toString(36).substr(2, 9);
  window.displayName = 'Guest';
  
  console.log('Continuing as guest:', window.userId);
  
  // Initialize guest UI
  initializeRoleBasedUI();
  
  // Load only shared data for guests (no playlists since they don't have Spotify auth)
  loadQueue();
  
  // Socket.IO will automatically connect when the page loads
  console.log('Guest setup complete');
}

// Initialize Spotify Web Playback SDK
window.onSpotifyWebPlaybackSDKReady = () => {
  initializeSpotifyPlayer();
};

// Spotify player initialization
async function initializeSpotifyPlayer() {
  // Only initialize Spotify Player for hosts
  if (window.userRole !== 'host') {
    console.log('Skipping Spotify Player initialization - user is not host');
    return;
  }
  
  try {
    // Get access token from backend
    const tokenResponse = await fetch('/playback/spotify-token', {
      credentials: 'include'
    });
    if (!tokenResponse.ok) {
      console.log('Failed to get Spotify token, status:', tokenResponse.status);
      updateConnectionStatus('🔴 Not authenticated');
      console.log('User not authenticated with Spotify');
      return;
    }
    
    const tokenData = await tokenResponse.json();
    accessToken = tokenData.access_token;
    console.log('Successfully retrieved access token for Spotify Player:', accessToken ? 'Token present' : 'No token');

    // Initialize the Spotify Player
    player = new Spotify.Player({
      name: 'BeatSync Mixer Player',
      getOAuthToken: cb => { cb(accessToken); },
      volume: 0.5
    });

    // Error handling
    player.addListener('initialization_error', ({ message }) => {
      console.error('Spotify Player initialization error:', message);
      updateConnectionStatus('🔴 Initialization error');
      if (message.includes('Spotify Premium')) {
        alert('Spotify Premium is required for web playback. Please upgrade your account to use the music player.');
      }
    });

    player.addListener('authentication_error', ({ message }) => {
      console.error('Spotify Player authentication error:', message);
      updateConnectionStatus('🔴 Authentication error');
    });

    player.addListener('account_error', ({ message }) => {
      console.error('Spotify Player account error:', message);
      updateConnectionStatus('🔴 Premium required');
      alert('Spotify Premium is required for web playback. Please upgrade your account.');
    });

    player.addListener('playback_error', ({ message }) => {
      console.error('Spotify Player playback error:', message);
      alert('Playback error: ' + message);
    });

    // Ready
    player.addListener('ready', ({ device_id }) => {
      console.log('Ready with Device ID', device_id);
      deviceId = device_id;
      updateConnectionStatus('🟢 Connected');
      enablePlaybackControls(true);
      
      // Transfer playback to this device
      transferPlaybackToDevice(device_id);
    });

    // Not Ready
    player.addListener('not_ready', ({ device_id }) => {
      console.log('Device ID has gone offline', device_id);
      updateConnectionStatus('🔴 Disconnected');
      enablePlaybackControls(false);
    });

    // Player state changed
    player.addListener('player_state_changed', (state) => {
      if (!state) return;

      const previousTrack = currentTrack;
      const wasPlaying = isPlaying;
      const previousPosition = currentPosition;

      currentTrack = state.track_window.current_track;
      isPlaying = !state.paused;
      currentPosition = state.position;
      duration = state.duration;
      
      // Check if we have a new track playing
      const newTrackUri = currentTrack ? currentTrack.uri : null;
      const trackChanged = newTrackUri !== currentTrackUri;
      
      if (trackChanged) {
        // Remove the previous track from queue if it was from our queue
        if (currentTrackUri && window.userRole === 'host') {
          removeTrackFromQueue(currentTrackUri);
        }
        currentTrackUri = newTrackUri;
      }

      updateNowPlaying(currentTrack);
      updatePlayPauseButton(isPlaying);
      updateProgress(currentPosition, duration);
      
      // Improved song end detection
      const songEnded = wasPlaying && !isPlaying && 
                       previousPosition > 0 && 
                       currentPosition === 0 && 
                       !trackChanged; // Make sure it's actually the end, not a track change
      
      // Also check if we're near the end of the track (within last 3 seconds) and stopped
      const nearEnd = currentPosition > (duration - 3000) && currentPosition > 0;
      const stoppedNearEnd = wasPlaying && !isPlaying && nearEnd;
      
      if ((songEnded || stoppedNearEnd) && window.userRole === 'host') {
        console.log('Song ended, auto-playing next track...');
        console.log('Track end detection details:', {
          songEnded,
          stoppedNearEnd,
          wasPlaying,
          isPlaying,
          previousPosition,
          currentPosition,
          nearEnd,
          userRole: window.userRole
        });
        setTimeout(() => {
          autoPlayNext();
        }, 1000);
      }
      
      // Start or stop progress tracking
      if (isPlaying) {
        startProgressTracking();
        startTrackEndDetection(); // Start monitoring for track end
      } else {
        stopProgressTracking();
        stopTrackEndDetection();
      }
    });

    // Connect to the player
    const success = await player.connect();
    if (success) {
      console.log('The Web Playback SDK successfully connected to Spotify!');
    } else {
      console.error('The Web Playback SDK could not connect to Spotify');
      updateConnectionStatus('🔴 Connection failed');
    }

  } catch (error) {
    console.error('Error initializing Spotify player:', error);
    updateConnectionStatus('🔴 Initialization failed');
  }
}

// Transfer playback to the Web Playback SDK device
async function transferPlaybackToDevice(deviceId) {
  try {
    const response = await fetch('/playback/transfer', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ device_id: deviceId })
    });

    if (response.ok) {
      console.log('Successfully transferred playback to web player');
    } else {
      const error = await response.json();
      console.warn('Failed to transfer playback:', error.error);
    }
  } catch (error) {
    console.error('Error transferring playback:', error);
  }
}

// Playback control functions
async function togglePlayback() {
  if (!player) return;
  
  try {
    await player.togglePlay();
  } catch (error) {
    console.error('Error toggling playback:', error);
  }
}

async function nextTrack() {
  // Use the auto-play system to get the most liked track
  await autoPlayNext();
}

async function previousTrack() {
  // Get previous track from our queue
  const queueItems = document.querySelectorAll('#queue li');
  if (queueItems.length === 0) return;
  
  // Find currently playing track
  let currentIndex = -1;
  for (let i = 0; i < queueItems.length; i++) {
    const trackUri = queueItems[i].getAttribute('data-track-uri');
    if (trackUri === currentTrackUri) {
      currentIndex = i;
      break;
    }
  }
  
  // Play previous track in queue
  const prevIndex = currentIndex - 1;
  if (prevIndex >= 0) {
    const prevTrackUri = queueItems[prevIndex].getAttribute('data-track-uri');
    await playTrackFromQueue(prevTrackUri);
  } else {
    console.log('No previous track in queue');
  }
}

async function setVolume(volume) {
  if (!player) return;
  
  try {
    await player.setVolume(volume / 100);
  } catch (error) {
    console.error('Error setting volume:', error);
  }
}

function seekToPosition(event) {
  if (!player || !currentTrack) return;
  
  const progressBar = event.currentTarget;
  const rect = progressBar.getBoundingClientRect();
  const clickX = event.clientX - rect.left;
  const width = rect.width;
  const percentage = clickX / width;
  const seekPosition = Math.floor(duration * percentage);
  
  player.seek(seekPosition).then(() => {
    currentPosition = seekPosition;
    updateProgress(currentPosition, duration);
  }).catch(error => {
    console.error('Error seeking:', error);
  });
}

// UI update functions
function updateConnectionStatus(status) {
  const statusElement = document.getElementById('connection-status');
  if (statusElement) statusElement.textContent = status;
}

function updateNowPlaying(track) {
  const trackName = document.getElementById('current-track-name');
  const trackArtist = document.getElementById('current-track-artist');
  const albumImage = document.getElementById('album-image');
  const placeholder = document.getElementById('no-track-placeholder');
  
  if (track) {
    const name = track.name;
    const artists = track.artists.map(artist => artist.name).join(', ');
    const imageUrl = track.album.images[0]?.url;
    
    if (trackName) trackName.textContent = name;
    if (trackArtist) trackArtist.textContent = artists;
    
    if (imageUrl && albumImage) {
      albumImage.src = imageUrl;
      albumImage.style.display = 'block';
      if (placeholder) placeholder.style.display = 'none';
    } else {
      if (albumImage) albumImage.style.display = 'none';
      if (placeholder) placeholder.style.display = 'flex';
    }
  } else {
    if (trackName) trackName.textContent = 'No track playing';
    if (trackArtist) trackArtist.textContent = 'Connect to start playback';
    if (albumImage) albumImage.style.display = 'none';
    if (placeholder) placeholder.style.display = 'flex';
  }
}

function updatePlayPauseButton(playing) {
  const button = document.getElementById('play-pause-btn');
  if (button) {
    button.textContent = playing ? '⏸️' : '▶️';
  }
}

function enablePlaybackControls(enabled) {
  const playPause = document.getElementById('play-pause-btn');
  const next = document.getElementById('next-btn');
  const prev = document.getElementById('prev-btn');
  const volumeSlider = document.getElementById('volume-slider');
  
  if (playPause) playPause.disabled = !enabled;
  if (next) next.disabled = !enabled;
  if (prev) prev.disabled = !enabled;
  if (volumeSlider) volumeSlider.disabled = !enabled;
}

function formatTime(ms) {
  const minutes = Math.floor(ms / 60000);
  const seconds = Math.floor((ms % 60000) / 1000);
  return minutes + ':' + (seconds < 10 ? '0' : '') + seconds;
}

function updateProgress(position, trackDuration) {
  const progressFill = document.getElementById('progress-fill');
  const currentTime = document.getElementById('current-time');
  const totalTime = document.getElementById('total-time');
  
  if (progressFill && trackDuration > 0) {
    const percentage = (position / trackDuration) * 100;
    progressFill.style.width = percentage + '%';
  }
  
  if (currentTime) {
    currentTime.textContent = formatTime(position);
  }
  
  if (totalTime) {
    totalTime.textContent = formatTime(trackDuration);
  }
}

// Progress tracking functions
function startProgressTracking() {
  stopProgressTracking(); // Clear any existing interval
  progressInterval = setInterval(async () => {
    if (player && isPlaying) {
      try {
        const state = await player.getCurrentState();
        if (state) {
          currentPosition = state.position;
          updateProgress(currentPosition, duration);
        }
      } catch (error) {
        console.error('Error getting current state:', error);
      }
    }
  }, 1000);
}

function stopProgressTracking() {
  if (progressInterval) {
    clearInterval(progressInterval);
    progressInterval = null;
  }
}

// Auto-play debounce to prevent multiple simultaneous calls
let autoPlayInProgress = false;
let lastAutoPlayTime = 0;

// Auto-play the most liked track (silent operation)
async function autoPlayNext() {
  const now = Date.now();
  console.log('autoPlayNext called', { 
    accessToken: !!accessToken, 
    deviceId, 
    userRole: window.userRole,
    autoPlayInProgress,
    timeSinceLastCall: now - lastAutoPlayTime
  });
  
  // Debounce: prevent multiple calls within 2 seconds
  if (autoPlayInProgress || (now - lastAutoPlayTime) < 2000) {
    console.log('Auto-play call blocked by debounce');
    return;
  }
  
  if (!accessToken || !deviceId) {
    console.log('Spotify player not connected for auto-play');
    return;
  }

  autoPlayInProgress = true;
  lastAutoPlayTime = now;

  try {
    console.log('Sending auto-play request to /queue/auto-play');
    const response = await fetch('/queue/auto-play', {
      method: 'POST',
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ device_id: deviceId })
    });

    console.log('Auto-play response status:', response.status);
    
    if (response.ok) {
      const result = await response.json();
      console.log(`Auto-played: ${result.message}`, result);
      
      // Show a subtle notification in the connection status
      updateConnectionStatus(`🎵 Auto-playing: ${result.track.track_name}`);
      setTimeout(() => {
        updateConnectionStatus('🟢 Connected');
      }, 3000);
    } else {
      const error = await response.json();
      console.log('No suitable tracks for auto-play:', error.error);
      console.log('Full error response:', error);
    }
  } catch (error) {
    console.error('Error auto-playing track:', error);
  } finally {
    // Reset the flag after a delay to allow the next legitimate auto-play
    setTimeout(() => {
      autoPlayInProgress = false;
    }, 1000);
  }
}

// Play a specific track from the queue
async function playTrackFromQueue(trackUri) {
  if (!accessToken || !deviceId) {
    alert('Spotify player not connected');
    return;
  }

  // Find the track name from the queue
  const trackElement = document.querySelector(`li[data-track-uri="${trackUri}"]`);
  let trackName = trackUri.split(':').pop(); // fallback
  
  if (trackElement) {
    const trackNameSpan = trackElement.querySelector('span:first-child');
    if (trackNameSpan) {
      trackName = trackNameSpan.textContent.trim();
    }
  }

  try {
    const response = await fetch('/playback/play', {
      method: 'POST',
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ 
        track_uri: trackUri,
        track_name: trackName,
        device_id: deviceId 
      })
    });

    if (!response.ok) {
      const error = await response.json();
      console.error('Error playing track:', error);
      
      // Provide more specific error messages
      if (response.status === 404) {
        alert('No active device found. Make sure Spotify is open and try refreshing the page.');
      } else if (error.error && error.error.includes('Premium')) {
        alert('Spotify Premium is required for web playback. Please upgrade your account.');
      } else {
        alert(error.error || 'Failed to play track');
      }
    } else {
      console.log('Successfully started playback');
      
      // DON'T remove the track immediately - let it stay in queue while playing
      // The track will be removed when it finishes playing or when skipped
    }
  } catch (error) {
    console.error('Error playing track:', error);
    alert('Network error. Please check your connection and try again.');
  }
}

// Remove track from queue after it's played
async function removeTrackFromQueue(trackUri) {
  try {
    const response = await fetch(`/queue/remove/${encodeURIComponent(trackUri)}`, {
      method: 'POST',
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json'
      }
    });

    if (response.ok) {
      console.log('Track removed from queue:', trackUri);
    } else {
      console.log('Failed to remove track from queue:', trackUri);
    }
  } catch (error) {
    console.error('Error removing track from queue:', error);
  }
}

// Track end detection using progress tracking
function startTrackEndDetection() {
  stopTrackEndDetection();
  
  trackEndCheckInterval = setInterval(async () => {
    if (player && isPlaying && currentTrack && duration > 0) {
      try {
        const state = await player.getCurrentState();
        if (state && state.position > (duration - 2000)) { // Within last 2 seconds
          console.log('Track ending soon, preparing auto-play...');
          
          // Schedule auto-play
          setTimeout(() => {
            if (window.userRole === 'host') {
              console.log('Track ended via time check, auto-playing next...');
              autoPlayNext();
            }
          }, duration - state.position + 500); // Play next track 500ms after current ends
          
          stopTrackEndDetection(); // Stop checking since we've scheduled the next track
        }
      } catch (error) {
        console.error('Error checking track end:', error);
      }
    }
  }, 1000); // Check every second
}

function stopTrackEndDetection() {
  if (trackEndCheckInterval) {
    clearInterval(trackEndCheckInterval);
    trackEndCheckInterval = null;
  }
}

// Restart session function (for hosts)
async function restartSession() {
  if (confirm('⚠️ RESTART SESSION\n\nThis will:\n• Clear all sessions for everyone\n• Remove current host\n• Clear the entire queue\n• Reset all votes\n• Clear all chat messages\n• Force all users to reconnect\n\nAre you sure you want to restart the entire session?')) {
    try {
      const response = await fetch('/restart-session', {
        method: 'POST',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json'
        }
      });
      
      if (response.ok) {
        const data = await response.json();
        alert('✅ ' + data.message + '\n\nRedirecting to start page...');
        window.location.href = '/';
      } else {
        const error = await response.json();
        alert('❌ Error restarting session: ' + (error.error || 'Unknown error'));
      }
    } catch (error) {
      console.error('Error restarting session:', error);
      alert('❌ Network error while restarting session. Please try again.');
    }
  }
}

function voteTrack(trackUri, voteType, buttonElement) {
  // Ensure user is authenticated
  if (!window.userRole) {
    alert('Please log in to vote on tracks');
    return;
  }
  
  // Add visual feedback to the clicked button - quick and responsive
  if (buttonElement) {
    buttonElement.classList.remove('just-voted');
    // Force reflow to restart animation
    buttonElement.offsetHeight;
    buttonElement.classList.add('just-voted');
    
    // Remove the animation class after it completes
    setTimeout(() => {
      buttonElement.classList.remove('just-voted');
    }, 300); // Quick animation
  }
  
  const voteId = Math.random().toString(36).substr(2, 8);
  console.log(`[VOTE ${voteId}] Voting ${voteType} on track: ${trackUri} (role: ${window.userRole})`);
  
  // Send vote to backend immediately - responsive to every click
  socket.emit('vote_add', {
    track_uri: trackUri,
    vote: voteType,
    client_vote_id: voteId  // Add unique ID to track this specific vote
  });
}

function sendChatMessage(event) {
  event.preventDefault();
  const input = document.getElementById('chat-input');
  const message = input.value.trim();
  
  if (message) {
    // Use session user info instead of random currentUser
    const user = window.displayName || window.userId || 'Anonymous';
    socket.emit('chat_message', {
      user: user,
      message: message
    });
    input.value = '';
  }
}

function toggleChat() {
  const chatBox = document.getElementById('floating-chat');
  const toggleBtn = document.getElementById('chat-toggle');
  
  chatBox.classList.toggle('minimized');
  toggleBtn.textContent = chatBox.classList.contains('minimized') ? '+' : '−';
}

function updateQueueDisplay() {
  const queueEmpty = document.getElementById("queue-empty");
  const clearBtn = document.getElementById("clear-queue-btn");
  
  console.log('updateQueueDisplay called - queueCount:', queueCount, 'userRole:', window.userRole);
  
  if (queueCount === 0) {
    queueEmpty.style.display = "block";
    clearBtn.style.display = "none";
    console.log('Queue empty - hiding clear button');
  } else {
    queueEmpty.style.display = "none";
    // Only show clear button for hosts
    if (window.userRole === 'host') {
      clearBtn.style.display = "inline-block";
      console.log('Queue not empty, showing clear button for host');
    } else {
      clearBtn.style.display = "none";
      console.log('Queue not empty, hiding clear button for non-host role:', window.userRole);
    }
  }
}

function reorderQueueByVotes() {
  const queueContainer = document.getElementById("queue");
  const queueItems = Array.from(queueContainer.children);
  
  // Store original positions
  const originalPositions = new Map();
  queueItems.forEach((item, index) => {
    const trackUri = item.getAttribute('data-track-uri');
    originalPositions.set(trackUri, index);
  });
  
  // Sort queue items by vote score (up votes - down votes), then by timestamp
  queueItems.sort((a, b) => {
    const trackUriA = a.getAttribute('data-track-uri');
    const trackUriB = b.getAttribute('data-track-uri');
    
    const votesA = voteData[trackUriA] || { up: 0, down: 0 };
    const votesB = voteData[trackUriB] || { up: 0, down: 0 };
    
    const scoreA = votesA.up - votesA.down;
    const scoreB = votesB.up - votesB.down;
    
    // Sort by score (descending), then by timestamp (ascending) for tie-breaking
    if (scoreB !== scoreA) {
      return scoreB - scoreA; // Higher score first
    }
    
    // If scores are equal, maintain original order (timestamp)
    const timestampA = a.getAttribute('data-timestamp') || 0;
    const timestampB = b.getAttribute('data-timestamp') || 0;
    return timestampA - timestampB;
  });
  
  // Calculate new positions and determine movement direction
  const movements = new Map();
  queueItems.forEach((item, newIndex) => {
    const trackUri = item.getAttribute('data-track-uri');
    const oldIndex = originalPositions.get(trackUri);
    
    if (oldIndex !== newIndex) {
      if (newIndex < oldIndex) {
        movements.set(trackUri, 'up');
      } else {
        movements.set(trackUri, 'down');
      }
    }
  });
  
  // Apply movement animations before reordering
  queueItems.forEach((item) => {
    const trackUri = item.getAttribute('data-track-uri');
    const movement = movements.get(trackUri);
    
    // Remove any existing animation classes
    item.classList.remove('moving-up', 'moving-down', 'highlight-new-vote');
    
    if (movement === 'up') {
      item.classList.add('moving-up');
    } else if (movement === 'down') {
      item.classList.add('moving-down');
    }
  });
  
  // Wait a brief moment for animations to start, then reorder
  setTimeout(() => {
    // Clear the queue container and re-append in new order
    queueContainer.innerHTML = '';
    queueItems.forEach((item, index) => {
      // Add class name for styling
      item.className = 'queue-item';
      
      // Add "Up Next" indicator for the first item only
      const positionIndicator = item.querySelector('.position-indicator');
      if (index === 0) {
        // First item gets "Up Next" label
        if (positionIndicator) {
          positionIndicator.textContent = 'Up Next';
          positionIndicator.style.cssText = 'position: absolute; top: 5px; left: 5px; background: #1db954; color: white; padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: bold;';
        } else {
          // Create "Up Next" indicator
          const indicator = document.createElement('span');
          indicator.className = 'position-indicator';
          indicator.style.cssText = 'position: absolute; top: 5px; left: 5px; background: #1db954; color: white; padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: bold;';
          indicator.textContent = 'Up Next';
          item.style.position = 'relative';
          item.appendChild(indicator);
        }
      } else {
        // Remove position indicator for other items
        if (positionIndicator) {
          positionIndicator.remove();
        }
      }
      
      // Highlight the first track (next to play)
      if (index === 0) {
        item.classList.add('next-to-play');
      } else {
        item.classList.remove('next-to-play');
      }
      
      // Re-apply movement animations if they were active
      const trackUri = item.getAttribute('data-track-uri');
      const movement = movements.get(trackUri);
      if (movement === 'up') {
        item.classList.add('moving-up');
      } else if (movement === 'down') {
        item.classList.add('moving-down');
      }
      
      queueContainer.appendChild(item);
    });
    
    // Clean up animation classes after animation completes
    setTimeout(() => {
      queueItems.forEach((item) => {
        item.classList.remove('moving-up', 'moving-down');
      });
    }, 600);
    
  }, 50);
  
  console.log('Queue reordered by votes with animations');
}

async function clearQueue() {
  if (confirm('Are you sure you want to clear the entire queue?')) {
    try {
      const response = await fetch('/queue/clear', { 
        method: 'POST',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json'
        }
      });
      if (response.ok) {
        // The socket event will handle UI update
        console.log('Queue cleared successfully');
      } else {
        const errorText = await response.text();
        console.error('Failed to clear queue:', response.status, errorText);
        if (response.status === 403) {
          alert('Only hosts can clear the queue. Please make sure you are logged in as a host.');
        } else {
          alert('Failed to clear queue: ' + response.status);
        }
      }
    } catch (err) {
      console.error('Error clearing queue:', err);
      alert('Error clearing queue: ' + err.message);
    }
  }
}

async function loadPlaylists() {
  try {
    console.log('loadPlaylists called - User role:', window.userRole);
    
    // Show loading indicator
    const playlistList = document.getElementById('playlist-list');
    playlistList.innerHTML = '<div style="text-align: center; padding: 20px; color: #666;"><div class="loading-spinner"></div> Loading playlists...</div>';
    
    console.log('Fetching playlists from /playlists/');
    const res = await fetch('/playlists/', {
      credentials: 'include'
    });
    
    console.log('Playlists response status:', res.status, 'redirected:', res.redirected);
    
    if (res.redirected) {
      console.log('Response was redirected, showing login');
      document.getElementById('login').style.display = 'block';
      return;
    }
    
    const data = await res.json();
    console.log('Playlists data received:', data);
    
    document.getElementById('login').style.display = 'none';
    document.getElementById('playlists').style.display = 'block';
    
    // Update the playlist section title based on user role
    const playlistsTitle = document.querySelector('#playlists h2');
    if (data.is_listener) {
      playlistsTitle.textContent = '🎵 Host\'s Playlists';
    } else if (data.is_host) {
      playlistsTitle.textContent = 'Your Playlists';
    } else {
      playlistsTitle.textContent = 'Playlists';
    }
    
    const ul = document.getElementById('playlist-list');
    ul.innerHTML = ''; // Clear loading indicator
    
    console.log('Processing playlists - Total items:', data.items.length, 'Is listener:', data.is_listener, 'Is host:', data.is_host);
    
    // Visual confirmation that we're processing playlists
    console.log('About to update playlist list element with', data.items.length, 'items');
    
    // Show message if listener and no playlists
    if (data.is_listener && data.items.length === 0) {
      const messageDiv = document.createElement('div');
      messageDiv.style.cssText = `
        text-align: center;
        padding: 20px;
        color: #666;
        font-style: italic;
        border: 2px dashed #444;
        border-radius: 8px;
        margin: 20px 0;
      `;
      messageDiv.innerHTML = `
        <div style="font-size: 2em; margin-bottom: 10px;">🎵</div>
        ${data.message || 'No playlists shared yet'}<br><br>
        <small>When a host connects and browses their playlists, they'll appear here for you to explore!</small>
      `;
      ul.appendChild(messageDiv);
      return;
    }
    
    console.log('About to render playlists...');
    data.items.forEach(pl => {
      console.log('Rendering playlist:', pl.name, 'ID:', pl.id, 'Tracks:', pl.tracks ? pl.tracks.total : 'Unknown');
      const li = document.createElement('li');
      li.innerHTML = `
        <span>${pl.name}</span>
        <small>${pl.tracks ? pl.tracks.total : 'Unknown'} tracks</small>
        ${data.is_listener ? '<small style="color: #9C27B0;">👤 Host\'s Playlist</small>' : ''}
      `;
      li.onclick = () => loadPlaylistTracks(pl.id);
      ul.appendChild(li);
    });
    console.log('Finished rendering', data.items.length, 'playlists');
    
    // Add listener mode info message
    if (data.is_listener && data.items.length > 0) {
      const infoDiv = document.createElement('div');
      infoDiv.style.cssText = `
        background: rgba(156, 39, 176, 0.1);
        padding: 10px;
        border-radius: 6px;
        margin: 15px 0;
        font-size: 0.85em;
        color: #ccc;
        text-align: center;
      `;
      infoDiv.innerHTML = '💡 These are playlists shared by the current host. Click to explore!';
      ul.appendChild(infoDiv);
    }
    
  } catch (err) {
    console.error('Error loading playlists:', err);
    
    // Show error message with more details
    const ul = document.getElementById('playlist-list');
    ul.innerHTML = `
      <div style="text-align: center; padding: 20px; color: #e74c3c;">
        <div style="font-size: 2em; margin-bottom: 10px;">❌</div>
        Error loading playlists<br>
        <small style="color: #999; margin-top: 10px; display: block;">
          Error: ${err.message}<br>
          User Role: ${window.userRole}<br>
          Time: ${new Date().toLocaleTimeString()}
        </small>
        <button onclick="loadPlaylists()" style="
          margin-top: 10px; 
          padding: 5px 10px; 
          background: #1db954; 
          color: white; 
          border: none; 
          border-radius: 3px; 
          cursor: pointer;
        ">Try Again</button>
      </div>
    `;
  }
}

function queueTrack(trackUri, trackName) {
  console.log('queueTrack called with:', { trackUri, trackName });
  console.log('Socket connected:', socketConnected);
  console.log('User role:', window.userRole);
  
  if (!socketConnected) {
    console.error('Socket not connected');
    alert('Connection issue. Please refresh the page.');
    return;
  }
  
  // Allow both hosts and listeners to add tracks to the queue
  if (window.userRole !== 'host' && window.userRole !== 'listener') {
    alert('You must be a host or listener to add tracks to the queue.');
    return;
  }
  
  // Debug session info before attempting to queue
  fetch('/session-info', {
    credentials: 'include'
  })
           .then(response => response.json())
    .then(sessionData => {
      console.log('Current session data:', sessionData);
    })
    .catch(err => console.error('Failed to fetch session info:', err));
  
  socket.emit('queue_add', { 
    track_uri: trackUri,
    track_name: trackName
  });
  
  console.log('Emitted queue_add event');
}

async function loadPlaylistTracks(playlistId) {
  try {
    // Show loading indicator
    document.getElementById('playlists').style.display = 'none';
    document.getElementById('tracks').style.display = 'block';
    
    const trackList = document.getElementById('track-list');
    trackList.innerHTML = '<div style="text-align: center; padding: 20px; color: #666;"><div class="loading-spinner"></div> Loading tracks...</div>';
    
    const res = await fetch(`/playlists/${playlistId}/tracks`, {
      credentials: 'include'
    });
    if (res.redirected) {
      window.location = res.url;
      return;
    }
    const data = await res.json();
    
    // Update tracks section title
    const tracksTitle = document.querySelector('#tracks h2');
    if (data.guest_mode) {
      tracksTitle.textContent = '🎵 Playlist Tracks (Guest View)';
    } else {
      tracksTitle.textContent = 'Playlist Tracks';
    }
    
    const ul = document.getElementById('track-list');
    ul.innerHTML = ''; // Clear loading indicator

    // Handle guest mode with no tracks
    if (data.guest_mode && data.items.length === 0) {
      const messageDiv = document.createElement('div');
      messageDiv.style.cssText = `
        text-align: center;
        padding: 30px 20px;
        color: #666;
        border: 2px dashed #444;
        border-radius: 8px;
        margin: 20px 0;
      `;
      messageDiv.innerHTML = `
        <div style="font-size: 2.5em; margin-bottom: 15px;">🎵</div>
        <strong>${data.message || 'No tracks cached yet'}</strong><br><br>
        <small style="color: #999;">
          The host needs to browse this playlist first to cache the tracks for guests.<br>
          You can still vote on tracks that are already in the queue!
        </small><br><br>
        <button onclick="loadPlaylists()" style="
          background: linear-gradient(135deg, #9C27B0, #E91E63);
          color: white;
          border: none;
          padding: 8px 16px;
          border-radius: 6px;
          cursor: pointer;
          margin-top: 10px;
        ">← Back to Playlists</button>
      `;
      ul.appendChild(messageDiv);
      return;
    }

    // Display tracks
    data.items.forEach(item => {
      const t = item.track;
      if (t && t.name) { // Check if track exists (some tracks can be null)
        const li = document.createElement('li');
        li.innerHTML = `
          <div>
            <strong>${t.name}</strong><br>
            <small>${t.artists.map(a => a.name).join(', ')}</small>
            ${data.guest_mode ? '<small style="color: #9C27B0; font-size: 0.7em;">👤 Cached for guests</small>' : ''}
          </div>
        `;
        const btn = document.createElement('button');
        
        // Show appropriate button based on role
        console.log('Creating track button for role:', window.userRole);
        if (window.userRole === 'host' || window.userRole === 'listener') {
          btn.textContent = 'Add to Queue';
          btn.onclick = () => queueTrack(t.uri, `${t.name} - ${t.artists.map(a => a.name).join(', ')}`);
          li.appendChild(btn);
          console.log('Added "Add to Queue" button for role:', window.userRole);
        } else {
          // Guests get a different message
          const guestMsg = document.createElement('small');
          guestMsg.style.cssText = 'color: #9C27B0; font-style: italic; margin-left: 10px;';
          guestMsg.textContent = '(Vote on queued tracks instead!)';
          li.appendChild(guestMsg);
          console.log('Added guest message for role:', window.userRole);
        }
        
        ul.appendChild(li);
      }
    });
    
    // Add info for guest mode
    if (data.guest_mode && data.items.length > 0) {
      const infoDiv = document.createElement('div');
      infoDiv.style.cssText = `
        background: rgba(156, 39, 176, 0.1);
        padding: 12px;
        border-radius: 6px;
        margin: 15px 0;
        font-size: 0.85em;
        color: #ccc;
        text-align: center;
      `;
      infoDiv.innerHTML = `
        💡 <strong>Guest Mode:</strong> You can see tracks but can't add them to the queue.<br>
        Head to the queue section to vote on tracks that are already queued!
      `;
      ul.appendChild(infoDiv);
    }
    
  } catch (err) {
    console.error('Error loading playlist tracks:', err);
    const ul = document.getElementById('track-list');
    ul.innerHTML = `
      <div style="text-align: center; padding: 20px; color: #e74c3c;">
        <div style="font-size: 2em; margin-bottom: 10px;">❌</div>
        Error loading tracks. Please try again later.
      </div>
    `;
  }
}

async function loadInitialQueue() {
  try {
    const response = await fetch('/queue');
    const data = await response.json();
    queueCount = data.count;
    updateQueueDisplay();
  } catch (err) {
    console.error('Error loading initial queue:', err);
  }
}

// Load recommendations for a track
async function loadRecs(trackUri, safeTrackId) {
  const recsContainer = document.getElementById(`recs-${safeTrackId}`);
  const btn = event.target;
  
  // Toggle visibility if already loaded
  if (recsContainer.classList.contains('visible')) {
    recsContainer.classList.remove('visible');
    btn.textContent = 'See Similar Tracks';
    return;
  }
  
  // Show container instantly with loading message
  recsContainer.innerHTML = '<div class="recommendation-item" style="color: #666; padding: 10px; text-align: center;">⏳ Loading recommendations...</div>';
  recsContainer.classList.add('visible');
  btn.textContent = 'Hide Similar Tracks';
  
  // Load recommendations in background
  try {
    const response = await fetch(`/recommend/${encodeURIComponent(trackUri)}`);
    
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    
    const data = await response.json();
    const recommendations = data.recommendations || [];
    
    if (recommendations.length === 0) {
      const message = data.message || 'No similar tracks found for this song.';
      recsContainer.innerHTML = `<div class="recommendation-item" style="color: #666; font-style: italic; padding: 10px; text-align: center;">${message}</div>`;
    } else {
      recsContainer.innerHTML = recommendations.map(rec => `
        <div class="recommendation-item" style="padding: 8px; border-bottom: 1px solid #444; margin-bottom: 5px;">
          <a href="${rec.url}" target="_blank" class="recommendation-link" style="color: #1db954; text-decoration: none;">
            <strong>${rec.artist}</strong> — ${rec.title}
          </a>
          ${rec.source ? `<small style="color: #666; margin-left: 10px; font-size: 10px;">(${rec.source})</small>` : ''}
        </div>
      `).join('');
    }
    
  } catch (error) {
    console.error('Error loading recommendations:', error);
    recsContainer.innerHTML = '<div class="recommendation-item" style="color: #e74c3c; padding: 10px; text-align: center;">Error loading recommendations. Please try again.</div>';
  }
}

// Music Search Functionality
let searchResults = [];
let searchTimeout = null;

// Auto-search with debouncing
function setupAutoSearch() {
  const searchInput = document.getElementById('search-input');
  if (!searchInput) return;
  
  searchInput.addEventListener('input', function() {
    const query = this.value.trim();
    
    // Clear previous timeout
    if (searchTimeout) {
      clearTimeout(searchTimeout);
    }
    
    // Hide results if query is empty
    if (!query) {
      document.getElementById('search-results').style.display = 'none';
      return;
    }
    
    // Set new timeout for auto-search (500ms delay)
    searchTimeout = setTimeout(() => {
      if (query.length >= 2) { // Only search if 2+ characters
        searchMusic(query);
      }
    }, 500);
  });
  
  // Also keep Enter key functionality
  searchInput.addEventListener('keypress', function(e) {
    if (e.key === 'Enter') {
      if (searchTimeout) {
        clearTimeout(searchTimeout);
      }
      const query = this.value.trim();
      if (query) {
        searchMusic(query);
      }
    }
  });
}

async function searchMusic(query = null) {
  const searchInput = document.getElementById('search-input');
  const searchQuery = query || searchInput.value.trim();
  
  if (!searchQuery) {
    document.getElementById('search-results').style.display = 'none';
    return;
  }
  
  // Show loading state
  const searchBtn = document.getElementById('search-btn');
  const originalText = searchBtn.textContent;
  searchBtn.textContent = 'Searching...';
  searchBtn.disabled = true;
  
  try {
    console.log('Searching for:', searchQuery);
    const response = await fetch(`/search/tracks?q=${encodeURIComponent(searchQuery)}&limit=20`);
    const data = await response.json();
    
    if (data.error) {
      console.error('Search error:', data.error);
      showNotification(`❌ Search failed: ${data.error}`, 'error');
      document.getElementById('search-results').style.display = 'none';
      return;
    }
    
    searchResults = data.tracks || [];
    displaySearchResults(searchResults);
    
  } catch (error) {
    console.error('Search request failed:', error);
    showNotification('❌ Search failed. Please try again.', 'error');
    document.getElementById('search-results').style.display = 'none';
  } finally {
    // Restore button state
    searchBtn.textContent = originalText;
    searchBtn.disabled = false;
  }
}

function displaySearchResults(tracks) {
  const resultsDiv = document.getElementById('search-results');
  const resultsList = document.getElementById('search-results-list');
  
  if (!tracks || tracks.length === 0) {
    resultsDiv.style.display = 'none';
    alert('No tracks found. Try a different search term.');
    return;
  }
  
  resultsList.innerHTML = '';
  
  tracks.forEach(track => {
    const li = document.createElement('li');
    li.className = 'search-result-item';
    
    li.innerHTML = `
      <div class="track-info">
        <div class="track-name">${track.name}</div>
        <div class="track-details">
          ${track.artist_names} • ${track.album}
          ${track.duration_text ? ' • ' + track.duration_text : ''}
        </div>
      </div>
      <button onclick="addTrackToQueue('${track.uri}', '${track.name.replace(/'/g, "\\'")}', '${track.artist_names.replace(/'/g, "\\'")}')">
        Add to Queue
      </button>
    `;
    
    resultsList.appendChild(li);
  });
  
  resultsDiv.style.display = 'block';
}

async function addTrackToQueue(trackUri, trackName, artistNames) {
  try {
    console.log('Adding to queue:', trackName, 'by', artistNames);
    
    // Show loading state
    const button = event.target;
    const originalText = button.textContent;
    button.textContent = 'Adding...';
    button.disabled = true;
    
    const response = await fetch('/search/add-to-queue', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        track_uri: trackUri,
        track_name: `${trackName} - ${artistNames}`
      })
    });
    
    const data = await response.json();
    
    if (response.ok) {
      console.log('Track added successfully:', data.message);
      showNotification(`✅ ${data.message}`, 'success');
      
      // Increment queue count immediately for UI feedback
      queueCount++;
      updateQueueDisplay();
      
      // Refresh queue display after a short delay
      setTimeout(() => {
        if (typeof loadQueue === 'function') {
          loadQueue();
        } else {
          // Fallback: manually refresh queue
          refreshQueueDisplay();
        }
      }, 500);
      
      // Mark button as added
      button.textContent = '✅ Added';
      button.style.backgroundColor = '#27ae60';
      setTimeout(() => {
        button.textContent = originalText;
        button.style.backgroundColor = '#1db954';
        button.disabled = false;
      }, 2000);
      
    } else {
      console.error('Failed to add track:', data.error);
      showNotification(`❌ ${data.error}`, 'error');
      
      // Restore button
      button.textContent = originalText;
      button.disabled = false;
    }
    
  } catch (error) {
    console.error('Error adding track to queue:', error);
    showNotification('❌ Failed to add track to queue', 'error');
    
    // Restore button on error
    if (event && event.target) {
      event.target.textContent = 'Add to Queue';
      event.target.disabled = false;
    }
  }
}

// Function to manually refresh queue display
async function refreshQueueDisplay() {
  try {
    const response = await fetch('/queue/');
    const data = await response.json();
    
    queueCount = data.count || 0;
    updateQueueDisplay();
    
    // Update queue list if it exists
    const queueList = document.getElementById('queue-list');
    if (queueList && data.queue) {
      queueList.innerHTML = '';
      data.queue.forEach(item => {
        const li = document.createElement('li');
        li.textContent = item.track_name;
        queueList.appendChild(li);
      });
    }
    
    console.log('Queue refreshed, count:', queueCount);
  } catch (error) {
    console.error('Error refreshing queue:', error);
  }
}

function showNotification(message, type = 'info') {
  // Create notification element
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
  
  // Set color based on type
  if (type === 'success') {
    notification.style.backgroundColor = '#27ae60';
  } else if (type === 'error') {
    notification.style.backgroundColor = '#e74c3c';
  } else {
    notification.style.backgroundColor = '#3498db';
  }
  
  notification.textContent = message;
  document.body.appendChild(notification);
  
  // Remove after 3 seconds
  setTimeout(() => {
    notification.style.opacity = '0';
    notification.style.transform = 'translateX(100%)';
    setTimeout(() => {
      document.body.removeChild(notification);
    }, 300);
  }, 3000);
}

// Add search on Enter key press and auto-search setup
document.addEventListener('DOMContentLoaded', function() {
  // Setup auto-search functionality
  setupAutoSearch();
  
  // Initialize role-based UI
  initializeRoleBasedUI();
  
  // Initialize queue display
  if (typeof loadQueue === 'function') {
    loadQueue();
  } else {
    refreshQueueDisplay();
  }
});

function initializeRoleBasedUI() {
  const userRole = window.userRole;
  console.log('Initializing UI for role:', userRole);
  
  // Elements to control
  const playlistsDiv = document.getElementById('playlists');
  const tracksDiv = document.getElementById('tracks');
  const searchSection = document.getElementById('search-section');
  
  if (userRole === 'host') {
    // Host sees everything: search + playlists
    if (searchSection) searchSection.style.display = 'block';
    if (playlistsDiv) playlistsDiv.style.display = 'block';
    if (tracksDiv) tracksDiv.style.display = 'none';
  } else {
    // Listeners and guests see only search
    if (searchSection) searchSection.style.display = 'block';
    if (playlistsDiv) playlistsDiv.style.display = 'none';
    if (tracksDiv) tracksDiv.style.display = 'none';
  }
}
