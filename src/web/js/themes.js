// themes.js — THEMES registry, buildThemeCSS, applyTheme, preview cards, toggle sáng/tối.
// Clean Semantic Design Token Engine (Milestone 1 / R5, P2.3)

const THEMES = [
  {
    id: 'ocean',
    name: 'Ocean Blue',
    mode: 'dual',
    modeLabel: 'Sáng + Tối',
    accent: {
      primary: '#3b82f6',
      hover: '#2563eb',
      a400: '#60a5fa',
      a500: '#3b82f6',
      a600: '#2563eb',
      a700: '#1d4ed8'
    },
    dark: {
      bg: '#0b0f19',
      surface: '#111827',
      elevated: '#161f30',
      textPrimary: '#f8fafc',
      textSecondary: '#94a3b8',
      textMuted: '#64748b',
      borderSubtle: '#1f293d',
      borderDefault: '#334155',
      card: '#161f30',
      sidebar: '#111827',
      input: '#0d1321',
      border: '#1f293d'
    },
    light: {
      bg: '#f0f4f9',
      surface: '#ffffff',
      elevated: '#e9f1fe',
      textPrimary: '#0f172a',
      textSecondary: '#475569',
      textMuted: '#64748b',
      borderSubtle: '#e2e8f0',
      borderDefault: '#cbd5e1',
      nav: '#e9f1fe',
      panel: '#f4f8ff'
    },
    grad: ['#3b82f6', '#6366f1', '#8b5cf6']
  },
  {
    id: 'emerald',
    name: 'Emerald Green',
    mode: 'dual',
    modeLabel: 'Sáng + Tối',
    accent: {
      primary: '#10b981',
      hover: '#059669',
      a400: '#34d399',
      a500: '#10b981',
      a600: '#059669',
      a700: '#047857'
    },
    dark: {
      bg: '#090f0d',
      surface: '#0e1a14',
      elevated: '#122019',
      textPrimary: '#f8fafc',
      textSecondary: '#94a3b8',
      textMuted: '#5f7367',
      borderSubtle: '#1c2f25',
      borderDefault: '#2a4436',
      card: '#122019',
      sidebar: '#0e1a14',
      input: '#0b1410',
      border: '#1c2f25'
    },
    light: {
      bg: '#edf7f2',
      surface: '#ffffff',
      elevated: '#e6f6ee',
      textPrimary: '#062319',
      textSecondary: '#335345',
      textMuted: '#5a7c6e',
      borderSubtle: '#d1ece0',
      borderDefault: '#b5dfcd',
      nav: '#e6f6ee',
      panel: '#f2faf6'
    },
    grad: ['#10b981', '#14b8a6', '#0ea5e9']
  },
  {
    id: 'violet',
    name: 'Violet Purple',
    mode: 'dual',
    modeLabel: 'Sáng + Tối',
    accent: {
      primary: '#8b5cf6',
      hover: '#7c3aed',
      a400: '#a78bfa',
      a500: '#8b5cf6',
      a600: '#7c3aed',
      a700: '#6d28d9'
    },
    dark: {
      bg: '#0c0a18',
      surface: '#141128',
      elevated: '#1a1533',
      textPrimary: '#f8fafc',
      textSecondary: '#a7a3c2',
      textMuted: '#6e6894',
      borderSubtle: '#2a2145',
      borderDefault: '#3c3061',
      card: '#1a1533',
      sidebar: '#141128',
      input: '#100c22',
      border: '#2a2145'
    },
    light: {
      bg: '#f4f1fa',
      surface: '#ffffff',
      elevated: '#efe9fd',
      textPrimary: '#1e1436',
      textSecondary: '#4c416a',
      textMuted: '#746797',
      borderSubtle: '#e4daf7',
      borderDefault: '#d0c1f0',
      nav: '#efe9fd',
      panel: '#f5f2fe'
    },
    grad: ['#8b5cf6', '#a855f7', '#ec4899']
  },
  {
    id: 'sunset',
    name: 'Sunset Orange',
    mode: 'dual',
    modeLabel: 'Sáng + Tối',
    accent: {
      primary: '#f97316',
      hover: '#ea580c',
      a400: '#fb923c',
      a500: '#f97316',
      a600: '#ea580c',
      a700: '#c2410c'
    },
    dark: {
      bg: '#120c07',
      surface: '#1a110a',
      elevated: '#221610',
      textPrimary: '#f8fafc',
      textSecondary: '#bcaaa0',
      textMuted: '#806e64',
      borderSubtle: '#332217',
      borderDefault: '#4c3323',
      card: '#221610',
      sidebar: '#1a110a',
      input: '#150e08',
      border: '#332217'
    },
    light: {
      bg: '#faf4ee',
      surface: '#ffffff',
      elevated: '#fdeee2',
      textPrimary: '#2e190c',
      textSecondary: '#634430',
      textMuted: '#916d55',
      borderSubtle: '#f7e0ce',
      borderDefault: '#f0ccb0',
      nav: '#fdeee2',
      panel: '#fdf5ee'
    },
    grad: ['#f97316', '#ef4444', '#ec4899']
  },
  {
    id: 'rose',
    name: 'Rose Pink',
    mode: 'dual',
    modeLabel: 'Sáng + Tối',
    accent: {
      primary: '#f43f5e',
      hover: '#e11d48',
      a400: '#fb7185',
      a500: '#f43f5e',
      a600: '#e11d48',
      a700: '#be123c'
    },
    dark: {
      bg: '#130a0e',
      surface: '#1c0f16',
      elevated: '#251220',
      textPrimary: '#f8fafc',
      textSecondary: '#bfa8b3',
      textMuted: '#826976',
      borderSubtle: '#3a1c2c',
      borderDefault: '#542940',
      card: '#251220',
      sidebar: '#1c0f16',
      input: '#170c12',
      border: '#3a1c2c'
    },
    light: {
      bg: '#faf1f4',
      surface: '#ffffff',
      elevated: '#fde9ef',
      textPrimary: '#2d0f1b',
      textSecondary: '#66394e',
      textMuted: '#966078',
      borderSubtle: '#f7d7e3',
      borderDefault: '#efbecf',
      nav: '#fde9ef',
      panel: '#fdf2f5'
    },
    grad: ['#f43f5e', '#ec4899', '#a855f7']
  },
  {
    id: 'mono',
    name: 'Midnight Mono',
    mode: 'dual',
    modeLabel: 'Sáng + Tối',
    accent: {
      primary: '#9ca3af',
      hover: '#6b7280',
      a400: '#d1d5db',
      a500: '#9ca3af',
      a600: '#6b7280',
      a700: '#4b5563'
    },
    dark: {
      bg: '#0a0a0b',
      surface: '#111214',
      elevated: '#17181c',
      textPrimary: '#f8fafc',
      textSecondary: '#9ca3af',
      textMuted: '#6b7280',
      borderSubtle: '#26282e',
      borderDefault: '#374151',
      card: '#17181c',
      sidebar: '#111214',
      input: '#0e0f11',
      border: '#26282e'
    },
    light: {
      bg: '#f4f5f7',
      surface: '#ffffff',
      elevated: '#eceef1',
      textPrimary: '#111827',
      textSecondary: '#4b5563',
      textMuted: '#6b7280',
      borderSubtle: '#e5e7eb',
      borderDefault: '#d1d5db',
      nav: '#eceef1',
      panel: '#f4f6f8'
    },
    grad: ['#9ca3af', '#6b7280', '#374151']
  }
];

function getTheme(id) {
  return THEMES.find(t => t.id === id) || THEMES[0];
}

function getStoredThemeId() {
  try { return localStorage.getItem('vb_theme_id') || 'ocean'; } catch (e) { return 'ocean'; }
}

function hexA(hex, alpha) {
  const h = hex.replace('#', '');
  const r = parseInt(h.slice(0, 2), 16), g = parseInt(h.slice(2, 4), 16), b = parseInt(h.slice(4, 6), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

/**
 * Builds semantic CSS Custom Properties without utility overrides.
 * Strictly separates brand accent from status colors.
 */
function buildThemeCSS(t) {
  const P = `html[data-theme="${t.id}"]`;
  const A = t.accent, D = t.dark, L = t.light, G = t.grad;

  // Static semantic status colors (independent from theme brand accents)
  const STATUS = {
    success: '#10b981',
    warning: '#f59e0b',
    error: '#ef4444',
    info: '#3b82f6'
  };

  const css = [];

  // Light Mode Tokens
  css.push(`${P} {`);
  css.push(`  --bg-app: ${L.bg};`);
  css.push(`  --bg-surface: ${L.surface};`);
  css.push(`  --bg-elevated: ${L.elevated};`);
  css.push(`  --text-primary: ${L.textPrimary};`);
  css.push(`  --text-secondary: ${L.textSecondary};`);
  css.push(`  --text-muted: ${L.textMuted};`);
  css.push(`  --border-subtle: ${L.borderSubtle};`);
  css.push(`  --border-default: ${L.borderDefault};`);
  css.push(`  --accent-primary: ${A.primary};`);
  css.push(`  --accent-hover: ${A.hover};`);
  css.push(`  --status-success: ${STATUS.success};`);
  css.push(`  --status-warning: ${STATUS.warning};`);
  css.push(`  --status-error: ${STATUS.error};`);
  css.push(`  --status-info: ${STATUS.info};`);
  css.push(`  --grad-start: ${G[0]};`);
  css.push(`  --grad-mid: ${G[1]};`);
  css.push(`  --grad-end: ${G[2]};`);
  css.push(`}`);

  // Dark Mode Tokens
  css.push(`${P}.dark, ${P} .dark {`);
  css.push(`  --bg-app: ${D.bg};`);
  css.push(`  --bg-surface: ${D.surface};`);
  css.push(`  --bg-elevated: ${D.elevated};`);
  css.push(`  --text-primary: ${D.textPrimary};`);
  css.push(`  --text-secondary: ${D.textSecondary};`);
  css.push(`  --text-muted: ${D.textMuted};`);
  css.push(`  --border-subtle: ${D.borderSubtle};`);
  css.push(`  --border-default: ${D.borderDefault};`);
  css.push(`  --accent-primary: ${A.primary};`);
  css.push(`  --accent-hover: ${A.hover};`);
  css.push(`  --status-success: ${STATUS.success};`);
  css.push(`  --status-warning: ${STATUS.warning};`);
  css.push(`  --status-error: ${STATUS.error};`);
  css.push(`  --status-info: ${STATUS.info};`);
  css.push(`  --grad-start: ${G[0]};`);
  css.push(`  --grad-mid: ${G[1]};`);
  css.push(`  --grad-end: ${G[2]};`);
  css.push(`}`);

  return css.join('\n');
}

function setColorMode(isDark) {
  const html = document.documentElement;
  html.classList.toggle('dark', isDark);
  if (window.appState) appState.theme = isDark ? 'Dark' : 'Light';
  const iconEl = document.getElementById('theme-icon');
  const txt = document.getElementById('theme-text');
  const dot = document.getElementById('theme-toggle-dot');
  if (iconEl && typeof icon === 'function') iconEl.innerHTML = icon(isDark ? 'moon' : 'sun', 'w-3.5 h-3.5');
  if (txt) txt.innerText = isDark ? 'Giao diện Tối' : 'Giao diện Sáng';
  if (dot) dot.className = isDark ? 'w-3.5 h-3.5 bg-white rounded-full transition-transform translate-x-3.5' : 'w-3.5 h-3.5 bg-white rounded-full transition-transform translate-x-0';
  try { localStorage.setItem('vb_color_mode', isDark ? 'dark' : 'light'); } catch (e) {}
  renderThemeCards();
}

function applyTheme(themeId) {
  const t = getTheme(themeId);
  document.documentElement.dataset.theme = t.id;
  const styleEl = document.getElementById('theme-style');
  if (styleEl) styleEl.textContent = buildThemeCSS(t);

  // Restore or default color mode
  let isDark = true;
  try {
    const saved = localStorage.getItem('vb_color_mode');
    if (saved) isDark = saved === 'dark';
    else isDark = document.documentElement.classList.contains('dark');
  } catch (e) { isDark = true; }
  setColorMode(isDark);

  // Show theme toggle wrap for all dual-mode themes
  const wrap = document.getElementById('theme-toggle-wrap');
  if (wrap) wrap.classList.remove('hidden');

  try { localStorage.setItem('vb_theme_id', t.id); } catch (e) {}
  if (window.appState) appState.theme_id = t.id;
  renderThemeCards();
}

function renderThemeCards() {
  const grid = document.getElementById('theme-grid');
  if (!grid) return;
  const active = getStoredThemeId();
  const isDark = document.documentElement.classList.contains('dark');
  grid.innerHTML = THEMES.map(t => {
    const sel = t.id === active;
    const p = isDark ? t.dark : t.light;
    const previewSurface = isDark ? p.surface : (p.nav || p.surface);
    const previewBg = p.bg;
    const previewElevated = isDark ? p.elevated : (p.panel || p.elevated);
    const previewBorder = p.borderSubtle;
    const dots = [t.accent.primary, t.accent.hover, p.surface, p.borderSubtle, p.elevated]
      .map(c => `<span class="w-5 h-5 rounded-full border border-black/20" style="background:${c}" title="${c}"></span>`).join('');
    return `
      <button onclick="applyTheme('${t.id}')" class="text-left p-3.5 rounded-xl border-2 transition-all ${sel ? 'border-blue-500 shadow-lg shadow-blue-500/10' : 'border-slate-200 dark:border-dark-border hover:border-slate-300 dark:hover:border-slate-600'} bg-slate-50 dark:bg-dark-input">
        <div class="flex items-center justify-between gap-2">
          <span class="text-sm font-extrabold text-slate-800 dark:text-slate-100">${t.name}</span>
          <span class="text-xs font-bold px-2 py-0.5 rounded-full bg-blue-500/10 text-blue-500">${t.modeLabel}</span>
        </div>
        <div class="mt-2.5 rounded-lg overflow-hidden border border-black/10">
          <div class="flex items-center gap-1 px-2 py-1.5" style="background:${previewSurface}">
            <span class="w-2 h-2 rounded-full" style="background:${t.accent.primary}"></span>
            <span class="h-1.5 rounded flex-1" style="background:${previewBorder}"></span>
          </div>
          <div class="flex gap-1.5 p-2" style="background:${previewBg}">
            <span class="h-7 flex-1 rounded" style="background:${previewElevated}"></span>
            <span class="h-7 w-10 rounded text-xs font-bold text-white flex items-center justify-center" style="background:${t.accent.primary}">Mở</span>
          </div>
          <div class="h-1.5" style="background:linear-gradient(90deg, ${t.grad[0]}, ${t.grad[1]}, ${t.grad[2]})"></div>
        </div>
        <div class="mt-2.5 flex items-center justify-between gap-2">
          <span class="flex items-center gap-1.5">${dots}</span>
          <span class="text-xs font-mono text-slate-400">${t.accent.primary}</span>
        </div>
        ${sel ? `<p class="mt-1.5 text-xs font-bold text-blue-500 inline-flex items-center gap-1">${typeof icon === 'function' ? icon('check', 'w-3 h-3') : '✓ '}Đang dùng</p>` : ''}
      </button>`;
  }).join('');
}

// Dark/Light Theme Toggle
function toggleTheme() {
  const html = document.documentElement;
  setColorMode(!html.classList.contains('dark'));
}

// Apply stored theme immediately on script load to prevent FOUC
try { applyTheme(getStoredThemeId()); } catch (e) { console.warn('applyTheme:', e); }
