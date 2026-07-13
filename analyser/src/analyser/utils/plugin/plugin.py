from packaging import version
from typing import Union, Dict, Any

from analyser.utils.helper import convert_name


class Plugin:
    @classmethod
    def __init_subclass__(
        cls,
        config: Dict[str, Any] = None,
        parameters: Dict[str, Any] = None,
        version: str = None,
        **kwargs,
    ):
        super().__init_subclass__(**kwargs)
        cls._default_config = config
        cls._version = version
        cls._parameters = parameters
        cls._name = convert_name(cls.__name__)

    def __init__(self, config=None):
        self._config = self._default_config
        if self._config is None:
            self._config = dict()
        if config is not None:
            self._config.update(config)

    @property
    def config(self):
        return self._config

    @classmethod
    def default_config(cls):
        return cls._default_config

    @classmethod
    def version(cls):
        return cls._version

    @classmethod
    def name(cls):
        return cls._name
