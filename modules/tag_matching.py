import json
import os
import requests
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple, Optional

def get_embedding(text: str, api_key:str) -> List[float]:
    """
    通过硅基流动API获取文本的bge-large-zh-v1.5嵌入向量
    
    Args:
        text: 需要生成嵌入的文本
        api_key: API密钥 (可选, 优先从环境变量获取)
        
    Returns:
        嵌入向量列表
    """
    # 获取API密钥
    api_key = api_key
    if not api_key:
        raise ValueError(
            "SILICONFLOW_API_KEY环境变量未设置!\n"
            "请执行: export SILICONFLOW_API_KEY='your_api_key_here'\n"
            "或在代码中传入api_key参数"
        )
    
    # 设置API端点和参数 [4]
    url = "https://api.siliconflow.cn/v1/embeddings"
    payload = {
        "model": "BAAI/bge-large-zh-v1.5",
        "input": text
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    try:
        print(f"调用硅基流动API生成嵌入向量: '{text[:30]}{'...' if len(text) > 30 else ''}'")
        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=10
        )
        response.raise_for_status()
        response_data = response.json()
        
        # 提取嵌入向量
        embedding = response_data["data"][0]["embedding"]
        return embedding
    
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"API请求失败: {str(e)}\n请检查网络连接和API配置") from e [4][5]
    except (KeyError, IndexError) as e:
        raise RuntimeError(f"API响应解析失败: {str(e)}\n原始响应: {response.text}") from e [5][6]


def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """
    计算两个向量的余弦相似度
    
    Args:
        vec1: 第一个向量
        vec2: 第二个向量
        
    Returns:
        余弦相似度值 (0-1之间, 越接近1表示越相似)
    """
    # 转换为numpy数组以提高计算效率
    v1 = np.array(vec1)
    v2 = np.array(vec2)
    
    # 计算余弦相似度
    dot_product = np.dot(v1, v2)
    norm1 = np.linalg.norm(v1)
    norm2 = np.linalg.norm(v2)
    
    # 避免除以零
    if norm1 == 0 or norm2 == 0:
        return 0.0
    
    return float(dot_product / (norm1 * norm2))


def load_music_library(library_path: str = "../music_library.json") -> List[Dict]:
    """
    加载音乐库JSON文件
    
    Args:
        library_path: 音乐库文件路径 (默认为上一级目录)
        
    Returns:
        音乐库列表
    """
    path = Path(library_path)
    if not path.exists():
        raise FileNotFoundError(f"音乐库文件不存在: {library_path}")
    
    try:
        with open(path, 'r', encoding='utf-8') as f:
            library = json.load(f)
        
        # 验证数据格式
        for idx, song in enumerate(library):
            required_fields = ["title", "type", "link", "features"]
            missing = [field for field in required_fields if field not in song]
            if missing:
                raise ValueError(f"歌曲'{song.get('title', f'未知#{idx}')}缺少字段: {', '.join(missing)}") [3]
                
        print(f"成功加载音乐库: {len(library)}首歌曲")
        return library
    
    except json.JSONDecodeError as e:
        raise ValueError(f"音乐库文件格式错误: {str(e)}") from e
    except Exception as e:
        raise RuntimeError(f"加载音乐库失败: {str(e)}") from e


def match_music(
    environment: str,
    mood: str,
    lib_path: str,
    api_key: str,
    top_n: int = 1,
) -> List[Tuple[Dict, float]]:
    """
    根据环境和情绪特征匹配最合适的音乐
    
    Args:
        environment: 环境特征 (如"咖啡馆")
        mood: 情绪特征 (如"放松")
        api_key: 硅基流动API密钥 (可选)
        top_n: 返回前N个匹配结果
        
    Returns:
        列表[(匹配的歌曲信息, 相似度得分), ...], 按相似度降序排列
    """
    #获取api_key
    api_key = api_key
    
    # 合并环境和情绪特征作为查询
    query = f"环境:{environment}, 情绪:{mood}"
    print(f"开始音乐匹配: 查询='{query}'")
    
    # 加载音乐库
    music_library = load_music_library(lib_path)
    
    # 生成查询的嵌入向量
    query_embedding = get_embedding(query, api_key)
    
    # 计算每首歌与查询的相似度
    matches = []
    for song in music_library:
        # 组合歌曲的特征信息
        song_features = f"韵律:{song['features'].get('rhythm', '')}, 情绪:{song['features'].get('mood', '')}"
        
        # 生成歌曲特征的嵌入向量
        song_embedding = get_embedding(song_features, api_key)
        
        # 计算相似度
        similarity = cosine_similarity(query_embedding, song_embedding)
        matches.append((song, similarity))
        
        print(f"  '{song['title']}' 匹配度: {similarity:.4f}")

    # 按相似度排序并返回前N个结果
    matches.sort(key=lambda x: x[1], reverse=True)
    print(f"\n匹配完成! 最佳匹配: '{matches[0][0]['title']}' (相似度: {matches[0][1]:.4f})")
    
    # 确保返回至少1个结果
    return matches[:max(1, top_n)]


#测试代码
if __name__ == "__main__":
    """
    使用示例:
    1. 确保设置了SILICONFLOW_API_KEY环境变量
    2. 确保存在../music_library.json文件
    3. 运行 python match_engine.py
    """
    # 模拟vision_analysis模块的输出
    mock_analysis_result = {
        "environment": "咖啡馆",
        "mood": "放松"
    }
    print(f"模拟输入特征:\n环境: {mock_analysis_result['environment']}\n情绪: {mock_analysis_result['mood']}")
    
    with open("config.json", "r", encoding="utf-8") as k:
        api_key = json.load(k)["api_key"]

    try:
        print("\n" + "="*50)
        matches = match_music(
            environment=mock_analysis_result["environment"],
            mood=mock_analysis_result["mood"],
            lib_path=r"J:\Life_Imitating_Art\song_list.json",
            api_key=api_key
        )
        
        print("\n最终推荐结果:")
        for i, (song, score) in enumerate(matches, 1):
            print(f"{i}. '{song['title']}' [{song['type'].upper()}] - {score:.4f}")
            print(f"   链接: {song['link']}")
            print(f"   牢特征: {song['features']}")
    
    except Exception as e:
        print(f"\n❌ 匹配过程出错: {str(e)}")
        import traceback
        traceback.print_exc()