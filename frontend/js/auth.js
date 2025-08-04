/**
 * Authentication and Role Management Module
 */

// Global role variables
window.userRole = window.userRole || null;
window.userId = window.userId || null;
window.displayName = window.displayName || 'Guest';

// Immediate role initialization
(function initializeAuth() {
  const role = window.userRole;
  const loginDiv = document.getElementById('login');
  
  console.log('Auth init - Role:', role, 'Login div exists:', !!loginDiv);
  
  if (!role || role === 'undefined' || role === '' || role === 'null') {
    console.log('No valid role found');
    
    if (window.location.pathname === '/' || window.location.pathname === '/index.html') {
      console.log('Redirecting to role selection');
      window.location.href = '/select-role?error=session_lost';
      return;
    }
    
    if (loginDiv) {
      loginDiv.style.display = 'block';
      loginDiv.style.visibility = 'visible';
    }
    
  } else if (role && role !== 'guest' && loginDiv) {
    loginDiv.style.display = 'none';
    loginDiv.style.visibility = 'hidden';
    
    const clearQueueBtn = document.getElementById('clear-queue-btn');
    if (role === 'host' && clearQueueBtn) {
      clearQueueBtn.style.display = 'inline-block';
    } else if (role === 'listener' && clearQueueBtn) {
      clearQueueBtn.style.display = 'none';
    }
    
  } else if (!role && loginDiv) {
    loginDiv.style.display = 'block';
    loginDiv.style.visibility = 'visible';
  }
})();

function continueAsGuest() {
  window.userRole = 'guest';
  window.userId = 'guest_' + Date.now() + '_' + Math.floor(Math.random() * 1000);
  window.displayName = 'Guest';
  
  const loginDiv = document.getElementById('login');
  if (loginDiv) {
    loginDiv.style.display = 'none';
  }
  
  console.log('Continuing as guest with ID:', window.userId);
  
  if (typeof initializeUI === 'function') {
    initializeUI();
  }
}

function initializeRoleBasedUI() {
  const role = window.userRole;
  const loginDiv = document.getElementById('login');
  const playlistsDiv = document.getElementById('playlists');
  const tracksDiv = document.getElementById('tracks');
  const searchSection = document.getElementById('search-section');
  const clearQueueBtn = document.getElementById('clear-queue-btn');
  const restartBtn = document.getElementById('host-restart-btn');
  
  // Remove any existing role indicator first
  if (typeof removeRoleIndicator === 'function') {
    removeRoleIndicator();
  }
  
  if (role === 'host') {
    // Host sees everything: search + playlists + restart button
    if (searchSection) searchSection.style.display = 'block';
    if (playlistsDiv) playlistsDiv.style.display = 'block';
    if (tracksDiv) tracksDiv.style.display = 'none';
    if (clearQueueBtn) clearQueueBtn.style.display = 'inline-block';
    if (restartBtn) {
      restartBtn.style.display = 'inline-block';
      restartBtn.style.visibility = 'visible';
    }
    
    // Add role indicator
    if (typeof addRoleIndicator === 'function') {
      addRoleIndicator('host');
    }
    
  } else {
    // Listeners and guests see only search, no restart button
    if (searchSection) searchSection.style.display = 'block';
    if (playlistsDiv) playlistsDiv.style.display = 'none';
    if (tracksDiv) tracksDiv.style.display = 'none';
    if (clearQueueBtn) clearQueueBtn.style.display = 'none';
    if (restartBtn) restartBtn.style.display = 'none';
    
    // Add role indicator for listeners and guests
    if (typeof addRoleIndicator === 'function') {
      addRoleIndicator(role || 'guest');
    }
  }
}

// Export functions for global access
window.continueAsGuest = continueAsGuest;
window.initializeRoleBasedUI = initializeRoleBasedUI;
