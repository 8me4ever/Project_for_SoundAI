import os
import time
import webbrowser
import threading
from datetime import datetime
from flask import Flask, render_template, request, jsonify
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
from utils.baidu_transcriber import BaiduTranscriber

#加载环境文件
load_dotenv()
app = Flask(__name__)

app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['ALLOWED_EXTENSIONS'] = {'wav', 'mp3', 'pcm', 'm4a', 'amr'}
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024 #由于百度转写最高文件要求为10MB，在此定义限制

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

#初始化百度转写器
transcriber = BaiduTranscriber(
    api_key=os.getenv('BAIDU_API_KEY'),
    secret_key=os.getenv('BAIDU_SECRET_KEY')
)

#检查扩展名
def allowed_file(filename: str) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/transcribe', methods=['POST'])
def transcribe_audio():
    try:
        file = request.files.get('file') or request.files.get('audio')
        if not file:
            return jsonify({'success': False, 'error': '没有找到音频文件'}), 400

        if file.filename == '':
            return jsonify({'success': False, 'error': '没有选择文件'}), 400

        if not allowed_file(file.filename):
            return jsonify({'success': False, 'error': '不支持的文件格式'}), 400

        # 保存临时文件
        filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{secure_filename(file.filename)}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        # 调用百度转写
        result = transcriber.transcribe_with_details(filepath)

        # 清理临时文件
        try:
            os.remove(filepath)
        except FileNotFoundError:
            pass

        if result.get('success'):
            return jsonify({'success': True, 'text': result['text']}), 200
        else:
            return jsonify({'success': False, 'error': result.get('error', '转写失败')}), 500

    except Exception:
        return jsonify({'success': False, 'error': '服务器错误'}), 500

@app.errorhandler(413)
def too_large(e):
    return jsonify({'success': False, 'error': '文件太大，请上传小于10MB的音频文件'}), 413

#自动打开浏览器
def open_browser(port: int, path: str = "/", delay: float = 1.0):
    def _open():
        time.sleep(delay)
        try:
            webbrowser.open(f"http://127.0.0.1:{port}{path}", new=2)
        except Exception:
            pass
    threading.Thread(target=_open, daemon=True).start()

if __name__ == '__main__':
    port = 5000
    open_browser(port, "/")
    app.run(host='127.0.0.1', port=port, debug=False, threaded=True)
