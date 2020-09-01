from dataclasses import dataclass, field
from itertools import count

_ids = (f'item{n}' for n in count(1000))

@dataclass
class Medium:
    name: str
    data: str
    id: str = field(default_factory=lambda:next(_ids))
    attributes: dict = field(default_factory=dict)
