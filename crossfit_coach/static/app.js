/* ============ STATE ============ */
let currentAthleteId = null;
let currentView = 'dashboard';
let timerInterval = null;
let timerSeconds = 0;
let timerRunning = false;
let lastGeneratedWorkoutId = null;
let historyOffset = 0;
const HISTORY_LIMIT = 10;

// Auth state
let authToken = localStorage.getItem('cfc_token');
let authUser = JSON.parse(localStorage.getItem('cfc_user') || 'null');

// Chart instances
let chartRpe = null, chartRx = null, chartVolume = null, chartModalities = null, dashModChart = null;

const API = '';  // same origin

/* ============ INIT ============ */
document.addEventListener('DOMContentLoaded', async () => {
  buildRpeSelector();
  buildStarSelector('energy-selector', 5);
  buildStarSelector('sleep-selector', 5);

  if (authToken && authUser) {
    enterApp();
  }
  // else: auth screen is visible by default
});

/* ============ NAVIGATION ============ */
function navigate(view) {
  document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
  document.getElementById(`view-${view}`).classList.add('active');
  document.querySelectorAll('.nav-link').forEach(l => l.classList.remove('active'));
  document.querySelector(`.nav-link[data-view="${view}"]`)?.classList.add('active');
  currentView = view;

  if (view === 'dashboard') loadDashboard();
  else if (view === 'history') { historyOffset = 0; loadHistory(); }
  else if (view === 'progress') loadProgress();
  else if (view === 'feed') loadFeed();
}

/* ============ AUTH ============ */
function showRegister() {
  document.getElementById('auth-login').classList.add('hidden');
  document.getElementById('auth-register').classList.remove('hidden');
  document.getElementById('auth-error').classList.add('hidden');
}

function showLogin() {
  document.getElementById('auth-register').classList.add('hidden');
  document.getElementById('auth-login').classList.remove('hidden');
  document.getElementById('auth-error').classList.add('hidden');
}

function authError(msg) {
  const el = document.getElementById('auth-error');
  el.textContent = msg;
  el.classList.remove('hidden');
}

async function doRegister() {
  const name = document.getElementById('reg-name').value.trim();
  const email = document.getElementById('reg-email').value.trim();
  const password = document.getElementById('reg-password').value;

  if (!name || !email || !password) return authError('Completa todos los campos');
  if (password.length < 6) return authError('La contrase\u00f1a debe tener al menos 6 caracteres');

  try {
    const res = await fetch('/auth/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password, display_name: name }),
    });
    const data = await res.json();
    if (!res.ok) return authError(data.detail || 'Error al registrar');

    saveAuth(data);
    enterApp();
  } catch (e) {
    authError('Error de conexi\u00f3n');
  }
}

async function doLogin() {
  const email = document.getElementById('login-email').value.trim();
  const password = document.getElementById('login-password').value;

  if (!email || !password) return authError('Completa todos los campos');

  try {
    const res = await fetch('/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });
    const data = await res.json();
    if (!res.ok) return authError(data.detail || 'Error al iniciar sesi\u00f3n');

    saveAuth(data);
    enterApp();
  } catch (e) {
    authError('Error de conexi\u00f3n');
  }
}

function skipAuth() {
  // Demo mode: no token, just enter the app
  authToken = null;
  authUser = null;
  enterApp();
}

function saveAuth(data) {
  authToken = data.token;
  authUser = { id: data.user_id, email: data.email, display_name: data.display_name, athlete_id: data.athlete_id };
  localStorage.setItem('cfc_token', authToken);
  localStorage.setItem('cfc_user', JSON.stringify(authUser));
}

function doLogout() {
  authToken = null;
  authUser = null;
  localStorage.removeItem('cfc_token');
  localStorage.removeItem('cfc_user');
  currentAthleteId = null;

  document.getElementById('auth-screen').classList.remove('hidden');
  document.getElementById('main-navbar').classList.add('hidden');
  document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
  showLogin();
}

async function enterApp() {
  document.getElementById('auth-screen').classList.add('hidden');
  document.getElementById('main-navbar').classList.remove('hidden');

  // Show user info in nav
  if (authUser) {
    document.getElementById('nav-user-name').textContent = authUser.display_name;
    document.getElementById('btn-logout').style.display = '';
    if (authUser.athlete_id) currentAthleteId = authUser.athlete_id;
  } else {
    document.getElementById('nav-user-name').textContent = 'Demo';
    document.getElementById('btn-logout').style.display = 'none';
  }

  await loadAthletes();
  if (currentAthleteId) {
    navigate('dashboard');
  }
}

/* ============ API HELPERS ============ */
async function api(path, opts = {}) {
  const url = API + path;
  const headers = { 'Content-Type': 'application/json' };
  if (authToken) headers['Authorization'] = `Bearer ${authToken}`;
  const config = { headers, ...opts };
  if (opts.body && typeof opts.body === 'object') config.body = JSON.stringify(opts.body);
  const res = await fetch(url, config);
  if (res.status === 401) {
    doLogout();
    throw new Error('Sesi\u00f3n expirada');
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'Error');
  }
  return res.json();
}

function toast(msg, duration = 3000) {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.classList.remove('hidden');
  setTimeout(() => el.classList.add('hidden'), duration);
}

function fmtDuration(secs) {
  if (!secs) return '-';
  const m = Math.floor(secs / 60);
  const s = secs % 60;
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

function fmtDate(isoStr) {
  const d = new Date(isoStr);
  return d.toLocaleDateString('es-ES', { day: 'numeric', month: 'short' });
}

function fmtTimeAgo(isoStr) {
  const d = new Date(isoStr);
  const now = new Date();
  const diff = Math.floor((now - d) / 1000);
  if (diff < 60) return 'hace un momento';
  if (diff < 3600) return `hace ${Math.floor(diff / 60)} min`;
  if (diff < 86400) return `hace ${Math.floor(diff / 3600)}h`;
  return fmtDate(isoStr);
}

/* ============ ATHLETES ============ */
async function loadAthletes() {
  try {
    const athletes = await api('/athletes');
    const sel = document.getElementById('athlete-selector');
    sel.innerHTML = '';
    if (athletes.length === 0) {
      sel.innerHTML = '<option value="">Sin atletas</option>';
      currentAthleteId = null;
      return;
    }
    athletes.forEach(a => {
      const opt = document.createElement('option');
      opt.value = a.id;
      opt.textContent = a.name;
      sel.appendChild(opt);
    });
    if (!currentAthleteId || !athletes.find(a => a.id === currentAthleteId)) {
      currentAthleteId = athletes[0].id;
    }
    sel.value = currentAthleteId;
  } catch (e) {
    console.error('Failed to load athletes:', e);
  }
}

function switchAthlete() {
  currentAthleteId = parseInt(document.getElementById('athlete-selector').value);
  if (currentView === 'dashboard') loadDashboard();
  else if (currentView === 'history') loadHistory();
  else if (currentView === 'progress') loadProgress();
}

function showCreateAthleteModal() {
  document.getElementById('modal-overlay').classList.remove('hidden');
}

function closeModal() {
  document.getElementById('modal-overlay').classList.add('hidden');
}

async function createAthlete() {
  const equipment = [];
  document.querySelectorAll('#equipment-grid input:checked').forEach(cb => equipment.push(cb.value));

  try {
    const data = {
      name: document.getElementById('new-name').value || 'Atleta',
      level: document.getElementById('new-level').value,
      training_days_per_week: parseInt(document.getElementById('new-days').value) || 4,
      session_duration_minutes: parseInt(document.getElementById('new-minutes').value) || 60,
      goals: document.getElementById('new-goals').value || null,
      equipment: equipment,
    };
    const athlete = await api('/athletes', { method: 'POST', body: data });
    currentAthleteId = athlete.id;
    await loadAthletes();
    closeModal();
    navigate('dashboard');
    toast(`${athlete.name} creado!`);
  } catch (e) {
    toast('Error: ' + e.message);
  }
}

/* ============ DASHBOARD ============ */
async function loadDashboard() {
  if (!currentAthleteId) return;
  try {
    const [athlete, progress] = await Promise.all([
      api(`/athletes/${currentAthleteId}`),
      api(`/progress/${currentAthleteId}`),
    ]);

    document.getElementById('dash-greeting').textContent = `Hola, ${athlete.name}!`;
    document.getElementById('dash-phase').textContent = phaseLabel(progress.current_phase);
    document.getElementById('dash-total').textContent = progress.total_workouts;
    document.getElementById('dash-rx').textContent = `${progress.rx_percentage}%`;
    document.getElementById('dash-rpe').textContent = progress.avg_rpe_last_week != null ? progress.avg_rpe_last_week.toFixed(1) : '-';
    document.getElementById('dash-week').textContent = progress.current_week;
    document.getElementById('dash-assessment').textContent = progress.assessment;

    // Benchmarks
    const bmDiv = document.getElementById('dash-benchmarks');
    if (progress.recent_benchmarks.length === 0) {
      bmDiv.innerHTML = '<p style="color:var(--text-muted);font-size:0.85rem">Sin benchmarks a\u00fan</p>';
    } else {
      bmDiv.innerHTML = progress.recent_benchmarks.map(b =>
        `<div class="benchmark-card"><div class="bm-name">${b.name}</div><div class="bm-value">${b.value}</div></div>`
      ).join('');
    }

    // Modality chart
    const md = progress.modality_distribution;
    renderDonut('dash-mod-chart', dashModChart, chart => { dashModChart = chart; },
      ['Mono', 'Gymnastics', 'Weightlifting'],
      [md.monostructural || 0, md.gymnastics || 0, md.weightlifting || 0],
      ['#ff6b6b', '#6c5ce7', '#00b894']
    );
  } catch (e) {
    console.error('Dashboard error:', e);
  }
}

function phaseLabel(phase) {
  const labels = {
    foundation: 'Base', accumulation: 'Acumulaci\u00f3n', intensification: 'Intensificaci\u00f3n',
    realization: 'Realizaci\u00f3n', deload: 'Descarga'
  };
  return labels[phase] || phase;
}

/* ============ WOD GENERATION ============ */
async function generateWod() {
  if (!currentAthleteId) return toast('Selecciona un atleta primero');
  const btn = document.getElementById('btn-generate');
  btn.disabled = true;
  btn.textContent = 'Generando...';

  try {
    const focus = document.getElementById('wod-focus').value || undefined;
    const result = await api('/workouts/generate', {
      method: 'POST',
      body: { athlete_id: currentAthleteId, focus },
    });

    document.getElementById('wod-warmup').textContent = result.warmup;
    if (result.strength_or_skill) {
      document.getElementById('wod-strength').textContent = result.strength_or_skill;
      document.getElementById('wod-strength-section').classList.remove('hidden');
    } else {
      document.getElementById('wod-strength-section').classList.add('hidden');
    }
    document.getElementById('wod-wod').textContent = result.wod;
    document.getElementById('wod-type-badge').textContent = result.wod_type;
    document.getElementById('wod-time-domain').textContent = `Dominio: ${result.target_time_domain}`;
    document.getElementById('wod-modalities').textContent = result.modalities.map(m => m.charAt(0).toUpperCase() + m.slice(1)).join(' + ');
    document.getElementById('wod-coaches').textContent = result.coaches_notes;
    document.getElementById('wod-scaling').textContent = result.scaling_notes;
    document.getElementById('wod-cooldown').textContent = result.cooldown;
    document.getElementById('wod-result').classList.remove('hidden');

    // Get the last workout ID for logging
    const hist = await api(`/workouts/${currentAthleteId}/history?limit=1`);
    if (hist.workouts.length > 0) lastGeneratedWorkoutId = hist.workouts[0].id;

    toast('WOD generado!');
  } catch (e) {
    toast('Error: ' + e.message);
  } finally {
    btn.disabled = false;
    btn.textContent = 'Generar Entrenamiento';
  }
}

/* ============ TIMER ============ */
function timerStart() {
  if (timerRunning) return;
  timerRunning = true;
  document.getElementById('timer-display').classList.add('running');
  document.getElementById('timer-display').classList.remove('paused');
  document.getElementById('btn-timer-start').disabled = true;
  document.getElementById('btn-timer-pause').disabled = false;

  timerInterval = setInterval(() => {
    timerSeconds++;
    updateTimerDisplay();
  }, 1000);
}

function timerPause() {
  timerRunning = false;
  clearInterval(timerInterval);
  document.getElementById('timer-display').classList.remove('running');
  document.getElementById('timer-display').classList.add('paused');
  document.getElementById('btn-timer-start').disabled = false;
  document.getElementById('btn-timer-pause').disabled = true;
}

function timerReset() {
  timerPause();
  timerSeconds = 0;
  updateTimerDisplay();
  document.getElementById('timer-display').classList.remove('paused');
}

function updateTimerDisplay() {
  const h = Math.floor(timerSeconds / 3600);
  const m = Math.floor((timerSeconds % 3600) / 60);
  const s = timerSeconds % 60;
  const display = h > 0
    ? `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
    : `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
  document.getElementById('timer-display').textContent = display;
}

/* ============ RPE & STAR SELECTORS ============ */
function buildRpeSelector() {
  const container = document.getElementById('rpe-selector');
  for (let i = 1; i <= 10; i++) {
    const btn = document.createElement('button');
    btn.className = `rpe-btn ${i <= 4 ? 'rpe-low' : i <= 7 ? 'rpe-mid' : 'rpe-high'}`;
    btn.textContent = i;
    btn.type = 'button';
    btn.onclick = () => {
      container.querySelectorAll('.rpe-btn').forEach(b => b.classList.remove('selected'));
      btn.classList.add('selected');
      btn.dataset.value = i;
    };
    container.appendChild(btn);
  }
}

function buildStarSelector(containerId, count) {
  const container = document.getElementById(containerId);
  for (let i = 1; i <= count; i++) {
    const btn = document.createElement('button');
    btn.className = 'star-btn';
    btn.textContent = '\u2605';
    btn.type = 'button';
    btn.onclick = () => {
      container.querySelectorAll('.star-btn').forEach((b, idx) => {
        b.classList.toggle('selected', idx < i);
      });
      container.dataset.value = i;
    };
    container.appendChild(btn);
  }
}

function getSelectedRpe() {
  const sel = document.querySelector('#rpe-selector .rpe-btn.selected');
  return sel ? parseInt(sel.textContent) : null;
}

/* ============ LOG WORKOUT ============ */
async function logWorkout() {
  if (!currentAthleteId) return toast('Selecciona un atleta');
  const rpe = getSelectedRpe();
  if (!rpe) return toast('Selecciona un RPE');

  // Auto-pause timer if running
  if (timerRunning) timerPause();

  const data = {
    athlete_id: currentAthleteId,
    planned_workout_id: lastGeneratedWorkoutId || null,
    score: document.getElementById('log-score').value || null,
    rpe: rpe,
    went_rx: document.getElementById('log-rx').checked,
    notes: document.getElementById('log-notes').value || null,
    energy_level: parseInt(document.getElementById('energy-selector').dataset.value) || null,
    sleep_quality: parseInt(document.getElementById('sleep-selector').dataset.value) || null,
    duration_seconds: timerSeconds > 0 ? timerSeconds : null,
  };

  try {
    const result = await api('/logs', { method: 'POST', body: data });
    const fb = document.getElementById('log-feedback');
    fb.textContent = result.adaptation_feedback;
    fb.classList.remove('hidden');

    if (result.duration_seconds) {
      toast(`Registrado! Duraci\u00f3n: ${fmtDuration(result.duration_seconds)}`);
    } else {
      toast('Resultado registrado!');
    }

    // Reset form
    document.getElementById('log-score').value = '';
    document.getElementById('log-rx').checked = false;
    document.getElementById('log-notes').value = '';
    document.querySelectorAll('#rpe-selector .rpe-btn').forEach(b => b.classList.remove('selected'));
    document.querySelectorAll('.star-btn').forEach(b => b.classList.remove('selected'));
    document.getElementById('energy-selector').dataset.value = '';
    document.getElementById('sleep-selector').dataset.value = '';
    timerReset();
  } catch (e) {
    toast('Error: ' + e.message);
  }
}

/* ============ HISTORY ============ */
async function loadHistory() {
  if (!currentAthleteId) return;
  try {
    const data = await api(`/workouts/${currentAthleteId}/history?limit=${HISTORY_LIMIT}&offset=${historyOffset}`);
    const list = document.getElementById('history-list');

    if (data.workouts.length === 0) {
      list.innerHTML = '<p style="color:var(--text-muted);text-align:center;padding:40px">Sin entrenamientos a\u00fan. Genera tu primer WOD!</p>';
    } else {
      list.innerHTML = data.workouts.map(w => {
        const wodShort = (w.wod || '').split('\n')[0].substring(0, 60);
        return `
          <div class="history-item" onclick="showWorkoutDetail(${w.id})">
            <span class="history-date">${fmtDate(w.created_at)}</span>
            <span class="history-type">${w.workout_type || '?'}</span>
            <span class="history-wod">${wodShort}</span>
            <span class="history-logged ${w.has_log ? 'yes' : 'no'}">${w.has_log ? '\u2713' : '\u00b7'}</span>
          </div>
        `;
      }).join('');
    }

    const page = Math.floor(historyOffset / HISTORY_LIMIT) + 1;
    const totalPages = Math.ceil(data.total / HISTORY_LIMIT);
    document.getElementById('hist-page-info').textContent = `${page} / ${totalPages || 1}`;
    document.getElementById('hist-prev').disabled = historyOffset === 0;
    document.getElementById('hist-next').disabled = historyOffset + HISTORY_LIMIT >= data.total;
  } catch (e) {
    console.error('History error:', e);
  }
}

function historyPrev() { historyOffset = Math.max(0, historyOffset - HISTORY_LIMIT); loadHistory(); }
function historyNext() { historyOffset += HISTORY_LIMIT; loadHistory(); }

async function showWorkoutDetail(id) {
  try {
    const w = await api(`/workouts/detail/${id}`);
    // Navigate to WOD view and display it
    navigate('workout');
    document.getElementById('wod-warmup').textContent = w.warmup || '';
    if (w.strength) {
      document.getElementById('wod-strength').textContent = w.strength;
      document.getElementById('wod-strength-section').classList.remove('hidden');
    } else {
      document.getElementById('wod-strength-section').classList.add('hidden');
    }
    document.getElementById('wod-wod').textContent = w.wod || '';
    document.getElementById('wod-type-badge').textContent = w.workout_type || '';
    document.getElementById('wod-time-domain').textContent = `Dominio: ${w.target_time_domain || ''}`;
    document.getElementById('wod-modalities').textContent = (w.modalities || '').split(',').map(m => m.trim()).join(' + ');
    document.getElementById('wod-coaches').textContent = w.coaches_notes || '';
    document.getElementById('wod-scaling').textContent = w.scaling_notes || '';
    document.getElementById('wod-cooldown').textContent = w.cooldown || '';
    document.getElementById('wod-result').classList.remove('hidden');
    lastGeneratedWorkoutId = w.id;
  } catch (e) {
    toast('Error cargando workout');
  }
}

/* ============ PROGRESS ============ */
async function loadProgress() {
  if (!currentAthleteId) return;
  try {
    const [trends, prs] = await Promise.all([
      api(`/progress/${currentAthleteId}/trends?weeks=8`),
      api(`/progress/${currentAthleteId}/prs`),
    ]);

    const labels = trends.weeks.map(w => fmtDate(w.week_start));
    const rpeData = trends.weeks.map(w => w.avg_rpe);
    const rxData = trends.weeks.map(w => w.rx_percentage);
    const volData = trends.weeks.map(w => w.total_workouts);
    const modData = {
      mono: trends.weeks.map(w => w.modality_distribution.monostructural || 0),
      gym: trends.weeks.map(w => w.modality_distribution.gymnastics || 0),
      wl: trends.weeks.map(w => w.modality_distribution.weightlifting || 0),
    };

    // RPE chart
    chartRpe = renderLine('chart-rpe', chartRpe, labels, [
      { label: 'RPE', data: rpeData, borderColor: '#ff6b6b', backgroundColor: 'rgba(255,107,107,0.1)', fill: true },
    ], { suggestedMin: 0, suggestedMax: 10 });

    // Rx chart
    chartRx = renderLine('chart-rx', chartRx, labels, [
      { label: 'Rx %', data: rxData, borderColor: '#00b894', backgroundColor: 'rgba(0,184,148,0.1)', fill: true },
    ], { suggestedMin: 0, suggestedMax: 100 });

    // Volume chart
    chartVolume = renderBar('chart-volume', chartVolume, labels, [
      { label: 'Workouts', data: volData, backgroundColor: 'rgba(108,92,231,0.6)', borderColor: '#6c5ce7', borderWidth: 1 },
    ]);

    // Modalities stacked
    chartModalities = renderBar('chart-modalities', chartModalities, labels, [
      { label: 'Mono', data: modData.mono, backgroundColor: 'rgba(255,107,107,0.7)' },
      { label: 'Gymnastics', data: modData.gym, backgroundColor: 'rgba(108,92,231,0.7)' },
      { label: 'Weightlifting', data: modData.wl, backgroundColor: 'rgba(0,184,148,0.7)' },
    ], true);

    // PRs
    const prDiv = document.getElementById('prs-list');
    if (prs.records.length === 0) {
      prDiv.innerHTML = '<p style="color:var(--text-muted)">Sin records a\u00fan. A\u00f1ade benchmarks!</p>';
    } else {
      prDiv.innerHTML = prs.records.map(r =>
        `<div class="pr-card"><div class="pr-name">${r.name}</div><div class="pr-value">${r.value}</div><div class="pr-date">${fmtDate(r.recorded_at)}</div></div>`
      ).join('');
    }
  } catch (e) {
    console.error('Progress error:', e);
  }
}

/* ============ FEED ============ */
let feedTab = 'all';
let followingList = [];

async function loadFeed() {
  try {
    const url = feedTab === 'following' && currentAthleteId
      ? `/feed/${currentAthleteId}/following?limit=30`
      : '/feed?limit=30';
    const data = await api(url);
    const list = document.getElementById('feed-list');

    // Show/hide follow panel
    const followPanel = document.getElementById('feed-follow-panel');
    if (feedTab === 'following') {
      followPanel.classList.remove('hidden');
      await loadFollowing();
    } else {
      followPanel.classList.add('hidden');
    }

    if (data.entries.length === 0) {
      const msg = feedTab === 'following'
        ? 'No hay entrenamientos de las personas que sigues. Sigue a alguien para ver su actividad.'
        : 'No hay entrenamientos en el feed a\u00fan.';
      list.innerHTML = `<p style="color:var(--text-muted);text-align:center;padding:40px">${msg}</p>`;
      return;
    }

    list.innerHTML = data.entries.map((e, i) => {
      const initial = (e.athlete_name || '?')[0].toUpperCase();
      const wodText = e.wod_summary || 'Entrenamiento completado';
      const hasDetails = e.wod_full || e.warmup || e.strength;
      const expandBtn = hasDetails
        ? `<button class="btn btn-sm feed-expand-btn" onclick="toggleFeedDetail(${i})">Ver sesi\u00f3n completa</button>`
        : '';

      const detailSections = [];
      if (e.warmup) detailSections.push(`<div class="feed-detail-section"><h5>Warm-up</h5><pre>${e.warmup}</pre></div>`);
      if (e.strength) detailSections.push(`<div class="feed-detail-section"><h5>Fuerza / Skill</h5><pre>${e.strength}</pre></div>`);
      if (e.wod_full) detailSections.push(`<div class="feed-detail-section feed-detail-wod"><h5>WOD</h5><pre>${e.wod_full}</pre></div>`);
      if (e.scaling) detailSections.push(`<div class="feed-detail-section"><h5>Escalado</h5><pre>${e.scaling}</pre></div>`);
      if (e.cooldown) detailSections.push(`<div class="feed-detail-section"><h5>Cooldown</h5><pre>${e.cooldown}</pre></div>`);
      if (e.coaches_notes) detailSections.push(`<div class="feed-detail-section"><h5>Notas del Coach</h5><p>${e.coaches_notes}</p></div>`);

      return `
        <div class="feed-item">
          <div class="feed-header">
            <div class="feed-avatar">${initial}</div>
            <div>
              <div class="feed-name">${e.athlete_name}</div>
              <div class="feed-time">${fmtTimeAgo(e.completed_at)}</div>
            </div>
          </div>
          <div class="feed-body">${wodText}</div>
          <div class="feed-stats">
            ${e.workout_type ? `<span>${e.workout_type.toUpperCase()}</span>` : ''}
            ${e.rpe ? `<span>RPE: <b class="feed-stat-val">${e.rpe}</b></span>` : ''}
            ${e.went_rx ? '<span style="color:var(--success)">Rx \u2713</span>' : ''}
            ${e.duration_seconds ? `<span>Duraci\u00f3n: <b class="feed-stat-val">${fmtDuration(e.duration_seconds)}</b></span>` : ''}
            ${e.score ? `<span>Score: <b class="feed-stat-val">${e.score}</b></span>` : ''}
          </div>
          ${e.notes ? `<p style="margin-top:8px;font-size:0.8rem;color:var(--text-muted);font-style:italic">"${e.notes}"</p>` : ''}
          ${expandBtn}
          <div class="feed-detail hidden" id="feed-detail-${i}">
            ${detailSections.join('')}
          </div>
        </div>
      `;
    }).join('');
  } catch (e) {
    console.error('Feed error:', e);
  }
}

function toggleFeedDetail(idx) {
  const el = document.getElementById(`feed-detail-${idx}`);
  const btn = el.previousElementSibling;
  el.classList.toggle('hidden');
  btn.textContent = el.classList.contains('hidden') ? 'Ver sesi\u00f3n completa' : 'Ocultar sesi\u00f3n';
}

function switchFeedTab(tab) {
  feedTab = tab;
  document.getElementById('feed-tab-all').classList.toggle('active', tab === 'all');
  document.getElementById('feed-tab-following').classList.toggle('active', tab === 'following');
  loadFeed();
}

/* ============ FOLLOW SYSTEM ============ */

async function loadFollowing() {
  if (!currentAthleteId) return;
  try {
    const data = await api(`/athletes/${currentAthleteId}/follows`);
    followingList = data.following;

    // Render chips
    const container = document.getElementById('following-list');
    if (followingList.length === 0) {
      container.innerHTML = '<span style="color:var(--text-muted);font-size:0.8rem">No sigues a nadie a\u00fan</span>';
    } else {
      container.innerHTML = followingList.map(f => `
        <span class="follow-chip">
          ${f.followed_name}
          <button class="follow-chip-x" onclick="doUnfollow(${f.followed_id})">&times;</button>
        </span>
      `).join('');
    }

    // Populate follow select (exclude self + already following)
    const followedIds = new Set(followingList.map(f => f.followed_id));
    followedIds.add(currentAthleteId);
    const allAthletes = await api('/athletes');
    const sel = document.getElementById('follow-select');
    sel.innerHTML = '<option value="">Seguir a un atleta...</option>' +
      allAthletes.filter(a => !followedIds.has(a.id)).map(a =>
        `<option value="${a.id}">${a.name}</option>`
      ).join('');
  } catch (e) {
    console.error('Follow load error:', e);
  }
}

async function doFollow() {
  const sel = document.getElementById('follow-select');
  const followedId = parseInt(sel.value);
  if (!followedId || !currentAthleteId) return;

  try {
    await api(`/athletes/${currentAthleteId}/follow`, {
      method: 'POST',
      body: { follower_id: currentAthleteId, followed_id: followedId },
    });
    toast(`Ahora sigues a este atleta`);
    loadFeed();
  } catch (e) {
    toast(e.message);
  }
}

async function doUnfollow(followedId) {
  if (!currentAthleteId) return;
  try {
    await api(`/athletes/${currentAthleteId}/follow/${followedId}`, { method: 'DELETE' });
    toast('Dejaste de seguir');
    loadFeed();
  } catch (e) {
    toast(e.message);
  }
}

/* ============ CHART HELPERS ============ */
const CHART_DEFAULTS = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: { legend: { labels: { color: '#8888a0', font: { size: 11 } } } },
  scales: {
    x: { ticks: { color: '#8888a0', font: { size: 10 } }, grid: { color: 'rgba(255,255,255,0.04)' } },
    y: { ticks: { color: '#8888a0', font: { size: 10 } }, grid: { color: 'rgba(255,255,255,0.04)' } },
  }
};

function renderLine(canvasId, existingChart, labels, datasets, yOpts = {}) {
  if (existingChart) existingChart.destroy();
  const ctx = document.getElementById(canvasId).getContext('2d');
  return new Chart(ctx, {
    type: 'line',
    data: { labels, datasets: datasets.map(d => ({ ...d, tension: 0.3, pointRadius: 4, pointBackgroundColor: d.borderColor })) },
    options: { ...CHART_DEFAULTS, scales: { ...CHART_DEFAULTS.scales, y: { ...CHART_DEFAULTS.scales.y, ...yOpts } } }
  });
}

function renderBar(canvasId, existingChart, labels, datasets, stacked = false) {
  if (existingChart) existingChart.destroy();
  const ctx = document.getElementById(canvasId).getContext('2d');
  return new Chart(ctx, {
    type: 'bar',
    data: { labels, datasets },
    options: {
      ...CHART_DEFAULTS,
      scales: {
        x: { ...CHART_DEFAULTS.scales.x, stacked },
        y: { ...CHART_DEFAULTS.scales.y, stacked, beginAtZero: true },
      }
    }
  });
}

function renderDonut(canvasId, existingChart, setter, labels, data, colors) {
  if (existingChart) existingChart.destroy();
  const ctx = document.getElementById(canvasId).getContext('2d');
  const chart = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels,
      datasets: [{ data, backgroundColor: colors, borderWidth: 0 }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: '65%',
      plugins: { legend: { position: 'bottom', labels: { color: '#8888a0', padding: 16, font: { size: 11 } } } },
    }
  });
  setter(chart);
}
