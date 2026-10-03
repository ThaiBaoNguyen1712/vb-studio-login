// accounts.js — CRUD tài khoản + kênh lẻ, upload logo, modal thêm/sửa.
    // Operator name (ô nhập tên người thao tác ở sidebar)
    function renderOperator() {
      const inp = document.getElementById('input-operator-name');
      if (inp) inp.value = appState.active_user;
      const av = document.getElementById('user-avatar');
      if (av) av.innerText = (appState.active_user || 'U')[0].toUpperCase();
    }

    async function saveOperatorName() {
      const inp = document.getElementById('input-operator-name');
      const name = (inp.value || '').trim() || 'Admin';
      appState.active_user = name;
      inp.value = name;
      document.getElementById('user-avatar').innerText = name[0].toUpperCase();
      try {
        await window.pywebview.api.save_settings({ general: { default_user: name } });
        if (!appState.settings.general) appState.settings.general = {};
        appState.settings.general.default_user = name;
      } catch (err) {
        console.error('Lỗi lưu tên người thao tác:', err);
      }
    }

    // Modals
    function renderBranchPlatforms() {
      const grid = document.getElementById('branch-platform-grid');
      if (!grid) return;
      const plats = appState.platforms || [];
      grid.innerHTML = plats.map(p => `
        <label class="flex items-center gap-2.5 p-3 bg-slate-100 dark:bg-dark-input border border-slate-200 dark:border-dark-border rounded-xl text-sm font-bold cursor-pointer hover:border-blue-500 transition-colors">
          <input type="checkbox" class="modal-acc-plat w-5 h-5 accent-blue-600" value="${p.code}" checked>
          ${platBadge(p.code, 'w-5 h-5')}<span class="truncate">${p.name || p.code}</span>
        </label>`).join('');
    }
    function renderTablePlatformOptions() {
      const sel = document.getElementById('table-platform-filter');
      if (!sel) return;
      const cur = sel.value || 'ALL';
      sel.innerHTML = '<option value="ALL">Mọi nền tảng</option>' +
        (appState.platforms || []).map(p => `<option value="${p.code}">${p.name || p.code}</option>`).join('');
      sel.value = cur;
    }
    function setBranchPlatforms(checked) {
      document.querySelectorAll('.modal-acc-plat').forEach(cb => { cb.checked = checked; });
    }

    function getBranchPlatforms() {
      return [...document.querySelectorAll('.modal-acc-plat')]
        .filter(cb => cb.checked)
        .map(cb => cb.value);
    }

    function getNextAccountId() {
      let maxNum = 0;
      (appState.accounts || []).forEach(a => {
        const m = (a.id || '').match(/(\d+)/);
        if (m) {
          const n = parseInt(m[1], 10);
          if (n > maxNum) maxNum = n;
        }
      });
      return String(maxNum + 1).padStart(2, '0');
    }

    // Logo tài khoản: preview + đọc dataURL (nén nhẹ về max 128px để JSON gọn)
    function previewAccountLogo(input, previewId) {
      const prev = document.getElementById(previewId);
      const file = input.files && input.files[0];
      if (!file) return;
      if (!file.type.startsWith('image/')) { showToast('Vui lòng chọn file ảnh!', 'error'); return; }
      const reader = new FileReader();
      reader.onload = () => {
        const img = new Image();
        img.onload = () => {
          const max = 128;
          const scale = Math.min(1, max / Math.max(img.width, img.height));
          const w = Math.max(1, Math.round(img.width * scale));
          const h = Math.max(1, Math.round(img.height * scale));
          const cv = document.createElement('canvas');
          cv.width = w; cv.height = h;
          cv.getContext('2d').drawImage(img, 0, 0, w, h);
          const dataUrl = cv.toDataURL('image/png');
          prev.src = dataUrl;
          prev.classList.remove('hidden');
          prev.dataset.dataurl = dataUrl;
        };
        img.src = reader.result;
      };
      reader.readAsDataURL(file);
    }
    function clearAccountLogo(inputId, previewId) {
      const inp = document.getElementById(inputId);
      const prev = document.getElementById(previewId);
      if (inp) inp.value = '';
      if (prev) { prev.src = ''; prev.classList.add('hidden'); prev.dataset.dataurl = ''; }
    }
    function getLogoDataUrl(previewId) {
      const prev = document.getElementById(previewId);
      return (prev && prev.dataset.dataurl) || '';
    }
    function setLogoPreview(previewId, dataUrl) {
      const prev = document.getElementById(previewId);
      if (!prev) return;
      if (dataUrl) { prev.src = dataUrl; prev.dataset.dataurl = dataUrl; prev.classList.remove('hidden'); }
      else { prev.src = ''; prev.dataset.dataurl = ''; prev.classList.add('hidden'); }
    }

    function openAddAccountModal() {
      const nextIdx = getNextAccountId();
      document.getElementById('modal-acc-name').value = `Tài khoản #${nextIdx}`;
      document.getElementById('modal-acc-email').value = '';
      document.getElementById('modal-acc-notes').value = '';
      clearAccountLogo('modal-acc-logo', 'modal-acc-logo-preview');
      setBranchPlatforms(true);
      document.getElementById('modal-add-account').classList.remove('hidden');
      setTimeout(() => document.getElementById('modal-acc-email').focus(), 100);
    }

    function openEditAccountModal(accountId) {
      const acc = (appState.accounts || []).find(a => a.id === accountId);
      if (!acc) { showToast('Không tìm thấy tài khoản!', 'error'); return; }
      document.getElementById('modal-editacc-id').value = acc.id;
      document.getElementById('modal-editacc-name').value = acc.display_name || '';
      document.getElementById('modal-editacc-email').value = acc.email || '';
      document.getElementById('modal-editacc-notes').value = acc.notes || '';
      document.getElementById('modal-editacc-logo').value = '';
      setLogoPreview('modal-editacc-logo-preview', acc.logo || '');
      document.getElementById('modal-edit-account').classList.remove('hidden');
    }

    async function submitEditAccount() {
      const id = document.getElementById('modal-editacc-id').value;
      const name = document.getElementById('modal-editacc-name').value.trim();
      const email = document.getElementById('modal-editacc-email').value.trim();
      const notes = document.getElementById('modal-editacc-notes').value.trim();
      const prev = document.getElementById('modal-editacc-logo-preview');
      const logo = (prev && !prev.classList.contains('hidden') && prev.dataset.dataurl) ? prev.dataset.dataurl : '';
      if (!name) { showToast('Vui lòng nhập tên tài khoản!', 'error'); return; }
      if (!email) { showToast('Vui lòng nhập Gmail!', 'error'); return; }
      showBlockingLoading('Đang lưu thay đổi tài khoản...');
      try {
        const acc = (appState.accounts || []).find(a => a.id === id);
        const res = await window.pywebview.api.update_account({
          id, display_name: name, email, notes,
          recovery_email: (acc && acc.recovery_email) || '',
          logo: logo || (acc && acc.logo) || ''
        });
        if (res && res.success) {
          closeModal('modal-edit-account');
          showToast('Đã cập nhật tài khoản!', 'success');
          await refreshData(true);
        } else {
          showToast('Lỗi cập nhật tài khoản!', 'error');
        }
      } catch (err) {
        showToast('Lỗi cập nhật: ' + err, 'error');
      } finally {
        hideBlockingLoading();
      }
    }

    async function submitAddAccount() {
      const nextIdx = getNextAccountId();
      const name = document.getElementById('modal-acc-name').value.trim();
      const email = document.getElementById('modal-acc-email').value.trim();
      const notes = document.getElementById('modal-acc-notes').value.trim();

      if (!name) {
        showToast('Vui lòng nhập tên tài khoản!', 'error');
        return;
      }
      if (!email) {
        showToast('Vui lòng nhập Gmail đăng nhập!', 'error');
        return;
      }

      showBlockingLoading('Đang lưu tài khoản và phân nhánh kênh...');
      try {
        const data = {
          id: `acc_${nextIdx}`,
          display_name: name,
          email: email,
          notes: notes || 'Tài khoản chính',
          logo: getLogoDataUrl('modal-acc-logo-preview')
        };
        const platforms = getBranchPlatforms();
        const res = await window.pywebview.api.create_account(data, platforms);
        if (res.success) {
          closeModal('modal-add-account');
          showToast(res.message, 'success');
          await refreshData(true);
        } else {
          showToast(res.message, 'error');
        }
      } catch (err) {
        showToast('Lỗi tạo tài khoản: ' + err, 'error');
      } finally {
        hideBlockingLoading();
      }
    }

    function onEditChannelPlatformChange() {
      // Đổi social -> tự điền URL mặc định của social đó (nếu ô đang trống)
      const code = document.getElementById('modal-edit-platform').value;
      const p = getPlatform(code);
      if (!p) return;
      const studioEl = document.getElementById('modal-edit-studio');
      const loginEl = document.getElementById('modal-edit-login');
      if (studioEl && !studioEl.value.trim() && p.studio_url) studioEl.value = p.studio_url;
      if (loginEl && !loginEl.value.trim() && p.login_url) loginEl.value = p.login_url;
    }

    function openEditChannelModal(channelId) {
      const ch = appState.channels.find(c => c.id === channelId);
      if (!ch) return;
      document.getElementById('modal-edit-id').value = ch.id;
      const platSel = document.getElementById('modal-edit-platform');
      const knownPlat = (appState.platforms || []).some(p => p.code === ch.platform);
      platSel.innerHTML = (appState.platforms || []).map(p => `<option value="${p.code}" ${p.code === ch.platform ? 'selected' : ''}>${p.name || p.code}</option>`).join('')
        + (knownPlat ? '' : `<option value="${ch.platform}" selected>${ch.platform} (đã xóa)</option>`);
      document.getElementById('modal-edit-name').value = ch.channel_name;
      document.getElementById('modal-edit-studio').value = ch.studio_url;
      document.getElementById('modal-edit-login').value = ch.login_url;

      const sel = document.getElementById('modal-edit-acc-select');
      sel.innerHTML = appState.accounts.map(a => `<option value="${a.id}" ${a.id === ch.account_id ? 'selected' : ''}>${a.display_name} (${a.id})</option>`).join('');

      const sub = document.getElementById('modal-edit-subtitle');
      if (sub) sub.innerText = `${platName(ch.platform)} • ID: ${ch.id} • ${ch.account_email || ''}`;

      document.getElementById('modal-edit-channel').classList.remove('hidden');
    }

    async function submitEditChannel() {
      showBlockingLoading('Đang lưu cập nhật kênh...');
      try {
        const data = {
          id: document.getElementById('modal-edit-id').value,
          platform: document.getElementById('modal-edit-platform').value,
          channel_name: document.getElementById('modal-edit-name').value.trim(),
          studio_url: document.getElementById('modal-edit-studio').value.trim(),
          login_url: document.getElementById('modal-edit-login').value.trim(),
          account_id: document.getElementById('modal-edit-acc-select').value
        };
        await window.pywebview.api.update_channel(data);
        closeModal('modal-edit-channel');
        showToast('Đã cập nhật kênh!', 'success');
        await refreshData(true);
      } catch (err) {
        showToast('Lỗi cập nhật: ' + err, 'error');
      } finally {
        hideBlockingLoading();
      }
    }

    function closeModal(modalId) {
      document.getElementById(modalId).classList.add('hidden');
    }

    function renderAccountFilters() {
      const sel = document.getElementById('select-account-filter');
      sel.innerHTML = '<option value="ALL">Tất cả Google Acc</option>' + 
        appState.accounts.map(a => `<option value="${a.id}">${a.display_name} (${a.id})</option>`).join('');
    }

    // ============ Thêm kênh lẻ cho 1 tài khoản ============
    function openAddChannelModal(accountId) {
      const acc = (appState.accounts || []).find(a => a.id === accountId);
      if (!acc) { showToast('Không tìm thấy tài khoản!', 'error'); return; }
      document.getElementById('modal-addch-account').value = accountId;
      const sub = document.getElementById('modal-addch-subtitle');
      if (sub) sub.innerText = `${acc.display_name} • ${acc.email || ''}`;
      const sel = document.getElementById('modal-addch-platform');
      sel.innerHTML = (appState.platforms || []).map(p => `<option value="${p.code}">${p.name || p.code}</option>`).join('');
      previewAddChannel();
      document.getElementById('modal-add-channel').classList.remove('hidden');
    }

    function previewAddChannel() {
      const code = document.getElementById('modal-addch-platform').value;
      const p = getPlatform(code);
      const box = document.getElementById('modal-addch-preview');
      if (!p || !box) return;
      box.innerHTML = `${platBadge(code, 'w-10 h-10')}
        <div class="min-w-0">
          <p class="text-sm font-bold text-slate-800 dark:text-slate-100">${p.name || p.code}</p>
          <p class="text-[11px] text-slate-400 truncate">Mở: ${p.studio_url || '-'}${p.login_url && p.login_url !== p.studio_url ? `<br>Login: ${p.login_url}` : ''}</p>
        </div>`;
    }

    async function submitAddChannel() {
      const accountId = document.getElementById('modal-addch-account').value;
      const code = document.getElementById('modal-addch-platform').value;
      showBlockingLoading('Đang thêm kênh...');
      try {
        const res = await window.pywebview.api.add_account_channel(accountId, code);
        if (res && res.success) {
          closeModal('modal-add-channel');
          showToast(res.message, 'success');
          await refreshData(true);
        } else {
          showToast((res && res.message) || 'Lỗi thêm kênh!', 'error');
        }
      } catch (err) {
        showToast('Lỗi thêm kênh: ' + err, 'error');
      } finally {
        hideBlockingLoading();
      }
    }
