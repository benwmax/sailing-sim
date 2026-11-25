// Fetch GBIF URLs from a browser tab on https://api.gbif.org, for machines whose shell can't reach GBIF
// (docs/wildlife-0/README.md). Paste this into the tab's console, then:
//   __wfAdd([...urls from Data/Wildlife/raw/missing.json...]); __wfRun();
//   __wfStatus()                    -> {queued, done, failed, running}
//   __wfNext(240000)                -> '{url: body}' JSON, the next ~240 KB not yet handed over (__wfResend() repeats
//                                      the last piece); save each and run fetch_gbif.py --ingest that.json
// Stage 3 and 4 URLs can be made here from the facets already fetched, the same way fetch_gbif.py makes them:
//   __wfPages([[facetUrl, maxPages], ...])   queues the record pages of those cast entries
//   __wfDatasets()                          queues the metadata of every non-eBird dataset in the cast facets
// Responses are cut down exactly as gbif.py's reduce_body does; fetch_gbif.py --offline says what is still missing.
(() => {
  const w = window;
  const EBIRD = '4fa7b334-ce0d-4e88-aaae-2e0c138d049e';
  const FACETS = '&limit=0&facet=month&facet=datasetKey&facetLimit=100';
  const TOP_DATASETS = 40;
  const PAGE = 300;
  w.__wf = w.__wf || { queue: [], results: {}, failed: {}, running: false };
  w.__wfStore = w.__wfStore || {};
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const reducePage = (b) => {
    const ds = [], idx = {}, rows = [];
    for (const o of b.results || []) {
      const k = o.datasetKey ?? null;
      if (!(k in idx)) { idx[k] = ds.length; ds.push(k); }
      const has = o.decimalLatitude != null && o.decimalLongitude != null;
      rows.push([idx[k], o.speciesKey ?? null, o.individualCount || 0,
        has ? Math.round(o.decimalLatitude * 1000) / 1000 : null, has ? Math.round(o.decimalLongitude * 1000) / 1000 : null]);
    }
    return { offset: b.offset, limit: b.limit, endOfRecords: b.endOfRecords, count: b.count, reduced: 2, ds, r: rows };
  };
  const reduce = (u, b) => {
    if (u.includes('/occurrence/search?')) {
      if (u.includes('limit=0')) return { count: b.count, facets: b.facets || [] };
      return reducePage(b);
    }
    if (u.includes('/dataset/')) {
      return { key: b.key, title: b.title, license: b.license, doi: b.doi, publishingOrganizationKey: b.publishingOrganizationKey };
    }
    return b;
  };
  const facet = (b, field) => {
    const f = (b.facets || []).find((x) => x.field.toLowerCase() === field.toLowerCase());
    return f ? f.counts : [];
  };
  w.__wfAdd = (urls) => {
    for (const u of urls) if (!(u in w.__wfStore) && !w.__wf.queue.includes(u)) w.__wf.queue.push(u);
    return w.__wf.queue.length;
  };
  w.__wfStatus = () => ({ queued: w.__wf.queue.length, done: Object.keys(w.__wf.results).length,
    failed: Object.keys(w.__wf.failed).length, running: w.__wf.running });
  w.__wfTake = (n) => {
    const out = {};
    for (const u of Object.keys(w.__wf.results).slice(0, n)) { out[u] = w.__wf.results[u]; delete w.__wf.results[u]; }
    return out;
  };
  // Hand results over in pieces small enough for the bridge (about 250 KB): each call returns the next ones.
  w.__wfSent = w.__wfSent || new Set();
  w.__wfNext = (maxBytes) => {
    const out = {}; let size = 2; w.__wfLast = [];
    for (const [u, b] of Object.entries(w.__wfStore)) {
      if (w.__wfSent.has(u)) continue;
      const n = JSON.stringify(u).length + JSON.stringify(b).length + 2;
      if (size + n > maxBytes && w.__wfLast.length) break;
      out[u] = b; size += n; w.__wfSent.add(u); w.__wfLast.push(u);
    }
    return JSON.stringify(out);
  };
  w.__wfResend = () => { for (const u of w.__wfLast || []) w.__wfSent.delete(u); return (w.__wfLast || []).length; };
  w.__wfPages = (jobs) => {
    let n = 0;
    for (const [fu, maxPages] of jobs) {
      const b = w.__wfStore[fu];
      if (!b) continue;
      const ds = facet(b, 'DATASET_KEY').filter((c) => c.name !== EBIRD).sort((a, c) => c.count - a.count).slice(0, TOP_DATASETS);
      if (!ds.length) continue;
      const total = ds.reduce((s, c) => s + c.count, 0);
      const base = fu.replace(FACETS, '') + ds.map((c) => c.name).sort().map((k) => '&datasetKey=' + k).join('');
      const pages = Math.min(maxPages, Math.ceil(total / PAGE));
      for (let i = 0; i < pages; i++) { w.__wfAdd([base + '&limit=300&offset=' + i * PAGE]); n++; }
    }
    return n;
  };
  w.__wfDatasets = () => {
    const keys = new Set();
    for (const [u, b] of Object.entries(w.__wfStore)) {
      if (!u.includes(FACETS) || u.includes('&taxonKey=212&')) continue;
      for (const c of facet(b, 'DATASET_KEY')) if (c.name !== EBIRD) keys.add(c.name);
    }
    return w.__wfAdd([...keys].sort().map((k) => 'https://api.gbif.org/v1/dataset/' + k));
  };
  w.__wfRun = () => {
    if (w.__wf.running) return 'already running';
    w.__wf.running = true;
    (async () => {
      while (w.__wf.queue.length) {
        const u = w.__wf.queue.shift();
        let ok = false;
        for (let a = 0; a < 6 && !ok; a++) {
          try {
            const r = await fetch(u);
            if (r.status === 429 || r.status >= 500) { await sleep(1000 * 2 ** a); continue; }
            if (!r.ok) { w.__wf.failed[u] = r.status; break; }
            const b = reduce(u, await r.json());
            w.__wf.results[u] = b;
            w.__wfStore[u] = b;
            ok = true;
          } catch (e) { await sleep(1000 * 2 ** a); }
        }
        if (!ok && !(u in w.__wf.failed)) w.__wf.failed[u] = 'gave up';
        await sleep(100);
      }
      w.__wf.running = false;
    })();
    return 'started';
  };
  return 'ready';
})();
