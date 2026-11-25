(async () => {
  const D = await (await fetch('data.json')).json(), $ = id => document.getElementById(id);
  const fmt = n => Number(n).toLocaleString('en-US');
  const el = (t, c, x) => { const e = document.createElement(t); if (c) e.className = c; if (x !== undefined) e.textContent = x; return e; };
  const R = D.report;

  [[fmt(R.rows_before), 'rows in the raw file'], [fmt(R.rows_after), 'rows after cleaning'],
   [D.completeness[0] + '% → ' + D.completeness[1] + '%', 'cells filled'], [fmt(D.rows_changed), 'rows with at least one fix']]
   .forEach(([b, s]) => { const k = el('div', 'kpi'); k.append(el('b', '', b), el('span', '', s)); $('kpis').append(k); });

  const bars = (box, rows, cls) => {
    const max = Math.max(...rows.map(r => r[1]), 1);
    rows.forEach(r => { const row = el('div', 'hb'), t = el('div', 't'), f = el('div', 'f' + (r[3] ? ' ' + r[3] : (cls ? ' ' + cls : '')));
      f.style.width = (r[1] / max * 100) + '%'; t.append(f); row.append(el('div', 'n', r[0]), t, el('div', 'v', r[2] ?? fmt(r[1]))); box.append(row); });
  };
  bars($('steps'), D.steps.map((s, i) => [s[0], Math.abs(s[1]), (i === 0 || i === 4 ? '' : '') + fmt(s[1]), i === 0 || i === 4 ? 'ok' : 'bad']));
  const mx = D.missing.filter(m => m[1] > 0);
  mx.forEach(([c, b, a]) => { const w = el('div'); bars(w, [[c + ' (raw)', b, fmt(b), 'bad'], [c + ' (clean)', a, fmt(a), 'ok']].map(x => x)); $('missing').append(w); });
  if (!mx.length) $('missing').textContent = 'No missing values.';
  // all bars in one chart share scale only inside each pair, which is the point: raw vs clean

  const df = D.date_formats; bars($('dates'), Object.entries(df).map(([k, v]) => [k, v]));
  const a = D.date_ambiguity;
  $('dateFinding').innerHTML = '';
  const f = $('dateFinding');
  f.append('Of ', Object.assign(el('b', '', fmt(a.slash_dates)), {}), ' dates written like 31/01/2025, ', el('b', '', fmt(a.ambiguous)),
    ' have both numbers 12 or below, so they could be day-first or month-first. The pipeline reads a slash as day-first and a dash as month-first. A month-first reading would have changed ',
    el('b', '', fmt(a.differs_from_month_first_reading)), ' of them. If your source writes m/d/Y, switch the option off.');

  bars($('prices'), Object.entries(D.price_formats).map(([k, v]) => [k, v]));
  bars($('outl'), Object.entries(D.fix_counts).map(([k, v]) => [k, v, fmt(v)]));

  // live cleaner
  const upd = () => {
    const p = Clean.cleanPrice($('inP').value), t = Clean.cleanText($('inT').value), d = Clean.cleanDate($('inD').value, !$('mdy').checked);
    const show = (box, v, rule) => { box.replaceChildren(); if (v === null) box.append(el('em', '', 'not usable → dropped or filled')); else box.append('→ ', String(v), el('br'), el('i', '', rule)); };
    show($('outP'), p, 'strip symbols, read as a number'); show($('outT'), t, 'trim, "and" → "&", Title Case'); show($('outD'), d, 'to ISO YYYY-MM-DD');
  };
  ['inP', 'inT', 'inD', 'mdy'].forEach(i => $(i).addEventListener('input', upd)); upd();
  [['$330.44', 'inP'], ['4,611.88', 'inP'], ['USB-C HUB', 'inT'], ['  giza', 'inT'], ['18/04/2025', 'inD'], ['07 Apr 2026', 'inD'], ['12-01-2026', 'inD']].forEach(([v, i]) => {
    const b = el('button', 'chip', v); b.type = 'button'; b.onclick = () => { $(i).value = v; upd(); }; $('chips').append(b); });

  // variants
  const cols = Object.keys(D.variants); let col = cols[0];
  const drawVar = () => {
    [...$('colSeg').children].forEach(b => b.classList.toggle('on', b.dataset.c === col));
    const V = D.variants[col], t = $('varTable'); t.replaceChildren();
    const h = el('tr'); ['cleaned value', 'raw spellings (count)'].forEach(x => h.append(el('th', '', x))); t.append(h);
    Object.entries(V.map).forEach(([clean, raws]) => { const tr = el('tr'); tr.append(el('td', 'm new', clean), el('td', 'm', raws.map(r => JSON.stringify(r[0]) + ' ×' + r[1]).join('   '))); t.append(tr); });
    $('varTable').dataset.s = V.raw_distinct + ' → ' + V.clean_distinct;
  };
  cols.forEach(c => { const b = el('button', '', c); b.dataset.c = c; b.onclick = () => { col = c; drawVar(); }; $('colSeg').append(b); }); drawVar();

  // before / after
  $('rowsChanged').textContent = fmt(D.rows_changed) + ' of ' + fmt(R.rows_after) + ' kept rows changed';
  let fix = 'all'; const fixes = ['all', 'date', 'price', 'category', 'region', 'payment_method'];
  const drawRows = () => {
    [...$('fixSeg').children].forEach(b => b.classList.toggle('on', b.dataset.f === fix));
    const t = $('rowsTable'); t.replaceChildren(); const h = el('tr');
    ['order', 'fixes', 'date', 'category', 'region', 'unit_price'].forEach(x => h.append(el('th', '', x))); t.append(h);
    D.changed_sample.filter(r => fix === 'all' || r.changes.includes(fix)).slice(0, 12).forEach(r => {
      const tr = el('tr'), tg = el('td'); r.changes.forEach(c => tg.append(el('span', 'tag', c)));
      tr.append(el('td', 'm', r.id), tg);
      r.raw.forEach((v, i) => { const td = el('td', 'm'); if (v.trim() !== r.clean[i]) td.append(el('span', 'old', JSON.stringify(v)), el('br'), el('span', 'new', r.clean[i])); else td.textContent = v; tr.append(td); });
      t.append(tr); });
  };
  fixes.forEach(x => { const b = el('button', '', x); b.dataset.f = x; b.onclick = () => { fix = x; drawRows(); }; $('fixSeg').append(b); }); drawRows();
})();
