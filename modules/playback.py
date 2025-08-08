from ast import Num, Str
from numbers import Number
import pygame
import threading
import time
import logging
import json
from pydub import AudioSegment
from typing import Dict, Optional, Tuple, Any

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('MusicPlayer')

class MusicPlayer:
    """音乐播放控制器，支持本地播放基础功能，为未来Web UI提供控制接口"""
    
    def __init__(self):
        """初始化播放器状态和pygame混音器"""
        pygame.mixer.init()
        self.current_song: Optional[Dict] = None
        self.is_playing = False
        self.is_paused = False
        self.progress = 0.0  # 0.0-100.0，百分比
        self.song_length = 0.0  # 歌曲总时长(秒)
        self.start_time = 0.0  # 播放开始时间戳
        self.progress_thread: Optional[threading.Thread] = None
        self.thread_stop_event = threading.Event()
        self.lock = threading.Lock()
        
        logger.info("音乐播放器已初始化")
    
    def _calculate_song_length(self, file_path: str) -> float:
        """
        估算音频文件长度
        """
        audio = AudioSegment.from_file(file_path)
        return len(audio)
    
    def play(self, song_info: Dict[str, Any]) -> bool:
        """
        播放指定歌曲，支持本地和在线（在线部分W.I.P.）
        
        Args:
            song_info: 来自tag_matching.py的歌曲信息字典，格式参考song_list.json
            
        Returns:
            bool: 是否成功开始播放
        """
        with self.lock:
            # 停止当前播放（如果有）
            if self.is_playing or self.is_paused:
                self.stop()
            
            self.current_song = song_info
            self.is_paused = False
            self.progress = 0.0
            
            logger.info(f"准备播放: {song_info['title']}")
            
            # 区分本地和在线音乐处理
            if song_info['type'] == 'local':
                try:
                    # 加载并播放本地音频文件
                    pygame.mixer.music.load(song_info['link'])
                    pygame.mixer.music.play()
                    
                    # 记录播放开始时间
                    self.start_time = time.time()
                    self.song_length = self._calculate_song_length(song_info['link'])
                    
                    # 启动进度跟踪线程
                    self.thread_stop_event.clear()
                    self.progress_thread = threading.Thread(
                        target=self._track_progress, 
                        daemon=True
                    )
                    self.progress_thread.start()
                    
                    self.is_playing = True
                    logger.info(f"正在播放: {song_info['title']}")
                    return True
                
                except Exception as e:
                    logger.error(f"本地播放失败: {str(e)}")
                    self.current_song = None
                    return False
            
            elif song_info['type'] == 'online':
                # 原型阶段：在线音乐只做标记，不实际实现
                logger.warning("在线音乐播放(W.I.P.): 当前仅记录选择，将在后续版本实现")
                logger.info(f"已选择在线歌曲: {song_info['title']} (ID: {song_info['link']})")
                # TODO: 在线音乐集成 (未来扩展)
                # 例如: open_netease_music(song_info['link'])
                return False
            
            else:
                logger.error(f"不支持的音乐类型")
                return False
    
    def pause(self) -> None:
        """暂停当前播放"""
        with self.lock:
            if self.is_playing and not self.is_paused:
                pygame.mixer.music.pause()
                self.is_paused = True
                # 计算已播放时间以便恢复
                elapsed = time.time() - self.start_time
                self.progress = min(100.0, (elapsed / self.song_length) * 100)
                logger.info(f"已暂停: {self.current_song['title'] if self.current_song else '无歌曲'}")
    
    def resume(self) -> None:
        """继续播放已暂停的音乐"""
        with self.lock:
            if self.is_paused:
                pygame.mixer.music.unpause()
                # 重置开始时间，以便准确计算进度
                self.start_time = time.time() - (self.progress / 100.0 * self.song_length)
                self.is_paused = False
                self.is_playing = True
                logger.info(f"继续播放: {self.current_song['title']}")
    
    def stop(self) -> None:
        """停止当前播放"""
        with self.lock:
            if self.is_playing or self.is_paused:
                pygame.mixer.music.stop()
                self.thread_stop_event.set()
                
                if self.progress_thread and self.progress_thread.is_alive():
                    self.progress_thread.join(timeout=1.0)
                
                self.is_playing = False
                self.is_paused = False
                self.progress = 0.0
                logger.info(f"已停止: {self.current_song['title'] if self.current_song else '无歌曲'}")
    
    def skip(self) -> None:
        """跳过当前歌曲"""
        logger.info(f"跳过歌曲: {self.current_song['title'] if self.current_song else '无歌曲'}")
        self.stop()
    
    def set_volume(self, target_volume: Num)  -> None:
        """改变音量"""
        with self.lock:
            pygame.mixer.music.set_volume(target_volume/100)        
    
    def set_progress(self, percentage: float) -> None:
        """
        设置播放进度（原型阶段简化实现）
        
        Args:
            percentage: 0.0-100.0的进度百分比
        """
        with self.lock:
            if not self.is_playing or self.is_paused:
                return
            
            # 原型阶段：由于pygame不支持精确跳转，仅记录概念
            logger.warning("注意: pygame不支持精确跳转，此功能在原型中仅记录概念")
            clamped_percentage = max(0.0, min(100.0, percentage))
            self.progress = clamped_percentage
            # 未来版本可集成pydub等库实现精确跳转
    
    def get_progress(self) -> Tuple[bool, float, Optional[Dict]]:
        """
        获取当前播放状态
        
        Returns:
            tuple: (是否正在播放, 当前进度百分比, 当前歌曲信息)
        """
        with self.lock:
            return (self.is_playing and not self.is_paused, 
                   self.progress, 
                   self.current_song)
    
    def _track_progress(self) -> None:
        """后台线程：每秒更新播放进度"""
        while not self.thread_stop_event.is_set():
            time.sleep(1.0)
            
            with self.lock:
                if not self.is_playing or self.is_paused or not self.current_song:
                    continue
                
                # 计算当前播放进度
                elapsed = time.time() - self.start_time
                self.progress = min(100.0, (elapsed / self.song_length) * 100)
                return self.progress
                
                # 检查是否播放完毕
                if self.progress >= 100.0:
                    logger.info(f"歌曲结束: {self.current_song['title']}")
                    # 可以在这里添加自动播放下一首的逻辑
                    self.stop()
                    break
    
    def cleanup(self) -> None:
        """清理资源，应在应用退出时调用"""
        self.stop()
        pygame.mixer.quit()
        logger.info("播放器资源已释放")

# 测试代码
if __name__ == "__main__":
    # 模拟来自tag_matching.py的推荐结果
    mock_recommendation = {
        "title": "いよわ - きゅうくらりん - STUDY WITH MIKU ver. -",
        "type": "local",  # 本地音乐
        "link": "J:\Life_Imitating_Art\いよわ - きゅうくらりん - STUDY WITH MIKU ver. -.mp3",  # 本地文件路径
        "features": {
            "genre": "Lo-Fi",
            "rhythm": "舒缓",
            "mood": "轻松"
        }
    }
    
    player = MusicPlayer()
    
    try:
        # 测试计算长度
        print(f"音频长度: {player._calculate_song_length(mock_recommendation['link'])}")

        # 测试播放
        player.play(mock_recommendation)
        time.sleep(15)
        
        # 测试暂停
        player.pause()
        time.sleep(2)
        
        # 测试恢复
        player.resume()
        time.sleep(3)
        
        # 测试进度获取
        is_playing, progress, song = player.get_progress()
        print(f"当前进度: {progress:.1f}% - 播放状态: {'正在播放' if is_playing else '已暂停'}")
        
        # 测试跳过
        player.skip()
        
    finally:
        player.cleanup()
