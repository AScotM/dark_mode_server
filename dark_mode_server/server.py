import os
import json
import logging
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from threading import Semaphore
from pathlib import Path
import time
import socket

# Configuration
HOST = "0.0.0.0"
PORT = 3333
MAX_CONCURRENT_REQUESTS = 100

# Dark Mode CSS
DARK_THEME = """
:root {
    --bg: #121212;
    --text: #e0e0e0;
    --accent: #bb86fc;
    --border: #333;
}
body {
    font-family: 'Segoe UI', sans-serif;
    background: var(--bg);
    color: var(--text);
    margin: 0;
    padding: 20px;
    line-height: 1.6;
}
a {
    color: var(--accent);
    text-decoration: none;
}
a:hover {
    text-decoration: underline;
}
.container {
    max-width: 800px;
    margin: 0 auto;
    background: #1e1e1e;
    border-radius: 8px;
    padding: 20px;
    box-shadow: 0 4px 6px rgba(0,0,0,0.3);
}
.header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 20px;
    padding-bottom: 10px;
    border-bottom: 1px solid var(--border);
}
.file-list {
    margin: 0;
    padding: 0;
    list-style: none;
}
.file-item {
    display: flex;
    justify-content: space-between;
    padding: 8px 12px;
    margin: 4px 0;
    border-radius: 4px;
}
.file-item:hover {
    background: #333;
}
.file-size {
    color: #aaa;
    font-family: monospace;
}
"""

class DarkModeHTTPHandler(SimpleHTTPRequestHandler):
    """Modern dark mode file server with TCP stats endpoint"""
    
    semaphore = Semaphore(MAX_CONCURRENT_REQUESTS)
    
    def __init__(self, *args, **kwargs):
        self.base_path = Path(os.getcwd())
        super().__init__(*args, directory=str(self.base_path), **kwargs)
    
    def handle_one_request(self):
        """Thread-safe request handling with proper cleanup"""
        try:
            with self.semaphore:
                super().handle_one_request()
        except (ConnectionResetError, BrokenPipeError):
            logging.warning("Client disconnected prematurely")
        except Exception as e:
            logging.error(f"Request failed: {e}", exc_info=True)
        finally:
            self.close_connection = True
    
    def do_GET(self):
        """Route requests to appropriate handlers"""
        try:
            if self.path == '/tcpstates':
                self.handle_api()
            else:
                self.handle_file_or_dir()
        except Exception as e:
            self.send_error(500, f"Server error: {str(e)}")
    
    def handle_api(self):
        """TCP stats API endpoint"""
        response = json.dumps({
            'status': 'ok',
            'timestamp': time.time(),
            'host': socket.gethostname(),
            'message': 'VM-compatible dark mode server'
        }).encode('utf-8')
        
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(response)))
        self.end_headers()
        self.wfile.write(response)
    
    def handle_file_or_dir(self):
        """Serve files or directory listings with dark theme"""
        path = self.base_path / self.path.lstrip('/')
        
        if not path.exists():
            self.send_error(404, "Not Found")
            return
        
        if path.is_dir():
            self.send_directory_listing(path)
        else:
            super().do_GET()
    
    def send_directory_listing(self, path):
        """Generate beautiful dark mode directory listing"""
        try:
            title = f"Directory listing for /{path.relative_to(self.base_path)}"
            items = []
            
            # Add parent directory link
            if path != self.base_path:
                items.append(('../', 'Parent Directory', '-'))
            
            # Collect directory contents
            for item in sorted(path.iterdir()):
                if item.is_dir():
                    items.append((f"{item.name}/", 'Directory', '-'))
                else:
                    size = f"{item.stat().st_size/1024:.1f} KB" if item.stat().st_size > 0 else "0 KB"
                    items.append((item.name, 'File', size))
            
            # Generate HTML
            file_items = "\n".join(
                f'<li class="file-item">'
                f'<a href="{name}">{name}</a>'
                f'<span class="file-size">{size}</span>'
                f'</li>'
                for name, _, size in items
            )
            
            html = f"""<!DOCTYPE html>
<html>
<head>
    <title>{title}</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>{DARK_THEME}</style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{title}</h1>
            <small>{time.ctime()}</small>
        </div>
        <ul class="file-list">
            {file_items}
        </ul>
    </div>
</body>
</html>"""
            
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.send_header('Content-Length', str(len(html)))
            self.end_headers()
            self.wfile.write(html.encode('utf-8'))
            
        except Exception as e:
            self.send_error(500, f"Directory listing failed: {str(e)}")

def run_server():
    """Start the server with VM-friendly settings"""
    server = ThreadingHTTPServer((HOST, PORT), DarkModeHTTPHandler)
    server.allow_reuse_address = True  # Critical for VM environments
    server.daemon_threads = True       # Allow clean shutdown
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('server.log')
        ]
    )
    
    logging.info(f"Dark mode server running on http://{HOST}:{PORT}")
    logging.info("Available endpoints:")
    logging.info("  /tcpstates - API endpoint")
    logging.info("  /          - Dark mode file browser")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logging.info("Shutting down server...")
    finally:
        server.server_close()

if __name__ == "__main__":
    run_server()
