// PATH: /Archen/tailwind.config.js
/** Tailwind config for building local CSS without CDN.
 *  Scans Django templates for class usage.
 */
module.exports = {
  content: [
    './templates/**/*.html',
    './**/templates/**/*.html',
    './**/*.py',
    './static/js/**/*.js'
  ],
  theme: {
    extend: {},
  },
  plugins: [],
}

