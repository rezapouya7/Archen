// PATH: /Archen/static/js/sort.js

(function () {
  "use strict";

  function cellText(td) {
    return (td && td.textContent ? td.textContent : "").trim();
  }

  // Normalize Persian/Arabic-Indic digits to ASCII so numeric/date parsing works reliably
  function normalizeDigits(str) {
    if (!str) return "";
    return String(str)
      .replace(/[\u06F0-\u06F9]/g, function (d) { return String(d.charCodeAt(0) - 0x06F0); })
      .replace(/[\u0660-\u0669]/g, function (d) { return String(d.charCodeAt(0) - 0x0660); });
  }

  function parseValue(text, type) {
    if (type === "num") {
      const normalized = normalizeDigits(text);
      const num = parseFloat(normalized.replace(/[^\d.-]/g, ""));
      return isNaN(num) ? Number.NEGATIVE_INFINITY : num;
    }
    if (type === "date") {
      const t = Date.parse(normalizeDigits(text));
      return isNaN(t) ? 0 : t;
    }
    return text.toLowerCase();
  }

  window.sortByCol = function (btn) {
    if (!btn) return;
    const col = parseInt(btn.dataset.col, 10);
    if (Number.isNaN(col)) return;

    const table = btn.closest("table");
    if (!table || !table.tBodies || !table.tBodies[0]) return;
    const tbody = table.tBodies[0];
    const rows = Array.from(tbody.querySelectorAll("tr"));

    window.__sortState = window.__sortState || {};
    const tableId = table.id || "table";
    const key = tableId + ":" + col;
    const next = window.__sortState[key] === "asc" ? "desc" : "asc";
    window.__sortState[key] = next;

    const type = btn.dataset.type || "text";

    rows
      .sort((a, b) => {
        const ta = parseValue(cellText(a.children[col]), type);
        const tb = parseValue(cellText(b.children[col]), type);
        if (ta < tb) return next === "asc" ? -1 : 1;
        if (ta > tb) return next === "asc" ? 1 : -1;
        return 0;
      })
      .forEach((r) => tbody.appendChild(r));


    table.querySelectorAll("thead .sort-btn").forEach((b) => {
      b.classList.remove("text-blue-700", "font-semibold");
      const ic = b.querySelector(".sort-indicator");
      if (ic) {
        ic.classList.remove("opacity-100", "rotate-180");
        ic.classList.add("opacity-40");
      }
    });

    btn.classList.add("text-blue-700", "font-semibold");
    const icon = btn.querySelector(".sort-indicator");
    if (icon) {
      icon.classList.remove("opacity-40");
      icon.classList.add("opacity-100");
      if (next === "asc") icon.classList.add("rotate-180");
      else icon.classList.remove("rotate-180");
    }
  };

  // Delegate clicks if no inline onclick present
  document.addEventListener("click", function (e) {
    const el = e.target.closest(".sort-btn");
    if (!el) return;
    if (!el.hasAttribute("onclick")) {
      e.preventDefault();
      window.sortByCol(el);
    }
  });
})();
