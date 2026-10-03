// auth.js — Google login/logout qua bridge, renderAuthUI, whitelist email.
    // Whitelist Google Accounts được cấp quyền sử dụng hệ thống
    const ALLOWED_EMAILS = [
      "gamingbao32@gmail.com",
      "nthaibao1712@gmail.com",
      "nhatvanwork@gmail.com"
    ];

    function isEmailAllowed(email) {
      if (!email) return false;
      return ALLOWED_EMAILS.includes(email.trim().toLowerCase());
    }

    // Google Authentication & Firebase Config UI Handlers
    function renderAuthUI() {
      const user = appState.auth_user;
      const authGate = document.getElementById('auth-gate-overlay');
      const gateErr = document.getElementById('auth-gate-error');
      const opLoggedIn = document.getElementById('operator-logged-in');
      const opAnon = document.getElementById('operator-anonymous');
      const stLoggedIn = document.getElementById('settings-auth-logged-in');
      const stLoggedOut = document.getElementById('settings-auth-logged-out');
      const authPill = document.getElementById('firebase-auth-status-pill');

      const isAuthorized = Boolean(user && user.email && isEmailAllowed(user.email));

      if (isAuthorized) {
        // Mở quyền truy cập: ẩn overlay màn hình khóa
        if (authGate) authGate.classList.add('hidden');
        cancelBrowserAuth();
        if (gateErr) {
          gateErr.innerText = '';
          gateErr.classList.add('hidden');
        }

        // Sidebar Operator Box
        if (opLoggedIn) opLoggedIn.classList.remove('hidden');
        if (opAnon) opAnon.classList.add('hidden');
        const opAv = document.getElementById('operator-google-avatar');
        if (opAv) {
          opAv.src = user.photoURL || './assets/logo.png';
          opAv.onerror = () => { opAv.src = './assets/logo.png'; };
        }
        const opName = document.getElementById('operator-google-name');
        if (opName) opName.innerText = user.displayName || user.email;
        const opEmail = document.getElementById('operator-google-email');
        if (opEmail) opEmail.innerText = user.email;

        // Settings Auth Card
        if (stLoggedIn) stLoggedIn.classList.remove('hidden');
        if (stLoggedOut) stLoggedOut.classList.add('hidden');
        const stAv = document.getElementById('settings-auth-avatar');
        if (stAv) {
          stAv.src = user.photoURL || './assets/logo.png';
          stAv.onerror = () => { stAv.src = './assets/logo.png'; };
        }
        const stName = document.getElementById('settings-auth-name');
        if (stName) stName.innerText = user.displayName || user.email;
        const stEmail = document.getElementById('settings-auth-email');
        if (stEmail) stEmail.innerText = user.email;
        const stUid = document.getElementById('settings-auth-uid');
        if (stUid) stUid.innerText = 'UID: ' + (user.uid || '-');

        if (authPill) {
          authPill.className = 'px-3 py-1 rounded-full text-xs font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20';
          authPill.innerText = 'Đã xác thực Google';
        }
      } else {
        // Khóa màn hình: hiển thị yêu cầu đăng nhập trước khi dùng
        if (authGate) authGate.classList.remove('hidden');

        // Sidebar Operator Box
        if (opLoggedIn) opLoggedIn.classList.add('hidden');
        if (opAnon) opAnon.classList.remove('hidden');

        // Settings Auth Card
        if (stLoggedIn) stLoggedIn.classList.add('hidden');
        if (stLoggedOut) stLoggedOut.classList.remove('hidden');

        if (authPill) {
          authPill.className = 'px-3 py-1 rounded-full text-xs font-bold bg-slate-100 dark:bg-dark-input text-slate-400';
          authPill.innerText = 'Chưa đăng nhập';
        }

        // Nếu email không nằm trong danh sách whitelist
        if (user && user.email && !isEmailAllowed(user.email)) {
          if (gateErr) {
            gateErr.innerText = `Tài khoản "${user.email}" không được cấp quyền truy cập hệ thống. Vui lòng liên hệ quản trị viên!`;
            gateErr.classList.remove('hidden');
          }
          logoutGoogle(true);
        }
      }

    }

    function cancelBrowserAuth() {
      const initBox = document.getElementById('auth-gate-initial');
      const waitBox = document.getElementById('auth-gate-waiting');
      if (initBox) initBox.classList.remove('hidden');
      if (waitBox) {
        waitBox.classList.add('hidden');
        waitBox.classList.remove('flex');
      }
    }

    async function loginWithGoogle() {
      // Chuyển màn hình đăng nhập sang trạng thái chờ xác thực trên web
      const initBox = document.getElementById('auth-gate-initial');
      const waitBox = document.getElementById('auth-gate-waiting');
      const gateErr = document.getElementById('auth-gate-error');
      if (gateErr) gateErr.classList.add('hidden');

      if (initBox) initBox.classList.add('hidden');
      if (waitBox) {
        waitBox.classList.remove('hidden');
        waitBox.classList.add('flex');
      }

      showAsyncLoading('Mở trình duyệt web để xác thực...');
      try {
        const res = await window.pywebview.api.start_google_auth();
        if (res && res.success) {
          showToast('Đã mở trình duyệt web. Vui lòng đăng nhập tài khoản Google của bạn trên trang web!', 'info');
        } else {
          cancelBrowserAuth();
          showToast('Không thể mở đăng nhập Google: ' + (res?.error || 'Lỗi không xác định'), 'error');
        }
      } catch (err) {
        cancelBrowserAuth();
        showToast('Lỗi gọi đăng nhập Google: ' + err, 'error');
      } finally {
        hideAsyncLoading();
      }
    }

    async function logoutGoogle(silent) {
      if (!silent) {
        const ok = await showConfirm({
          title: 'Đăng xuất',
          message: 'Đăng xuất tài khoản Google khỏi hệ thống? Lần mở tiếp theo sẽ cần đăng nhập lại.',
          okText: 'Đăng xuất'
        });
        if (!ok) return;
      }
      showAsyncLoading('Đang đăng xuất...');
      try {
        await window.pywebview.api.logout_google_auth();
      } catch (err) {
        showToast('Lỗi đăng xuất: ' + err, 'error');
      } finally {
        hideAsyncLoading();
      }
    }
