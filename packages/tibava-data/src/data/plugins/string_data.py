import logging
from typing import List
from dataclasses import dataclass, field

import numpy.typing as npt
import numpy as np

from ..manager import DataManager
from ..data import Data
from interface import analyser_pb2


@DataManager.export("StringData", analyser_pb2.STRING_DATA)
@dataclass(kw_only=True)
class StringData(Data):
    type: str = field(default="StringData")
    text: str = None

    def load(self) -> None:
        super().load()
        assert self.check_fs(), "No filesystem handler installed"

        data = self.load_dict("string_data.yml")
        self.text = data.get("text")

    def save(self) -> None:
        super().save()
        assert self.check_fs(), "No filesystem handler installed"
        assert self.fs.mode == "w", "Data packet is open read only"

        self.save_dict(
            "string_data.yml",
            {
                "text": self.text,
            },
        )

    def to_dict(self) -> dict:
        return {"text": self.text}


@DataManager.export("StringsData", analyser_pb2.TEXT_EMBEDDING_DATA)
@dataclass(kw_only=True)
class StringsData(Data):
    type: str = field(default="StringsData")
    strings: List[StringData] = field(default_factory=list)

    def load(self) -> None:
        super().load()
        assert self.check_fs(), "No filesystem handler installed"

        data = self.load_dict("strings_data.yml")
        self.strings = [StringData(**x) for x in data.get("strings")]

    def save(self) -> None:
        super().save()
        assert self.check_fs(), "No filesystem handler installed"
        assert self.fs.mode == "w", "Data packet is open read only"

        self.save_dict(
            "strings_data.yml", {"strings": [t.to_dict() for t in self.strings]}
        )

    def to_dict(self) -> dict:
        return {**super().to_dict(), "strings": [t.to_dict() for t in self.strings]}
