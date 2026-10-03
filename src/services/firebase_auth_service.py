import http.server
import json
import socket
import threading
import urllib.parse
import webbrowser
from typing import Optional, Callable, Dict, Any
from src.core.logger import logger
from src.services.settings_service import SettingsService


ALLOWED_EMAILS = [
    "gamingbao32@gmail.com",
    "nthaibao1712@gmail.com",
    "nhatvanwork@gmail.com"
]


class FirebaseAuthService:
    """Quản lý xác thực tài khoản cho ứng dụng VB-Studio Login."""

    def __init__(self, settings_service: SettingsService, on_auth_success: Optional[Callable[[Dict[str, Any]], None]] = None):
        self.settings_service = settings_service
        self.on_auth_success = on_auth_success
        self._server: Optional[http.server.HTTPServer] = None
        self._server_thread: Optional[threading.Thread] = None
        self._port = 52140

    def is_running(self) -> bool:
        return self._server is not None

    def get_auth_state(self) -> Dict[str, Any]:
        user = self.settings_service.get_auth_user()
        if user and user.get("email"):
            if user["email"].strip().lower() not in [e.lower() for e in ALLOWED_EMAILS]:
                self.settings_service.clear_auth_user()
                user = None

        fb = self.settings_service.settings.get("firebase", {})
        return {
            "is_authenticated": bool(user and user.get("email")),
            "user": user,
            "allowed_emails": ALLOWED_EMAILS,
            "config": {
                "url": fb.get("url", ""),
                "api_key": fb.get("api_key", ""),
                "auth_domain": fb.get("auth_domain", "vb-studio-login-sync.firebaseapp.com"),
                "project_id": fb.get("project_id", "vb-studio-login-sync"),
                "app_id": fb.get("app_id", ""),
                "enabled": fb.get("enabled", True),
            }
        }

    def start_auth_flow(self, callback_port: int = 52140) -> Dict[str, Any]:
        """
        Khởi chạy loopback server và mở trang xác thực Google trên trình duyệt mặc định.
        """
        # Tìm port rảnh trong dải 52140 - 52160
        port = callback_port
        for p in range(callback_port, callback_port + 20):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                if s.connect_ex(('127.0.0.1', p)) != 0:
                    port = p
                    break
        self._port = port

        # Đóng server cũ nếu còn chạy
        self.stop_server()

        service_ref = self

        class AuthHandler(http.server.BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                pass  # Tắt log console mặc định để giữ console sạch sẽ

                if parsed.path.startswith("/vendor/"):
                    import sys
                    from pathlib import Path
                    vendor_name = parsed.path.replace("/vendor/", "")
                    candidates = [
                        Path(getattr(sys, "_MEIPASS", "")) / "src" / "web" / "vendor" / vendor_name if getattr(sys, "_MEIPASS", "") else None,
                        Path(__file__).resolve().parent.parent / "web" / "vendor" / vendor_name,
                        Path("src/web/vendor") / vendor_name,
                    ]
                    vendor_file = next((c for c in candidates if c and Path(c).exists()), None)
                    if vendor_file:
                        self.send_response(200)
                        self.send_header("Content-Type", "application/javascript; charset=utf-8")
                        self.end_headers()
                        self.wfile.write(Path(vendor_file).read_bytes())
                        return


                if parsed.path in ("/", "/auth", "/login"):
                    fb_config = {
                        "apiKey": service_ref.settings_service.get("firebase", "api_key", ""),
                        "authDomain": service_ref.settings_service.get("firebase", "auth_domain", "vb-studio-login-sync.firebaseapp.com"),
                        "databaseURL": service_ref.settings_service.get("firebase", "url", "https://vb-studio-login-sync-default-rtdb.asia-southeast1.firebasedatabase.app/"),
                        "projectId": service_ref.settings_service.get("firebase", "project_id", "vb-studio-login-sync"),
                        "appId": service_ref.settings_service.get("firebase", "app_id", ""),
                    }
                    html = service_ref.generate_auth_page_html(fb_config, service_ref._port)
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(html.encode("utf-8"))
                else:
                    self.send_response(404)
                    self.end_headers()

            def do_POST(self):
                if self.path == "/callback":
                    length = int(self.headers.get("Content-Length", 0))
                    body = self.rfile.read(length).decode("utf-8")
                    try:
                        data = json.loads(body)
                        email = (data.get("email") or "").strip().lower()
                        if email not in [e.lower() for e in ALLOWED_EMAILS]:
                            logger.warning(f"Từ chối đăng nhập: email {email} không có trong whitelist")
                            self.send_response(403)
                            self.send_header("Content-Type", "application/json")
                            self.send_header("Access-Control-Allow-Origin", "*")
                            self.end_headers()
                            self.wfile.write(json.dumps({
                                "success": False,
                                "error": "Tài khoản của bạn không được cấp quyền truy cập hệ thống. Vui lòng liên hệ quản trị viên!"
                            }).encode("utf-8"))
                            return

                        user_info = {
                            "uid": data.get("uid"),
                            "email": data.get("email"),
                            "displayName": data.get("displayName") or data.get("email") or "Google User",
                            "photoURL": data.get("photoURL"),
                            "idToken": data.get("idToken")
                        }
                        
                        # Lưu vào cấu hình
                        service_ref.settings_service.save_auth_user(user_info)
                        if user_info.get("displayName"):
                            service_ref.settings_service.settings.setdefault("general", {})["default_user"] = user_info["displayName"]
                            service_ref.settings_service.save_settings()

                        # Lưu API Key nếu được truyền lên từ trang đăng nhập
                        if data.get("apiKey") and not service_ref.settings_service.get("firebase", "api_key"):
                            service_ref.settings_service.settings.setdefault("firebase", {})["api_key"] = data["apiKey"]
                            service_ref.settings_service.save_settings()

                        logger.info(f"Xác thực Google Firebase thành công: {user_info['email']} ({user_info['displayName']})")

                        if service_ref.on_auth_success:
                            service_ref.on_auth_success(user_info)

                        self.send_response(200)
                        self.send_header("Content-Type", "application/json")
                        self.send_header("Access-Control-Allow-Origin", "*")
                        self.end_headers()
                        self.wfile.write(json.dumps({"success": True}).encode("utf-8"))
                    except Exception as err:
                        logger.error(f"Lỗi xử lý callback auth: {err}")
                        self.send_response(400)
                        self.send_header("Content-Type", "application/json")
                        self.end_headers()
                        self.wfile.write(json.dumps({"success": False, "error": str(err)}).encode("utf-8"))

            def do_OPTIONS(self):
                self.send_response(200)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "Content-Type")
                self.end_headers()

        try:
            self._server = http.server.ThreadingHTTPServer(("127.0.0.1", port), AuthHandler)
            self._server_thread = threading.Thread(target=self._server.serve_forever, daemon=True)
            self._server_thread.start()

            auth_url = f"http://localhost:{port}/"
            logger.info(f"Đã mở cổng xác thực tại: {auth_url}")

            # Mở trình duyệt mặc định để người dùng đăng nhập Google
            webbrowser.open(auth_url)
            return {"success": True, "auth_url": auth_url, "port": port}
        except Exception as e:
            logger.error(f"Không thể khởi động Auth loopback server: {e}")
            return {"success": False, "error": str(e)}

    def stop_server(self):
        if self._server:
            try:
                self._server.shutdown()
                self._server.server_close()
            except Exception:
                pass
            self._server = None
            self._server_thread = None

    def generate_auth_page_html(self, fb_config: dict, callback_port: int) -> str:
        """Tạo trang web xác thực Google Firebase chuẩn, giao diện hiện đại đồng bộ với VB-STUDIO."""
        api_key_val = fb_config.get("apiKey", "")
        auth_domain_val = fb_config.get("authDomain", "vb-studio-login-sync.firebaseapp.com")
        db_url_val = fb_config.get("databaseURL", "https://vb-studio-login-sync-default-rtdb.asia-southeast1.firebasedatabase.app/")
        project_id_val = fb_config.get("projectId", "vb-studio-login-sync")

        return f"""<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8">
  <title>VB-Studio Login • Xác thực Google</title>
  <script src="/vendor/firebase-app-compat.js"></script>
  <script src="/vendor/firebase-auth-compat.js"></script>
  <script>
    if (typeof firebase === 'undefined') {{
      var s1 = document.createElement('script');
      s1.src = 'https://www.gstatic.com/firebasejs/10.8.0/firebase-app-compat.js';
      document.head.appendChild(s1);
      var s2 = document.createElement('script');
      s2.src = 'https://www.gstatic.com/firebasejs/10.8.0/firebase-auth-compat.js';
      document.head.appendChild(s2);
    }}
  </script>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}

    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      background: #0b0f19;
      color: #f1f5f9;
      display: flex;
      align-items: center;
      justify-content: center;
      min-height: 100vh;
      padding: 20px;
    }}
    .card {{
      background: #161f30;
      border: 1px solid #1f293d;
      border-radius: 16px;
      padding: 32px;
      max-width: 440px;
      width: 100%;
      box-shadow: 0 20px 40px rgba(0, 0, 0, 0.4);
      text-align: center;
    }}
    .brand-title {{
      font-size: 20px;
      font-weight: 800;
      background: linear-gradient(135deg, #3b82f6, #8b5cf6);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      margin-bottom: 6px;
    }}
    .subtext {{
      font-size: 13px;
      color: #94a3b8;
      margin-bottom: 24px;
    }}
    .google-btn {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 12px;
      width: 100%;
      height: 48px;
      background: #ffffff;
      color: #1e293b;
      font-size: 14px;
      font-weight: 700;
      border-radius: 10px;
      border: none;
      cursor: pointer;
      transition: all 0.2s ease;
      box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    }}
    .google-btn:hover {{
      background: #f8fafc;
      transform: translateY(-1px);
      box-shadow: 0 6px 16px rgba(0,0,0,0.25);
    }}
    .google-btn:disabled {{
      opacity: 0.6;
      cursor: not-allowed;
      transform: none;
    }}
    .success-box {{
      display: none;
      background: rgba(16, 185, 129, 0.1);
      border: 1px solid rgba(16, 185, 129, 0.3);
      padding: 18px;
      border-radius: 12px;
      margin-top: 16px;
    }}
    .error-box {{
      display: none;
      background: rgba(239, 68, 68, 0.1);
      border: 1px solid rgba(239, 68, 68, 0.3);
      padding: 12px;
      border-radius: 10px;
      color: #f87171;
      font-size: 12px;
      margin-top: 16px;
      word-break: break-word;
    }}
    .input-group {{
      margin-top: 16px;
      text-align: left;
    }}
    .input-label {{
      display: block;
      font-size: 11px;
      font-weight: 700;
      color: #94a3b8;
      text-transform: uppercase;
      margin-bottom: 6px;
    }}
    .text-input {{
      width: 100%;
      height: 38px;
      background: #0d1321;
      border: 1px solid #1f293d;
      border-radius: 8px;
      padding: 0 12px;
      font-size: 13px;
      color: #f1f5f9;
      outline: none;
    }}
    .text-input:focus {{
      border-color: #3b82f6;
    }}
    .avatar-preview {{
      width: 56px;
      height: 56px;
      border-radius: 50%;
      border: 2px solid #10b981;
      margin: 0 auto 12px;
      object-fit: cover;
    }}
  </style>
</head>
<body>
  <div class="card">
    <div class="brand-title">VB-Studio Login</div>
    <div class="subtext">Đăng nhập hệ thống qua Google Firebase</div>

    <div id="api-key-container" style="display: {'none' if api_key_val else 'block'}; margin-bottom: 20px; text-align: left;">
      <p style="font-size: 12px; color: #fbbf24; margin-bottom: 8px; line-height: 1.4;">
        ⚠️ Hệ thống chưa có mã khóa kết nối. Vui lòng nhập mã khóa để tiếp tục:
      </p>
      <input type="text" id="input-api-key" placeholder="Nhập mã khóa..." value="{api_key_val}" class="text-input" style="font-family: monospace;">
    </div>

    <button id="btn-login" onclick="doGoogleLogin()" class="google-btn">
      <svg width="20" height="20" viewBox="0 0 48 48">
        <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/>
        <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"/>
        <path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"/>
        <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"/>
      </svg>
      <span>Đăng nhập với Google</span>
    </button>

    <div id="success-box" class="success-box">
      <img id="user-avatar" class="avatar-preview" src="" style="display: none;">
      <h3 id="user-name" style="color: #10b981; font-size: 15px; font-weight: 800;">Đăng nhập thành công!</h3>
      <p id="user-email" style="font-size: 12px; color: #94a3b8; margin-top: 4px;"></p>
      <p style="font-size: 11px; color: #64748b; margin-top: 10px;">Đang chuyển về VB-Studio Login... Tab này sẽ tự đóng.</p>
    </div>

    <div id="error-box" class="error-box"></div>
  </div>

  <script>
    let appConfig = {{
      apiKey: "{api_key_val}",
      authDomain: "{auth_domain_val}",
      databaseURL: "{db_url_val}",
      projectId: "{project_id_val}"
    }};

    function ensureInit(apiKey) {{
      if (apiKey) appConfig.apiKey = apiKey;
      if (!firebase.apps.length) {{
        firebase.initializeApp(appConfig);
      }}
    }}

    function getApiKey() {{
      const customKey = document.getElementById('input-api-key') ? document.getElementById('input-api-key').value.trim() : '';
      return customKey || appConfig.apiKey;
    }}

    async function handleAuthenticatedUser(user) {{
      const errBox = document.getElementById('error-box');
      const succBox = document.getElementById('success-box');
      const btn = document.getElementById('btn-login');
      const apiKey = getApiKey();
      const allowedEmails = ["gamingbao32@gmail.com", "nthaibao1712@gmail.com", "nhatvanwork@gmail.com"];
      const emailLower = (user.email || "").trim().toLowerCase();
      if (!allowedEmails.includes(emailLower)) {{
        await firebase.auth().signOut();
        btn.disabled = false;
        btn.innerHTML = '<span>Thử lại đăng nhập Google</span>';
        errBox.innerText = 'Tài khoản của bạn không được cấp quyền truy cập hệ thống. Vui lòng liên hệ quản trị viên!';
        errBox.style.display = 'block';
        return;
      }}

      const idToken = await user.getIdToken();

      btn.style.display = 'none';
      const apiBox = document.getElementById('api-key-container');
      if (apiBox) apiBox.style.display = 'none';

      if (user.photoURL) {{
        const av = document.getElementById('user-avatar');
        av.src = user.photoURL;
        av.style.display = 'block';
      }}
      document.getElementById('user-name').innerText = 'Xin chào, ' + (user.displayName || user.email);
      document.getElementById('user-email').innerText = user.email;
      succBox.style.display = 'block';

      // Gửi thông tin về loopback server cục bộ
      await fetch('/callback', {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{
          uid: user.uid,
          email: user.email,
          displayName: user.displayName || user.email,
          photoURL: user.photoURL,
          idToken: idToken,
          apiKey: apiKey
        }})
      }});

      setTimeout(() => {{
        window.close();
      }}, 1800);
    }}

    async function doGoogleLogin() {{
      const errBox = document.getElementById('error-box');
      const btn = document.getElementById('btn-login');
      errBox.style.display = 'none';

      const apiKey = getApiKey();
      if (!apiKey) {{
        errBox.innerText = 'Vui lòng nhập mã khóa để tiếp tục.';
        errBox.style.display = 'block';
        return;
      }}

      // QUAN TRỌNG: phải gọi signInWithPopup đồng bộ trong user-gesture (click).
      // Không await gì trước nó, nếu không browser coi là popup tự động -> auth/popup-blocked.
      ensureInit(apiKey);
      const provider = new firebase.auth.GoogleAuthProvider();
      provider.setCustomParameters({{ prompt: 'select_account' }});

      btn.disabled = true;
      btn.innerText = 'Đang mở cửa sổ Google...';

      let popupPromise = null;
      try {{
        popupPromise = firebase.auth().signInWithPopup(provider);
      }} catch (syncErr) {{
        // Một số trình duyệt chặn ngay khi gọi window.open
        console.warn('Popup bị chặn đồng bộ, chuyển sang redirect:', syncErr);
        errBox.innerText = 'Trình duyệt đã chặn popup. Đang chuyển sang đăng nhập chuyển hướng...';
        errBox.style.display = 'block';
        await firebase.auth().signInWithRedirect(provider);
        return;
      }}

      try {{
        const result = await popupPromise;
        if (result && result.user) {{
          await handleAuthenticatedUser(result.user);
        }}
      }} catch (err) {{
        console.error('Lỗi xác thực:', err);
        const code = (err && err.code) || '';
        if (code === 'auth/popup-blocked' || code === 'auth/cancelled-popup-request') {{
          // Fallback: dùng redirect nên không bao giờ bị popup-blocked nữa
          errBox.innerText = 'Trình duyệt đã chặn popup. Đang chuyển sang đăng nhập chuyển hướng, vui lòng chờ...';
          errBox.style.display = 'block';
          setTimeout(() => {{
            firebase.auth().signInWithRedirect(provider);
          }}, 600);
          return;
        }}
        if (code === 'auth/popup-closed-by-user') {{
          btn.disabled = false;
          btn.innerHTML = '<span>Thử lại đăng nhập Google</span>';
          errBox.innerText = 'Bạn đã đóng cửa sổ đăng nhập Google. Vui lòng bấm lại nút để thử lại (nếu vẫn bị chặn, hệ thống sẽ tự chuyển sang đăng nhập chuyển hướng).';
          errBox.style.display = 'block';
          return;
        }}
        if (code === 'auth/unauthorized-domain') {{
          btn.disabled = false;
          btn.innerHTML = '<span>Thử lại đăng nhập Google</span>';
          errBox.innerText = 'Lỗi cấu hình Firebase: domain ' + window.location.hostname + ' chưa được Authorized trong Firebase Console > Authentication > Settings > Authorized domains. Hãy thêm "localhost" vào đó rồi thử lại.';
          errBox.style.display = 'block';
          return;
        }}
        btn.disabled = false;
        btn.innerHTML = '<span>Thử lại đăng nhập Google</span>';
        errBox.innerText = 'Lỗi đăng nhập: ' + (err.message || err);
        errBox.style.display = 'block';
      }}
    }}

    // KHÔNG tự gọi doGoogleLogin() khi tải trang — browser sẽ block popup vì thiếu user-gesture.
    // Chỉ xử lý kết quả redirect (nếu user vừa quay về từ Google).
    window.addEventListener('DOMContentLoaded', async () => {{
      const apiKey = getApiKey();
      if (!apiKey) return;
      try {{
        ensureInit(apiKey);
        const btn = document.getElementById('btn-login');
        if (btn) {{
          btn.disabled = true;
          btn.innerText = 'Đang kiểm tra phiên đăng nhập...';
        }}
        const redirResult = await firebase.auth().getRedirectResult();
        if (redirResult && redirResult.user) {{
          await handleAuthenticatedUser(redirResult.user);
          return;
        }}
        // Đã có user đăng nhập từ trước (redirect xong reload, hoặc session còn)
        const current = firebase.auth().currentUser;
        if (current && current.email) {{
          await handleAuthenticatedUser(current);
          return;
        }}
      }} catch (e) {{
        console.log('getRedirectResult:', e);
      }} finally {{
        const btn = document.getElementById('btn-login');
        if (btn && btn.style.display !== 'none') {{
          btn.disabled = false;
          btn.innerHTML = '<span>Đăng nhập với Google</span>';
        }}
      }}
    }});
  </script>
</body>
</html>"""
