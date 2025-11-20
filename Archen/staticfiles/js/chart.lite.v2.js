/* Lightweight Chart renderer (bar/doughnut) with no in-canvas legend.
 * Always overrides window.Chart to avoid cached/remote versions.
 */
(function() {
  // Global registry for simple update/broadcast patterns across pages
  window.ArchenCharts = window.ArchenCharts || {
    _m: {},
    register: function(id, chart){ if (!id || !chart) return; this._m[id] = chart; },
    get: function(id){ return this._m[id]; },
    updateBar: function(id, labels, rec, pay, opts){
      var c = this._m[id]; if (!c) return;
      c.config.type = 'bar';
      c.config.data = { labels: labels||[], datasets:[
        { label:'بستانکاری', data:(rec||[]).map(Number), backgroundColor:'#22c55e' },
        { label:'بدهکاری', data:(pay||[]).map(function(v){return -Math.abs(Number(v||0));}), backgroundColor:'#ef4444' },
      ]};
      c.config.options = Object.assign({ responsive:true, darkTheme:true, legend:true, animationDuration:600 }, opts||{});
      c.draw();
    }
  };
  // Listen for custom update events
  try {
    document.addEventListener('archen:chart-update', function(ev){
      var d = ev && ev.detail || {}; if (!d || !d.id) return;
      if (d.type === 'finance-bar') {
        window.ArchenCharts.updateBar(d.id, d.labels, d.receivable, d.payable, { highlightIndex:d.highlight_index, period:d.period });
      }
    });
  } catch(_){}
  function resolveCanvas(ctxOrCanvas) {
    if (!ctxOrCanvas) return null;
    if (typeof HTMLCanvasElement !== 'undefined' && ctxOrCanvas instanceof HTMLCanvasElement) return ctxOrCanvas;
    if (ctxOrCanvas.canvas) return ctxOrCanvas.canvas;
    return null;
  }

  function getCtx2d(canvas) { return canvas.getContext('2d'); }

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

  const palette = ['#3b82f6','#10b981','#eab308','#ef4444','#22c55e','#a855f7','#f59e0b','#14b8a6','#8b5cf6','#f43f5e'];

  function normalizeLinePoints(data, fallbackLen) {
    const arr = Array.isArray(data) ? data : [];
    if (!arr.length && fallbackLen) {
      const placeholder = [];
      for (let i = 0; i < fallbackLen; i++) placeholder.push({ x: i, y: 0 });
      return placeholder;
    }
    return arr.map((item, idx) => {
      if (item && typeof item === 'object') {
        const rawX = (typeof item.x === 'number') ? item.x : (item.x !== undefined ? parseFloat(item.x) : idx);
        const x = Number.isFinite(rawX) ? rawX : idx;
        const rawY = (typeof item.y === 'number') ? item.y : parseFloat(item.y || 0);
        const y = Number.isFinite(rawY) ? rawY : 0;
        return { x, y };
      }
      const y = +item || 0;
      return { x: idx, y };
    });
  }

  function roundRect(ctx, x, y, w, h, r) {
    const rr = Math.max(0, Math.min(r || 0, Math.min(Math.abs(w), Math.abs(h)) / 2));
    const signH = h >= 0 ? 1 : -1;
    const signW = w >= 0 ? 1 : -1;
    ctx.beginPath();
    ctx.moveTo(x + rr * signW, y);
    ctx.lineTo(x + w - rr * signW, y);
    ctx.quadraticCurveTo(x + w, y, x + w, y + rr * signH);
    ctx.lineTo(x + w, y + h - rr * signH);
    ctx.quadraticCurveTo(x + w, y + h, x + w - rr * signW, y + h);
    ctx.lineTo(x + rr * signW, y + h);
    ctx.quadraticCurveTo(x, y + h, x, y + h - rr * signH);
    ctx.lineTo(x, y + rr * signH);
    ctx.quadraticCurveTo(x, y, x + rr * signW, y);
    ctx.closePath();
  }

  function drawBar(canvas, config) {
    const { labels = [], datasets = [] } = config.data || {};
    const opts = config.options || {};
    const ctx = getCtx2d(canvas);
    const W = canvas.clientWidth || canvas.width;
    const H = canvas.clientHeight || canvas.height;
    const legendH = opts.legend === false ? 0 : 22;
    // Determine if x labels should be tilted on mobile for all periods
    // Comments: This adds mobile-only diagonal labels to avoid overlap.
    const isMobile = W < 640; // Tailwind 'sm' breakpoint
    const period = (opts && typeof opts.period === 'string') ? opts.period.toLowerCase() : '';
    const angleOverride = (typeof opts.xLabelAngle === 'number') ? opts.xLabelAngle : null;
    // Apply tilt on mobile for daily, weekly, monthly, yearly (all periods)
    const needsTilt = !!(angleOverride !== null ? (isMobile && angleOverride !== 0) : isMobile);
    const tiltRad = angleOverride !== null ? (Math.max(-75, Math.min(75, angleOverride)) * Math.PI / 180) : (-40 * Math.PI / 180);
    // Legend position (top by default). Reserve space accordingly.
    const legendPos = ((opts && opts.legendPosition) ? String(opts.legendPosition) : 'top').toLowerCase();
    const legendTop = (legendH > 0) && (legendPos !== 'bottom');
    const paddingL = 40, paddingR = 16;
    // Minimal original paddings
    const basePaddingT = 20, basePaddingB = 28;
    // Compute a uniform extra bottom padding based on the longest label
    const fontSize = 12;
    const prevFont = ctx.font;
    ctx.font = fontSize + 'px sans-serif';
    let maxLabelW = 0;
    for (let i = 0; i < labels.length; i++) {
      const s = (labels[i] || '').toString();
      const w = ctx.measureText(s).width;
      if (w > maxLabelW) maxLabelW = w;
    }
    ctx.font = prevFont;
    const a = Math.abs(tiltRad);
    const bottomTextPad = needsTilt ? (Math.ceil(Math.sin(a) * maxLabelW + Math.cos(a) * fontSize) + 4) : 18;
    const paddingT = basePaddingT + (legendTop ? legendH : 0);
    const paddingB = basePaddingB + (!legendTop ? legendH : 0) + Math.max(0, bottomTextPad - 18);
    const n = labels.length;
    const dcount = Math.max(1, datasets.length);

    // Background theme
    const dark = !!opts.darkTheme;
    ctx.fillStyle = dark ? '#2f3439' : '#ffffff';
    ctx.fillRect(0, 0, W, H);

    // Determine min/max across datasets (include 0 for baseline)
    let min = 0, max = 0;
    for (let k = 0; k < dcount; k++) {
      const dataK = (datasets[k] && datasets[k].data) || [];
      for (let i = 0; i < n; i++) {
        const v = +dataK[i] || 0;
        if (v > max) max = v;
        if (v < min) min = v;
      }
    }
    if (max < 0) max = 0;
    if (min > 0) min = 0;
    const range = Math.max(1, max - min);

    // Layout
    const innerW = Math.max(10, W - paddingL - paddingR);
    const innerH = Math.max(10, H - paddingT - paddingB);
    const groupGap = 12; // gap between groups
    const barGap = 6;    // gap between bars in a group
    const groupW = Math.max(10, (innerW - groupGap * (n - 1)) / Math.max(1, n));
    const barW = Math.max(6, (groupW - barGap * (dcount - 1)) / dcount);

    const yFor = (v) => paddingT + innerH - ((v - min) / range) * innerH;
    const y0 = yFor(0);

    // Grid lines (5 steps)
    ctx.strokeStyle = dark ? '#4b5563' : '#e5e7eb';
    ctx.lineWidth = 1;
    ctx.beginPath();
    for (let i = 0; i <= 5; i++) {
      const yy = paddingT + (innerH / 5) * i;
      ctx.moveTo(paddingL, yy);
      ctx.lineTo(W - paddingR, yy);
    }
    ctx.stroke();

    // Zero line
    ctx.strokeStyle = dark ? '#9ca3af' : '#9ca3af';
    ctx.beginPath();
    ctx.moveTo(paddingL - 6, y0 + 0.5);
    ctx.lineTo(W - paddingR, y0 + 0.5);
    ctx.stroke();

    // Bars with simple animation
    const colorsCache = [];
    for (let k = 0; k < dcount; k++) {
      colorsCache[k] = toArray((datasets[k] && datasets[k].backgroundColor) || palette[k % palette.length], n, palette[k % palette.length]);
    }

    const duration = Math.max(250, Math.min(1200, opts.animationDuration || 600));
    const startTs = performance.now();
    function frame(now){
      const t = Math.min(1, (now - startTs) / duration);
      // Clear plot area only
      ctx.fillStyle = dark ? '#2f3439' : '#ffffff';
      ctx.fillRect(0, 0, W, H);
      // redraw grid + zero line
      ctx.strokeStyle = dark ? '#4b5563' : '#e5e7eb';
      ctx.lineWidth = 1;
      ctx.beginPath();
      for (let i = 0; i <= 5; i++) {
        const yy = paddingT + (innerH / 5) * i;
        ctx.moveTo(paddingL, yy);
        ctx.lineTo(W - paddingR, yy);
      }
      ctx.stroke();
      ctx.strokeStyle = dark ? '#9ca3af' : '#9ca3af';
      ctx.beginPath();
      ctx.moveTo(paddingL - 6, y0 + 0.5);
      ctx.lineTo(W - paddingR, y0 + 0.5);
      ctx.stroke();

      let gx = paddingL;
      for (let i = 0; i < n; i++) {
        let bx = gx;
        for (let k = 0; k < dcount; k++) {
          const dataK = (datasets[k] && datasets[k].data) || [];
          const colorsK = colorsCache[k];
          const v = +dataK[i] || 0;
          const yv = yFor(v);
          const bh = Math.abs(yv - y0) * t;
          const by = v >= 0 ? (y0 - bh) : y0;
          const col = Array.isArray(colorsK) ? colorsK[i % colorsK.length] : colorsK;
          ctx.fillStyle = col;
          ctx.beginPath();
          roundRect(ctx, bx, by, barW, bh, 6);
          ctx.fill();
          bx += barW + barGap;
        }
        gx += groupW + groupGap;
      }

    // X labels
    ctx.fillStyle = dark ? '#e5e7eb' : '#374151';
    const hl = (typeof opts.highlightIndex === 'number') ? opts.highlightIndex : -1;
    const bottomLegendExtra = (legendH && !legendTop) ? 28 : 0;
    const yText = H - (bottomLegendExtra + bottomTextPad);
    let lx = paddingL;
    for (let i = 0; i < n; i++) {
      const lbl = (labels[i] || '').toString();
      const text = needsTilt ? lbl : (lbl.length > 12 ? lbl.slice(0, 11) + '…' : lbl);
      const cx = lx + groupW / 2;
      ctx.font = (i === hl ? 'bold 12px sans-serif' : '12px sans-serif');
      if (needsTilt) {
        ctx.save();
        ctx.translate(cx, yText);
        ctx.rotate(tiltRad);
        ctx.textAlign = 'right';
        ctx.textBaseline = 'top';
        ctx.fillText(text, 0, 0);
        ctx.restore();
      } else {
        ctx.textAlign = 'center';
        ctx.textBaseline = 'alphabetic';
        ctx.fillText(text, cx, H - (bottomLegendExtra + 18));
      }
      lx += groupW + groupGap;
    }

      // Legend (positioned, centered)
      if (legendH) {
        const gap = 16, sw = 12;
        ctx.font = 'bold 12px sans-serif';
        ctx.textAlign = 'left';
        let items = datasets.map((ds, idx) => ({
          label: ds.label || '—',
          color: Array.isArray(ds.backgroundColor) ? (ds.backgroundColor[0] || palette[idx % palette.length]) : (ds.backgroundColor || palette[idx % palette.length])
        }));
        const totalW = items.reduce((acc, it) => acc + sw + 6 + ctx.measureText(it.label).width + gap, -gap);
        let x = Math.max(paddingL, (W - totalW) / 2);
        const y = legendTop ? 16 : (H - 16);
        for (const it of items) {
          ctx.fillStyle = it.color;
          ctx.fillRect(x, y - sw + 2, sw, sw);
          x += sw + 6;
          ctx.fillStyle = dark ? '#f3f4f6' : '#0f172a';
          ctx.fillText(it.label, x, y);
          x += ctx.measureText(it.label).width + gap;
        }
      }

      if (t < 1) requestAnimationFrame(frame);
    }
    requestAnimationFrame(frame);
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
    ctx.globalCompositeOperation = 'destination-out';
    ctx.beginPath();
    ctx.arc(cx, cy, inner, 0, Math.PI * 2);
    ctx.fill();
    ctx.globalCompositeOperation = 'source-over';
  }

  function drawLine(canvas, config) {
    const { labels = [], datasets = [] } = config.data || {};
    const opts = config.options || {};
    const ctx = getCtx2d(canvas);
    const W = canvas.clientWidth || canvas.width;
    const H = canvas.clientHeight || canvas.height;
    const legendH = opts.legend === false ? 0 : 22;
    // Determine if x labels should be tilted on mobile for all periods
    // Comments: Keep in sync with bar chart behavior
    const isMobile = W < 640;
    const period = (opts && typeof opts.period === 'string') ? opts.period.toLowerCase() : '';
    const angleOverride = (typeof opts.xLabelAngle === 'number') ? opts.xLabelAngle : null;
    const needsTilt = !!(angleOverride !== null ? (isMobile && angleOverride !== 0) : isMobile);
    const tiltRad = angleOverride !== null ? (Math.max(-75, Math.min(75, angleOverride)) * Math.PI / 180) : (-40 * Math.PI / 180);
    // Legend position (top by default). Reserve space accordingly.
    const legendPos = ((opts && opts.legendPosition) ? String(opts.legendPosition) : 'top').toLowerCase();
    const legendTop = (legendH > 0) && (legendPos !== 'bottom');
    const paddingL = 48, paddingR = 20;
    // Minimal original paddings
    const basePaddingT = 24, basePaddingB = 32;
    // Compute a uniform extra bottom padding based on the longest label
    const fontSize = 12;
    const prevFont = ctx.font;
    ctx.font = fontSize + 'px sans-serif';
    let maxLabelW = 0;
    for (let i = 0; i < labels.length; i++) {
      const s = (labels[i] || '').toString();
      const w = ctx.measureText(s).width;
      if (w > maxLabelW) maxLabelW = w;
    }
    ctx.font = prevFont;
    const a = Math.abs(tiltRad);
    const bottomTextPad = needsTilt ? (Math.ceil(Math.sin(a) * maxLabelW + Math.cos(a) * fontSize) + 4) : 18;
    const paddingT = basePaddingT + (legendTop ? legendH : 0);
    const paddingB = basePaddingB + (!legendTop ? legendH : 0) + Math.max(0, bottomTextPad - 18);

    const dark = !!opts.darkTheme;
    ctx.fillStyle = dark ? '#2f3439' : '#ffffff';
    ctx.fillRect(0, 0, W, H);

    // Normalize datasets to point arrays and compute bounds
    const series = datasets.map((ds, idx) => {
      const pts = normalizeLinePoints(ds && ds.data, labels.length);
      return { ds, pts, idx };
    });

    let minY = 0, maxY = 0, maxX = (labels.length ? labels.length - 1 : 0);
    series.forEach(({ pts }) => {
      pts.forEach((pt) => {
        const y = +pt.y || 0;
        if (y > maxY) maxY = y;
        if (y < minY) minY = y;
        if (Number.isFinite(pt.x) && pt.x > maxX) maxX = pt.x;
      });
    });
    if (maxY < 0) maxY = 0;
    if (minY > 0) minY = 0;
    const rangeY = Math.max(1, maxY - minY);
    const domainMax = Math.max(labels.length ? labels.length - 1 : 0, maxX, 0);
    const rangeX = Math.max(1, domainMax);

    const innerW = Math.max(10, W - paddingL - paddingR);
    const innerH = Math.max(10, H - paddingT - paddingB);

    const yFor = (v) => paddingT + innerH - ((v - minY) / rangeY) * innerH;
    const xFor = (x) => {
      const clamped = Math.max(0, Math.min(domainMax, x));
      return paddingL + (clamped / rangeX) * innerW;
    };
    const y0 = yFor(0);

    // Grid lines
    ctx.strokeStyle = dark ? '#4b5563' : '#e5e7eb';
    ctx.lineWidth = 1;
    ctx.beginPath();
    for (let i = 0; i <= 5; i++) {
      const yy = paddingT + (innerH / 5) * i;
      ctx.moveTo(paddingL, yy);
      ctx.lineTo(W - paddingR, yy);
    }
    ctx.stroke();

    // Zero line
    ctx.strokeStyle = dark ? '#9ca3af' : '#9ca3af';
    ctx.beginPath();
    ctx.moveTo(paddingL - 6, y0 + 0.5);
    ctx.lineTo(W - paddingR, y0 + 0.5);
    ctx.stroke();

    const duration = Math.max(250, Math.min(1200, opts.animationDuration || 600));
    const startTs = performance.now();

    function frame(now) {
      const t = Math.min(1, (now - startTs) / duration);
      ctx.fillStyle = dark ? '#2f3439' : '#ffffff';
      ctx.fillRect(0, 0, W, H);

      // redraw grid
      ctx.strokeStyle = dark ? '#4b5563' : '#e5e7eb';
      ctx.lineWidth = 1;
      ctx.beginPath();
      for (let i = 0; i <= 5; i++) {
        const yy = paddingT + (innerH / 5) * i;
        ctx.moveTo(paddingL, yy);
        ctx.lineTo(W - paddingR, yy);
      }
      ctx.stroke();
      ctx.strokeStyle = dark ? '#9ca3af' : '#9ca3af';
      ctx.beginPath();
      ctx.moveTo(paddingL - 6, y0 + 0.5);
      ctx.lineTo(W - paddingR, y0 + 0.5);
      ctx.stroke();

      series.forEach(({ ds, pts, idx }) => {
        const color = Array.isArray(ds && ds.borderColor) ? (ds.borderColor[0] || palette[idx % palette.length]) : (ds && ds.borderColor) || palette[idx % palette.length];
        const dash = (ds && ds.borderDash) || [];
        const width = (ds && ds.borderWidth) || 2;
        const pointRadius = (ds && ds.pointRadius) || 4;
        const pointFill = (ds && ds.pointBackgroundColor) || color;

        ctx.setLineDash([]);
        ctx.lineWidth = width;
        ctx.strokeStyle = color;
        if (dash && dash.length) ctx.setLineDash(dash);

        ctx.beginPath();
        pts.forEach((pt, i) => {
          const x = xFor(pt.x);
          const yTarget = yFor(pt.y);
          const y = y0 + (yTarget - y0) * t;
          if (i === 0) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
        });
        ctx.stroke();
        ctx.setLineDash([]);

        // Optional fill to zero line
        if (ds && ds.fill) {
          ctx.beginPath();
          pts.forEach((pt, i) => {
            const x = xFor(pt.x);
            const yTarget = yFor(pt.y);
            const y = y0 + (yTarget - y0) * t;
            if (i === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
          });
          const lastX = xFor(pts.length ? pts[pts.length - 1].x : 0);
          ctx.lineTo(lastX, y0);
          const firstX = xFor(pts.length ? pts[0].x : 0);
          ctx.lineTo(firstX, y0);
          ctx.closePath();
          const fillColor = (ds.backgroundColor || color);
          ctx.fillStyle = typeof fillColor === 'string' ? fillColor : color;
          ctx.globalAlpha = 0.2;
          ctx.fill();
          ctx.globalAlpha = 1;
        }

        // Points
        ctx.fillStyle = pointFill;
        ctx.strokeStyle = '#ffffff';
        ctx.lineWidth = 1;
        pts.forEach((pt) => {
          const x = xFor(pt.x);
          const yTarget = yFor(pt.y);
          const y = y0 + (yTarget - y0) * t;
          const r = Math.max(0, pointRadius);
          if (!r) return;
          ctx.beginPath();
          ctx.arc(x, y, r, 0, Math.PI * 2);
          ctx.fill();
          if (ds && ds.pointBorderWidth) {
            ctx.lineWidth = ds.pointBorderWidth;
            ctx.strokeStyle = (ds.pointBorderColor || '#ffffff');
            ctx.stroke();
          }
        });
        ctx.lineWidth = 1;
      });

      // X labels
      ctx.fillStyle = dark ? '#e5e7eb' : '#374151';
      ctx.font = '12px sans-serif';
      if (labels.length) {
        const bottomLegendExtra = (legendH && !legendTop) ? 28 : 0;
        const yText = H - (bottomLegendExtra + bottomTextPad);
        const step = rangeX === 0 ? 0 : innerW / Math.max(1, labels.length - 1);
        for (let i = 0; i < labels.length; i++) {
          const lbl = (labels[i] || '').toString();
          const text = needsTilt ? lbl : (lbl.length > 12 ? lbl.slice(0, 11) + '…' : lbl);
          const x = paddingL + step * i;
          if (needsTilt) {
            ctx.save();
            ctx.translate(x, yText);
            ctx.rotate(tiltRad);
            ctx.textAlign = 'right';
            ctx.textBaseline = 'top';
            ctx.fillText(text, 0, 0);
            ctx.restore();
          } else {
            ctx.textAlign = 'center';
            ctx.textBaseline = 'alphabetic';
            ctx.fillText(text, x, H - (bottomLegendExtra + 18));
          }
        }
      }

      // Legend (positioned, centered)
      if (legendH) {
        const gap = 16, sw = 12;
        ctx.font = '12px sans-serif';
        ctx.textAlign = 'left';
        const items = datasets.map((ds, idx) => ({
          label: ds.label || '—',
          color: Array.isArray(ds.borderColor) ? (ds.borderColor[0] || palette[idx % palette.length]) : (ds.borderColor || palette[idx % palette.length])
        }));
        const totalW = items.reduce((acc, it) => acc + sw + 6 + ctx.measureText(it.label).width + gap, -gap);
        let x = Math.max(paddingL, (W - totalW) / 2);
        const y = legendTop ? 16 : (H - 16);
        for (const it of items) {
          ctx.fillStyle = it.color;
          ctx.fillRect(x, y - sw + 2, sw, sw);
          x += sw + 6;
          ctx.fillStyle = dark ? '#e5e7eb' : '#111827';
          ctx.fillText(it.label, x, y);
          x += ctx.measureText(it.label).width + gap;
        }
      }

      if (t < 1) requestAnimationFrame(frame);
    }

    requestAnimationFrame(frame);
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
    if (type === 'doughnut' || type === 'pie') drawDoughnut(this.canvas, this.config);
    else if (type === 'line' || type === 'area' || type === 'scatter') drawLine(this.canvas, this.config);
    else drawBar(this.canvas, this.config);
  };
  Chart.prototype.destroy = function() { clearCanvas(this.canvas); };

  // Always overwrite global
  window.Chart = Chart;
})();
