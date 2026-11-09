"""
dashboard.py — Flask web server serving the live transfer dashboard.
"""

from flask import Flask, jsonify, render_template_string
from sync_engine import state

app = Flask(__name__)


@app.after_request
def cors(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    return response


DASHBOARD = r"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Medal Export to Immich</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

    :root {
      --bg:        #06080d;
      --surface:   #0d1117;
      --surface-2: #161b22;
      --border:    #21262d;
      --border-hi: #30363d;
      --text:      #e6edf3;
      --text-dim:  #7d8590;
      --text-xdim: #484f58;
      --green:     #3fb950;
      --green-bg:  rgba(63,185,80,.08);
      --amber:     #d29922;
      --amber-bg:  rgba(210,153,34,.08);
      --red:       #f85149;
      --sky:       #58a6ff;
      --purple:    #a855f7;
      --purple-bg: rgba(168,85,247,.12);
      --orange:    #f97316;
      --orange-bg: rgba(249,115,22,.12);
      --indigo:    #818cf8;
    }

    body {
      background: var(--bg);
      color: var(--text);
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
      min-height: 100vh;
      -webkit-font-smoothing: antialiased;
    }

    .mono { font-family: 'JetBrains Mono', monospace; }

    .container { max-width: 1200px; margin: 0 auto; padding: 24px; }

    /* ── HEADER ───────────────────────────────────── */
    .header {
      display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 16px;
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 16px;
      padding: 20px 24px;
    }
    .header-left { display: flex; align-items: center; gap: 16px; }
    .logo {
      width: 48px; height: 48px; border-radius: 14px;
      background: linear-gradient(135deg, var(--orange), #ef4444);
      display: flex; align-items: center; justify-content: center;
      font-size: 24px; font-weight: 800; color: #fff;
      box-shadow: 0 4px 24px rgba(249,115,22,.25);
    }
    .header h1 { font-size: 20px; font-weight: 800; letter-spacing: -.02em; }
    .header p  { font-size: 12px; color: var(--text-dim); margin-top: 2px; }
    .badge {
      display: inline-flex; align-items: center; gap: 6px;
      font-size: 11px; font-weight: 600; padding: 3px 10px;
      border-radius: 999px; margin-left: 10px;
    }
    .badge-active  { background: var(--green-bg);  color: var(--green);  border: 1px solid rgba(63,185,80,.2); }
    .badge-done    { background: var(--green-bg);  color: var(--green);  border: 1px solid rgba(63,185,80,.3); }
    .badge-syncing { background: var(--amber-bg);  color: var(--amber);  border: 1px solid rgba(210,153,34,.2); }
    .badge-dot { width: 7px; height: 7px; border-radius: 50%; }
    .badge-active .badge-dot  { background: var(--green);  animation: pulse 2s infinite; }
    .badge-syncing .badge-dot { background: var(--amber);  animation: pulse 1.5s infinite; }
    .badge-done .badge-dot    { background: var(--green); }

    @keyframes pulse { 0%,100% { opacity:1; } 50% { opacity:.4; } }
    @keyframes glow-purple {
      0%,100% { text-shadow: 0 0 6px rgba(168,85,247,.6), 0 0 20px rgba(168,85,247,.3); }
      50%     { text-shadow: 0 0 12px rgba(168,85,247,.9), 0 0 40px rgba(168,85,247,.5); }
    }
    @keyframes glow-orange {
      0%,100% { text-shadow: 0 0 6px rgba(249,115,22,.6), 0 0 20px rgba(249,115,22,.3); }
      50%     { text-shadow: 0 0 12px rgba(249,115,22,.9), 0 0 40px rgba(249,115,22,.5); }
    }

    .immich-btn {
      display: inline-flex; align-items: center; gap: 6px;
      padding: 8px 16px; border-radius: 10px; font-size: 12px; font-weight: 600;
      background: var(--indigo); color: #fff; text-decoration: none;
      transition: all .15s;
    }
    .immich-btn:hover { filter: brightness(1.15); transform: translateY(-1px); }

    /* ── STATS ROW ────────────────────────────────── */
    .stats-row {
      display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 12px;
      margin-top: 20px;
    }
    .stat-card {
      background: var(--surface); border: 1px solid var(--border); border-radius: 14px;
      padding: 16px 18px; text-align: center;
    }
    .stat-label { font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: .08em; color: var(--text-dim); }
    .stat-value { font-size: 26px; font-weight: 800; margin-top: 4px; letter-spacing: -.02em; }
    .stat-sub   { font-size: 11px; color: var(--text-dim); margin-top: 2px; }
    .c-green  { color: var(--green); }
    .c-amber  { color: var(--amber); }
    .c-sky    { color: var(--sky); }
    .c-purple { color: var(--purple); }
    .c-orange { color: var(--orange); }
    .c-red    { color: var(--red); }

    /* ── PROGRESS SECTION ─────────────────────────── */
    .progress-section {
      background: var(--surface); border: 1px solid var(--border); border-radius: 16px;
      padding: 24px; margin-top: 20px;
    }
    .progress-header { display: flex; align-items: baseline; justify-content: space-between; flex-wrap: wrap; gap: 8px; }
    .progress-pct { font-size: 42px; font-weight: 900; letter-spacing: -.03em; }
    .progress-files { font-size: 13px; color: var(--text-dim); font-weight: 500; }

    .bar-track {
      width: 100%; height: 20px; background: var(--bg); border-radius: 999px;
      border: 1px solid var(--border); padding: 3px; margin-top: 16px; overflow: hidden;
    }
    .bar-fill {
      height: 100%; border-radius: 999px;
      background: linear-gradient(90deg, var(--orange), var(--amber), var(--green));
      transition: width .6s cubic-bezier(.4,0,.2,1);
      box-shadow: 0 0 16px rgba(249,115,22,.3);
    }

    .current-info {
      display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px;
      margin-top: 16px;
    }
    .current-card {
      background: var(--bg); border: 1px solid var(--border); border-radius: 12px; padding: 12px 14px;
    }
    .current-label { font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: .06em; color: var(--text-dim); }
    .current-value { font-size: 13px; font-weight: 600; margin-top: 4px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

    /* ── TWO-COL PANELS ───────────────────────────── */
    .panels { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-top: 20px; }
    @media (max-width: 860px) { .panels { grid-template-columns: 1fr; } }

    .panel {
      background: var(--surface); border: 1px solid var(--border); border-radius: 16px;
      padding: 20px; display: flex; flex-direction: column; height: 420px;
    }
    .panel-header {
      display: flex; align-items: center; justify-content: space-between;
      padding-bottom: 12px; border-bottom: 1px solid var(--border);
    }
    .panel-title { font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: .08em; display: flex; align-items: center; gap: 8px; }
    .panel-title .dot { width: 8px; height: 8px; border-radius: 50%; background: var(--green); animation: pulse 2s infinite; }
    .panel-count { font-size: 11px; color: var(--text-dim); }
    .panel-body { flex: 1; overflow-y: auto; margin-top: 12px; padding-right: 6px; }
    .panel-body::-webkit-scrollbar { width: 5px; }
    .panel-body::-webkit-scrollbar-thumb { background: var(--border-hi); border-radius: 4px; }

    /* Log entries */
    .log-entry { display: flex; align-items: flex-start; gap: 8px; padding: 4px 0; font-size: 12px; line-height: 1.4; }
    .log-time { color: var(--text-xdim); flex-shrink: 0; font-size: 10px; padding-top: 1px; }
    .log-icon { flex-shrink: 0; }
    .log-msg  { word-break: break-all; }
    .log-success .log-msg { color: var(--green); }
    .log-warn    .log-msg { color: var(--amber); }
    .log-error   .log-msg { color: var(--red); }
    .log-target  .log-msg { color: var(--sky); font-weight: 600; }
    .log-info    .log-msg { color: var(--text-dim); }

    /* Target list entries */
    .target-entry {
      display: flex; align-items: center; justify-content: space-between;
      padding: 10px 12px; border-radius: 10px; margin-bottom: 6px;
      border: 1px solid var(--border); background: var(--bg);
      transition: border-color .2s;
    }
    .target-entry.active { border-color: rgba(210,153,34,.4); background: var(--amber-bg); }
    .target-entry.done   { border-color: rgba(63,185,80,.15); }
    .target-name { font-size: 13px; font-weight: 600; }
    .target-meta { font-size: 10px; color: var(--text-dim); margin-top: 2px; }
    .target-badge {
      font-size: 10px; font-weight: 600; padding: 2px 8px; border-radius: 6px;
    }
    .tb-queued    { background: var(--surface-2); color: var(--text-dim); }
    .tb-uploading { background: var(--amber-bg); color: var(--amber); animation: pulse 1.5s infinite; }
    .tb-done      { background: var(--green-bg); color: var(--green); }
    .tb-failed    { background: rgba(248,81,73,.1); color: var(--red); }

    /* ── FOOTER ───────────────────────────────────── */
    .footer {
      text-align: center; padding: 32px 0 16px; font-size: 13px; color: var(--text-dim);
    }
    .footer a { text-decoration: none; font-weight: 700; }
    .credit-nog {
      color: var(--purple);
      animation: glow-purple 3s ease-in-out infinite;
    }
    .credit-claude {
      color: var(--orange);
      animation: glow-orange 3s ease-in-out infinite;
    }
  </style>
</head>
<body>
<div class="container">

  <!-- HEADER -->
  <header class="header">
    <div class="header-left">
      <div class="logo">⚡</div>
      <div>
        <h1>
          Medal Export to Immich
          <span id="badge" class="badge badge-syncing"><span class="badge-dot"></span> Starting</span>
        </h1>
        <p>Lossless Ethernet Transfer &bull; Per-File Streaming &bull; SHA-1 Dedup</p>
      </div>
    </div>
    <a id="immich-link" href="#" target="_blank" class="immich-btn">Open Immich Album →</a>
  </header>

  <!-- STATS ROW -->
  <div class="stats-row">
    <div class="stat-card">
      <div class="stat-label">Speed</div>
      <div class="stat-value c-green mono" id="s-speed">—</div>
      <div class="stat-sub">MB/s</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Uploaded</div>
      <div class="stat-value c-sky mono" id="s-uploaded">0</div>
      <div class="stat-sub">new files</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Duplicates</div>
      <div class="stat-value c-amber mono" id="s-dupes">0</div>
      <div class="stat-sub">already on server</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Failed</div>
      <div class="stat-value c-red mono" id="s-failed">0</div>
      <div class="stat-sub">errors</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">ETA</div>
      <div class="stat-value c-purple mono" id="s-eta">—</div>
      <div class="stat-sub" id="s-elapsed">0s elapsed</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Data</div>
      <div class="stat-value c-orange mono" id="s-data">0 GB</div>
      <div class="stat-sub" id="s-datatotal">of 0 GB</div>
    </div>
  </div>

  <!-- PROGRESS -->
  <section class="progress-section">
    <div class="progress-header">
      <div>
        <span class="progress-pct" id="p-pct">0.0%</span>
        <span class="progress-files" id="p-files">(0 / 0 files)</span>
      </div>
    </div>
    <div class="bar-track"><div class="bar-fill" id="p-bar" style="width:0%"></div></div>
    <div class="current-info">
      <div class="current-card">
        <div class="current-label">Current Folder</div>
        <div class="current-value" id="p-target">Initializing...</div>
      </div>
      <div class="current-card">
        <div class="current-label">Current File</div>
        <div class="current-value mono" id="p-file" style="color:var(--amber)">—</div>
      </div>
      <div class="current-card">
        <div class="current-label">Destination</div>
        <div class="current-value" id="p-dest" style="color:var(--indigo)">
          <span style="display:inline-block;width:7px;height:7px;border-radius:50%;background:var(--green);margin-right:6px"></span>
          Connecting...
        </div>
      </div>
    </div>
  </section>

  <!-- PANELS -->
  <div class="panels">
    <!-- Live Feed -->
    <section class="panel">
      <div class="panel-header">
        <div class="panel-title"><span class="dot"></span> Live Activity Feed</div>
        <span class="panel-count mono" id="log-count">0 events</span>
      </div>
      <div class="panel-body mono" id="log-feed">
        <div style="color:var(--text-xdim);font-style:italic">Waiting for events...</div>
      </div>
    </section>

    <!-- Targets -->
    <section class="panel">
      <div class="panel-header">
        <div class="panel-title">Target Folders &amp; Games</div>
        <span class="panel-count" id="t-count">0 / 0</span>
      </div>
      <div class="panel-body" id="t-list"></div>
    </section>
  </div>

  <!-- FOOTER -->
  <footer class="footer">
    Built with ❤️ by
    <a href="https://github.com/nagatesz" target="_blank" class="credit-nog">nog</a>
    &amp;
    <a href="https://docs.anthropic.com/en/docs/about-claude/models#claude-opus-4" target="_blank" class="credit-claude">Claude Opus 4</a>
  </footer>

</div>

<script>
const $ = id => document.getElementById(id);

function fmt(n) { return n.toLocaleString(); }

async function poll() {
  try {
    const r = await fetch('/api/status');
    if (!r.ok) return;
    const d = await r.json();

    // Badge
    const b = $('badge');
    if (d.status === 'completed') {
      b.className = 'badge badge-done'; b.innerHTML = '<span class="badge-dot"></span> Completed';
    } else if (d.status === 'running') {
      b.className = 'badge badge-syncing'; b.innerHTML = '<span class="badge-dot"></span> Syncing';
    } else {
      b.className = 'badge badge-active'; b.innerHTML = '<span class="badge-dot"></span> ' + d.status;
    }

    // Immich link
    if (d.immich_url && d.album_id) {
      $('immich-link').href = d.immich_url + '/albums/' + d.album_id;
    }

    // Stats
    $('s-speed').textContent = d.speed_mbps > 0 ? d.speed_mbps.toFixed(1) : '—';
    $('s-uploaded').textContent = fmt(d.uploaded_files);
    $('s-dupes').textContent = fmt(d.duplicate_files);
    $('s-failed').textContent = fmt(d.failed_files);

    if (d.eta_seconds > 0) {
      const m = Math.floor(d.eta_seconds / 60), s = d.eta_seconds % 60;
      $('s-eta').textContent = m > 0 ? m + 'm ' + s + 's' : s + 's';
    } else {
      $('s-eta').textContent = d.status === 'completed' ? '✓' : '—';
    }
    const em = Math.floor(d.elapsed_seconds / 60), es = d.elapsed_seconds % 60;
    $('s-elapsed').textContent = (em > 0 ? em + 'm ' : '') + es + 's elapsed';

    const gbDone = (d.processed_bytes / 1073741824).toFixed(1);
    const gbTotal = (d.total_bytes / 1073741824).toFixed(1);
    $('s-data').textContent = gbDone + ' GB';
    $('s-datatotal').textContent = 'of ' + gbTotal + ' GB';

    // Progress
    const pct = Math.min(100, Math.max(0, d.percent));
    $('p-pct').textContent = pct.toFixed(1) + '%';
    $('p-bar').style.width = pct + '%';
    $('p-files').textContent = '(' + fmt(d.processed_files) + ' / ' + fmt(d.total_files) + ' files)';
    $('p-target').textContent = d.current_target || '—';
    $('p-file').textContent = d.current_file || '—';
    if (d.immich_url) {
      $('p-dest').innerHTML = '<span style="display:inline-block;width:7px;height:7px;border-radius:50%;background:var(--green);margin-right:6px"></span>' + d.immich_url;
    }

    // Logs
    if (d.recent_logs && d.recent_logs.length) {
      $('log-count').textContent = d.recent_logs.length + ' events';
      const icons = { success:'✔', warn:'⚠', error:'✖', target:'📁', info:'⚡' };
      $('log-feed').innerHTML = d.recent_logs.map(l => {
        const cls = 'log-' + (l.type || 'info');
        return '<div class="log-entry ' + cls + '">' +
          '<span class="log-time mono">' + l.time + '</span>' +
          '<span class="log-icon">' + (icons[l.type] || '⚡') + '</span>' +
          '<span class="log-msg">' + l.message + '</span></div>';
      }).join('');
      $('log-feed').scrollTop = $('log-feed').scrollHeight;
    }

    // Targets
    if (d.targets && d.targets.length) {
      let done = 0;
      $('t-list').innerHTML = d.targets.map(t => {
        const isDone = t.status === 'completed';
        const isActive = d.current_target === t.name && d.status !== 'completed';
        if (isDone) done++;
        const cls = isDone ? 'done' : isActive ? 'active' : '';
        const tb = isDone ? 'tb-done' : isActive ? 'tb-uploading' : t.status === 'failed' ? 'tb-failed' : 'tb-queued';
        const label = isDone ? 'Done' : isActive ? 'Uploading' : t.status === 'failed' ? 'Failed' : 'Queued';
        return '<div class="target-entry ' + cls + '">' +
          '<div><div class="target-name">' + t.name + '</div>' +
          '<div class="target-meta">' + t.file_count + ' files · ' + (t.total_bytes/1048576).toFixed(0) + ' MB</div></div>' +
          '<span class="target-badge ' + tb + '">' + label + '</span></div>';
      }).join('');
      $('t-count').textContent = done + ' / ' + d.targets.length + ' completed';
    }
  } catch(e) {}
}

setInterval(poll, 1000);
poll();
</script>
</body>
</html>
"""


@app.route("/")
def index():
    return render_template_string(DASHBOARD)


@app.route("/api/status")
def api_status():
    return jsonify(state.as_dict())
