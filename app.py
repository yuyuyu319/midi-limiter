import os
import io
import time
import mido
from flask import Flask, request, send_file, make_response

app = Flask(__name__)

# --- デザイン & コンテンツ ---
HTML_PAGE = """
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MIDI Limiter | ベロシティ範囲制限ツール</title>
    <meta name="description" content="MIDIのベロシティを音楽的に制限。強すぎる音を抑え、弱すぎる音を底上げすることで、ニュアンスを保ったままダイナミクスをコントロールします。">
    
    <script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-4758959657594096"
     crossorigin="anonymous"></script>

    <style>
        :root { --accent: #ff9100; --bg: #0f172a; --card: #1e293b; --text: #f8fafc; }
        body { background: var(--bg); color: var(--text); font-family: 'Inter', sans-serif; text-align: center; padding: 50px 20px; margin:0; line-height: 1.6; }
        .card { background: var(--card); padding: 40px; border-radius: 24px; max-width: 650px; margin: auto; border: 1px solid #334155; box-shadow: 0 20px 25px -5px rgba(0,0,0,0.3); }
        h1 { color: var(--accent); font-size: 2.5rem; margin-bottom: 10px; font-weight: 800; }
        .subtitle { color: #94a3b8; margin-bottom: 30px; font-size: 1.1rem; }
        .form-group { margin: 25px 0; text-align: left; max-width: 400px; margin-left: auto; margin-right: auto; }
        label { display: block; font-size: 0.9rem; color: #94a3b8; margin-bottom: 10px; font-weight: 600; }
        input[type="number"] { width: 100%; padding: 15px; background: #0f172a; border: 1px solid #334155; color: white; border-radius: 10px; font-size: 1.2rem; box-sizing: border-box; transition: 0.3s; }
        input[type="number"]:focus { border-color: var(--accent); outline: none; }
        button { background: var(--accent); color: white; border: none; padding: 18px; border-radius: 12px; font-weight: bold; cursor: pointer; width: 100%; font-size: 1.1rem; margin-top: 20px; transition: 0.2s; }
        button:hover { transform: translateY(-2px); opacity: 0.9; }
        
        /* 相互リンク用スタイル：全5ツールのカラーを反映 */
        .link-box { margin-top: 25px; padding-top: 20px; border-top: 1px solid #334155; font-size: 0.8rem; color: #94a3b8; }
        .link-box a { text-decoration: none; font-weight: bold; margin: 0 4px; display: inline-block; }
        .link-box a.humanizer { color: #00e676; }   /* 緑 */
        .link-box a.normalizer { color: #00b0ff; }  /* 青 */
        .link-box a.compressor { color: #d500f9; }  /* 紫 */
        .link-box a.expander { color: #ff5252; }    /* 赤 */

        .content-section { max-width: 700px; margin: 60px auto; text-align: left; background: rgba(30, 41, 59, 0.5); padding: 40px; border-radius: 20px; border: 1px solid #1e293b; }
        .content-section h2 { color: var(--accent); border-bottom: 2px solid #334155; padding-bottom: 10px; margin-top: 40px; }
        .policy-section { max-width: 600px; margin: 80px auto 0; text-align: left; padding: 30px; border-top: 1px solid #334155; color: #94a3b8; font-size: 0.85rem; }
        .policy-section h2 { color: #f8fafc; font-size: 1.1rem; border-left: 4px solid var(--accent); padding-left: 10px; margin-bottom: 15px; }
        .footer-copy { margin-top: 40px; font-size: 0.75rem; color: #475569; padding-bottom: 40px; }
    </style>
</head>
<body>
    <div class="card">
        <h1>MIDI Limiter</h1>
        <p class="subtitle">ベロシティの最大・最小値を、安全な範囲に制限する。</p>
        <form action="/process" method="post" enctype="multipart/form-data">
            <div style="margin-bottom: 25px; border: 2px dashed #334155; padding: 20px; border-radius: 12px;">
                <input type="file" name="midi_file" accept=".mid,.midi" required style="color: #94a3b8;">
            </div>
            <div class="form-group">
                <label>最小ベロシティ (Min: 1-127)</label>
                <input type="number" name="min_v" value="40" min="1" max="127">
            </div>
            <div class="form-group">
                <label>最大ベロシティ (Max: 1-127)</label>
                <input type="number" name="max_v" value="100" min="1" max="127">
            </div>
            <button type="submit">LIMIT & DOWNLOAD</button>
        </form>
        <div class="link-box">
            関連ツール: 
            <a href="https://midi-humanizer.onrender.com/" class="humanizer">Humanizer</a> | 
            <a href="https://midi-normalizer.onrender.com/" class="normalizer">Normalizer</a> | 
            <a href="https://midi-compressor.onrender.com/" class="compressor">Compressor</a> | 
            <a href="https://midi-expander.onrender.com/" class="expander">Expander</a>
        </div>
    </div>
    <div class="content-section">
        <h2>なぜMIDIリミッターが必要なのか？</h2>
        <p>強すぎる音を抑え、弱すぎる音を底上げすることで、音源ソフトのポテンシャルを最大限に引き出し、ミックスを安定させます。ベロシティが最大値（127）に達した際の不自然な音色変化を防ぐのにも有効です。</p>
    </div>
    <div class="policy-section">
        <h2>プライバシーポリシー</h2>
        <p>データは保存されずメモリ内で即座に処理されます。当サイトではGoogle AdSenseを利用しています。</p>
    </div>
    <div class="footer-copy">&copy; 2026 MIDI Limiter. All rights reserved.</div>
</body>
</html>
"""

def process_limiter(midi_file_stream, min_v, max_v):
    midi_file_stream.seek(0); input_data = io.BytesIO(midi_file_stream.read())
    try: mid = mido.MidiFile(file=input_data)
    except: return None
    for track in mid.tracks:
        for msg in track:
            if msg.type == 'note_on' and msg.velocity > 0:
                if msg.velocity < min_v: msg.velocity = min_v
                elif msg.velocity > max_v: msg.velocity = max_v
    output = io.BytesIO(); mid.save(file=output); output.seek(0); return output

@app.route('/')
def index():
    response = make_response(HTML_PAGE)
    response.headers['Content-Type'] = 'text/html; charset=utf-8'
    return response

@app.route('/process', methods=['POST'])
def process():
    file = request.files['midi_file']
    min_v = int(request.form.get('min_v', 1))
    max_v = int(request.form.get('max_v', 127))
    processed_midi = process_limiter(file, min_v, max_v)
    return send_file(processed_midi, as_attachment=True, download_name="limited.mid", mimetype='audio/midi')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
