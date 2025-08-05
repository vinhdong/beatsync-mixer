/**
 * Queue Management Module
 */

let queueCount = 0;
let voteData = {};

// Helper function to extract song title from track name (format: "Song Title - Artist Names")
function extractSongTitleFromTrackName(trackName) {
  if (!trackName) return 'Unknown Track';
  
  // Extract song title from "Song Title - Artist Names" format
  if (trackName.includes(' - ')) {
    return trackName.split(' - ')[0].trim();
  } else if (trackName.includes(' — ')) {
    return trackName.split(' — ')[0].trim();
  } else if (trackName.includes(': ')) {
    return trackName.split(': ')[0].trim();
  }
  
  // If no separator found, return the whole track name
  return trackName;
}

function extractArtistFromTrackName(trackName) {
  if (!trackName) return 'Unknown Artist';
  
  // Extract artist from "Song Title - Artist Names" format
  if (trackName.includes(' - ')) {
    const parts = trackName.split(' - ');
    return parts.length > 1 ? parts.slice(1).join(' - ').trim() : 'Unknown Artist';
  } else if (trackName.includes(' — ')) {
    const parts = trackName.split(' — ');
    return parts.length > 1 ? parts.slice(1).join(' — ').trim() : 'Unknown Artist';
  } else if (trackName.includes(': ')) {
    const parts = trackName.split(': ');
    return parts.length > 1 ? parts.slice(1).join(': ').trim() : 'Unknown Artist';
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
      // Removed notification: showNotification(`✅ Added "${trackName}" to queue`, 'success');
      
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

// Auto-advance to next song in queue by clicking the play button
function autoAdvanceToNextSong() {
  if (window.userRole !== 'host') {
    console.log('Auto-advance denied: User is not host');
    return;
  }

  // Call the actual auto-advance function with retry logic
  autoAdvanceWithRetry(0);
}

function autoAdvanceWithRetry(retryCount) {
  const maxRetries = 3;
  
  try {
    console.log(`=== AUTO-ADVANCE DEBUG (Attempt ${retryCount + 1}/${maxRetries + 1}) ===`);
    
    // First, refresh the queue to ensure we have the latest data
    setTimeout(async () => {
      try {
        // Force refresh the queue display first
        await refreshQueueDisplay();
        
        // Debug: Check what queue elements exist after refresh
        const queueList = document.getElementById('queue');
        console.log('Queue list element after refresh:', queueList);
        
        if (queueList) {
          console.log('Queue list HTML length:', queueList.innerHTML.length);
          console.log('Queue list children count:', queueList.children.length);
          
          // Log first few characters to see structure
          if (queueList.innerHTML.length > 0) {
            console.log('Queue list HTML preview:', queueList.innerHTML.substring(0, 500));
          }
        }
        
        // Try to find queue items with multiple selectors
        const queueItems1 = document.querySelectorAll('#queue li[data-track-uri]');
        const queueItems2 = document.querySelectorAll('#queue li.queue-item');
        const queueItems3 = document.querySelectorAll('#queue li');
        
        console.log('Selector #queue li[data-track-uri] found:', queueItems1.length);
        console.log('Selector #queue li.queue-item found:', queueItems2.length);
        console.log('Selector #queue li found:', queueItems3.length);
        
        // Use the best selector that finds items
        let queueItems = queueItems1;
        if (queueItems1.length === 0 && queueItems2.length > 0) {
          queueItems = queueItems2;
          console.log('Using #queue li.queue-item selector instead');
        } else if (queueItems1.length === 0 && queueItems2.length === 0 && queueItems3.length > 0) {
          queueItems = queueItems3;
          console.log('Using #queue li selector as fallback');
        }
        
        console.log('Final queue items to use:', queueItems.length);
        
        if (queueItems.length === 0) {
          console.log('No songs found in DOM after refresh');
          
          // Check if we actually have tracks in the backend
          try {
            const response = await fetch('/queue/');
            const data = await response.json();
            console.log('Backend queue count:', data.count);
            console.log('Backend queue data preview:', data.queue ? data.queue.slice(0, 2) : 'No queue data');
            
            if (data.count > 0 && retryCount < maxRetries) {
              console.log(`Backend has ${data.count} tracks but DOM is empty - retrying in 1 second...`);
              setTimeout(() => autoAdvanceWithRetry(retryCount + 1), 1000);
              return;
            } else if (data.count > 0) {
              console.log('Max retries reached, DOM still empty despite backend data');
              showNotification('⚠️ Queue loading issue - please refresh page', 'error');
              return;
            }
          } catch (fetchError) {
            console.error('Error checking backend queue:', fetchError);
          }
          
          console.log('Queue is actually empty');
          showNotification('🎵 Queue is empty', 'info');
          return;
        }

        // Find the first song in the queue
        const firstSong = queueItems[0];
        console.log('First song element:', firstSong);
        
        const trackUri = firstSong.getAttribute('data-track-uri');
        const trackName = firstSong.querySelector('span')?.textContent || 'Unknown';
        
        console.log('First song in queue:', trackName, trackUri);
        
        if (!trackUri) {
          console.log('No track URI found for first song');
          showNotification('❌ No track URI found', 'error');
          return;
        }
        
        // Try to find play button with multiple approaches
        let playButton = firstSong.querySelector('button[onclick*="playTrackFromQueue"]');
        
        if (!playButton) {
          // Try to find any button with play text or icon
          const allButtons = firstSong.querySelectorAll('button');
          console.log('All buttons in first song:', allButtons.length);
          
          for (const btn of allButtons) {
            const btnText = btn.textContent.trim();
            const onclick = btn.getAttribute('onclick') || '';
            console.log(`  Button: "${btnText}", onclick: "${onclick}"`);
            
            if (onclick.includes('playTrackFromQueue') || btnText.includes('▶️') || btnText.includes('Play')) {
              playButton = btn;
              console.log('Found play button by content search');
              break;
            }
          }
        }
        
        if (!playButton) {
          console.log('No play button found, calling playTrackFromQueue directly');
          
          // Call playTrackFromQueue directly if available
          if (typeof playTrackFromQueue === 'function') {
            console.log('Calling playTrackFromQueue directly with trackUri:', trackUri);
            playTrackFromQueue(trackUri);
            // Removed notification: showNotification('🎵 Auto-playing next song', 'success');
            return;
          } else {
            console.error('playTrackFromQueue function not available');
            showNotification('❌ Unable to play track', 'error');
            return;
          }
        }

        console.log('Found play button, clicking it...');
        
        // Simulate clicking the play button
        playButton.click();
        
        console.log('Auto-advance completed by clicking play button');
        // Removed notification: showNotification('🎵 Auto-playing next song', 'success');
        
      } catch (innerError) {
        console.error('Error in auto-advance inner logic:', innerError);
        
        if (retryCount < maxRetries) {
          console.log(`Retrying auto-advance due to error (attempt ${retryCount + 1}/${maxRetries + 1})`);
          setTimeout(() => autoAdvanceWithRetry(retryCount + 1), 1000);
        } else {
          showNotification('❌ Auto-advance failed after retries', 'error');
        }
      }
    }, 100); // Small delay to ensure DOM is ready
    
  } catch (error) {
    console.error('Error auto-advancing to next song:', error);
    
    if (retryCount < maxRetries) {
      console.log(`Retrying auto-advance due to outer error (attempt ${retryCount + 1}/${maxRetries + 1})`);
      setTimeout(() => autoAdvanceWithRetry(retryCount + 1), 1000);
    } else {
      showNotification('❌ Failed to auto-advance after retries', 'error');
    }
  }
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
window.autoAdvanceToNextSong = autoAdvanceToNextSong;
window.autoAdvanceWithRetry = autoAdvanceWithRetry;
