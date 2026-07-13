import logging

import numpy as np
from analyser.plugins import MappingPlugin, MappingPluginManager


@MappingPluginManager.export("FeatureCosineMapping")
class FeatureCosineMapping(MappingPlugin):
    default_config = {}

    default_version = 0.1

    def __init__(self, **kwargs):
        super(FeatureCosineMapping, self).__init__(**kwargs)

    def call(self, entries, query):
        if query is not None:
            new_entries = []
            for e in entries:
                score = 0
                for q_f in query:
                    for e_f in e["feature"]:
                        if q_f["plugin"] != e_f["plugin"]:
                            continue

                        if "value" in e_f["annotations"][0]:
                            a = e_f["annotations"][0]["value"]
                            b = q_f["value"]
                            score += (
                                np.dot(a, b)
                                / (np.linalg.norm(a) * np.linalg.norm(b))
                                * q_f["weight"]
                            )

                new_entries.append((score, {**e, "coordinates": [score]}))
            new_entries = sorted(new_entries, key=lambda x: -x[0])
            for x in new_entries[:10]:
                logging.info(f"{x[1]['id']} {x[0]}")
            entries = [x[1] for x in new_entries]

        return entries
