// PATH: /Archen/static/js/validation-fa.js
// Provide Persian messages for the browser's built-in form validation.
(function () {
  const messages = {
    valueMissing: 'پر کردن این فیلد الزامی است.',
    typeMismatch: 'مقدار وارد شده با نوع فیلد سازگار نیست.',
    patternMismatch: 'الگوی وارد شده معتبر نیست.',
    tooShort: 'این مقدار بسیار کوتاه است.',
    tooLong: 'این مقدار بسیار طولانی است.',
    rangeUnderflow: 'مقدار باید حداقل %(limit_value)s باشد.',
    rangeOverflow: 'مقدار باید حداکثر %(limit_value)s باشد.',
    stepMismatch: 'لطفاً از گام‌های معتبر استفاده کنید.',
    badInput: 'مقدار وارد شده معتبر نیست.',
  };

  function formatRangeMessage(key, element) {
    const min = element.getAttribute('min');
    const max = element.getAttribute('max');
    if (key === 'rangeUnderflow' && min !== null) {
      return messages[key].replace('%(limit_value)s', min);
    }
    if (key === 'rangeOverflow' && max !== null) {
      return messages[key].replace('%(limit_value)s', max);
    }
    return messages[key];
  }

  document.addEventListener('DOMContentLoaded', function () {
    document.addEventListener(
      'invalid',
      function (event) {
        const element = event.target;
        if (!element || typeof element.setCustomValidity !== 'function') {
          return;
        }

        const validity = element.validity;
        element.setCustomValidity('');

        let message = '';
        if (validity.valueMissing) {
          message = messages.valueMissing;
        } else if (validity.typeMismatch) {
          message = messages.typeMismatch;
        } else if (validity.patternMismatch) {
          message = messages.patternMismatch;
        } else if (validity.tooShort) {
          message = messages.tooShort;
        } else if (validity.tooLong) {
          message = messages.tooLong;
        } else if (validity.rangeUnderflow) {
          message = formatRangeMessage('rangeUnderflow', element);
        } else if (validity.rangeOverflow) {
          message = formatRangeMessage('rangeOverflow', element);
        } else if (validity.stepMismatch) {
          message = messages.stepMismatch;
        } else if (validity.badInput) {
          message = messages.badInput;
        }

        if (message) {
          element.setCustomValidity(message);
        }
      },
      true
    );

    document.addEventListener('input', function (event) {
      const element = event.target;
      if (element && typeof element.setCustomValidity === 'function') {
        element.setCustomValidity('');
      }
    });
  });
})();

