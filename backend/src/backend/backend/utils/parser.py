import logging
from typing import Dict, List


logger = logging.getLogger(__name__)


class Parser:
    def __init__(self):
        self.valid_parameter = {}

    def __call__(self, parameters: Dict = None, **kwargs) -> Dict:
        if not parameters:
            parameters = []

        task_parameter = {}
        for k, v in self.valid_parameter.items():
            if v.get("default"):
                task_parameter[k] = v.get("default")

        for p in parameters:
            if p["name"] not in self.valid_parameter:
                logger.error(f"[Parser] {p['name']} unknown")
                return None

            try:
                parser = self.valid_parameter[p["name"]].get("parser", lambda x: x)
                # TODO make this more generic
                if "path" in p:
                    value = parser(p["path"])
                else:
                    value = parser(p["value"])
                task_parameter[p["name"]] = value

            except Exception as e:
                logger.error(f"[Parser] {p['name']} could not parse ({e})")
                return None
        logger.debug(f"Task Parameter {task_parameter}")
        for k, v in self.valid_parameter.items():
            if v.get("required", None):
                if k not in task_parameter:
                    logger.error(f"[Parser] {k} is required")
                    return None

        return task_parameter
