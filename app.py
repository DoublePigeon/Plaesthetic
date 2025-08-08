import os
import json
import threading
import time
import logging
from tkinter import W
import psutil
from flask import Flask, render_template, request, jsonify, send_from_directory
from modules.vision_analysis import analyze_image
from modules.tag_matching import match_music
from modules.playback import MusicPlayer
from modules.writer import *

# 配置日志
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
app_logger = logging.getLogger('MainApp')

# 初始化 Flask 应用
app = Flask(__name__, static_folder='static', template_folder='templates')

# 加载配置
try:
    with open('config.json', 'r', encoding='utf-8') as f:
        config = json.load(f)
        API_KEY = config.get('api_key', '')
        MUSIC_LIBRARY_PATH = config.get('lib_path', '')
        if not API_KEY or not MUSIC_LIBRARY_PATH:
            print("config.json 中缺少部分未填充的参数")
except Exception as e:
    print(f"加载配置文件失败: {str(e)}")
    print("请确保 config.json 文件存在且格式正确")
    exit(1)

# 初始化模块
player = MusicPlayer()

# 全局变量用于控制服务器退出
server_should_stop = threading.Event()
server_thread = None
stop_lock = threading.Lock()

@app.route('/')
def index():
    """主页面路由"""
    return render_template('index.html')

@app.route('/api/analyse', methods=['POST'])
def analyse_image_api():
    """图像分析API端点"""
    if 'image' not in request.files:
        return jsonify({"error": "未上传图片"}), 400
    
    image_file = request.files['image']
    image_data = image_file.read()
    
    try:
        # 调用视觉分析模块
        features = analyze_image(image_data, API_KEY)
        environment = features.get('environment', '')
        mood = features.get('mood', '')
        print(f"视觉分析成功! 环境:{environment}, 情绪:{mood}")
        
        # 使用全局变量中的音乐库路径（关键修改）
        recommendations = match_music(
            environment=environment,
            mood=mood,
            lib_path=MUSIC_LIBRARY_PATH,  #使用全局变量
            api_key=API_KEY,
            top_n=1
        )
        
        if not recommendations:
            return jsonify({"error": "未找到匹配的音乐"}), 404
        
        # 获取第一个推荐结果
        recommended_song, _ = recommendations[0]
        
        # 调用播放控制模块
        success = player.play(recommended_song)
        
        return jsonify({
            "success": success,
            "environment": environment,
            "mood": mood,
            "recommended_song": recommended_song
        })
    
    except Exception as e:
        print(f"处理过程中出错: {str(e)}")
        return None

@app.route('/api/progress')
def get_progress():
    """获取当前播放进度"""
    is_playing, progress, current_song = player.get_progress()
    return jsonify({
        "is_playing": is_playing,
        "progress": progress,
        "current_song": current_song
    })

@app.route('/api/control', methods=['POST'])
def control_music():
    """播放控制API"""
    command = request.json.get('command')
    
    if command == 'pause':
        player.pause()
    elif command == 'resume':
        player.resume()
    elif command == 'stop':
        player.stop()
    elif command == 'skip':
        player.skip()
    
    is_playing, progress, current_song = player.get_progress()
    return jsonify({
        "is_playing": is_playing,
        "progress": progress,
        "current_song": current_song
    })

@app.route('/api/volume', methods=['POST'])
def set_volume():
    """设置播放器音量"""
    try:
        volume_input = request.json.get('volume', 50)
        volume_percent = int(float(volume_input))
    except (TypeError, ValueError) as e:
        print(f"音量转换错误: {str(e)}，使用默认值50")
        volume_percent = 50
    
    # 确保在0-100范围内
    volume_percent = max(0, min(100, volume_percent))
    
    # 设置播放器音量
    player.set_volume(volume_percent)
    
    return jsonify({
        "volume": volume_percent
    })

@app.route('/api/set_music_library', methods=['POST'])
def set_music_library_path():
    """设置音乐库路径"""
    global MUSIC_LIBRARY_PATH
    
    data = request.json
    new_path = data.get('path', '')
    
    if not new_path:
        return jsonify({"success": False, "error": "路径不能为空"}), 400
    
    # 验证路径是否存在
    if not os.path.exists(new_path):
        return jsonify({"success": False, "error": f"文件不存在: {new_path}"}), 400
    
    # 确保是JSON文件
    if not new_path.lower().endswith('.json'):
        return jsonify({"success": False, "error": "路径必须指向JSON文件"}), 400
    
    # 更新音乐库路径
    MUSIC_LIBRARY_PATH = new_path
    write_lib_path(MUSIC_LIBRARY_PATH)
    
    app_logger.info(f"音乐库路径已更新为: {MUSIC_LIBRARY_PATH}")
    
    return jsonify({"success": True, "message": "音乐库路径已更新"})

def run_flask():
    """运行Flask应用的函数"""
    print("启动音乐播放器服务...")
    print("访问 http://localhost:5000 打开界面")
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)

def stop_server():
    """安全停止服务器"""
    with stop_lock:
        server_should_stop.set()
    
    # 清理播放器资源
    player.cleanup()
    
    # 发送关闭请求到Flask应用
    try:
        import requests
        requests.post('http://localhost:5000/shutdown')
    except:
        pass
    
    print("\n程序已停止")
    os._exit(0)

@app.route('/shutdown', methods=['POST'])
def shutdown():
    """内部端点用于安全关闭服务器"""
    stop_server()
    return '服务器正在关闭...'

def is_port_in_use(port):
    """检查指定端口是否被占用"""
    for conn in psutil.net_connections():
        if conn.laddr.port == port:
            return True
    return False

@app.route('/start_lib_manager', methods=['POST'])
def start_lib_manager():
    """启动音乐库管理器进程"""
    manager_port = 5001
    
    # 检查端口是否已被占用
    if is_port_in_use(manager_port):
        return jsonify({
            "success": True,
            "message": "管理器已在运行",
            "port": manager_port
        })
    
    try:
        # 获取项目根目录
        project_root = os.path.dirname(os.path.abspath(__file__))
        
        # 构建env/python.exe的路径
        python_path = os.path.join(project_root, 'env', 'python.exe')
        # 构建manager.py的路径
        manager_path = os.path.join(project_root, 'manager.py')
        
        app_logger.info(f"尝试启动音乐库管理器: {python_path} {manager_path}")
        
        # 启动manager.py
        os.system(r"env\python manager.py")
            
    except Exception as e:
        error_msg = f"启动管理器时出错: {str(e)}"
        app_logger.error(error_msg, exc_info=True)
        raise Warning(f"管理器在启动时出错: {str(e)}")

if __name__ == '__main__':
    try:
        print(f"初始音乐库路径: {MUSIC_LIBRARY_PATH}")
    except Exception as e:
        print(f"无法加载初始音乐库: {e}")
    try:
        # 启动Flask服务器在单独线程
        server_thread = threading.Thread(target=run_flask, daemon=True)
        server_thread.start()
        
        # 等待服务器启动
        time.sleep(1)
        
        # 保持主线程运行，直到收到停止信号
        while not server_should_stop.is_set():
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        print("\n正在关闭服务...")
        stop_server()
    except Exception as e:
        print(f"发生严重错误: {str(e)}")
        stop_server()
