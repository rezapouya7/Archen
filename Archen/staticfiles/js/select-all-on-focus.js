// Global behavior: auto-select all text on focus/click across the app
// Applies to inputs and textareas with textual content. Password fields are excluded.
// This is a safe, unobtrusive enhancement that helps fast editing on data-entry forms.

(function () {
  'use strict';

  /**
   * Determine if an element is a text-like input suitable for selection.
   * - Excludes password fields intentionally.
   * - Skips disabled elements.
   */
  function isTextLike(el) {
    if (!el || el.disabled) return false;
    if (el.tagName === 'TEXTAREA') return true;
    if (el.tagName !== 'INPUT') return false;
    const t = (el.getAttribute('type') || 'text').toLowerCase();
    if (t === 'password' || t === 'hidden' || t === 'checkbox' || t === 'radio' || t === 'file') return false;
    // Important: exclude number inputs from auto-select to avoid
    // interfering with native spinner interactions (up/down arrows).
    if (t === 'number') return false;
    // Typical text-like input types
    return [
      'text', 'search', 'email', 'url', 'tel', 'number', 'date', 'time', ''
    ].includes(t);
  }

  /**
   * Attempt to select entire text content within the control.
   */
  function selectAll(el) {
    try {
      // Some browsers may throw on unsupported input types
      el.select();
    } catch (e) {
      // No-op: selection not supported for this element/type
    }
  }

  // Use capture phase so we get the event before it bubbles to other handlers
  document.addEventListener('focus', function (e) {
    const el = e.target;
    if (isTextLike(el)) {
      selectAll(el);
    }
  }, true);

  // Prevent mouseup from clearing the selection immediately after focus/select
  document.addEventListener('mouseup', function (e) {
    const el = e.target;
    if (isTextLike(el)) {
      // Prevent default to keep the selection that was set on focus
      e.preventDefault();
    }
  }, true);
})();
