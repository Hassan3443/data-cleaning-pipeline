/* In-browser port of three pipeline rules. tests/js/check.test.js compares it with
   the Python pipeline on every distinct value in the raw file. */
(function (root) {
  const MONTHS = {jan:1,feb:2,mar:3,apr:4,may:5,jun:6,jul:7,aug:8,sep:9,oct:10,nov:11,dec:12};
  function title(s) { return s.toLowerCase().replace(/[a-z]+/g, w => w[0].toUpperCase() + w.slice(1)); }
  function cleanText(v) {
    const t = String(v == null ? '' : v).trim().replace(/\s+and\s+/g, ' & ');
    return t === '' || t.toLowerCase() === 'nan' ? null : title(t);
  }
  function cleanPrice(v) {
    const t = String(v == null ? '' : v).replace(/[^\d.\-]/g, '');
    if (t === '' || t === '-') return null;
    const n = Number(t);
    return Number.isFinite(n) ? n : null;
  }
  function valid(y, m, d) {
    const dt = new Date(Date.UTC(y, m - 1, d));
    return dt.getUTCFullYear() === y && dt.getUTCMonth() === m - 1 && dt.getUTCDate() === d;
  }
  const iso = (y, m, d) => y + '-' + String(m).padStart(2, '0') + '-' + String(d).padStart(2, '0');
  function cleanDate(v, slashDayFirst) {
    if (slashDayFirst === undefined) slashDayFirst = true;
    const t = String(v == null ? '' : v).trim();
    let m;
    if ((m = t.match(/^(\d{4})-(\d{2})-(\d{2})$/))) return valid(+m[1], +m[2], +m[3]) ? iso(+m[1], +m[2], +m[3]) : null;
    if ((m = t.match(/^(\d{1,2}) ([A-Za-z]{3}) (\d{4})$/))) {
      const mo = MONTHS[m[2].toLowerCase()];
      return mo && valid(+m[3], mo, +m[1]) ? iso(+m[3], mo, +m[1]) : null;
    }
    if ((m = t.match(/^(\d{1,2})([\/-])(\d{1,2})\2(\d{4})$/))) {
      const a = +m[1], b = +m[3], y = +m[4];
      const dayFirst = m[2] === '/' ? slashDayFirst : false;
      const [d1, m1, d2, m2] = dayFirst ? [a, b, b, a] : [b, a, a, b];
      if (valid(y, m1, d1)) return iso(y, m1, d1);
      if (valid(y, m2, d2)) return iso(y, m2, d2);
    }
    return null;
  }
  const api = { cleanText, cleanPrice, cleanDate };
  if (typeof module !== 'undefined') module.exports = api; else root.Clean = api;
})(this);
