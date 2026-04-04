// Modal functionality
function showModal(formulaId, name, category, resultVar) {
  const modal = document.getElementById('formula-modal');
  const modalContent = document.getElementById('modal-content');

  // Load modal content via HTMX
  htmx.ajax('GET', `/api/formula-modal/${formulaId}`, {
    target: '#modal-content',
    swap: 'innerHTML'
  });

  modal.style.display = 'block';
}

function closeModal() {
  const modal = document.getElementById('formula-modal');
  modal.style.display = 'none';
}

// Close modal when clicking outside
window.onclick = function(event) {
  const modal = document.getElementById('formula-modal');
  if (event.target === modal) {
    modal.style.display = 'none';
  }
}

// Close modal with ESC key
document.addEventListener('keydown', function(event) {
  if (event.key === 'Escape') {
    closeModal();
  }
});

// Form validation
function validateNumberInput(input) {
  const value = parseFloat(input.value);
  const min = input.min ? parseFloat(input.min) : null;
  const max = input.max ? parseFloat(input.max) : null;

  if (isNaN(value)) return true; // Allow empty

  if (min !== null && value < min) {
    input.setCustomValidity(`El valor debe ser mayor o igual a ${min}`);
    return false;
  }

  if (max !== null && value > max) {
    input.setCustomValidity(`El valor debe ser menor o igual a ${max}`);
    return false;
  }

  input.setCustomValidity('');
  return true;
}

// Add validation to number inputs
document.addEventListener('DOMContentLoaded', function() {
  const numberInputs = document.querySelectorAll('input[type="number"]');

  numberInputs.forEach(input => {
    input.addEventListener('input', function() {
      validateNumberInput(this);
    });

    input.addEventListener('blur', function() {
      validateNumberInput(this);
    });
  });
});

// Auto-refresh MathJax when content changes
document.addEventListener('DOMContentLoaded', function() {
  // Re-render MathJax after HTMX swaps
  document.body.addEventListener('htmx:afterSwap', function(evt) {
    if (window.MathJax) {
      MathJax.typesetPromise();
    }
  });
});

// Loading indicators
document.addEventListener('DOMContentLoaded', function() {
  // Show loading state for forms
  document.body.addEventListener('htmx:beforeRequest', function(evt) {
    const target = evt.target;
    if (target.tagName === 'FORM') {
      const submitBtn = target.querySelector('button[type="submit"]');
      if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.textContent = 'Procesando...';
      }
    }
  });

  document.body.addEventListener('htmx:afterRequest', function(evt) {
    const target = evt.target;
    if (target.tagName === 'FORM') {
      const submitBtn = target.querySelector('button[type="submit"]');
      if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.textContent = submitBtn.getAttribute('data-original-text') || 'Enviar';
      }
    }
  });
});

// Store original button text
document.addEventListener('DOMContentLoaded', function() {
  const buttons = document.querySelectorAll('button[type="submit"]');
  buttons.forEach(btn => {
    btn.setAttribute('data-original-text', btn.textContent);
  });
});