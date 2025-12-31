import os
import uuid
import webbrowser
from threading import Timer
from flask import Flask, request, render_template, flash, redirect, url_for, jsonify
from werkzeug.utils import secure_filename

# 从我们现有的脚本中导入核心功能
from sort_receipts import sort_bank_receipts, load_config, resource_path

# --- 配置 ---
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf'}

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['SECRET_KEY'] = 'super secret key' # 用于flash消息

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --- Web 路由 ---

@app.route('/', methods=['GET', 'POST'])
def upload_and_process():
    if request.method == 'POST':
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
                
                config_path = resource_path("config.json")
                app_config = load_config(config_path)
                sort_bank_receipts(input_path, output_path, app_config)
                
                # 返回成功信息和输出文件的绝对路径
                return jsonify({
                    'status': 'success',
                    'message': f"文件 '{original_filename}' 处理完成！",
                    'output_path': os.path.abspath(output_path),
                    'output_filename': f"{os.path.splitext(original_filename)[0]}_sorted.pdf"
                })

            except Exception as e:
                return jsonify({'status': 'error', 'message': str(e)}), 500
            finally:
                # 注意：我们不再在这里删除文件，以便用户可以从文件夹中访问它们
                if os.path.exists(input_path):
                    os.remove(input_path) # 输入文件可以删除
                # if os.path.exists(output_path):
                #     os.remove(output_path)
        else:
            return jsonify({'status': 'error', 'message': 'Invalid file type'}), 400

    return render_template('index.html')

def shutdown_server():
    func = request.environ.get('werkzeug.server.shutdown')
    if func is None:
        raise RuntimeError('Not running with the Werkzeug Server')
    func()

@app.route('/shutdown')
def shutdown():
    shutdown_server()
    return 'Server shutting down...'

# --- 启动器 ---

def open_browser():
      webbrowser.open_new("http://127.0.0.1:5000/")

if __name__ == '__main__':
    # 在 1 秒后打开浏览器，给服务器一点启动时间
    Timer(1, open_browser).start()
    # 运行 Flask app
    app.run(host='127.0.0.1', port=5000, debug=False)
