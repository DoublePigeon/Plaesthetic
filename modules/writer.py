import json
from pathlib import Path
from turtle import title
from typing import Dict, List, Tuple, Optional

def write_lib_path(lib_path: str, config_path = "config.json") -> None:
    """用于向config写入音乐库路径"""
    config = Path(config_path)
    content = json.loads(config.read_text(encoding="utf-8"))
    content["lib_path"] = str(Path(lib_path).as_posix())
    config.write_text(json.dumps(content, indent=2, ensure_ascii=False), encoding="utf-8")
    
def write_new_music(title:str, type:str, link:str, rhythm:str, mood:str, lib_path:str):
    """用于向音乐库写入新的歌曲信息"""
    lib_path = Path(lib_path)
    lib_content = json.loads(lib_path.read_text(encoding="utf-8"))
    if lib_content == "":
        lib_content = []
    #判断文件的类型
    if type == "local":
        new_music_content = {
            "title": title,
            "type": type,
            "link": Path(link).as_posix(),
            "features": {
                "rhythm": rhythm,
                "mood": mood}    
            }
    elif type == "online":
         new_music_content = {
            "title": title,
            "type": type,
            "link": link,
            "features": {
                "rhythm": rhythm,
                "mood": mood}    
            }
    else:
        raise TypeError("文件的指定类型错误")
    
    lib_content.append(new_music_content)
    
    #写入新的音乐库文件
    lib_path.write_text(json.dumps(lib_content, indent=2, ensure_ascii=False), encoding="utf-8")
    
def edit_library(lib_path, target_title, new_title = "", new_type = "", new_link = "", new_rhythm = "", new_mood = "") -> None:
    """用于修改音乐库当中的指定项"""
    lib_file = Path(lib_path)
    lib_content = json.loads(lib_file.read_text(encoding="utf-8"))
    target_music_info = list(filter(lambda music_info: music_info["title"] == target_title, lib_content))
    
    if target_music_info ==  []:
        raise FileNotFoundError("没有对应的音乐文件")
    else:
        #转为字典
        target_music_info = target_music_info[0]
        print_info = target_music_info["title"]
        print(f"修改了此曲目的信息: {print_info}")

        #删除原有音乐信息
        lib_content.remove(target_music_info)
    
        #添加新的音乐信息
        if new_title != "":
            target_music_info["title"] = new_title
        if new_type != "":
            target_music_info["type"] = new_type
        if new_link != "":
            if target_music_info["type"] == "local":
                target_music_info["link"] = Path(new_link).as_posix()
            elif target_music_info["type"] == "online":
                target_music_info["link"] = new_link
            else:
                raise TypeError("错误的本地/在线音乐信息")
        if new_rhythm != "":
            target_music_info["features"]["rhythm"] = new_rhythm
        if new_mood != "":
            target_music_info["features"]["mood"] = new_mood
    
        #加入修改后的音乐信息
        lib_content.append(target_music_info)
    
        #写入新的音乐库文件
        lib_file.write_text(json.dumps(lib_content, indent=2, ensure_ascii=False), encoding="utf-8")
    
def delete_song(lib_path, target_title) -> None:
    """从音乐库中删除指定曲目"""
    lib_file = Path(lib_path)
    lib_content = json.loads(lib_file.read_text(encoding="utf-8"))
    target_music_info = list(filter(lambda music_info: music_info["title"] == target_title, lib_content))
    
    if target_music_info == []:
        raise FileNotFoundError("没有对应的音乐文件")
    else:
        #转为字典
        target_music_info = target_music_info[0]

        #删去指定音乐信息
        lib_content.remove(target_music_info)
        print_text = target_music_info["title"]
        print(f"删去了曲目: {print_text}")
    
        #写入新的音乐库文件
        lib_file.write_text(json.dumps(lib_content, indent=2, ensure_ascii=False), encoding="utf8")

if __name__ == "__main__":
    #print("测试write_lib_path函数")
    #write_lib_path("C:\Doglas.json", "testconfig.json")

    #try:
       # print("测试写入新音乐的函数")
        #write_new_music("Test Song", "local", "J:\Life_Imitating_Art\666中文にほん.flac", "Messy", "生气了喵", "J:/Life_Imitating_Art/testlist.json")
    #except Exception as e:
        #print(str(e))
    #else:
       #print("测试成功！")


    print("Test delete song and edit song")
    edit_library("J:/Life_Imitating_Art/testlist.json", "Dynamedion - Structural Analysis", "DYM-SA", "online", "C:\Cyka Blyat.mp1000", "slow", "happy")
        
    delete_song("J:/Life_Imitating_Art/testlist.json", "Jochen Flach - Heel, Narcissus (Sunken Treasures DLC)")