"""
Mock Server for testing Playwright Crawler (Phase 1).
Uses only Python standard library http.server.
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.parse
import http.cookies
import sys
import random

PORT = 8888

# Simple database for validation
MOCK_USER = "admin"
MOCK_PASS = "admin123"
MOCK_CAPTCHA = "E8K9"

MOCK_ORDERS_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Supplier Portal - Orders</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; background-color: #f5f5f5; }
        h1 { color: #333; }
        table { width: 100%; border-collapse: collapse; margin-top: 20px; background: white; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
        th { background-color: #4CAF50; color: white; }
        tr:hover { background-color: #f1f1f1; }
    </style>
</head>
<body>
    <h1>Supplier Portal - Active Orders</h1>
    <p>Logged in successfully.</p>
    <table>
        <thead>
            <tr>
                <th>Order ID</th>
                <th>Vendor</th>
                <th>Order Date</th>
                <th>Total Amount</th>
                <th>Barcodes</th>
            </tr>
        </thead>
        <tbody>
            <tr>
                <td>ORD-2026-001</td>
                <td>Global Tech Solutions</td>
                <td>2026-05-24</td>
                <td>12500.50</td>
                <td>9780201379624, 9780201485677</td>
            </tr>
            <tr>
                <td>ORD-2026-002</td>
                <td>Vina Supply Corp</td>
                <td>2026-05-25</td>
                <td>4800.00</td>
                <td>8935001718224</td>
            </tr>
            <tr>
                <td>ORD-2026-003</td>
                <td>Invalid-Date-Order</td>
                <td>25-05-2026</td>
                <td>300.00</td>
                <td>12345</td>
            </tr>
            <tr>
                <td>ORD-2026-004</td>
                <td>Sino Logistics</td>
                <td>2026-05-23</td>
                <td>-150.00</td>
                <td>8935001718225</td>
            </tr>
        </tbody>
    </table>
    <a href="/logout">Logout</a>
</body>
</html>
"""

MOCK_LOGIN_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Supplier Portal - Login</title>
    <style>
        body {{ font-family: Arial, sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; background-color: #f0f2f5; margin: 0; }}
        .login-container {{ background: white; padding: 30px; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); width: 300px; }}
        h2 {{ margin-bottom: 20px; text-align: center; color: #1877f2; }}
        .form-group {{ margin-bottom: 15px; }}
        label {{ display: block; margin-bottom: 5px; font-weight: bold; color: #555; }}
        input[type="text"], input[type="password"] {{ width: 100%; padding: 8px; box-sizing: border-box; border: 1px solid #ccc; border-radius: 4px; }}
        .captcha-box {{ background: #eee; padding: 10px; text-align: center; font-weight: bold; font-size: 20px; letter-spacing: 5px; margin: 10px 0; border: 1px dashed #999; }}
        .btn {{ width: 100%; padding: 10px; background-color: #1877f2; border: none; color: white; font-weight: bold; border-radius: 4px; cursor: pointer; }}
        .btn:hover {{ background-color: #166fe5; }}
        .error {{ color: red; font-size: 14px; margin-bottom: 10px; text-align: center; }}
    </style>
</head>
<body>
    <div class="login-container">
        <h2>Portal Login</h2>
        {error_msg}
        <form method="POST" action="/login">
            <div class="form-group">
                <label for="username">Username</label>
                <input type="text" id="username" name="username" required>
            </div>
            <div class="form-group">
                <label for="password">Password</label>
                <input type="password" id="password" name="password" required>
            </div>
            <div class="form-group">
                <label>CAPTCHA Verification</label>
                <div class="captcha-box" id="captcha-container">{captcha_code}</div>
                <input type="text" id="captcha" name="captcha" placeholder="Enter CAPTCHA" required>
            </div>
            <button type="submit" class="btn">Login</button>
        </form>
    </div>
</body>
</html>
"""

class MockPortalHandler(BaseHTTPRequestHandler):
    def _get_cookie_session(self):
        cookie_header = self.headers.get('Cookie')
        if cookie_header:
            cookie = http.cookies.SimpleCookie(cookie_header)
            if 'session_id' in cookie:
                return cookie['session_id'].value
        return None

    def do_GET(self):
        session = self._get_cookie_session()
        
        if self.path == "/orders":
            if session == "mock_session_123":
                self.send_response(200)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                self.wfile.write(MOCK_ORDERS_HTML.encode('utf-8'))
            else:
                self.send_response(302)
                self.send_header("Location", "/login?error=unauthorized")
                self.end_headers()
                
        elif self.path.startswith("/login") or self.path == "/":
            query = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(query)
            error_msg = ""
            if "error" in params:
                err = params["error"][0]
                if err == "invalid":
                    error_msg = '<div class="error">Invalid username or password!</div>'
                elif err == "captcha":
                    error_msg = '<div class="error">Incorrect CAPTCHA!</div>'
                elif err == "unauthorized":
                    error_msg = '<div class="error">Please login first!</div>'
                    
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            html = MOCK_LOGIN_HTML.format(error_msg=error_msg, captcha_code=MOCK_CAPTCHA)
            self.wfile.write(html.encode('utf-8'))
            
        elif self.path == "/logout":
            self.send_response(302)
            self.send_header("Set-Cookie", "session_id=; Max-Age=0; Path=/")
            self.send_header("Location", "/login")
            self.end_headers()
            
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not Found")

    def do_POST(self):
        if self.path == "/login":
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length).decode('utf-8')
            params = urllib.parse.parse_qs(post_data)
            
            username = params.get("username", [""])[0]
            password = params.get("password", [""])[0]
            captcha = params.get("captcha", [""])[0]
            
            if captcha != MOCK_CAPTCHA:
                self.send_response(302)
                self.send_header("Location", "/login?error=captcha")
                self.end_headers()
                return

            if username == MOCK_USER and password == MOCK_PASS:
                self.send_response(302)
                self.send_header("Set-Cookie", "session_id=mock_session_123; Path=/")
                self.send_header("Location", "/orders")
                self.end_headers()
            else:
                self.send_response(302)
                self.send_header("Location", "/login?error=invalid")
                self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

def run(server_class=HTTPServer, handler_class=MockPortalHandler, port=PORT):
    server_address = ('', port)
    httpd = server_class(server_address, handler_class)
    print(f"Starting mock portal server on port {port}...")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    httpd.server_close()
    print("Mock portal server stopped.")

if __name__ == "__main__":
    port = PORT
    if len(sys.argv) > 1:
        port = int(sys.argv[1])
    run(port=port)
