import os
import base64
import json
import requests
from typing import Dict, Any, Optional
from pathlib import Path

def analyze_image(image_data: bytes, api_key) -> Dict[str, str]:
    """
    分析输入图像的环境特征和情绪特征
    
    Args:
        image_data: 图像二进制数据
        
    Returns:
        包含以下字段的字典:
        - "environment": 环境特征描述 (如"咖啡馆")
        - "mood": 情绪特征描述 (如"放松")
    
    Note:
        这个函数会调用智谱GLM-4V API进行分析
        需要您补充ZHIPU_API_KEY环境变量和API端点
    """   
    # 获取API密钥
    api_key = api_key
    base_url = "https://api.siliconflow.cn/v1/chat/completions"
    
    # 设置模型名称
    model_name = "THUDM/GLM-4.1V-9B-Thinking"
    
    # 将图像转换为base64编码 (智谱API要求)
    base64_image = base64.b64encode(image_data).decode('utf-8')
    
    # 智谱API要求的图像数据URI格式
    image_url = f"data:image/jpeg;base64,{base64_image}"
    
    # 构建API请求的提示词 (Prompts)
    # 这里定义了我们期望模型返回的结构化数据格式
    prompt = (
        "请分析这张图片的环境特征和情绪特征。\n"
        "环境特征指场景、地点、元素等具体环境特点，如喧闹，安静等。\n"
        "情绪特征指图片传达的情绪氛围，如愉悦、平静、兴奋等。\n\n"
        "请用中文返回严格JSON格式，仅包含以下两个字段：\n"
        "- \"environment\": 字符串 (场景描述，5个汉字以内)\n"
        "- \"mood\": 字符串 (情绪描述，3-4个汉字)\n\n"
        "示例输出：{\"environment\": \"咖啡馆\", \"mood\": \"放松\"}\n"
        "不要包含任何其他信息，不要解释，只输出JSON"
    )
    
    #调用GLM4.1V
    payload = {
        "model": model_name,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": prompt
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": image_url
                        }
                    }
                ]
            }
        ],
        "temperature": 0.3  # 降低随机性，确保格式稳定
    }
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
        # 调用智谱API
    try:
        print("调用智谱API进行图像分析...")
        response = requests.post(
            base_url,
            headers = headers,
            data=json.dumps(payload),
            timeout=300
        )
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        # 智能重试机制 (原型阶段简单处理)
        raise RuntimeError(f"API请求失败: {str(e)}\n请检查网络连接和API配置") from e
    
    
    # 解析API响应
    try:
        response_data = response.json()
        # 提取模型生成的内容
        content = response_data["choices"][0]["message"]["content"].strip()
        
        # 尝试解析JSON结果
        try:
            result = json.loads(content)
        except json.JSONDecodeError:
            # 处理可能的非JSON响应 (模型有时会添加额外文本)
            # 尝试从文本中提取JSON片段
            import re
            json_match = re.search(r'\{.*\}', content)
            if json_match:
                result = json.loads(json_match.group())
            else:
                raise ValueError("无法从响应中提取有效JSON")
        
        # 验证必要字段
        if "environment" not in result or "mood" not in result:
            raise ValueError("响应缺少必要字段 (environment/mood)")
        
        print(f"图像分析结果: 环境={result['environment']}, 情绪={result['mood']}")
        #返回结果
        return {
            "environment": result["environment"].strip(),
            "mood": result["mood"].strip()
        }
    
    except (KeyError, IndexError) as e:
        raise RuntimeError(f"API响应解析失败: {str(e)}\n原始响应: {response.text}") from e
    except Exception as e:
        raise RuntimeError(f"结果处理异常: {str(e)}") from e


# Test
if __name__ == "__main__":
    """
    使用示例:
    1. 确保设置了ZHIPU_API_KEY环境变量
    2. 将测试图片放在同目录下
    3. 运行 python vision_analysis.py
    
    注意: 正式集成到app.py时将删除此测试代码
    """
    TEST_IMAGE_PATH = "test_image.png"  # 替换为您的测试图片路径
    
    if not os.path.exists(TEST_IMAGE_PATH):
        print(f"⚠️ 测试图片不存在: {TEST_IMAGE_PATH}")
        print("请添加测试图片或修改TEST_IMAGE_PATH变量")
    else:
        try:
            with open(TEST_IMAGE_PATH, "rb") as img_file:
                image_data = img_file.read()
            
            print(f"正在分析图片: {TEST_IMAGE_PATH}")
            result = analyze_image(image_data)
            print("\n✅ 分析成功! 结果:")
            print(f"环境特征: {result['environment']}")
            print(f"情绪特征: {result['mood']}")
            
            # 验证结果格式是否符合后续模块要求
            assert "environment" in result, "缺少environment字段"
            assert "mood" in result, "缺少mood字段"
            print("\n🔄 格式验证通过! 可用于后续音乐匹配")
            
        except Exception as e:
            print(f"\n❌ 分析失败: {str(e)}")
            import traceback
            traceback.print_exc()
