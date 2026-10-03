// sidebar.js — thu gọn/mở rộng toàn bộ sidebar (persist localStorage).
    // Sidebar thu gọn / mở rộng (di chuột vào để expand khi thu gọn)
    const SB_ICON_COLLAPSE = '<svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M9 3v18"/><path d="m15 18-6-6 6-6"/></svg>';
    const SB_ICON_EXPAND = '<svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M9 3v18"/><path d="m9 18 6-6-6-6"/></svg>';
    function applySidebarState() {
      let collapsed = false;
      try { collapsed = localStorage.getItem('vb_sidebar_collapsed') === '1'; } catch (e) {}
      const sb = document.getElementById('sidebar');
      if (sb) sb.classList.toggle('sb-collapsed', collapsed);
      const pinBtn = document.getElementById('sidebar-pin-btn');
      if (pinBtn) {
        pinBtn.innerHTML = collapsed ? SB_ICON_EXPAND : SB_ICON_COLLAPSE;
        pinBtn.title = collapsed ? 'Mở rộng thanh bên (đang thu gọn)' : 'Thu gọn thanh bên';
      }
    }
    function toggleSidebar() {
      let collapsed = false;
      try {
        collapsed = localStorage.getItem('vb_sidebar_collapsed') === '1';
        localStorage.setItem('vb_sidebar_collapsed', collapsed ? '0' : '1');
      } catch (e) {}
      applySidebarState();
    }
