from dataclasses import dataclass, field
from typing import Set, Dict, Any


@dataclass
class Messages:
    spam: Set = field(default_factory=set)
    normal: Dict[Any, Any] = field(default_factory=dict)
    image_spam: Set = field(default_factory=set)
    image_authors: Dict[Any, Any] = field(default_factory=dict)
