from dataclasses import dataclass

from .plugin_data import PluginData


@dataclass(kw_only=True, frozen=True)
class StringData(PluginData):
    text: str = None

    def to_dict(self) -> dict:
        return {"text": self.text}
