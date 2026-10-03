// vault.js — UI kho cookies mã hóa (trạng thái, mã hóa toàn bộ, xóa cookies).
    // ============ Kho cookies mã hóa ============
    async function renderVaultStatus() {
      const tbody = document.getElementById('vault-tbody');
      const summary = document.getElementById('vault-summary');
      if (!tbody) return;
      tbody.innerHTML = '<tr><td colspan="5" class="py-8 px-4 text-center text-slate-400 text-sm">Đang tải...</td></tr>';
      try {
        const rows = await window.pywebview.api.get_cookie_vault_status() || [];
        const bad = rows.filter(r => !r.encrypted && r.cookies_count > 0);
        if (summary) {
          summary.innerText = bad.length === 0
            ? `Tất cả cookies đã mã hóa (${rows.filter(r => r.cookies_count > 0).length} kênh có phiên).`
            : `Còn ${bad.length} kênh cookies chưa mã hóa — bấm "Mã hóa toàn bộ".`;
        }
        if (!rows.length) {
          tbody.innerHTML = '<tr><td colspan="5" class="py-10 px-4 text-center text-slate-400 text-sm">Chưa có kênh nào.</td></tr>';
          return;
        }
        tbody.innerHTML = rows.map(r => `
          <tr class="hover:bg-slate-50/50 dark:hover:bg-dark-input/50 transition-colors">
            <td class="py-3 px-4 text-sm font-bold text-slate-800 dark:text-slate-100">${r.channel_name} <span class="text-slate-400 font-normal text-xs">(#${r.channel_id})</span>${r.in_use_by ? ` <span class="text-[10px] text-sky-500">• đang mở: ${r.in_use_by}</span>` : ''}</td>
            <td class="py-3 px-4 text-center text-sm font-bold">${r.cookies_count}</td>
            <td class="py-3 px-4 text-center text-xs font-bold">${r.encrypted ? '<span class="text-emerald-500">Đã mã hóa</span>' : '<span class="text-amber-500">Plaintext</span>'}</td>
            <td class="py-3 px-4 text-xs text-slate-400">${r.last_synced_at || '-'}</td>
            <td class="py-3 px-4 text-right whitespace-nowrap">
              ${r.cookies_count > 0 ? `<button onclick="clearChannelCookies('${r.channel_id}')" class="px-3 py-1.5 bg-red-500/10 hover:bg-red-500/20 text-red-500 rounded-lg text-xs font-bold transition-all">Xóa cookies</button>` : '<span class="text-xs text-slate-400">—</span>'}
            </td>
          </tr>`).join('');
      } catch (err) {
        tbody.innerHTML = `<tr><td colspan="5" class="py-8 px-4 text-center text-red-400 text-sm">Lỗi tải: ${err}</td></tr>`;
      }
    }

    async function encryptAllCookies() {
      showBlockingLoading('Đang mã hóa toàn bộ cookies...');
      try {
        const res = await window.pywebview.api.encrypt_all_cookies();
        if (res && res.success) {
          showToast(`Đã mã hóa ${res.migrated || 0} phiên cookies!`, 'success');
          renderVaultStatus();
          await refreshData(true);
        } else {
          showToast((res && res.message) || 'Lỗi mã hóa!', 'error');
        }
      } catch (err) {
        showToast('Lỗi mã hóa: ' + err, 'error');
      } finally {
        hideBlockingLoading();
      }
    }

    async function clearChannelCookies(channelId) {
      const ok = await showConfirm({
        title: 'Xóa cookies',
        message: `Xóa toàn bộ cookies của kênh #${channelId}? Kênh sẽ về trạng thái "Chưa setup" và cần đăng nhập lại.`,
        okText: 'Xóa cookies'
      });
      if (!ok) return;
      showBlockingLoading('Đang xóa cookies...');
      try {
        const res = await window.pywebview.api.clear_channel_cookies(channelId);
        if (res && res.success) {
          showToast('Đã xóa cookies của kênh!', 'success');
          renderVaultStatus();
          await refreshData(true);
        } else {
          showToast((res && res.message) || 'Lỗi xóa cookies!', 'error');
        }
      } catch (err) {
        showToast('Lỗi xóa cookies: ' + err, 'error');
      } finally {
        hideBlockingLoading();
      }
    }
