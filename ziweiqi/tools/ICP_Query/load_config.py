# -*- coding: utf-8 -*-
import os
import sys
import yaml

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
from encoding_utils import read_text_guess

try:
    class Config:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                # 如果值是字典，则递归转换为对象
                if isinstance(value, dict):
                    value = Config(**value)
                setattr(self, key, value)

        def __repr__(self):
            return str(self.__dict__)
        
        def __getattr__(self, name):
            return None

    def load_config(file_path):
        data = yaml.safe_load(read_text_guess(file_path))

        return Config(**data)

    config = load_config('config.yml')
except:
    print("加载配置文件失败")
    sys.exit()
