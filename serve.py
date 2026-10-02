from pathlib import Path
import argparse, http.server, socketserver, subprocess, sys, webbrowser, threading, time, os

ROOT=Path(__file__).resolve().parent

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--port",type=int,default=8080)
    ap.add_argument("--update",action="store_true")
    ap.add_argument("--no-browser",action="store_true")
    args=ap.parse_args()
    os.chdir(ROOT)
    if args.update:
        subprocess.run([sys.executable, str(ROOT/"scripts/update.py")], check=False)
    Handler=http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("127.0.0.1",args.port),Handler) as httpd:
        url=f"http://127.0.0.1:{args.port}"
        if not args.no_browser:
            threading.Timer(.7, lambda:webbrowser.open(url)).start()
        print("AI 前沿日报已启动：",url)
        try:httpd.serve_forever()
        except KeyboardInterrupt:pass

if __name__=="__main__":
    main()
