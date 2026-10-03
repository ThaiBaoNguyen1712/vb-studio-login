// socials.js — quản lý registry mạng xã hội (thêm/sửa/xóa social).
    // ============ Quản lý socials (platform registry) ============
    function platformChannelCount(code) {
      return (appState.channels || []).filter(c => c.platform === code).length;
    }

    appState.social_sort = appState.social_sort || { key: null, dir: 1 };
    appState.social_q = appState.social_q || '';

    function sortSocialBy(key) {
      if (appState.social_sort.key === key) {
        appState.social_sort.dir *= -1;
      } else {
        appState.social_sort = { key, dir: 1 };
      }
      renderSocialsTable();
    }

    function onSocialSearchInput() {
      const el = document.getElementById('social-search');
      appState.social_q = (el ? el.value : '').trim().toLowerCase();
      renderSocialsTable();
    }

    function updateSocialSortIndicators() {
      ['name', 'code', 'channels'].forEach(k => {
        const el = document.getElementById('sort-soc-' + k);
        if (!el) return;
        el.innerHTML = appState.social_sort.key === k ? icon(appState.social_sort.dir === 1 ? 'chev-up' : 'chev-down', 'w-3 h-3 inline') : '';
      });
    }

    function getSocialRows() {
      let rows = [...(appState.platforms || [])];
      const q = (appState.social_q || '').toLowerCase();
      if (q) {
        rows = rows.filter(p =>
          (p.name || '').toLowerCase().includes(q) ||
          (p.code || '').toLowerCase().includes(q) ||
          (p.tag || '').toLowerCase().includes(q) ||
          (p.studio_url || '').toLowerCase().includes(q) ||
          (p.login_url || '').toLowerCase().includes(q)
        );
      }
      const { key, dir } = appState.social_sort || {};
      if (key === 'name') rows.sort((a, b) => String(a.name || a.code).localeCompare(String(b.name || b.code), 'vi') * dir);
      else if (key === 'code') rows.sort((a, b) => String(a.code).localeCompare(String(b.code)) * dir);
      else if (key === 'channels') rows.sort((a, b) => (platformChannelCount(a.code) - platformChannelCount(b.code)) * dir);
      return rows;
    }

    function renderSocialsTable() {
      const tbody = document.getElementById('socials-tbody');
      if (!tbody) return;
      updateSocialSortIndicators();
      const plats = getSocialRows();
      const counter = document.getElementById('social-result-count');
      if (counter) counter.innerText = `Hiển thị ${plats.length} / ${(appState.platforms || []).length} social`;
      if (!plats.length) {
        tbody.innerHTML = '<tr><td colspan="5" class="py-10 px-4 text-center text-slate-400 text-sm">Không có social nào khớp.</td></tr>';
        return;
      }
      tbody.innerHTML = plats.map(p => {
        const n = platformChannelCount(p.code);
        return `
          <tr class="hover:bg-slate-50/50 dark:hover:bg-dark-input/50 transition-colors">
            <td class="py-3 px-4">
              <span class="flex items-center gap-2.5 font-bold text-sm text-slate-800 dark:text-slate-100">
                ${platBadge(p.code, 'w-8 h-8')}
                <span>${p.name || p.code}${p.builtin ? ' <span class="text-[10px] font-bold text-slate-400">• mặc định</span>' : ''}</span>
              </span>
            </td>
            <td class="py-3 px-4 text-xs font-mono text-slate-500 dark:text-slate-400">${p.code}<br><span class="text-slate-400">prefix: ${p.prefix || '-'}</span></td>
            <td class="py-3 px-4 text-xs text-slate-500 dark:text-slate-400 max-w-[260px] truncate" title="${p.studio_url || ''}">${p.studio_url || '-'}<br><span class="text-slate-400">${p.login_url || ''}</span></td>
            <td class="py-3 px-4 text-center font-bold text-sm">${n}</td>
            <td class="py-3 px-4 text-right whitespace-nowrap">
              <button onclick="openPlatformModal('${p.code}')" class="px-3 py-1.5 bg-slate-200 dark:bg-slate-700 hover:bg-slate-300 dark:hover:bg-slate-600 rounded-lg text-xs font-bold transition-all">Sửa</button>
              <button onclick="deletePlatform('${p.code}')" class="px-3 py-1.5 bg-red-500/10 hover:bg-red-500/20 text-red-500 rounded-lg text-xs font-bold transition-all">Xóa</button>
            </td>
          </tr>`;
      }).join('');
    }

    function openPlatformModal(code) {
      const editing = code ? (appState.platforms || []).find(p => p.code === code) : null;
      document.getElementById('modal-platform-title').innerText = editing ? `Sửa social ${code}` : 'Thêm mạng xã hội';
      document.getElementById('modal-plat-editing').value = editing ? editing.code : '';
      const codeInput = document.getElementById('modal-plat-code');
      codeInput.value = editing ? editing.code : '';
      codeInput.disabled = !!editing;
      document.getElementById('modal-plat-prefix').value = editing ? (editing.prefix || '') : '';
      document.getElementById('modal-plat-name').value = editing ? (editing.name || '') : '';
      document.getElementById('modal-plat-studio').value = editing ? (editing.studio_url || '') : '';
      document.getElementById('modal-plat-login').value = editing ? (editing.login_url || '') : '';
      document.getElementById('modal-plat-logo').value = '';
      setLogoPreview('modal-plat-logo-preview', editing ? (editing.icon || '') : '');
      document.getElementById('modal-platform').classList.remove('hidden');
      if (!editing) setTimeout(() => codeInput.focus(), 100);
    }

    async function submitPlatform() {
      const editingCode = document.getElementById('modal-plat-editing').value;
      const logoIcon = getLogoDataUrl('modal-plat-logo-preview')
        || document.getElementById('modal-plat-logo-preview').src || '';
      const data = {
        code: (document.getElementById('modal-plat-code').value || '').trim().toUpperCase(),
        prefix: (document.getElementById('modal-plat-prefix').value || '').trim().toLowerCase(),
        name: (document.getElementById('modal-plat-name').value || '').trim(),
        tag: (document.getElementById('modal-plat-name').value || '').trim(),
        studio_url: (document.getElementById('modal-plat-studio').value || '').trim(),
        login_url: (document.getElementById('modal-plat-login').value || '').trim(),
        icon: logoIcon && !document.getElementById('modal-plat-logo-preview').classList.contains('hidden') ? logoIcon : ''
      };
      if (!editingCode && !data.icon) {
        // tự gợi ý prefix từ mã nếu bỏ trống
        if (!data.prefix && data.code) data.prefix = data.code.replace(/[^A-Z0-9]/g, '').slice(0, 3).toLowerCase();
      }
      showBlockingLoading('Đang lưu social...');
      try {
        const api = window.pywebview.api;
        const res = editingCode
          ? await api.update_platform(editingCode, data)
          : await api.create_platform(data);
        if (res && res.success) {
          closeModal('modal-platform');
          showToast(editingCode ? 'Đã cập nhật social!' : 'Đã thêm social mới!', 'success');
          await refreshData(true);
          renderSocialsTable();
        } else {
          showToast((res && res.message) || 'Lỗi lưu social!', 'error');
        }
      } catch (err) {
        showToast('Lỗi lưu social: ' + err, 'error');
      } finally {
        hideBlockingLoading();
      }
    }

    async function deletePlatform(code) {
      const n = platformChannelCount(code);
      const ok = await showConfirm({
        title: 'Xóa social',
        message: n > 0
          ? `Social '${code}' còn ${n} kênh đang dùng — xóa/chuyển các kênh này trước khi xóa social.`
          : `Xóa social '${code}' khỏi hệ thống? Các kênh đã tạo từ social này phải được xóa trước (hiện còn ${n}).`,
        okText: 'Xóa social'
      });
      if (!ok) return;
      showBlockingLoading('Đang xóa social...');
      try {
        const res = await window.pywebview.api.delete_platform(code);
        if (res && res.success) {
          showToast('Đã xóa social!', 'success');
          await refreshData(true);
          renderSocialsTable();
        } else {
          showToast((res && res.message) || 'Không xóa được social!', 'error');
        }
      } catch (err) {
        showToast('Lỗi xóa social: ' + err, 'error');
      } finally {
        hideBlockingLoading();
      }
    }

    async function resetPlatforms() {
      const ok = await showConfirm({
        title: 'Khôi phục mặc định',
        message: 'Khôi phục 4 socials mặc định (YouTube, TikTok, Facebook, Instagram)? Các social tự thêm được giữ lại.',
        okText: 'Khôi phục',
        okDanger: false
      });
      if (!ok) return;
      showBlockingLoading('Đang khôi phục socials mặc định...');
      try {
        const res = await window.pywebview.api.reset_platforms();
        showToast(`Đã khôi phục 4 socials mặc định${res && res.added ? ` (thêm ${res.added})` : ''}!`, 'success');
        await refreshData(true);
        renderSocialsTable();
      } catch (err) {
        showToast('Lỗi khôi phục: ' + err, 'error');
      } finally {
        hideBlockingLoading();
      }
    }
