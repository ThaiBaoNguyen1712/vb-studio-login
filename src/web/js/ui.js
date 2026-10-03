// ui.js — loading overlays, toast, confirm/prompt modal thay alert() mặc định.
// Bộ icon SVG dùng chung toàn app (stroke 1.8 đồng bộ với nav sidebar).
// Icon thương hiệu (logo MXH, chữ G Google) KHÔNG nằm ở đây — giữ nguyên.
const ICON_PATHS = {
  'check': '<path d="m5 13 4 4L19 7"/>',
  'x': '<path d="M6 18 18 6M6 6l12 12"/>',
  'bell': '<path d="M14.857 17.082a23.848 23.848 0 0 0 5.454-1.31A8.967 8.967 0 0 1 18 9.75V9A6 6 0 0 0 6 9v.75a8.967 8.967 0 0 1-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 0 1-5.714 0m5.714 0a3 3 0 1 1-5.714 0"/>',
  'refresh': '<path d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0 3.181 3.183a8.25 8.25 0 0 0 13.803-3.7M4.031 9.865a8.25 8.25 0 0 1 13.803-3.7l3.181 3.182m0-4.991v4.99"/>',
  'gear': '<path d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.324.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 0 1 1.37.49l1.296 2.247a1.125 1.125 0 0 1-.26 1.431l-1.003.827c-.293.24-.438.613-.431.992a6.759 6.759 0 0 1 0 .255c-.007.378.138.75.43.99l1.005.828c.424.35.534.954.26 1.43l-1.298 2.247a1.125 1.125 0 0 1-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.57 6.57 0 0 1-.22.128c-.331.183-.581.495-.644.869l-.213 1.28c-.09.543-.56.941-1.11.941h-2.594c-.55 0-1.02-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 0 1-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 0 1-1.369-.49l-1.297-2.247a1.125 1.125 0 0 1 .26-1.431l1.004-.827c.292-.24.437-.613.43-.992a6.932 6.932 0 0 1 0-.255c.007-.378-.138-.75-.43-.99l-1.004-.828a1.125 1.125 0 0 1-.26-1.43l1.297-2.247a1.125 1.125 0 0 1 1.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.087.22-.128.332-.183.582-.495.644-.869l.214-1.28Z"/><path d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z"/>',
  'moon': '<path d="M21.752 15.002A9.718 9.718 0 0 1 18 15.75c-5.385 0-9.75-4.365-9.75-9.75 0-1.33.266-2.597.748-3.752A9.753 9.753 0 0 0 12 21.75a9.753 9.753 0 0 0 9.752-6.748Z"/>',
  'sun': '<circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M4.93 4.93l1.41 1.41m11.32 11.32 1.41 1.41M2 12h2m16 0h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41"/>',
  'search': '<circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/>',
  'chev-down': '<path d="m6 9 6 6 6-6"/>',
  'chev-up': '<path d="m18 15-6-6-6 6"/>',
  'chev-left': '<path d="m15 18-6-6 6-6"/>',
  'chev-right': '<path d="m9 18 6-6-6-6"/>',
  'pencil': '<path d="M16.862 4.487l1.687-1.688a1.875 1.875 0 1 1 2.652 2.652L10.582 16.07a4.5 4.5 0 0 1-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 0 1 1.13-1.897l8.932-8.931Zm0 0 2.639 2.638M18 14v4.75A2.25 2.25 0 0 1 15.75 21H5.25A2.25 2.25 0 0 1 3 18.75V8.25A2.25 2.25 0 0 1 5.25 6H10"/>',
  'trash': '<path d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 0 1-2.244 2.077H8.084a2.25 2.25 0 0 1-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 0 0-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 0 1 3.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 0 0-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 0 0-7.5 0"/>',
  'lock-open': '<path d="M13.5 10.5V6.75a4.5 4.5 0 1 1 9 0v3.75M3.75 21.75h10.5a2.25 2.25 0 0 0 2.25-2.25v-6.75a2.25 2.25 0 0 0-2.25-2.25H3.75a2.25 2.25 0 0 0-2.25 2.25v6.75a2.25 2.25 0 0 0 2.25 2.25Z"/>',
  'star': '<path d="M11.48 3.499a.562.562 0 0 1 1.04 0l2.125 5.111a.563.563 0 0 0 .475.345l5.518.442c.499.04.701.663.321.988l-4.204 3.602a.563.563 0 0 0-.182.557l1.285 5.385a.562.562 0 0 1-.84.61l-4.725-2.885a.563.563 0 0 0-.586 0L6.982 20.54a.562.562 0 0 1-.84-.61l1.285-5.386a.562.562 0 0 0-.182-.557l-4.204-3.602a.563.563 0 0 1 .321-.988l5.518-.442a.563.563 0 0 0 .475-.345L11.48 3.5Z"/>',
  'star-solid': '<path d="M11.48 3.499a.562.562 0 0 1 1.04 0l2.125 5.111a.563.563 0 0 0 .475.345l5.518.442c.499.04.701.663.321.988l-4.204 3.602a.563.563 0 0 0-.182.557l1.285 5.385a.562.562 0 0 1-.84.61l-4.725-2.885a.563.563 0 0 0-.586 0L6.982 20.54a.562.562 0 0 1-.84-.61l1.285-5.386a.562.562 0 0 0-.182-.557l-4.204-3.602a.563.563 0 0 1 .321-.988l5.518-.442a.563.563 0 0 0 .475-.345L11.48 3.5Z"/>',
  'user': '<path d="M15.75 6a3.75 3.75 0 1 1-7.5 0 3.75 3.75 0 0 1 7.5 0ZM4.501 20.118a7.5 7.5 0 0 1 14.998 0A17.933 17.933 0 0 1 12 21.75c-2.676 0-5.216-.584-7.499-1.632Z"/>',
  'globe': '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a15 15 0 0 1 0 18 15 15 0 0 1 0-18Z"/>',
  'send': '<path d="M6 12 3.269 3.125A59.768 59.768 0 0 1 21.485 12 59.77 59.77 0 0 1 3.27 20.875L5.999 12Zm0 0h7.5"/>',
  'camera': '<path d="M6.827 6.175A2.31 2.31 0 0 1 5.186 7.23c-.38.054-.757.112-1.134.175C2.999 7.58 2.25 8.507 2.25 9.574V18a2.25 2.25 0 0 0 2.25 2.25h15A2.25 2.25 0 0 0 21.75 18V9.574c0-1.067-.75-1.994-1.802-2.169a47.865 47.865 0 0 0-1.134-.175 2.31 2.31 0 0 1-1.64-1.055l-.822-1.316a2.192 2.192 0 0 0-1.736-1.039 48.774 48.774 0 0 0-5.232 0 2.192 2.192 0 0 0-1.736 1.039l-.824 1.316Z"/><path d="M16.5 12.75a4.5 4.5 0 1 1-9 0 4.5 4.5 0 0 1 9 0Z"/>',
  'info': '<circle cx="12" cy="12" r="9"/><path d="M12 8h.01M12 12v4"/>',
  'check-circle': '<circle cx="12" cy="12" r="9"/><path d="m8.5 12.5 2.5 2.5 5-5.5"/>',
  'x-circle': '<circle cx="12" cy="12" r="9"/><path d="M9 9l6 6M15 9l-6 6"/>',
  'alert': '<path d="M12 9v4m0 4h.01M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z"/>',
  'eye': '<path d="M2.036 12.322a1.012 1.012 0 0 1 0-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178Z"/><path d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z"/>',
  'play': '<path d="M8 5.5v13l11-6.5-11-6.5Z"/>',
  'release': '<path d="M5.636 5.636a9 9 0 1 0 12.728 0M12 3v9"/>',
};
const ICON_FILL = { 'play': true, 'star-solid': true };
function icon(name, cls) {
  const p = ICON_PATHS[name];
  if (!p) return '';
  cls = cls || 'w-4 h-4 shrink-0';
  if (ICON_FILL[name]) return `<svg class="${cls}" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">${p}</svg>`;
  return `<svg class="${cls}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${p}</svg>`;
}
// Chấm trạng thái dùng chung cho bảng/report.
const STATUS_DOT_COLOR = { READY: 'bg-emerald-400', NOT_SETUP: 'bg-amber-400', IN_USE: 'bg-sky-400', EXPIRED: 'bg-red-400' };
function statusDot(status, label) {
  const color = STATUS_DOT_COLOR[status] || 'bg-slate-400';
  return `<span class="inline-flex items-center gap-1.5"><span class="w-2 h-2 rounded-full ${color} shrink-0"></span><span>${label || status}</span></span>`;
}
    // Loading Indicators (Blocking & Non-blocking Async)
    function showBlockingLoading(text = 'Đang xử lý, vui lòng chờ...') {
      const overlay = document.getElementById('blocking-loading-overlay');
      const txt = document.getElementById('blocking-loading-text');
      if (txt) txt.innerText = text;
      if (overlay) overlay.classList.remove('hidden');
    }

    function hideBlockingLoading() {
      const overlay = document.getElementById('blocking-loading-overlay');
      if (overlay) overlay.classList.add('hidden');
    }

    let asyncLoadingCount = 0;
    function showAsyncLoading(text = 'Đang đồng bộ...') {
      asyncLoadingCount++;
      const spinner = document.getElementById('async-spinner');
      const txt = document.getElementById('async-spinner-text');
      if (txt && text) txt.innerText = text;
      if (spinner) spinner.classList.remove('hidden');
    }

    function hideAsyncLoading() {
      asyncLoadingCount = Math.max(0, asyncLoadingCount - 1);
      if (asyncLoadingCount === 0) {
        const spinner = document.getElementById('async-spinner');
        if (spinner) spinner.classList.add('hidden');
      }
    }

    // Kiểm tra kết nối ngầm (không hiển thị badge đồng bộ để tránh lộ thông tin)
    // Confirm / Prompt dạng toast-modal (thay alert/confirm/prompt mặc định)
    let _confirmResolve = null;
    function _closeConfirm(result) {
      const modal = document.getElementById('confirm-modal');
      if (modal) { modal.classList.add('hidden'); modal.classList.remove('flex'); }
      if (_confirmResolve) { _confirmResolve(result); _confirmResolve = null; }
    }
    function showConfirm({ title = 'Xác nhận', message = '', okText = 'Đồng ý', okDanger = true } = {}) {
      return new Promise((resolve) => {
        const modal = document.getElementById('confirm-modal');
        document.getElementById('confirm-title').innerText = title;
        document.getElementById('confirm-message').innerText = message;
        document.getElementById('confirm-input-wrap').classList.add('hidden');
        const okBtn = document.getElementById('confirm-ok-btn');
        okBtn.innerText = okText;
        okBtn.className = okDanger
          ? 'px-5 py-2.5 bg-red-600 hover:bg-red-500 text-white rounded-xl text-sm font-bold transition-all'
          : 'px-5 py-2.5 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-sm font-bold transition-all';
        document.getElementById('confirm-cancel-btn').onclick = () => _closeConfirm(false);
        okBtn.onclick = () => _closeConfirm(true);
        modal.onclick = (e) => { if (e.target === modal) _closeConfirm(false); };
        modal.classList.remove('hidden');
        modal.classList.add('flex');
        _confirmResolve = resolve;
      });
    }
    function showPromptToast({ title = 'Nhập nội dung', message = '', placeholder = '', okText = 'Xác nhận' } = {}) {
      return new Promise((resolve) => {
        const modal = document.getElementById('confirm-modal');
        document.getElementById('confirm-title').innerText = title;
        document.getElementById('confirm-message').innerText = message;
        const wrap = document.getElementById('confirm-input-wrap');
        const inp = document.getElementById('confirm-input');
        wrap.classList.remove('hidden');
        inp.value = '';
        inp.placeholder = placeholder;
        const okBtn = document.getElementById('confirm-ok-btn');
        okBtn.innerText = okText;
        okBtn.className = 'px-5 py-2.5 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-sm font-bold transition-all';
        document.getElementById('confirm-cancel-btn').onclick = () => _closeConfirm(null);
        okBtn.onclick = () => _closeConfirm(inp.value);
        modal.onclick = (e) => { if (e.target === modal) _closeConfirm(null); };
        modal.classList.remove('hidden');
        modal.classList.add('flex');
        _confirmResolve = resolve;
        setTimeout(() => inp.focus(), 80);
      });
    }
    document.addEventListener('keydown', (e) => {
      const modal = document.getElementById('confirm-modal');
      if (modal && !modal.classList.contains('hidden') && e.key === 'Escape') _closeConfirm(false);
    });

    // Toast Functionality (to, rõ, tỉ lệ chuẩn) + âm thanh hệ thống (nếu bật)
    function showToast(message, type = 'info') {
      try {
        if (typeof playSound === 'function') {
          playSound(type === 'info' ? 'info' : type);
        }
      } catch (e) {}
      const container = document.getElementById('toast-container');
      const toast = document.createElement('div');

      let border = 'border-blue-500/40 bg-blue-900/60 text-blue-100';
      let iconName = 'info';
      if (type === 'success') { border = 'border-emerald-500/40 bg-emerald-900/60 text-emerald-100'; iconName = 'check-circle'; }
      if (type === 'error') { border = 'border-red-500/40 bg-red-900/60 text-red-100'; iconName = 'x-circle'; }
      if (type === 'warning') { border = 'border-amber-500/40 bg-amber-900/60 text-amber-100'; iconName = 'alert'; }

      toast.className = `px-5 py-4 rounded-2xl border-2 ${border} glass shadow-2xl flex items-center gap-3 text-base font-bold pointer-events-auto transform transition-all duration-300 translate-y-3 opacity-0 leading-snug`;
      toast.innerHTML = `<span class="w-8 h-8 rounded-full bg-white/10 flex items-center justify-center shrink-0">${icon(iconName, 'w-4 h-4')}</span><span class="flex-1">${message}</span><button onclick="this.parentElement.remove()" class="shrink-0 w-8 h-8 flex items-center justify-center rounded-lg hover:bg-white/10 opacity-70 hover:opacity-100 transition-all">${icon('x', 'w-4 h-4')}</button>`;

      container.appendChild(toast);
      // Giới hạn tối đa 4 toast cùng lúc
      while (container.children.length > 4) container.firstChild.remove();
      setTimeout(() => { toast.classList.remove('translate-y-3', 'opacity-0'); }, 10);
      setTimeout(() => {
        toast.classList.add('opacity-0', 'translate-y-3');
        setTimeout(() => toast.remove(), 300);
      }, 4500);
    }

    window.showConfirm = showConfirm;
    window.showPromptToast = showPromptToast;
    window.icon = icon;

