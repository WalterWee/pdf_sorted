import os
import uuid
import webbrowser
import json # For saving config
from threading import Timer
from flask import Flask, request, render_template, jsonify
from werkzeug.utils import secure_filename

# 从我们现有的脚本中导入核心功能
from sort_receipts import sort_bank_receipts, load_config, resource_path

# --- 配置 ---
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf'}
CONFIG_PATH = resource_path("config.json") # Use resource_path for config

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['SECRET_KEY'] = 'super secret key'

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --- Web 路由 ---

@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_and_process():
    if 'file' not in request.files:
        return jsonify({'status': 'error', 'message': 'No file part'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'status': 'error', 'message': 'No selected file'}), 400
        
    if file and allowed_file(file.filename):
        unique_id = str(uuid.uuid4())
        original_filename = secure_filename(file.filename)
        input_filename = f"{unique_id}_{original_filename}"
        output_filename = f"{unique_id}_sorted.pdf"

        input_path = os.path.join(app.config['UPLOAD_FOLDER'], input_filename)
        output_path = os.path.join(app.config['UPLOAD_FOLDER'], output_filename)
        
        try:
            file.save(input_path)
            
            app_config = load_config(CONFIG_PATH)
            sort_bank_receipts(input_path, output_path, app_config)
            
            return jsonify({
                'status': 'success',
                'message': f"文件 '{original_filename}' 处理完成！",
                'output_path': os.path.abspath(output_path),
                'output_filename': f"{os.path.splitext(original_filename)[0]}_sorted.pdf"
            })

        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)}), 500
        finally:
            if os.path.exists(input_path):
                os.remove(input_path)
    else:
        return jsonify({'status': 'error', 'message': 'Invalid file type'}), 400

# --- 新增的配置 API ---

@app.route('/api/config', methods=['GET'])
def get_config():
    """读取并返回当前的 config.json 内容"""
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
        return jsonify(config_data)
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/config', methods=['POST'])
def save_config():
    """从前端接收 JSON 数据并保存到 config.json"""
    try:
        new_config = request.get_json()
        if not new_config:
            return jsonify({'status': 'error', 'message': 'No data provided'}), 400
        
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(new_config, f, ensure_ascii=False, indent=4)
            
        return jsonify({'status': 'success', 'message': '配置已保存！'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


# --- 关机路由 (保持不变) ---
def shutdown_server():
    func = request.environ.get('werkzeug.server.shutdown')
    if func is None:
        raise RuntimeError('Not running with the Werkzeug Server')
    func()

@app.route('/shutdown')
def shutdown():
    shutdown_server()
    return 'Server shutting down...'