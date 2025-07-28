# Queue Animation System

## Overview
Implemented smooth animations for the queue voting system to provide better visual feedback when tracks move up or down based on votes.

## Animation Features

### 1. **Smooth Queue Reordering**
- **slideUp Animation**: Green glow effect when tracks move up in the queue
- **slideDown Animation**: Orange glow effect when tracks move down in the queue
- **Duration**: 0.6 seconds with smooth cubic-bezier easing
- **Visual Feedback**: Temporary elevation and glow effects during movement

### 2. **Vote Button Feedback**
- **buttonPulse Animation**: Immediate visual feedback when vote buttons are clicked
- **Scale Effect**: Buttons scale up briefly when clicked
- **Color Flash**: Brief green background flash on vote
- **Duration**: 0.3 seconds

### 3. **Track Highlight on Vote**
- **pulseVote Animation**: Entire track briefly highlights when voted on
- **Scale Effect**: Subtle track scaling (1.02x) during vote
- **Background Flash**: Green background flash to show which track was voted on
- **Duration**: 0.4 seconds

### 4. **Position Indicators**
- **Queue Numbers**: Each track shows its current position (#1, #2, etc.)
- **Dynamic Updates**: Position numbers update automatically as tracks reorder
- **Visual Style**: Dark rounded badges in top-left corner

## CSS Animations

### Queue Movement Animations
```css
@keyframes slideUp {
  0% { transform: translateY(0); background-color: rgba(29, 185, 84, 0.1); }
  50% { transform: translateY(-10px); background-color: rgba(29, 185, 84, 0.3); }
  100% { transform: translateY(0); background-color: transparent; }
}

@keyframes slideDown {
  0% { transform: translateY(0); background-color: rgba(255, 165, 0, 0.1); }
  50% { transform: translateY(10px); background-color: rgba(255, 165, 0, 0.3); }
  100% { transform: translateY(0); background-color: transparent; }
}
```

### Vote Feedback Animations
```css
@keyframes buttonPulse {
  0% { transform: scale(1); background-color: transparent; }
  50% { transform: scale(1.2); background-color: rgba(29, 185, 84, 0.3); }
  100% { transform: scale(1); background-color: #f0f0f0; }
}

@keyframes pulseVote {
  0% { transform: scale(1); background-color: transparent; }
  50% { transform: scale(1.02); background-color: rgba(29, 185, 84, 0.2); }
  100% { transform: scale(1); background-color: transparent; }
}
```

## JavaScript Implementation

### Movement Detection
```javascript
// Store original positions before reordering
const originalPositions = new Map();
queueItems.forEach((item, index) => {
  const trackUri = item.getAttribute('data-track-uri');
  originalPositions.set(trackUri, index);
});

// Determine movement direction after sorting
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
```

### Animation Timing
- **Pre-animation**: Apply animation classes before DOM reordering
- **Reorder Delay**: 50ms delay to allow animation start
- **Cleanup**: Remove animation classes after 600ms

## User Experience Benefits

1. **Track Movement Visibility**: Users can clearly see which songs moved and in which direction
2. **Vote Confirmation**: Immediate feedback shows that their vote was registered
3. **Queue Understanding**: Position numbers help users understand the current order
4. **Smooth Transitions**: No jarring jumps or sudden repositioning
5. **Visual Polish**: Professional animations enhance the overall experience

## Technical Details

### Performance Optimizations
- Uses `transform` properties for smooth GPU-accelerated animations
- Minimal DOM manipulation during animations
- Efficient cleanup of animation classes
- Cubic-bezier easing for natural movement

### Browser Compatibility
- Modern CSS animations supported in all major browsers
- Graceful degradation on older browsers (animations simply won't show)
- No JavaScript animation dependencies

### Accessibility
- Animations respect user preferences (can be disabled via CSS `prefers-reduced-motion`)
- Color coding uses both color and motion for accessibility
- Position indicators provide non-visual queue understanding

## Future Enhancements
- Add sound effects for vote actions
- Implement drag-and-drop reordering with animations
- Add more sophisticated easing curves
- Implement staggered animations for multiple simultaneous changes
