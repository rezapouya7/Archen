/* Minimal Chart.js‑like API to render simple bar and doughnut charts.
 * Provides: new Chart(ctx2d, { type, data: { labels, datasets:[{ data, backgroundColor, label }] }, options })
 * Supports: type = 'bar' | 'doughnut'; destroy() method.
 */
(function() {
  if (window.Chart) return; // If real Chart.js exists, don't override

  function resolveCanvas(ctxOrCanvas) {
    if (!ctxOrCanvas) return null;
    if (typeof HTMLCanvasElement !== 'undefined' && ctxOrCanvas instanceof HTMLCanvasElement) return ctxOrCanvas;
    if (ctxOrCanvas.canvas) return ctxOrCanvas.canvas;
    return null;
  }

  function getCtx2d(canvas) {
    return canvas.getContext('2d');
  }

  function clearCanvas(canvas) {
    const ctx = getCtx2d(canvas);
    ctx.clearRect(0, 0, canvas.width, canvas.height);
  }

  function ensureHiDPI(canvas) {
    const ratio = window.devicePixelRatio || 1;
    const cssWidth = canvas.clientWidth || canvas.width;
    const cssHeight = canvas.clientHeight || canvas.height;
    if (canvas.width !== cssWidth * ratio || canvas.height !== cssHeight * ratio) {
      canvas.width = cssWidth * ratio;
      canvas.height = cssHeight * ratio;
      const ctx = getCtx2d(canvas);
      ctx.scale(ratio, ratio);
    }
  }

  function toArray(v, len, fallback) {
    if (Array.isArray(v)) return v;
    const out = [];
    for (let i = 0; i < len; i++) out.push(v || fallback);
    return out;
  }

  const palette = [
    '#3b82f6', '#10b981', '#eab308', '#ef4444', '#22c55e', '#a855f7', '#f59e0b', '#14b8a6', '#8b5cf6', '#f43f5e'
  ];

  function drawBar(canvas, config) {
    const { labels = [], datasets = [] } = config.data || {};
    const data = (datasets[0] && datasets[0].data) || [];
    const colors = toArray((datasets[0] && datasets[0].backgroundColor) || palette, data.length, '#3b82f6');
    const ctx = getCtx2d(canvas);
    const W = canvas.clientWidth || canvas.width;
    const H = canvas.clientHeight || canvas.height;
    const padding = 28; // space for labels
    const max = Math.max(1, Math.max.apply(null, data.map(x => +x || 0)));
    const n = data.length;
    const gap = 8;
    const barW = Math.max(6, (W - padding * 2 - gap * (n - 1)) / Math.max(1, n));

    // axes
    ctx.strokeStyle = '#e5e7eb';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(padding, 10);
    ctx.lineTo(padding, H - padding);
    ctx.lineTo(W - 8, H - padding);
    ctx.stroke();

    // bars
    let x = padding;
    for (let i = 0; i < n; i++) {
      const v = +data[i] || 0;
      const h = (v / max) * (H - padding * 2);
      ctx.fillStyle = colors[i % colors.length];
      ctx.fillRect(x, H - padding - h, barW, h);
      x += barW + gap;
    }

    // x labels (trim if long)
    ctx.fillStyle = '#6b7280';
    ctx.font = '12px sans-serif';
    ctx.textAlign = 'center';
    x = padding;
    for (let i = 0; i < n; i++) {
      const lbl = (labels[i] || '').toString();
      const short = lbl.length > 12 ? lbl.slice(0, 11) + '…' : lbl;
      const cx = x + barW / 2;
      ctx.fillText(short, cx, H - padding + 16);
      x += barW + gap;
    }
  }

  function drawDoughnut(canvas, config) {
    const { labels = [], datasets = [] } = config.data || {};
    const data = (datasets[0] && datasets[0].data) || [];
    const colors = toArray((datasets[0] && datasets[0].backgroundColor) || palette, data.length, '#3b82f6');
    const ctx = getCtx2d(canvas);
    const W = canvas.clientWidth || canvas.width;
    const H = canvas.clientHeight || canvas.height;
    const cx = W / 2;
    const cy = H / 2;
    const r = Math.min(W, H) * 0.36;
    const inner = r * 0.62;
    const sum = data.reduce((a, b) => a + (+b || 0), 0) || 1;
    let start = -Math.PI / 2;

    // slices
    for (let i = 0; i < data.length; i++) {
      const val = +data[i] || 0;
      const ang = (val / sum) * Math.PI * 2;
      ctx.beginPath();
      ctx.moveTo(cx, cy);
      ctx.arc(cx, cy, r, start, start + ang);
      ctx.closePath();
      ctx.fillStyle = colors[i % colors.length];
      ctx.fill();
      start += ang;
    }
    // cut inner circle
    ctx.globalCompositeOperation = 'destination-out';
    ctx.beginPath();
    ctx.arc(cx, cy, inner, 0, Math.PI * 2);
    ctx.fill();
    ctx.globalCompositeOperation = 'source-over';

    // Do not draw legend on canvas; external DOM legend is used.
  }

  function Chart(ctxOrCanvas, config) {
    this.canvas = resolveCanvas(ctxOrCanvas);
    if (!this.canvas) throw new Error('Invalid canvas/context for Chart');
    ensureHiDPI(this.canvas);
    this.config = config || {};
    this.draw();
  }
  Chart.prototype.draw = function() {
    clearCanvas(this.canvas);
    const type = (this.config.type || 'bar').toLowerCase();
    if (type === 'doughnut' || type === 'pie') {
      drawDoughnut(this.canvas, this.config);
    } else {
      drawBar(this.canvas, this.config);
    }
  };
  Chart.prototype.destroy = function() {
    clearCanvas(this.canvas);
  };

  window.Chart = Chart;
})();
