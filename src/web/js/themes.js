// themes.js — THEMES registry, buildThemeCSS, applyTheme, preview cards, toggle sáng/tối.
    // ============ Hệ theme (bộ màu + preview, dual / đơn sắc) ============
    const THEMES = [
      {
        id: 'ocean', name: 'Ocean Blue', mode: 'dual', modeLabel: 'Sáng + Tối',
        accent: { a400: '#60a5fa', a500: '#3b82f6', a600: '#2563eb', a700: '#1d4ed8' },
        dark: { bg: '#0b0f19', sidebar: '#111827', card: '#161f30', input: '#0d1321', border: '#1f293d' },
        light: { nav: '#e9f1fe', panel: '#f4f8ff' },
        grad: ['#3b82f6', '#6366f1', '#8b5cf6']
      },
      {
        id: 'emerald', name: 'Emerald Green', mode: 'dual', modeLabel: 'Sáng + Tối',
        accent: { a400: '#34d399', a500: '#10b981', a600: '#059669', a700: '#047857' },
        dark: { bg: '#090f0d', sidebar: '#0e1a14', card: '#122019', input: '#0b1410', border: '#1c2f25' },
        light: { nav: '#e6f6ee', panel: '#f2faf6' },
        grad: ['#10b981', '#14b8a6', '#0ea5e9']
      },
      {
        id: 'violet', name: 'Violet Purple', mode: 'dual', modeLabel: 'Sáng + Tối',
        accent: { a400: '#a78bfa', a500: '#8b5cf6', a600: '#7c3aed', a700: '#6d28d9' },
        dark: { bg: '#0c0a18', sidebar: '#141128', card: '#1a1533', input: '#100c22', border: '#2a2145' },
        light: { nav: '#efe9fd', panel: '#f5f2fe' },
        grad: ['#8b5cf6', '#a855f7', '#ec4899']
      },
      {
        id: 'sunset', name: 'Sunset Orange', mode: 'dual', modeLabel: 'Sáng + Tối',
        accent: { a400: '#fb923c', a500: '#f97316', a600: '#ea580c', a700: '#c2410c' },
        dark: { bg: '#120c07', sidebar: '#1a110a', card: '#221610', input: '#150e08', border: '#332217' },
        light: { nav: '#fdeee2', panel: '#fdf5ee' },
        grad: ['#f97316', '#ef4444', '#ec4899']
      },
      {
        id: 'rose', name: 'Rose Pink', mode: 'dual', modeLabel: 'Sáng + Tối',
        accent: { a400: '#fb7185', a500: '#f43f5e', a600: '#e11d48', a700: '#be123c' },
        dark: { bg: '#130a0e', sidebar: '#1c0f16', card: '#251220', input: '#170c12', border: '#3a1c2c' },
        light: { nav: '#fde9ef', panel: '#fdf2f5' },
        grad: ['#f43f5e', '#ec4899', '#a855f7']
      },
      {
        id: 'mono', name: 'Midnight Mono', mode: 'dark', modeLabel: 'Đơn sắc • Tối',
        accent: { a400: '#d1d5db', a500: '#9ca3af', a600: '#6b7280', a700: '#4b5563' },
        dark: { bg: '#0a0a0b', sidebar: '#111214', card: '#17181c', input: '#0e0f11', border: '#26282e' },
        light: { nav: '#eceef1', panel: '#f4f6f8' },
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

    function buildThemeCSS(t) {
      const A = t.accent, D = t.dark, G = t.grad;
      const P = `html[data-theme="${t.id}"]`;
      const imp = '!important';
      const soft = hexA(A.a500, 0.10), softBd = hexA(A.a500, 0.25);
      const css = [];
      // --- Accent: nút + chữ + viền ---
      css.push(`${P} .bg-blue-600{background-color:${A.a600}${imp}}`);
      css.push(`${P} .hover\\:bg-blue-500:hover{background-color:${A.a500}${imp}}`);
      css.push(`${P} .bg-blue-500{background-color:${A.a500}${imp}}`);
      css.push(`${P} .bg-blue-400{background-color:${A.a400}${imp}}`);
      css.push(`${P} .text-blue-600{color:${A.a600}${imp}}`);
      css.push(`${P} .text-blue-500{color:${A.a500}${imp}}`);
      css.push(`${P} .hover\\:text-blue-500:hover{color:${A.a500}${imp}}`);
      css.push(`${P} .text-blue-400{color:${A.a400}${imp}}`);
      css.push(`${P} .text-blue-300{color:${A.a400}${imp}}`);
      css.push(`${P} .text-blue-700,${P} .text-blue-800{color:${A.a700}${imp}}`);
      css.push(`${P} .hover\\:text-blue-800:hover{color:${A.a700}${imp}}`);
      css.push(`${P} .hover\\:text-blue-200:hover{color:${A.a400}${imp}}`);
      css.push(`${P} .border-blue-500{border-color:${A.a500}${imp}}`);
      css.push(`${P} .focus\\:border-blue-500:focus{border-color:${A.a500}${imp}}`);
      css.push(`${P} .accent-blue-600{accent-color:${A.a600}${imp}}`);
      css.push(`${P} .bg-blue-50{background-color:${soft}${imp}}`);
      css.push(`${P} .bg-blue-100{background-color:${hexA(A.a500, 0.16)}${imp}}`);
      css.push(`${P} .border-blue-200{border-color:${softBd}${imp}}`);
      css.push(`${P} .bg-blue-500\\/10{background-color:${soft}${imp}}`);
      css.push(`${P} .bg-blue-600\\/10{background-color:${soft}${imp}}`);
      css.push(`${P} .hover\\:bg-blue-600\\/20:hover{background-color:${hexA(A.a500, 0.2)}${imp}}`);
      css.push(`${P} .bg-blue-600\\/20{background-color:${hexA(A.a500, 0.2)}${imp}}`);
      css.push(`${P} .border-blue-500\\/20{border-color:${softBd}${imp}}`);
      css.push(`${P} .border-blue-500\\/40{border-color:${hexA(A.a500, 0.4)}${imp}}`);
      css.push(`${P} .border-blue-500\\/30{border-color:${hexA(A.a500, 0.3)}${imp}}`);
      css.push(`${P} .border-blue-900\\/40{border-color:${hexA(A.a700, 0.4)}${imp}}`);
      css.push(`${P} .bg-blue-900\\/60{background-color:${hexA(A.a700, 0.6)}${imp}}`);
      css.push(`${P} .bg-blue-950\\/30{background-color:${hexA(A.a700, 0.3)}${imp}}`);
      css.push(`${P} .text-blue-100,${P} .text-blue-200{color:${hexA(A.a400, 0.9)}${imp}}`);
      css.push(`${P} .shadow-blue-500\\/20{--tw-shadow-color:${hexA(A.a500, 0.2)}${imp}}`);
      css.push(`${P} .shadow-blue-600\\/20{--tw-shadow-color:${hexA(A.a600, 0.2)}${imp}}`);
      css.push(`${P} .shadow-blue-500\\/10{--tw-shadow-color:${hexA(A.a500, 0.1)}${imp}}`);
      // --- Gradient thương hiệu ---
      ['from-blue-600', 'from-blue-500', 'from-blue-400', 'from-purple-600'].forEach(c => {
        css.push(`${P} .${c}{--tw-gradient-from:${G[0]} ${imp};--tw-gradient-to:transparent ${imp};--tw-gradient-stops:var(--tw-gradient-from),var(--tw-gradient-to)${imp}}`);
      });
      ['via-indigo-600', 'via-indigo-500', 'via-indigo-400'].forEach(c => {
        css.push(`${P} .${c}{--tw-gradient-to:transparent ${imp};--tw-gradient-stops:var(--tw-gradient-from),${G[1]},var(--tw-gradient-to)${imp}}`);
      });
      ['to-purple-600', 'to-purple-500', 'to-purple-400', 'to-indigo-600'].forEach(c => {
        css.push(`${P} .${c}{--tw-gradient-to:${G[2]}${imp}}`);
      });
      css.push(`${P} .bg-purple-600\\/10{background-color:${soft}${imp}}`);
      // --- Bề mặt dark mode ---
      css.push(`${P} .dark .dark\\:bg-dark-bg{background-color:${D.bg}${imp}}`);
      css.push(`${P} .dark .dark\\:bg-dark-sidebar{background-color:${D.sidebar}${imp}}`);
      css.push(`${P} .dark .dark\\:bg-dark-card{background-color:${D.card}${imp}}`);
      css.push(`${P} .dark .dark\\:bg-dark-input{background-color:${D.input}${imp}}`);
      css.push(`${P} .dark .dark\\:border-dark-border{border-color:${D.border}${imp}}`);
      css.push(`${P} .dark .dark\\:divide-dark-border>:not([hidden])~:not([hidden]){border-color:${D.border}${imp}}`);
      css.push(`${P} .dark .dark\\:hover\\:bg-dark-card:hover{background-color:${D.card}${imp}}`);
      // --- Nav + background chế độ SÁNG (chỉ khi không dark để không đè dark mode) ---
      const L = t.light || { nav: '#eef2f7', panel: '#f7f9fc' };
      const lite = `html:not(.dark)[data-theme="${t.id}"]`;
      css.push(`${lite} .thm-nav{background-color:${L.nav}${imp}}`);
      css.push(`${lite} .thm-header{background-color:${hexA(L.nav, 0.92)}${imp}}`);
      css.push(`${lite} .thm-panel{background-color:${L.panel}${imp}}`);
      // --- Màu cứng ở màn hình khóa (arbitrary values) ---
      css.push(`${P} .bg-\\[\\#0b0f19\\]{background-color:${D.bg}${imp}}`);
      css.push(`${P} .bg-\\[\\#161f30\\]{background-color:${D.card}${imp}}`);
      css.push(`${P} .border-\\[\\#1f293d\\]{border-color:${D.border}${imp}}`);
      css.push(`${P} .bg-\\[\\#0d1321\\]{background-color:${D.input}${imp}}`);
      return css.join('\n');
    }

    function setColorMode(isDark) {
      const html = document.documentElement;
      html.classList.toggle('dark', isDark);
      appState.theme = isDark ? 'Dark' : 'Light';
      const iconEl = document.getElementById('theme-icon');
      const txt = document.getElementById('theme-text');
      const dot = document.getElementById('theme-toggle-dot');
      if (iconEl) iconEl.innerHTML = icon(isDark ? 'moon' : 'sun', 'w-3.5 h-3.5');
      if (txt) txt.innerText = isDark ? 'Giao diện Tối' : 'Giao diện Sáng';
      if (dot) dot.className = isDark ? 'w-3.5 h-3.5 bg-white rounded-full transition-transform translate-x-3.5' : 'w-3.5 h-3.5 bg-white rounded-full transition-transform translate-x-0';
      try { localStorage.setItem('vb_color_mode', isDark ? 'dark' : 'light'); } catch (e) {}
    }

    function applyTheme(themeId) {
      const t = getTheme(themeId);
      document.documentElement.dataset.theme = t.id;
      const styleEl = document.getElementById('theme-style');
      if (styleEl) styleEl.textContent = buildThemeCSS(t);
      // Chế độ sáng/tối theo theme
      let isDark;
      if (t.mode === 'dark') isDark = true;
      else if (t.mode === 'light') isDark = false;
      else {
        try {
          const saved = localStorage.getItem('vb_color_mode');
          isDark = saved ? saved === 'dark' : document.documentElement.classList.contains('dark');
          if (!saved) isDark = true;
        } catch (e) { isDark = true; }
      }
      setColorMode(isDark);
      // Theme đơn sắc -> ẩn nút chuyển sáng/tối
      const wrap = document.getElementById('theme-toggle-wrap');
      if (wrap) wrap.classList.toggle('hidden', t.mode !== 'dual');
      try { localStorage.setItem('vb_theme_id', t.id); } catch (e) {}
      appState.theme_id = t.id;
      renderThemeCards();
    }

    function renderThemeCards() {
      const grid = document.getElementById('theme-grid');
      if (!grid) return;
      const active = getStoredThemeId();
      grid.innerHTML = THEMES.map(t => {
        const sel = t.id === active;
        const dots = [t.accent.a500, t.accent.a600, t.dark.card, t.dark.border, (t.light || {}).nav || '#eef2f7']
          .map(c => `<span class="w-5 h-5 rounded-full border border-black/20" style="background:${c}" title="${c}"></span>`).join('');
        return `
          <button onclick="applyTheme('${t.id}')" class="text-left p-3.5 rounded-xl border-2 transition-all ${sel ? 'border-blue-500 shadow-lg shadow-blue-500/10' : 'border-slate-200 dark:border-dark-border hover:border-slate-300 dark:hover:border-slate-600'} bg-slate-50 dark:bg-dark-input">
            <div class="flex items-center justify-between gap-2">
              <span class="text-sm font-extrabold text-slate-800 dark:text-slate-100">${t.name}</span>
              <span class="text-[10px] font-bold px-2 py-0.5 rounded-full ${t.mode === 'dual' ? 'bg-blue-500/10 text-blue-500' : 'bg-slate-500/10 text-slate-400'}">${t.modeLabel}</span>
            </div>
            <div class="mt-2.5 rounded-lg overflow-hidden border border-black/10">
              <div class="flex items-center gap-1 px-2 py-1.5" style="background:${t.dark.sidebar}">
                <span class="w-2 h-2 rounded-full" style="background:${t.accent.a500}"></span>
                <span class="h-1.5 rounded flex-1" style="background:${t.dark.border}"></span>
              </div>
              <div class="flex gap-1.5 p-2" style="background:${t.dark.bg}">
                <span class="h-7 flex-1 rounded" style="background:${t.dark.card}"></span>
                <span class="h-7 w-10 rounded text-[8px] font-bold text-white flex items-center justify-center" style="background:${t.accent.a600}">Mở</span>
              </div>
              <div class="h-1.5" style="background:linear-gradient(90deg, ${t.grad[0]}, ${t.grad[1]}, ${t.grad[2]})"></div>
            </div>
            <div class="mt-2.5 flex items-center justify-between gap-2">
              <span class="flex items-center gap-1.5">${dots}</span>
              <span class="text-[10px] font-mono text-slate-400">${t.accent.a600}</span>
            </div>
            ${sel ? `<p class="mt-1.5 text-[11px] font-bold text-blue-500 inline-flex items-center gap-1">${icon('check', 'w-3 h-3')}Đang dùng</p>` : ''}
          </button>`;
      }).join('');
    }

    // Dark/Light Theme Toggle
    function toggleTheme() {
      const t = getTheme(getStoredThemeId());
      if (t.mode !== 'dual') return; // theme đơn sắc: toggle bị khóa
      const html = document.documentElement;
      setColorMode(!html.classList.contains('dark'));
    }

    // Áp theme đã lưu ngay khi script chạy (tránh nháy màu)
    try { applyTheme(getStoredThemeId()); } catch (e) { console.warn('applyTheme:', e); }
