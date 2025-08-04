/**
 * Music Search Module
 */

let searchResults = [];
let searchTimeout = null;

function setupAutoSearch() {
  const searchInput = document.getElementById('search-input');
  if (!searchInput) return;
  
  searchInput.addEventListener('input', function() {
    const query = this.value.trim();
    
    if (searchTimeout) {
      clearTimeout(searchTimeout);
    }
    
    if (!query) {
      document.getElementById('search-results').style.display = 'none';
      return;
    }
    
    searchTimeout = setTimeout(() => {
      if (query.length >= 2) {
        searchMusic(query);
      }
    }, 500);
  });
  
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
    searchBtn.textContent = originalText;
    searchBtn.disabled = false;
  }
}

function displaySearchResults(tracks) {
  const resultsDiv = document.getElementById('search-results');
  const resultsList = document.getElementById('search-results-list');
  
  if (!tracks || tracks.length === 0) {
    resultsDiv.style.display = 'none';
    showNotification('No tracks found. Try a different search term.', 'info');
    return;
  }
  
  resultsList.innerHTML = '';
  
  tracks.forEach(track => {
    const li = document.createElement('li');
    li.className = 'search-result-item';
    
    li.innerHTML = `
      <div class="track-info">
        <div class="track-name">${track.name}</div>
        <div class="track-artist">${track.artist_names}${track.duration_text ? ' • ' + track.duration_text : ''}</div>
        <div class="track-album">${track.album}</div>
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
      
      if (typeof updateQueueCount === 'function') {
        updateQueueCount();
      }
      
      setTimeout(() => {
        if (typeof loadQueue === 'function') {
          loadQueue();
        } else if (typeof refreshQueueDisplay === 'function') {
          refreshQueueDisplay();
        }
      }, 500);
      
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
      
      button.textContent = originalText;
      button.disabled = false;
    }
    
  } catch (error) {
    console.error('Error adding track to queue:', error);
    showNotification('❌ Failed to add track to queue', 'error');
    
    if (event && event.target) {
      event.target.textContent = 'Add to Queue';
      event.target.disabled = false;
    }
  }
}

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

// Export functions
window.setupAutoSearch = setupAutoSearch;
window.searchMusic = searchMusic;
window.addTrackToQueue = addTrackToQueue;
window.loadRecs = loadRecs;
