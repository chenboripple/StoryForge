"""
IP Models - IP 生成相关数据模型
人物 IP、Story Bible、场景设定
"""
from .ip_assets import CharacterIP, RelationshipEdge, SceneSetting, DerivedSetting, StoryBible

__all__ = [
    'CharacterIP', 'RelationshipEdge', 'SceneSetting', 'DerivedSetting', 'StoryBible',
]
