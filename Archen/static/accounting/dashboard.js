(function () {
  const digitMap = {
    '۰': '0', '۱': '1', '۲': '2', '۳': '3', '۴': '4',
    '۵': '5', '۶': '6', '۷': '7', '۸': '8', '۹': '9',
    '٠': '0', '١': '1', '٢': '2', '٣': '3', '٤': '4',
    '٥': '5', '٦': '6', '٧': '7', '٨': '8', '٩': '9',
  };

  function normalizeNumericString(value) {
    if (!value) return '';
    let result = '';
    for (const ch of value) {
      if (digitMap.hasOwnProperty(ch)) {
        result += digitMap[ch];
        continue;
      }
      if ((ch >= '0' && ch <= '9') || ch === '-') {
        result += ch;
      }
    }
    return result;
  }

  function formatNumber(value, formatter) {
    const numeric = Number(value) || 0;
    return formatter.format(numeric);
  }

  function getCsrfToken() {
    const name = 'csrftoken=';
    const parts = document.cookie ? document.cookie.split(';') : [];
    for (const part of parts) {
      const trimmed = part.trim();
      if (trimmed.startsWith(name)) {
        return decodeURIComponent(trimmed.substring(name.length));
      }
    }
    return '';
  }

  document.addEventListener('DOMContentLoaded', function () {
    const root = document.getElementById('finance-dashboard-root');
    if (!root) return;

    const updateUrl = root.dataset.updateUrl;
    let currentPeriod = root.dataset.initialPeriod || 'daily';

    const payloadScript = document.getElementById('finance-initial-data');
    let initialPayload = {
      chart: { labels: [], receivable: [], payable: [], net: [] },
      totals: { receivable: 0, payable: 0, net: 0 },
      period: currentPeriod,
    };
    if (payloadScript) {
      try {
        const parsed = JSON.parse(payloadScript.textContent);
        if (parsed && typeof parsed === 'object') {
          initialPayload = parsed;
          if (parsed.period) {
            currentPeriod = parsed.period;
          }
        }
      } catch (err) {
        console.warn('Unable to parse finance initial payload:', err);
      }
    }

    const chartCanvas = document.getElementById('financeTrendChart');
    const feedbackEl = document.getElementById('finance-feedback');
    const numberFormat = new Intl.NumberFormat('fa-IR');
    let chartData = null;

    function showFeedback(message, isError) {
      if (!feedbackEl) return;
      feedbackEl.textContent = message || '';
      if (!message) {
        feedbackEl.classList.add('hidden');
        return;
      }
      feedbackEl.classList.remove('hidden');
      feedbackEl.classList.toggle('bg-rose-100', !!isError);
      feedbackEl.classList.toggle('text-rose-700', !!isError);
      feedbackEl.classList.toggle('border', true);
      feedbackEl.classList.toggle('border-rose-300', !!isError);
      feedbackEl.classList.toggle('bg-emerald-100', !isError);
      feedbackEl.classList.toggle('text-emerald-700', !isError);
      feedbackEl.classList.toggle('border-emerald-300', !isError);
      setTimeout(() => {
        feedbackEl.classList.add('hidden');
      }, 2200);
    }

    function renderFinanceChart(data) {
      if (!chartCanvas) return;
      chartData = {
        labels: (data.labels_display || data.labels || []).slice(),
        receivable: (data.receivable || []).map(v => Number(v) || 0),
        payable: (data.payable || []).map(v => -Math.abs(Number(v) || 0)),
        net: (data.net || []).map(v => Number(v) || 0),
      };

      const ctx = chartCanvas.getContext('2d');
      const ratio = window.devicePixelRatio || 1;
      const cssWidth = chartCanvas.clientWidth || chartCanvas.width;
      const cssHeight = chartCanvas.clientHeight || chartCanvas.height;
      if (chartCanvas.width !== cssWidth * ratio) {
        chartCanvas.width = cssWidth * ratio;
        chartCanvas.height = cssHeight * ratio;
        ctx.scale(ratio, ratio);
      }

      const padding = { top: 36, right: 24, bottom: 64, left: 80 };
      const plotWidth = Math.max(10, cssWidth - padding.left - padding.right);
      const plotHeight = Math.max(10, cssHeight - padding.top - padding.bottom);

      const allValues = [...chartData.receivable, ...chartData.payable, ...chartData.net];
      let min = Math.min(0, ...allValues);
      let max = Math.max(0, ...allValues);
      if (max === min) {
        max = min + 1;
      }
      const steps = 5;
      const stepValue = (max - min) / steps;
      const yFor = (value) => padding.top + (max - value) * (plotHeight / (max - min));
      const xStep = chartData.labels.length > 1 ? plotWidth / (chartData.labels.length - 1) : plotWidth;

      ctx.clearRect(0, 0, cssWidth, cssHeight);
      ctx.fillStyle = '#2f3439';
      ctx.fillRect(0, 0, cssWidth, cssHeight);

      if (!chartData.labels.length) {
        ctx.fillStyle = '#9ca3af';
        ctx.font = '14px Vazirmatn, sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText('داده‌ای برای نمایش وجود ندارد.', padding.left + plotWidth / 2, padding.top + plotHeight / 2);
        return;
      }

      ctx.strokeStyle = 'rgba(255, 255, 255, 0.18)';
      ctx.lineWidth = 1;
      ctx.font = '12px Vazirmatn, sans-serif';
      ctx.fillStyle = '#e5e7eb';
      ctx.textAlign = 'right';
      ctx.textBaseline = 'middle';
      for (let i = 0; i <= steps; i++) {
        const value = min + stepValue * i;
        const y = yFor(value);
        ctx.beginPath();
        ctx.moveTo(padding.left, y);
        ctx.lineTo(padding.left + plotWidth, y);
        ctx.stroke();
        ctx.fillText(formatNumber(Math.round(value), numberFormat), padding.left - 12, y);
      }

      ctx.textAlign = 'center';
      ctx.textBaseline = 'top';
      const highlightIndex = (data.highlight_index != null) ? Number(data.highlight_index) : (chartData.labels.length - 1);
      chartData.labels.forEach((label, idx) => {
        const x = padding.left + idx * xStep;
        const truncated = label && label.length > 9 ? `${label.slice(0, 9)}…` : label;
        ctx.font = (idx === highlightIndex ? 'bold 12px Vazirmatn, sans-serif' : '12px Vazirmatn, sans-serif');
        ctx.fillText(truncated || '', x, padding.top + plotHeight + 14);
      });

      ctx.strokeStyle = '#9aa4b2';
      ctx.beginPath();
      ctx.moveTo(padding.left, padding.top);
      ctx.lineTo(padding.left, padding.top + plotHeight);
      ctx.lineTo(padding.left + plotWidth, padding.top + plotHeight);
      ctx.stroke();

      if (min < 0 && max > 0) {
        const y0 = yFor(0);
        ctx.strokeStyle = '#94a3b8';
        ctx.setLineDash([4, 4]);
        ctx.beginPath();
        ctx.moveTo(padding.left, y0);
        ctx.lineTo(padding.left + plotWidth, y0);
        ctx.stroke();
        ctx.setLineDash([]);
      }

      function drawBars(values, color) {
        const barGroup = Math.max(6, xStep * 0.7);
        const barW = barGroup / 2 - 3;
        const offset = barW + 3;
        values.forEach((value, idx) => {
          const cx = padding.left + idx * xStep;
          const x = cx - offset;
          const y0 = yFor(0);
          const y = yFor(value);
          const h = y0 - y;
          ctx.fillStyle = color;
          ctx.fillRect(x, h >= 0 ? y : y0, barW, Math.abs(h));
          // small border
          ctx.strokeStyle = 'rgba(0,0,0,0.05)';
          ctx.strokeRect(x, h >= 0 ? y : y0, barW, Math.abs(h));
        });
      }

      // Bars: receivable positive, payable negative
      drawBars(chartData.receivable, 'rgba(16,185,129,0.85)');
      drawBars(chartData.payable, 'rgba(239,68,68,0.85)');
      // Legend omitted to match production style (handled by header labels)
    }

    function updateSummary(totals) {
      const receivableEl = document.getElementById('finance-total-receivable');
      const payableEl = document.getElementById('finance-total-payable');
      const netEl = document.getElementById('finance-total-net');
      if (receivableEl) receivableEl.textContent = formatNumber(totals.receivable, numberFormat);
      if (payableEl) payableEl.textContent = formatNumber(totals.payable, numberFormat);
      if (netEl) {
        netEl.textContent = formatNumber(totals.net, numberFormat);
        const parent = netEl.parentElement;
        if (parent) {
          parent.classList.toggle('text-emerald-700', Number(totals.net) >= 0);
          parent.classList.toggle('text-rose-700', Number(totals.net) < 0);
        }
      }
    }

    function gatherRowData(row) {
      const entityCell = row.querySelector('[data-field="entity_name"]');
      const amountCell = row.querySelector('[data-field="amount"]');
      const descriptionCell = row.querySelector('[data-field="description"]');
      const typeBtn = row.querySelector('.record-type-toggle');
      return {
        entity_name: entityCell ? entityCell.textContent.trim() : '',
        amount: amountCell ? amountCell.textContent.trim() : '',
        description: descriptionCell ? descriptionCell.textContent.trim() : '',
        record_type: typeBtn ? typeBtn.dataset.value : 'receivable',
      };
    }

    function storeRowState(row, record) {
      if (!row || !record) return;
      row.dataset.entityName = record.entity_name || '';
      row.dataset.amount = String(record.amount || 0);
      row.dataset.description = record.description || '';
      row.dataset.recordType = record.record_type || 'receivable';
      row.dataset.recordTypeLabel = record.record_type_label || (record.record_type === 'payable' ? 'بدهکاری' : 'بستانکاری');
    }

    function applyRowData(row, record) {
      const entityCell = row.querySelector('[data-field="entity_name"]');
      const amountCell = row.querySelector('[data-field="amount"]');
      const descriptionCell = row.querySelector('[data-field="description"]');
      const typeBtn = row.querySelector('.record-type-toggle');
      if (entityCell) entityCell.textContent = record.entity_name;
      if (amountCell) amountCell.textContent = formatNumber(record.amount, numberFormat);
      if (descriptionCell) descriptionCell.textContent = record.description || '';
      if (typeBtn) {
        typeBtn.dataset.value = record.record_type;
        typeBtn.textContent = record.record_type_label;
        // Normalize classes to enforce consistent colors per type
        typeBtn.classList.remove('border-red-700','text-red-700','hover:bg-red-200','border-green-700','text-green-700','hover:bg-green-200','border-gray-300','text-gray-700','hover:bg-gray-100');
        if (record.record_type === 'payable') {
          typeBtn.classList.add('border','border-red-700','text-red-700','hover:bg-red-200');
        } else if (record.record_type === 'receivable') {
          typeBtn.classList.add('border','border-green-700','text-green-700','hover:bg-green-200','font-bold');
        } else {
          typeBtn.classList.add('border','border-gray-300','text-gray-700','hover:bg-gray-100');
        }
      }
      storeRowState(row, record);
    }

    function submitRowUpdate(row) {
      if (!row || row.dataset.saving === 'true') {
        return;
      }
      const rowData = gatherRowData(row);
      const amountClean = normalizeNumericString(rowData.amount);
      const payload = {
        id: row.dataset.recordId,
        entity_name: rowData.entity_name,
        amount: amountClean,
        description: rowData.description,
        record_type: rowData.record_type,
        period: currentPeriod,
      };

      const previous = {
        entity_name: row.dataset.entityName || '',
        amount: Number(row.dataset.amount || 0),
        description: row.dataset.description || '',
        record_type: row.dataset.recordType || 'receivable',
        record_type_label: row.dataset.recordTypeLabel || 'بستانکاری',
      };

      if (!payload.entity_name) {
        applyRowData(row, previous);
        showFeedback('نام نمی‌تواند خالی باشد.', true);
        return;
      }

      if (!payload.amount && payload.amount !== '0') {
        applyRowData(row, previous);
        showFeedback('مبلغ را وارد کنید.', true);
        return;
      }

      row.dataset.saving = 'true';
      row.classList.add('opacity-60');

      fetch(updateUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCsrfToken(),
        },
        body: JSON.stringify(payload),
      })
        .then(response => response.json().then(data => ({ status: response.status, body: data })))
        .then(({ status, body }) => {
          if (status >= 400 || !body.ok) {
            throw new Error(body.error || 'خطا در ذخیره تغییرات.');
          }
          applyRowData(row, body.record);
          updateSummary(body.totals);
          // Re-render the chart and keep using the current period unless server changed it
          if (body.chart) {
            renderFinanceChart(body.chart);
          }
          if (body.chart && body.chart.period) {
            currentPeriod = body.chart.period;
            window.currentFinancePeriod = currentPeriod;
          }
          showFeedback('تغییرات ذخیره شد.', false);
        })
        .catch(err => {
          applyRowData(row, previous);
          showFeedback(err.message || 'خطا در ذخیره تغییرات.', true);
        })
        .finally(() => {
          row.dataset.saving = 'false';
          row.classList.remove('opacity-60');
        });
    }

    function setupInlineEditing() {
      const table = document.querySelector('[data-finance-table]');
      if (!table) return;

      table.querySelectorAll('[data-editable="true"]').forEach(cell => {
        cell.setAttribute('contenteditable', 'true');
        cell.setAttribute('spellcheck', 'false');
        cell.addEventListener('focus', () => {
          cell.dataset.original = cell.textContent.trim();
        });
        cell.addEventListener('keydown', event => {
          if (event.key === 'Enter') {
            event.preventDefault();
            cell.blur();
          }
          if (event.key === 'Escape') {
            event.preventDefault();
            cell.textContent = cell.dataset.original || '';
            cell.blur();
          }
        });
        cell.addEventListener('blur', () => {
          const original = cell.dataset.original || '';
          const currentValue = cell.textContent.trim();
          if (original !== currentValue) {
            submitRowUpdate(cell.closest('tr[data-record-id]'));
          }
        });
      });

      table.querySelectorAll('.record-type-toggle').forEach(button => {
        button.addEventListener('click', () => {
          const current = button.dataset.value === 'receivable' ? 'payable' : 'receivable';
          button.dataset.value = current;
          button.textContent = current === 'receivable' ? 'بستانکاری' : 'بدهکاری';
          // Update classes immediately for visual feedback
          button.classList.remove('border-red-700','text-red-700','hover:bg-red-200','border-green-700','text-green-700','hover:bg-green-200','border-gray-300','text-gray-700','hover:bg-gray-100');
          if (current === 'payable') {
            button.classList.add('border','border-red-700','text-red-700','hover:bg-red-200');
          } else {
            button.classList.add('border','border-green-700','text-green-700','hover:bg-green-200','font-bold');
          }
          submitRowUpdate(button.closest('tr[data-record-id]'));
        });
      });

      table.querySelectorAll('tr[data-record-id]').forEach(row => {
        const rowData = gatherRowData(row);
        const amountClean = normalizeNumericString(rowData.amount);
        const typeBtn = row.querySelector('.record-type-toggle');
        const baseRecord = {
          entity_name: rowData.entity_name,
          amount: amountClean ? Number(amountClean) : 0,
          description: rowData.description,
          record_type: rowData.record_type,
          record_type_label: typeBtn ? typeBtn.textContent : 'بستانکاری',
        };
        storeRowState(row, baseRecord);
        const amountCell = row.querySelector('[data-field="amount"]');
        if (amountCell) {
          amountCell.textContent = formatNumber(baseRecord.amount, numberFormat);
        }
      });
    }

    // Prefer pretty labels from server if available
    renderFinanceChart(initialPayload.chart || {});
    updateSummary(initialPayload.totals || { receivable: 0, payable: 0, net: 0 });
    setupInlineEditing();
    window.currentFinancePeriod = currentPeriod;
  });
})();
