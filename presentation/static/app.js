// ============================================================
// Carousel Controller — pure CSS scroll-snap + vanilla JS
// ============================================================

/**
 * Scroll a carousel track left (-1) or right (+1) by the width
 * of one visible "page" (3 cards on desktop).
 */
function carouselScroll(groupId, direction) {
  const track = document.getElementById('track-' + groupId);
  if (!track) return;
  const cardWidth = track.querySelector('.formula-card')?.offsetWidth || 320;
  const gap = 20; // matches CSS gap
  const scrollAmount = (cardWidth + gap) * 3 * direction;
  track.scrollBy({ left: scrollAmount, behavior: 'smooth' });
}

/**
 * Update the "X" / N counter label for a carousel.
 */
function updateCarouselCounter(groupId) {
  const track = document.getElementById('track-' + groupId);
  const counter = document.getElementById('counter-' + groupId);
  if (!track || !counter) return;

  const cards = track.querySelectorAll('.formula-card');
  if (!cards.length) { counter.textContent = '0'; return; }

  const trackRect = track.getBoundingClientRect();
  let firstVisible = 1;
  for (let i = 0; i < cards.length; i++) {
    const r = cards[i].getBoundingClientRect();
    if (r.left >= trackRect.left - 10) { firstVisible = i + 1; break; }
  }
  counter.textContent = firstVisible;
}

// ============================================================
// DOMContentLoaded — MathJax + carousel counters + demo guard
// ============================================================
document.addEventListener('DOMContentLoaded', function () {

  // --- Initialize carousel counters ---
  document.querySelectorAll('.carousel-track').forEach(function (track) {
    const groupId = track.id.replace('track-', '');
    updateCarouselCounter(groupId);
    track.addEventListener('scroll', function () {
      updateCarouselCounter(groupId);
    });
  });

  // --- Re-render MathJax after page load ---
  if (window.MathJax) {
    MathJax.typesetPromise();
  }

  // ============================================================
  // DEMO MODE (dormant — only runs if __DEMO_MODE__ is true)
  // To reactivate: set DEMO_MODE=true in .env and restart server.
  // ============================================================
  if (window.__DEMO_MODE__) {
    runDemoSimulation();
  }
});

// ============================================================
// Demo simulation (kept for future reactivation)
// ============================================================
function runDemoSimulation() {
  console.log('Demo mode: auto-simulation is currently disabled in gallery view.');
  // The demo previously auto-filled PICS form fields and submitted.
  // In gallery mode there are no forms, so this is a no-op.
  // To restore demo behavior, re-add calculator forms and enable
  // DEMO_MODE=true in .env.
}