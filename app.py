import os
import uuid
import webbrowser
import json
import datetime # For timestamp in filenames
from threading import Timer
from flask import Flask, request, render_template, jsonify
from werkzeug.utils import secure_filename

# 从我们现有的脚本中导入核心功能
from sort_receipts import sort_bank_receipts, load_config, resource_path

# --- 配置 ---
OUTPUT_FOLDER = '已整理的回单' # 新的文件夹名
ALLOWED_EXTENSIONS = {'pdf'}
CONFIG_PATH = resource_path("config.json")

app = Flask(__name__)
app.config['OUTPUT_FOLDER'] = OUTPUT_FOLDER
app.config['SECRET_KEY'] = 'super secret key'

if not os.path.exists(OUTPUT_FOLDER):
    os.makedirs(OUTPUT_FOLDER)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --- Web 路由 ---

@app.route('/')
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
        original_filename = secure_filename(file.filename)
        
        # --- 文件名和路径生成逻辑更新 ---
        # 使用时间戳代替UUID，并确保显示和保存的文件名一致
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = os.path.splitext(original_filename)[0]
        output_filename = f"{base_name}_sorted_{timestamp}.pdf"

        # 使用 os.path.join 来创建路径
        temp_input_path = os.path.join(app.config['OUTPUT_FOLDER'], f"temp_{uuid.uuid4()}.pdf")
        output_path = os.path.join(app.config['OUTPUT_FOLDER'], output_filename)
        
        try:
            file.save(temp_input_path)
            
            app_config = load_config(CONFIG_PATH)
            sort_bank_receipts(temp_input_path, output_path, app_config)
            
            return jsonify({
                'status': 'success',
                'message': f"文件 '{original_filename}' 处理完成！",
                'output_path': os.path.abspath(output_path),
                'output_filename': output_filename # 返回真实、唯一的文件名
            })

        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)}), 500
        finally:
            # 清理临时的输入文件
            if os.path.exists(temp_input_path):
                os.remove(temp_input_path)
    else:
        return jsonify({'status': 'error', 'message': 'Invalid file type'}), 400

# --- 配置 API (保持不变) ---
@app.route('/api/config', methods=['GET'])
def get_config():
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
        return jsonify(config_data)
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/config', methods=['POST'])
def save_config():
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
