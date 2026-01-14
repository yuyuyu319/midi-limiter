import os
import io
import mido
from flask import Flask, request, send_file, make_response

app = Flask(__name__)

# --- デザイン & コンテンツ & ピアノロールプレビュー統合HTML ---
HTML_PAGE = """
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MIDI Limiter | ピアノロール・プレビュー付範囲制限ツール</title>
    <meta name="description" content="MIDIベロシティを安全な範囲に制限。ピアノロールとベロシティレーンのダブルプレビューで、どのノートがリミット対象か一目で確認できます。">
    <script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-4758959657594096" crossorigin="anonymous"></script>
    <style>
        :root { --accent: #ff9100; --bg: #0f172a; --card: #1e293b; --text: #f8fafc; }
        body { background: var(--bg); color: var(--text); font-family: 'Inter', -apple-system, sans-serif; text-align: center; padding: 50px 20px; margin:0; line-height: 1.6; }
        .card { background: var(--card); padding: 40px; border-radius: 24px; max-width: 850px; margin: auto; border: 1px solid #334155; box-shadow: 0 20px 25px -5px rgba(0,0,0,0.3); }
        h1 { color: var(--accent); font-size: 2.5rem; margin-bottom: 10px; font-weight: 800; }
        .subtitle { color: #94a3b8; margin-bottom: 30px; font-size: 1.1rem; }
        .form-group { margin: 25px 0; text-align: left; max-width: 400px; margin-left: auto; margin-right: auto; }
        label { display: block; font-size: 0.9rem; color: #94a3b8; margin-bottom: 10px; font-weight: 600; }
        input[type="number"] { width: 100%; padding: 15px; background: #0f172a; border: 1px solid #334155; color: white; border-radius: 10px; font-size: 1.2rem; box-sizing: border-box; }
        button { background: var(--accent); color: white; border: none; padding: 18px; border-radius: 12px; font-weight: bold; cursor: pointer; width: 100%; font-size: 1.1rem; margin-top: 20px; transition: 0.2s; }
        button:hover { transform: translateY(-2px); opacity: 0.9; }

        /* プレビューエリア */
        #preview-container { margin-top: 30px; display: none; text-align: left; }
        .scroll-wrapper { width: 100%; overflow-x: auto; background: #0f172a; border: 1px solid #334155; border-radius: 8px; }
        canvas { display: block; }
        .legend { display: flex; justify-content: center; gap: 20px; font-size: 0.8rem; margin: 15px 0; color: #94a3b8; }
        .legend-item span { display: inline-block; width: 12px; height: 12px; border-radius: 2px; margin-right: 5px; }
        
        .link-box { margin-top: 25px; padding-top: 20px; border-top: 1px solid #334155; font-size: 0.8rem; color: #94a3b8; }
        .link-box a { text-decoration: none; font-weight: bold; margin: 0 4px; display: inline-block; }
        .link-box a.humanizer { color: #00e676; } .link-box a.normalizer { color: #00b0ff; }
        .link-box a.compressor { color: #d500f9; } .link-box a.expander { color: #ff5252; }

        .content-section { max-width: 850px; margin: 60px auto; text-align: left; background: rgba(30, 41, 59, 0.5); padding: 40px; border-radius: 20px; border: 1px solid #1e293b; }
        .content-section h2 { color: var(--accent); border-bottom: 2px solid #334155; padding-bottom: 10px; margin-top: 40px; }
        .policy-section { max-width: 850px; margin: 80px auto 0; text-align: left; padding: 30px; border-top: 1px solid #334155; color: #94a3b8; font-size: 0.85rem; }
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
                <input type="file" id="file-input" name="midi_file" accept=".mid,.midi" required style="color: #94a3b8;">
            </div>
            <div class="form-group">
                <label>最小ベロシティ (Min: 1-127)</label>
                <input type="number" name="min_v" id="min_v" value="40" min="1" max="127">
            </div>
            <div class="form-group">
                <label>最大ベロシティ (Max: 1-127)</label>
                <input type="number" name="max_v" id="max_v" value="100" min="1" max="127">
            </div>

            <div id="preview-container">
                <div class="legend">
                    <div class="legend-item"><span style="background: #475569;"></span>元の値</div>
                    <div class="legend-item"><span style="background: var(--accent);"></span>リミット後</div>
                </div>
                <div class="scroll-wrapper" id="scroll-wrapper">
                    <canvas id="piano-roll-canvas"></canvas>
                </div>
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
        <h2>MIDIリミッターのメリット</h2>
        <p>強すぎる音を抑え、弱すぎる音を底上げすることで、音源ソフトのポテンシャルを最大限に引き出し、ミックスを安定させます。ベロシティが最大値（127）に達した際の不自然な音色変化を防ぐのにも有効です。</p>
    </div>

    <div class="policy-section">
        <h2>プライバシーポリシー</h2>
        <p><strong>データ処理：</strong>アップロードされたMIDIファイルはサーバーに保存されず、メモリ内で即座に処理・返送されます。プライバシーは完全に守られます。</p>
        <p><strong>広告配信：</strong>当サイトではGoogle AdSense等の第三者配信事業者がCookieを利用して広告を配信する場合があります。</p>
    </div>
    <div class="footer-copy">&copy; 2026 MIDI Limiter. All rights reserved.</div>

    <script>
        const fileInput = document.getElementById('file-input');
        const canvas = document.getElementById('piano-roll-canvas');
        const ctx = canvas.getContext('2d');
        const minInput = document.getElementById('min_v');
        const maxInput = document.getElementById('max_v');
        let notes = [];

        fileInput.addEventListener('change', async (e) => {
            const file = e.target.files[0];
            if (!file) return;
            const buffer = await file.arrayBuffer();
            const view = new DataView(buffer);
            notes = [];
            for (let i = 0; i < view.byteLength - 2; i++) {
                if ((view.getUint8(i) & 0xF0) === 0x90) {
                    const pitch = view.getUint8(i + 1);
                    const vel = view.getUint8(i + 2);
                    if (vel > 0) notes.push({pitch, vel});
                }
            }
            document.getElementById('preview-container').style.display = 'block';
            draw();
        });

        [minInput, maxInput].forEach(el => el.addEventListener('input', draw));

        function draw() {
            if (notes.length === 0) return;
            const barWidth = 12;
            const pianoRollHeight = 120;
            const velocityLaneHeight = 80;
            const margin = 10;
            
            canvas.width = Math.max(document.getElementById('scroll-wrapper').clientWidth, notes.length * barWidth);
            canvas.height = pianoRollHeight + velocityLaneHeight + margin;
            ctx.clearRect(0, 0, canvas.width, canvas.height);

            const minV = parseInt(minInput.value);
            const maxV = parseInt(maxInput.value);

            notes.forEach((n, i) => {
                const x = i * barWidth;
                const yPitch = pianoRollHeight - (n.pitch / 127) * pianoRollHeight;
                ctx.fillStyle = '#334155';
                ctx.fillRect(x, yPitch, barWidth - 2, 4);

                const laneBaseY = canvas.height;
                const hOrig = (n.vel / 127) * velocityLaneHeight;
                ctx.fillStyle = '#475569';
                ctx.fillRect(x, laneBaseY - hOrig, barWidth - 2, hOrig);

                let newV = n.vel;
                if (newV < minV) newV = minV;
                if (newV > maxV) newV = maxV;
                const hNew = (newV / 127) * velocityLaneHeight;
                ctx.fillStyle = '#ff9100';
                ctx.fillRect(x, laneBaseY - hNew, barWidth - 2, hNew);
            });

            ctx.strokeStyle = '#334155';
            ctx.beginPath(); ctx.moveTo(0, pianoRollHeight); ctx.lineTo(canvas.width, pianoRollHeight); ctx.stroke();
            
            ctx.strokeStyle = 'rgba(255, 255, 255, 0.1)';
            ctx.setLineDash([5, 5]);
            [minV, maxV].forEach(val => {
                const y = canvas.height - (val / 127) * velocityLaneHeight;
                ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(canvas.width, y); ctx.stroke();
            });
        }
    </script>
</body>
</html>
"""

# --- MIDI処理ロジック ---
def process_limiter(midi_file_stream, min_v, max_v):
    midi_file_stream.seek(0)
    input_data = io.BytesIO(midi_file_stream.read())
    try:
        mid = mido.MidiFile(file=input_data)
    except:
        return None
    for track in mid.tracks:
        for msg in track:
            if msg.type == 'note_on' and msg.velocity > 0:
                if msg.velocity < min_v:
                    msg.velocity = min_v
                elif msg.velocity > max_v:
                    msg.velocity = max_v
                msg.velocity = max(1, min(127, msg.velocity))
    output = io.BytesIO()
    mid.save(file=output)
    output.seek(0)
    return output

@app.route('/')
def index():
    response = make_response(HTML_PAGE)
    response.headers['Content-Type'] = 'text/html; charset=utf-8'
    return response

@app.route('/process', methods=['POST'])
def process():
    file = request.files.get('midi_file')
    if not file: return "File missing", 400
    try:
        min_v = int(request.form.get('min_v', 40))
        max_v = int(request.form.get('max_v', 100))
    except ValueError: return "Invalid values", 400
    processed_midi = process_limiter(file, min_v, max_v)
    return send_file(processed_midi, as_attachment=True, download_name="limited.mid", mimetype='audio/midi')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
