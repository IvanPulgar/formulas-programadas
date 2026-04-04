// ============================================================
// solver.js — Manual formula resolver frontend
//
// Responsibilities:
//   1. Open / close the solver modal
//   2. Build the input form dynamically from formula metadata
//   3. Validate inputs on the client side
//   4. POST to /api/solve/{formula_id} and display results
//   5. Store successful results in sessionStorage
//   6. Show / hide download button; generate CSV
// ============================================================

(function () {
  'use strict';

  // ── Formula metadata (injected by the template) ──────────────
  var FORMULAS = {};
  try {
    var el = document.getElementById('solver-data');
    if (el) FORMULAS = JSON.parse(el.textContent);
  } catch (_) { /* no-op */ }

  var HISTORY_KEY = '__solver_history__';

  // ────────────────────────────────────────────────────────────
  // MODAL
  // ────────────────────────────────────────────────────────────

  window.openSolverModal = function (formulaId) {
    var f = FORMULAS[formulaId];
    if (!f) return;

    var body = document.getElementById('solver-modal-body');
    body.innerHTML = buildFormHTML(formulaId, f);

    document.getElementById('solver-modal').style.display = 'block';

    // Re-render MathJax inside the modal
    if (window.MathJax) MathJax.typesetPromise();
  };

  window.closeSolverModal = function () {
    document.getElementById('solver-modal').style.display = 'none';
  };

  // Close on backdrop click or ESC
  window.addEventListener('click', function (e) {
    if (e.target === document.getElementById('solver-modal')) {
      closeSolverModal();
    }
  });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') closeSolverModal();
  });

  // ────────────────────────────────────────────────────────────
  // BUILD FORM HTML
  // ────────────────────────────────────────────────────────────

  function buildFormHTML(formulaId, f) {
    var html = '';

    // Header
    html += '<div class="solver-modal-header">';
    html += '<span class="card-category-badge">' + esc(f.category) + '</span>';
    html += '<h3>' + esc(f.name) + '</h3>';
    html += '<div class="card-formula-render">$$' + f.latex + '$$</div>';
    html += '<p class="solver-result-hint">Variable resultado: <strong>' + esc(f.resultSymbol) + '</strong> — ' + esc(f.resultName) + '</p>';
    html += '</div>';

    // Preconditions
    if (f.preconditions && f.preconditions.length) {
      html += '<div class="solver-preconditions"><strong>Precondiciones:</strong> ';
      html += f.preconditions.map(esc).join(' · ');
      html += '</div>';
    }

    // Form
    html += '<form id="solver-form" class="solver-form" onsubmit="submitSolverForm(event, \'' + formulaId + '\')">';

    for (var i = 0; i < f.inputs.length; i++) {
      var inp = f.inputs[i];
      var isInt = inp.fieldType === 'integer';
      html += '<div class="form-group">';
      html += '<label for="sf-' + inp.varId + '">' + esc(inp.symbol) + ' — ' + esc(inp.label);
      if (isInt) html += ' <small>(entero)</small>';
      html += '</label>';
      html += '<input id="sf-' + inp.varId + '" name="' + inp.varId + '"';
      html += ' type="number" step="' + inp.step + '"';
      if (inp.min !== null && inp.min !== undefined) html += ' min="' + inp.min + '"';
      if (inp.max !== null && inp.max !== undefined) html += ' max="' + inp.max + '"';
      html += ' required placeholder="Ingrese ' + esc(inp.symbol) + '"';
      html += ' autocomplete="off" />';
      html += '<span class="field-error" id="err-' + inp.varId + '"></span>';
      html += '</div>';
    }

    html += '<div class="form-actions">';
    html += '<button type="submit" class="btn btn-primary" id="solver-submit-btn">Calcular</button>';
    html += '<button type="button" class="btn btn-secondary" onclick="closeSolverModal()">Cancelar</button>';
    html += '</div>';
    html += '</form>';

    // Result placeholder
    html += '<div id="solver-result" class="solver-result"></div>';

    return html;
  }

  // ────────────────────────────────────────────────────────────
  // FRONTEND VALIDATION
  // ────────────────────────────────────────────────────────────

  function validateForm(formulaId) {
    var f = FORMULAS[formulaId];
    if (!f) return null;

    var errors = [];
    var values = {};

    for (var i = 0; i < f.inputs.length; i++) {
      var inp = f.inputs[i];
      var el = document.getElementById('sf-' + inp.varId);
      var errEl = document.getElementById('err-' + inp.varId);
      if (errEl) errEl.textContent = '';

      if (!el || el.value.trim() === '') {
        setFieldError(inp.varId, inp.symbol + ' es obligatorio.');
        errors.push(inp.symbol + ' es obligatorio.');
        continue;
      }

      var val = Number(el.value);
      if (isNaN(val)) {
        setFieldError(inp.varId, inp.symbol + ' debe ser numérico.');
        errors.push(inp.symbol + ' debe ser numérico.');
        continue;
      }

      // Integer check
      if (inp.fieldType === 'integer') {
        if (!Number.isInteger(val) || val < 0) {
          setFieldError(inp.varId, inp.symbol + ' debe ser un entero no negativo.');
          errors.push(inp.symbol + ' debe ser un entero no negativo.');
          continue;
        }
      }

      // Min/Max
      if (inp.min !== null && inp.min !== undefined && val < inp.min) {
        setFieldError(inp.varId, inp.symbol + ' debe ser ≥ ' + inp.min + '.');
        errors.push(inp.symbol + ' debe ser ≥ ' + inp.min + '.');
        continue;
      }
      if (inp.max !== null && inp.max !== undefined && val > inp.max) {
        setFieldError(inp.varId, inp.symbol + ' debe ser ≤ ' + inp.max + '.');
        errors.push(inp.symbol + ' debe ser ≤ ' + inp.max + '.');
        continue;
      }

      // Strict positive (λ, μ)
      if ((inp.varId === 'lambda_' || inp.varId === 'mu') && val <= 0) {
        setFieldError(inp.varId, inp.symbol + ' debe ser estrictamente positivo (> 0).');
        errors.push(inp.symbol + ' debe ser > 0.');
        continue;
      }

      // k must be ≥ 1
      if (inp.varId === 'k' && val < 1) {
        setFieldError(inp.varId, 'k debe ser ≥ 1.');
        errors.push('k debe ser ≥ 1.');
        continue;
      }

      // M must be ≥ 1
      if (inp.varId === 'M' && val < 1) {
        setFieldError(inp.varId, 'M debe ser ≥ 1.');
        errors.push('M debe ser ≥ 1.');
        continue;
      }

      values[inp.varId] = val;
    }

    // Category-level preconditions
    if (!errors.length) {
      var cat = f.categoryKey;
      if (cat === 'PICS' && values.lambda_ !== undefined && values.mu !== undefined) {
        if (values.lambda_ >= values.mu) {
          errors.push('PICS requiere λ < μ para estabilidad.');
        }
      }
      if (cat === 'PICM' && values.lambda_ !== undefined && values.mu !== undefined && values.k !== undefined) {
        if (values.lambda_ >= values.k * values.mu) {
          errors.push('PICM requiere λ < k·μ para estabilidad.');
        }
      }
    }

    return errors.length ? { errors: errors } : { values: values };
  }

  function setFieldError(varId, msg) {
    var el = document.getElementById('err-' + varId);
    if (el) el.textContent = msg;
  }

  // ────────────────────────────────────────────────────────────
  // SUBMIT FORM
  // ────────────────────────────────────────────────────────────

  window.submitSolverForm = function (event, formulaId) {
    event.preventDefault();

    var validation = validateForm(formulaId);
    if (!validation) return;

    if (validation.errors) {
      showResultInModal('error', validation.errors.join('<br>'));
      return;
    }

    var btn = document.getElementById('solver-submit-btn');
    if (btn) { btn.disabled = true; btn.textContent = 'Calculando...'; }

    fetch('/api/solve/' + encodeURIComponent(formulaId), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ inputs: validation.values }),
    })
      .then(function (res) { return res.json().then(function (data) { return { ok: res.ok, data: data }; }); })
      .then(function (resp) {
        if (btn) { btn.disabled = false; btn.textContent = 'Calcular'; }

        if (resp.data.status === 'success') {
          showSuccessResult(formulaId, resp.data, validation.values);
          saveToHistory(formulaId, resp.data, validation.values);
        } else {
          showResultInModal('error', resp.data.message || 'Error desconocido.');
        }
      })
      .catch(function (err) {
        if (btn) { btn.disabled = false; btn.textContent = 'Calcular'; }
        showResultInModal('error', 'Error de conexión: ' + err.message);
      });
  };

  // ────────────────────────────────────────────────────────────
  // SHOW RESULTS
  // ────────────────────────────────────────────────────────────

  function showSuccessResult(formulaId, data, inputValues) {
    var f = FORMULAS[formulaId];
    var html = '';
    html += '<div class="result-panel">';
    html += '<div class="result-header success"><h4>Cálculo exitoso</h4></div>';
    html += '<div class="result-section">';
    html += '<p><strong>Fórmula:</strong> ' + esc(data.formulaName) + '</p>';
    html += '<p><strong>Categoría:</strong> ' + esc(data.category) + '</p>';
    if (f) html += '<div class="card-formula-render">$$' + f.latex + '$$</div>';
    html += '</div>';

    // Inputs used
    html += '<div class="result-section">';
    html += '<h4>Variables de entrada</h4>';
    html += '<div class="variables-grid">';
    var keys = Object.keys(data.inputsUsed || inputValues);
    for (var i = 0; i < keys.length; i++) {
      var k = keys[i];
      var sym = getSymbol(k);
      html += '<div class="variable-item"><span class="variable-symbol">' + esc(sym) + '</span>';
      html += '<span class="variable-value">' + (data.inputsUsed ? data.inputsUsed[k] : inputValues[k]) + '</span></div>';
    }
    html += '</div></div>';

    // Result
    html += '<div class="result-section">';
    html += '<h4>Resultado</h4>';
    html += '<div class="result-value">';
    html += '<span class="result-number">' + data.resultValue + '</span> ';
    html += '<span class="result-unit">' + esc(data.resultUnit || '') + '</span>';
    html += '</div>';
    html += '<p><strong>Variable calculada:</strong> ' + esc(data.resultSymbol) + ' — ' + esc(data.resultName) + '</p>';
    html += '</div></div>';

    showResultInModal('success', html, true);
  }

  function showResultInModal(type, content, isRawHTML) {
    var div = document.getElementById('solver-result');
    if (!div) return;

    if (type === 'error') {
      div.innerHTML = '<div class="result-panel"><div class="result-header error"><h4>Error</h4></div>'
        + '<div class="result-section"><p>' + content + '</p></div></div>';
    } else if (isRawHTML) {
      div.innerHTML = content;
    } else {
      div.innerHTML = content;
    }

    if (window.MathJax) MathJax.typesetPromise();
  }

  function getSymbol(varId) {
    var map = {
      'lambda_': 'λ', 'mu': 'μ', 'k': 'k', 'n': 'n', 'M': 'M',
      'rho': 'ρ', 'Wq': 'Wq', 'W': 'W', 'CTE': 'CTE', 'CTS': 'CTS',
      'CTSE': 'CTSE', 'CS': 'CS', 'CT_TE': 'CT_TE', 'CT_TS': 'CT_TS',
      'CT_TSE': 'CT_TSE', 'CT_S': 'CT_S',
    };
    return map[varId] || varId;
  }

  // ────────────────────────────────────────────────────────────
  // SESSION STORAGE — history of successful calculations
  // ────────────────────────────────────────────────────────────

  function getHistory() {
    try {
      var raw = sessionStorage.getItem(HISTORY_KEY);
      return raw ? JSON.parse(raw) : [];
    } catch (_) { return []; }
  }

  function saveToHistory(formulaId, data, inputValues) {
    var f = FORMULAS[formulaId] || {};
    var record = {
      timestamp: new Date().toLocaleString(),
      category: data.category || f.category || '',
      formulaName: data.formulaName || f.name || formulaId,
      formulaLatex: f.latex || '',
      inputVariables: Object.keys(inputValues).join(', '),
      inputValues: JSON.stringify(inputValues),
      resultVariable: data.resultSymbol || '',
      resultValue: data.resultValue,
    };

    var history = getHistory();
    history.push(record);
    try { sessionStorage.setItem(HISTORY_KEY, JSON.stringify(history)); } catch (_) { /* quota */ }

    showDownloadButton();
  }

  function showDownloadButton() {
    var bar = document.getElementById('download-bar');
    if (bar && getHistory().length > 0) {
      bar.style.display = 'flex';
    }
  }

  // ────────────────────────────────────────────────────────────
  // CSV DOWNLOAD
  // ────────────────────────────────────────────────────────────

  window.downloadCSV = function () {
    var history = getHistory();
    if (!history.length) return;

    var headers = [
      'timestamp', 'category', 'formula_name', 'formula_latex',
      'input_variables', 'input_values', 'result_variable', 'result_value',
    ];

    var rows = [headers.join(',')];
    for (var i = 0; i < history.length; i++) {
      var r = history[i];
      rows.push([
        csvCell(r.timestamp),
        csvCell(r.category),
        csvCell(r.formulaName),
        csvCell(r.formulaLatex),
        csvCell(r.inputVariables),
        csvCell(r.inputValues),
        csvCell(r.resultVariable),
        r.resultValue,
      ].join(','));
    }

    var csv = rows.join('\n');
    var blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8;' });
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = url;
    a.download = 'resultados_' + new Date().toISOString().slice(0, 19).replace(/[T:]/g, '-') + '.csv';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  function csvCell(val) {
    if (val === null || val === undefined) return '""';
    var s = String(val).replace(/"/g, '""');
    return '"' + s + '"';
  }

  // ────────────────────────────────────────────────────────────
  // INIT
  // ────────────────────────────────────────────────────────────

  document.addEventListener('DOMContentLoaded', function () {
    showDownloadButton();
  });

  // ── Utility ───────────────────────────────────────────────
  function esc(s) {
    if (!s) return '';
    var d = document.createElement('div');
    d.appendChild(document.createTextNode(s));
    return d.innerHTML;
  }

})();
