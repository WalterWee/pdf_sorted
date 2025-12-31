import webview
from app import app
import threading
import urllib.request
import time

def run_server():
    app.run(host='127.0.0.1', port=5000, debug=False)

def on_closing():
    try:
        urllib.request.urlopen("http://127.0.0.1:5000/shutdown").read()
    except Exception as e:
        print(f"Error during shutdown: {e}")

if __name__ == '__main__':
    server_thread = threading.Thread(target=run_server)
    server_thread.daemon = True
    server_thread.start()

    url = f"http://127.0.0.1:5000/?t={int(time.time())}"
    
    window = webview.create_window(
        'PDF 回单分类工具',
        url,
        width=800,
        height=600,
        resizable=True
    )
    
    def on_loaded():
        window.evaluate_js("""
            window.addEventListener('dragover', e => { e.preventDefault(); });
            window.addEventListener('drop', e => { e.preventDefault(); });
        """)

    window.events.loaded += on_loaded
    window.events.closing += on_closing
    
    webview.start()