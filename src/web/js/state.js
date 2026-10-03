// state.js — appState, platform registry helpers (platIcon/platName/platBadge), sort maps.
    // State
    let appState = {
      accounts: [],
      channels: [],
      platforms: [],
      settings: {},
      current_view: 'DASHBOARD',
      selected_platform: 'ALL',
      selected_account: 'ALL',
      selected_status: 'ALL',
      search_keyword: '',
      sort_order: 'DEFAULT',
      display_mode: (function(){ try { return localStorage.getItem('vb_display_mode') || 'HORIZONTAL'; } catch(e){ return 'HORIZONTAL'; } })(),
      active_user: 'Admin',
      auth_user: null,
      theme: 'Dark',
      access_requests: [],
      health_runs: [],
      health_selected_run: null
    };

    // Registry socials động từ backend (fallback 4 mặc định khi chưa tải)
    const PLATFORM_FALLBACK = {
      'YOUTUBE_SHORTS': { name: 'YouTube', icon: './assets/youtube.png' },
      'TIKTOK': { name: 'TikTok', icon: './assets/tiktok.png' },
      'FACEBOOK_REELS': { name: 'Facebook', icon: './assets/facebook.png' },
      'INSTAGRAM_REELS': { name: 'Instagram', icon: './assets/instagram.png' }
    };
    function getPlatform(code) {
      return (appState.platforms || []).find(p => p.code === code)
        || (PLATFORM_FALLBACK[code] ? { code, ...PLATFORM_FALLBACK[code] } : null);
    }
    function platIcon(code) {
      const p = getPlatform(code);
      return (p && p.icon) || './assets/logo.png';
    }
    function platName(code) {
      const p = getPlatform(code);
      return (p && (p.name || p.tag)) || code;
    }
    function platOrderMap() {
      const m = {};
      (appState.platforms || []).forEach((p, i) => { m[p.code] = i + 1; });
      return m;
    }
    // Badge logo social: có icon thì hiện ảnh, null thì badge chữ cái đầu (gradient theo mã)
    const PLAT_GRADS = [
      'from-blue-600 to-indigo-600', 'from-purple-600 to-pink-600',
      'from-emerald-600 to-teal-600', 'from-amber-500 to-orange-600',
      'from-sky-600 to-cyan-600', 'from-rose-600 to-red-600'
    ];
    function platGrad(code) {
      let h = 0;
      for (const c of (code || '?')) h = (h * 31 + c.charCodeAt(0)) >>> 0;
      return PLAT_GRADS[h % PLAT_GRADS.length];
    }
    function platBadge(code, sizeCls) {
      const p = getPlatform(code);
      const label = ((p && (p.name || p.tag || p.code)) || code || '?').replace(/"/g, '&quot;');
      const size = sizeCls || 'w-4 h-4';
      if (p && p.icon) {
        const iconSrc = String(p.icon).replace(/"/g, '&quot;');
        return `<img src="${iconSrc}" class="${size} object-contain shrink-0" onerror="this.outerHTML=platBadgeFallback('${code}', '${sizeCls || ''}')" title="${label}">`;
      }
      return platBadgeFallback(code, sizeCls);
    }
    function platBadgeFallback(code, sizeCls) {
      const p = getPlatform(code);
      const label = (((p && (p.name || p.tag || p.code)) || code || '?').replace(/"/g, '&quot;'));
      const initial = (label.trim()[0] || '?').toUpperCase();
      const size = sizeCls || 'w-4 h-4';
      const rounded = (sizeCls && /w-(8|10|14)/.test(sizeCls)) ? 'rounded-lg' : 'rounded-md';
      const txt = (sizeCls && /w-(8|10|14)/.test(sizeCls)) ? 'text-xs' : 'text-[9px]';
      return `<span class="${size} ${rounded} bg-gradient-to-br ${platGrad(code)} text-white font-extrabold ${txt} inline-flex items-center justify-center shrink-0" title="${label}">${initial}</span>`;
    }
