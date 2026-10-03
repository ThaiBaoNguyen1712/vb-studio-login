// trash.js — thùng rác 30 ngày: liệt kê, khôi phục, xóa vĩnh viễn, dọn quá hạn.
    async function renderTrash() {
      const tbody = document.getElementById('trash-tbody');
      if (!tbody) return;
      tbody.innerHTML = '<tr><td colspan="5" class="py-8 px-4 text-center text-slate-400 text-sm">Đang tải...</td></tr>';
      try {
        const rows = await window.pywebview.api.get_trash() || [];
        if (!rows.length) {
          tbody.innerHTML = '<tr><td colspan="5" class="py-10 px-4 text-center text-slate-400 text-sm">Thùng rác trống.</td></tr>';
          return;
        }
        tbody.innerHTML = rows.map(r => {
          const kindLabel = r.kind === 'account' ? 'Tài khoản' : 'Kênh';
          const kindCls = r.kind === 'account' ? 'text-blue-500' : 'text-slate-500 dark:text-slate-300';
          let when = r.deleted_at || '-';
          try {
            const d = new Date(r.deleted_at);
            if (!isNaN(d)) when = d.toLocaleString('vi-VN', { hour: '2-digit', minute: '2-digit', day: '2-digit', month: '2-digit' });
          } catch (e) {}
          return `
          <tr class="hover:bg-slate-50/50 dark:hover:bg-dark-input/50 transition-colors">
            <td class="py-3 px-4 text-xs font-bold ${kindCls} whitespace-nowrap">${kindLabel}</td>
            <td class="py-3 px-4 text-sm font-bold text-slate-800 dark:text-slate-100">${r.name} <span class="text-slate-400 font-normal text-xs">(#${r.id})</span>${r.detail ? ` <span class="text-slate-400 font-normal text-xs">• ${r.detail}</span>` : ''}</td>
            <td class="py-3 px-4 text-xs text-slate-400 whitespace-nowrap">${when}</td>
            <td class="py-3 px-4 text-center text-xs font-bold ${r.days_left <= 5 ? 'text-red-400' : 'text-slate-400'} whitespace-nowrap">${r.days_left} ngày</td>
            <td class="py-3 px-4 text-right whitespace-nowrap">
              <button onclick="restoreTrash('${r.kind}', '${r.id}')" class="px-3 py-1.5 bg-emerald-600/10 hover:bg-emerald-600/20 text-emerald-500 rounded-lg text-xs font-bold transition-all">Khôi phục</button>
              <button onclick="deleteTrashForever('${r.kind}', '${r.id}')" class="px-3 py-1.5 bg-red-500/10 hover:bg-red-500/20 text-red-500 rounded-lg text-xs font-bold transition-all">Xóa vĩnh viễn</button>
            </td>
          </tr>`;
        }).join('');
      } catch (err) {
        tbody.innerHTML = `<tr><td colspan="5" class="py-8 px-4 text-center text-red-400 text-sm">Lỗi tải: ${err}</td></tr>`;
      }
    }

    async function restoreTrash(kind, itemId) {
      showBlockingLoading('Đang khôi phục...');
      try {
        const res = await window.pywebview.api.restore_trash(kind, itemId);
        if (res && res.success) {
          showToast('Đã khôi phục thành công!', 'success');
          await refreshData(true);
          renderTrash();
        } else {
          showToast((res && res.message) || 'Không khôi phục được!', 'error');
        }
      } catch (err) {
        showToast('Lỗi khôi phục: ' + err, 'error');
      } finally {
        hideBlockingLoading();
      }
    }

    async function deleteTrashForever(kind, itemId) {
      const ok = await showConfirm({
        title: 'Xóa vĩnh viễn',
        message: `Xóa vĩnh viễn "${itemId}" khỏi thùng rác? Không thể hoàn tác.`,
        okText: 'Xóa vĩnh viễn'
      });
      if (!ok) return;
      showBlockingLoading('Đang xóa vĩnh viễn...');
      try {
        const res = await window.pywebview.api.delete_trash_forever(kind, itemId);
        if (res && res.success) {
          showToast('Đã xóa vĩnh viễn!', 'info');
          renderTrash();
        } else {
          showToast((res && res.message) || 'Lỗi xóa!', 'error');
        }
      } catch (err) {
        showToast('Lỗi xóa: ' + err, 'error');
      } finally {
        hideBlockingLoading();
      }
    }

    async function purgeTrash() {
      showBlockingLoading('Đang dọn mục quá hạn...');
      try {
        const res = await window.pywebview.api.purge_trash();
        showToast(`Đã dọn ${res && res.purged ? res.purged : 0} mục quá hạn!`, 'success');
        renderTrash();
      } catch (err) {
        showToast('Lỗi dọn thùng rác: ' + err, 'error');
      } finally {
        hideBlockingLoading();
      }
    }
