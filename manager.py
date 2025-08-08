import os
import json
import logging
import threading
import time
from pathlib import Path
from tkinter import CURRENT
from flask import Flask, render_template, request, jsonify, send_from_directory
from modules.writer import *

# 全局变量用于控制服务器退出
server_should_stop = threading.Event()
server_thread = None
stop_lock = threading.Lock()

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
manager_logger = logging.getLogger('MusicLibraryManager')

# 初始化 Flask 应用
app = Flask(__name__, static_folder='static', template_folder='templates')

# 全局变量用于存储当前音乐库路径
CURRENT_LIB_PATH = json.loads(Path("config.json").read_text(encoding="utf-8"))["lib_path"]

@app.route('/')
def manager_index():
    """管理器主页面"""
    return render_template('lib_manager.html')

@app.route('/api/lib_path')
def get_lib_path():
    """获取当前音乐库路径"""
    global CURRENT_LIB_PATH
    
    config = get_config()
    CURRENT_LIB_PATH = config.get('lib_path', CURRENT_LIB_PATH)
    
    return jsonify({
        "lib_path": CURRENT_LIB_PATH
    })

@app.route('/api/set_lib_path', methods=['POST'])
def set_lib_path():
    """设置音乐库路径"""
    global CURRENT_LIB_PATH
    
    data = request.json
    new_path = data.get('path', '')
    
    # 验证路径
    is_valid, error_msg = validate_lib_path(new_path)
    if not is_valid:
        return jsonify({
            "success": False,
            "error": error_msg
        }), 400
    
    try:
        # 更新配置文件
        write_lib_path(new_path)
        
        # 更新全局变量
        CURRENT_LIB_PATH = new_path
        
        manager_logger.info(f"音乐库路径已更新为: {new_path}")
        
        # 加载新库并返回内容
        music_library = load_music_library()
        
        return jsonify({
            "success": True,
            "message": "音乐库路径已更新",
            "lib_path": new_path,
            "music_library": music_library
        })
    except Exception as e:
        manager_logger.error(f"更新音乐库路径时出错: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/api/music_library')
def get_music_library():
    """获取当前音乐库的内容"""
    global CURRENT_LIB_PATH
    
    # 确保有有效的库路径
    if not CURRENT_LIB_PATH or not os.path.exists(CURRENT_LIB_PATH):
        config = get_config()
        CURRENT_LIB_PATH = config.get('lib_path', CURRENT_LIB_PATH)
        
        if not CURRENT_LIB_PATH or not os.path.exists(CURRENT_LIB_PATH):
            return jsonify({
                "music_library": [],
                "error": "音乐库路径未设置或无效"
            })
    
    try:
        music_library = load_music_library()
        music_titles = []
        for music_info in music_library:
            if music_info["title"] not in music_titles:
                music_titles.append(music_info["title"])
            else:
                print_text = music_info["title"]
                manager_logger.warning(f"{music_info} 重复，已忽略")
        music_titles.sort()                

        return jsonify({
            "music_library": music_titles,
            "lib_path": CURRENT_LIB_PATH
        })
    except Exception as e:
        manager_logger.error(f"加载音乐库时出错: {str(e)}")
        return jsonify({
            "music_library": [],
            "error": str(e)
        })
    
@app.route('/api/music_info', methods=['POST'])
def get_specific_music():
    """显示特定歌曲的信息"""
    global CURRENT_LIB_PATH
    
    data = request.json
    music_title = data.get('title', '').strip()
    
    if not music_title:
        return jsonify({"success": False, "error": "必须提供歌曲标题"}), 400
    
    try:
        with open(CURRENT_LIB_PATH, 'r', encoding='utf-8') as f:
            music_lib_content = json.load(f)
        
        # 查找匹配的歌曲
        target_song_info = next((song for song in music_lib_content if song["title"] == music_title), None)
        
        if not target_song_info:
            return jsonify({"success": False, "error": "未找到指定歌曲"}), 404
            
        return jsonify(target_song_info)
    except Exception as e:
        manager_logger.error(f"获取歌曲信息时出错: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500
    

@app.route('/api/upload_song', methods = ['POST'])
def upload_song():
    """处理音乐文件上传请求"""
    try:
        # 获取项目根目录（manager.py所在目录）
        base_dir = os.path.dirname(os.path.abspath(__file__))
        # 定义音乐库目录
        music_lib_dir = os.path.join(base_dir, 'music_lib')
        
        # 确保音乐库目录存在
        if not os.path.exists(music_lib_dir):
            os.makedirs(music_lib_dir)
            print(f"已创建音乐库目录: {music_lib_dir}")
        
        # 检查是否有文件上传
        if 'file' not in request.files:
            return jsonify({"error": "请求中未包含文件"}), 400
        
        file = request.files['file']
        
        # 检查文件名是否为空
        if file.filename == '':
            return jsonify({"error": "未选择文件"}), 400
        
        filename = file.filename
        
        # 检查文件是否已经存在
        file_path = os.path.join(music_lib_dir, filename)
        if os.path.exists(file_path):
            print("文件已存在")
        else:
            # 保存文件
            file.save(file_path)
            print(f"文件已保存至: {file_path}")
        
        # 返回绝对路径
        abs_path = os.path.abspath(file_path)
        return jsonify({
            "file_path": abs_path,
            "filename": filename,
            "relative_path": os.path.join('music_lib', filename),
            "success": True
        })
    
    except Exception as e:
        print(f"文件上传失败: {str(e)}")
        return jsonify({"error": f"服务器错误: {str(e)}"}), 500

@app.route('/api/add_song', methods=['POST'])
def add_song():
    """添加新歌曲到音乐库"""
    global CURRENT_LIB_PATH
    
    if not CURRENT_LIB_PATH:
        config = get_config()
        CURRENT_LIB_PATH = config.get('lib_path', CURRENT_LIB_PATH)
        
        if not CURRENT_LIB_PATH:
            return jsonify({
                "success": False,
                "error": "请先设置音乐库路径"
            }), 400
    
    # 验证音乐库路径
    is_valid, error_msg = validate_lib_path(CURRENT_LIB_PATH)
    if not is_valid:
        return jsonify({
            "success": False,
            "error": error_msg
        }), 400
    
    try:
        data = request.json
        title = data.get('title', '').strip()
        type = data.get('type', '').strip()
        link = data.get('link', '').strip()
        rhythm = data.get('rhythm', '').strip()
        mood = data.get('mood', '').strip()
        
        # 验证必填字段
        if not title:
            return jsonify({
                "success": False,
                "error": "歌曲名不能为空"
            }), 400
        
        if not link:
            return jsonify({
                "success": False,
                "error": "链接不能为空"
            }), 400
        
    
        
        if not type or type not in ['local', 'online']:
            return jsonify({
                "success": False,
                "error": "必须指定有效的文件类型 (local/online)"
            }), 400
        
        # 添加歌曲
        write_new_music(
            title=title,
            type=type,
            link=link,
            rhythm=rhythm,
            mood=mood,
            lib_path=CURRENT_LIB_PATH
        )
        
        # 重新加载并返回更新后的音乐库
        updated_library = load_music_library()
        manager_logger.info(f"成功添加新歌曲: {title}")
        return jsonify({
            "success": True,
            "message": "歌曲添加成功",
            "music_library": updated_library
        })
    except Exception as e:
        manager_logger.error(f"添加歌曲时出错: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/api/edit_song', methods=['POST'])
def update_song():
    """修改已有歌曲信息"""
    global CURRENT_LIB_PATH
    
    if not CURRENT_LIB_PATH:
        config = get_config()
        CURRENT_LIB_PATH = config.get('lib_path', CURRENT_LIB_PATH)
        
        if not CURRENT_LIB_PATH:
            return jsonify({
                "success": False,
                "error": "请先设置音乐库路径"
            }), 400
    
    # 验证音乐库路径
    is_valid, error_msg = validate_lib_path(CURRENT_LIB_PATH)
    if not is_valid:
        return jsonify({
            "success": False,
            "error": error_msg
        }), 400
    
    try:
        data = request.json
        target_title = data.get('target_title', '').strip()
        new_title = data.get('new_title', '').strip()
        new_type = data.get('new_type', '').strip()
        new_link = data.get('new_link', '').strip()
        new_rhythm = data.get('new_rhythm', '').strip()
        new_mood = data.get('new_mood', '').strip()
        
        # 验证必填字段
        if not target_title:
            return jsonify({
                "success": False,
                "error": "必须指定要修改的歌曲名"
            }), 400
        
        # 验证新类型（如果提供了）
        if new_type and new_type not in ['local', 'online']:
            return jsonify({
                "success": False,
                "error": "无效的文件类型 (应为 local/online)"
            }), 400
        
        # 修改歌曲
        edit_library(
            lib_path=CURRENT_LIB_PATH,
            target_title=target_title,
            new_title=new_title,
            new_type=new_type,
            new_link=new_link,
            new_rhythm=new_rhythm,
            new_mood=new_mood
        )
        
        # 重新加载并返回更新后的音乐库
        updated_library = load_music_library()
        manager_logger.info(f"成功修改歌曲: {target_title}")
        return jsonify({
            "success": True,
            "message": "歌曲信息更新成功",
            "music_library": updated_library
        })
    except FileNotFoundError as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 404
    except Exception as e:
        manager_logger.error(f"修改歌曲时出错: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/api/delete_song', methods=['POST'])
def remove_song():
    """删除歌曲"""
    global CURRENT_LIB_PATH
    
    if not CURRENT_LIB_PATH:
        config = get_config()
        CURRENT_LIB_PATH = config.get('lib_path', CURRENT_LIB_PATH)
        
        if not CURRENT_LIB_PATH:
            return jsonify({
                "success": False,
                "error": "请先设置音乐库路径"
            }), 400
    
    # 验证音乐库路径
    is_valid, error_msg = validate_lib_path(CURRENT_LIB_PATH)
    if not is_valid:
        return jsonify({
            "success": False,
            "error": error_msg
        }), 400
    
    try:
        data = request.json
        target_title = data.get('title', '').strip()
        
        # 验证必填字段
        if not target_title:
            return jsonify({
                "success": False,
                "error": "必须指定要删除的歌曲名"
            }), 400
        
        # 删除歌曲
        delete_song(
            lib_path=CURRENT_LIB_PATH,
            target_title=target_title
        )
        
        # 重新加载并返回更新后的音乐库
        updated_library = load_music_library()
        
        manager_logger.info(f"成功删除歌曲: {target_title}")
        return jsonify({
            "success": True,
            "message": "歌曲删除成功",
            "music_library": updated_library
        })
    except FileNotFoundError as e:
        return jsonify({
            "success": False,
            "error": "找不到指定的歌曲"
        }), 404
    except Exception as e:
        manager_logger.error(f"删除歌曲时出错: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
    
@app.route('/api/set_music_library', methods=['POST'])
def set_music_library_path():
    """设置音乐库路径"""
    global CURRENT_LIB_PATH
    
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
    CURRENT_LIB_PATH = new_path
    write_lib_path(CURRENT_LIB_PATH)
    
    app_logger.info(f"音乐库路径已更新为: {CURRENT_LIB_PATH}")
    
    return jsonify({"success": True, "message": "音乐库路径已更新"})

@app.route('/shutdown', methods=['POST'])
def shutdown():
    """用于关闭服务器的端点"""
    print("收到关闭请求，正在准备关闭...")
    
    # 设置停止信号
    server_should_stop.set()
    
    # 尝试获取Werkzeug的关闭函数
    func = request.environ.get('werkzeug.server.shutdown')
    if func is not None:
        print("关闭服务器...")
        func()
        return jsonify({"success": True, "message": "正在关闭服务器..."})
    
    # 这里不直接退出，而是等待主线程处理
    print("在生产服务器环境中，将等待主线程处理关闭...")
    return jsonify({"success": True, "message": "已接收关闭请求，将在下一个请求周期关闭"})

def get_config():
    """获取配置信息"""
    global CURRENT_LIB_PATH
    
    try:
        if os.path.exists('config.json'):
            config = json.loads(Path("config.json").read_text(encoding="utf-8"))
            CURRENT_LIB_PATH = config["lib_path"]
            return config
    except Exception as e:
        manager_logger.error(f"读取配置文件失败: {str(e)}")
    
    return {}

def validate_lib_path(lib_path):
    """验证音乐库路径是否有效"""
    if not lib_path:
        return False, "路径不能为空"
    
    if not os.path.exists(lib_path):
        return False, f"文件不存在: {lib_path}"
    
    if not lib_path.lower().endswith('.json'):
        return False, "路径必须指向JSON文件"
    
    try:
        # 尝试读取JSON内容以验证格式
        with open(lib_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if not isinstance(data, list):
                return False, "JSON文件格式错误：必须是一个数组"
    except Exception as e:
        return False, f"JSON文件格式错误: {str(e)}"
    
    return True, ""

def load_music_library():
    """加载音乐库数据"""
    global CURRENT_LIB_PATH
    
    try:
        with open(CURRENT_LIB_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
            else:
                manager_logger.error(f"音乐库文件格式错误: {CURRENT_LIB_PATH} 必须是一个数组")
                return []
    except Exception as e:
        manager_logger.error(f"加载音乐库失败: {str(e)}")
        return []

def run_flask():
    """运行Flask应用的函数"""
    print("启动音乐播放器服务...")
    print("访问 http://localhost:5001 打开界面")
    app.run(host='0.0.0.0', port=5001, debug=False, use_reloader=False)
    
def stop_server():
    """安全停止服务器的包装函数"""
    server_should_stop.set()

def init_manager():
    """初始化音乐库管理器"""
    global CURRENT_LIB_PATH
    
    # 尝试从配置中获取当前库路径
    config = get_config()
    CURRENT_LIB_PATH = config.get('lib_path')
    
    if CURRENT_LIB_PATH:
        manager_logger.info(f"初始化管理器，使用音乐库路径: {CURRENT_LIB_PATH}")
    else:
        manager_logger.warning("未设置音乐库路径，需要用户先设置")

# 初始化管理器
init_manager()
    
try:
    # 启动Flask服务器在单独线程
    server_thread = threading.Thread(target=run_flask, daemon=True)
    server_thread.start()
    
    manager_logger.info(f"音乐库管理器已启动，访问 http://localhost:5001")
    print(f"初始音乐库路径: {CURRENT_LIB_PATH}")
        
    # 等待服务器启动
    time.sleep(1)
        
    # 保持主线程运行，直到收到关闭信号
    print("音乐库管理器已启动。按 Ctrl+C 关闭服务...")
    while True:
        try:
            # 每秒检查一次是否需要退出
            time.sleep(1)
                
            # 检查是否应该停止
            if server_should_stop.is_set():
                print("\n收到停止信号，正在关闭...")
                break
                    
        except KeyboardInterrupt:
            print("\n收到键盘中断，准备关闭...")
            server_should_stop.set()
            break
        except Exception as e:
            print(f"主线程循环中发生错误: {str(e)}")
            server_should_stop.set()
            time.sleep(1)
            break
        
    # 确保所有请求处理完成后再关闭     
    print("等待当前请求完成...")
    time.sleep(1)
        
     # 关闭
    print("正在关闭服务器...")
    try:
        # 尝试发送shutdown请求
        import requests
        requests.post('http://localhost:5001/shutdown', timeout=2)
        print("已发送关闭请求")
    except Exception as e:
        print(f"发送关闭请求失败 (可能已关闭): {str(e)}")
        
    # 等待服务器线程结束
    print("等待服务器线程结束...")
    if server_thread.is_alive():
        server_thread.join(timeout=3.0)
            
    print("服务已成功关闭")
        
except Exception as e:
    print(f"发生严重错误: {str(e)}")
    import traceback
    traceback.print_exc()