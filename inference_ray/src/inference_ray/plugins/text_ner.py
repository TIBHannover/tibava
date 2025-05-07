from typing import List, Any, Tuple, Callable, Dict
from pathlib import Path
import sys

from inference_ray.plugin import AnalyserPlugin, AnalyserPluginManager  # type: ignore
from data import AnnotationData, ListData, Annotation  # type: ignore

from data import DataManager, Data  # type: ignore

import logging

default_config = {
    "data_dir": "/data/",
    "host": "localhost",
    "port": 6379,
    "save_dir": Path("/models/text_ner"),
}

default_parameters = {"language_code": "de"}  # TODO check if only German is supported

requires = {
    "annotations": AnnotationData,
}

provides = {"annotations": AnnotationData}


@AnalyserPluginManager.export("text_ner")
class NamedEntityRecognition(
    AnalyserPlugin,
    config=default_config,
    parameters=default_parameters,
    version="0.1",
    requires=requires,
    provides=provides,
):
    def __init__(self, config=None, **kwargs):
        super().__init__(config, **kwargs)

        self.nlp_model = None

        self.ner_dict = {
            "EPER": 0,
            "LPER": 1,
            "LOC": 2,
            "ORG": 3,
            "EVENT": 4,
            "MISC": 5,
        }
        self.org_list = None
        self.event_list = None

        self.model_name = self.config.get("model", "ner_model")

    def call(
        self,
        inputs: Dict[str, Data],
        data_manager: DataManager,
        parameters: Dict = None,
        callbacks: Callable = None,
    ) -> Dict[str, Data]:
        import urllib
        import json
        import requests
        import numpy as np
        import stanza

        # functions from text_utils.py TODO clean import
        def get_stanza_ner_annotations(proc_text):
            named_entities = []
            for sent in proc_text.sentences:
                sent_ents = []
                for ent in sent.ents:
                    sent_ents.append(
                        {
                            "text": ent.text,
                            "type": ent.type,
                            "start": ent.start_char,
                            "end": ent.end_char,
                        }
                    )
                named_entities.extend(sent_ents)
            return named_entities

        def get_related_wikifier_entry(
            spacy_anno, wikifier_annotations, char_tolerance=2, threshold=1e-4
        ):
            # loop through entities found by wikifier
            aligned_candidates = []
            for wikifier_entity in wikifier_annotations:
                if (
                    "secTitle" not in wikifier_entity.keys()
                    or "wikiDataItemId" not in wikifier_entity.keys()
                ):
                    continue
                temp_entity = wikifier_entity.copy()
                wikifier_entity_occurences = wikifier_entity["support"]
                wikifier_entity_occurences = (
                    [wikifier_entity_occurences]
                    if type(wikifier_entity_occurences) == type(dict())
                    else wikifier_entity_occurences
                )
                # loop through all occurences of a given entity recognized by wikifier
                for wikifier_entity_occurence in wikifier_entity_occurences:
                    # print(wikifier_entity_occurence['chFrom'], spacy_anno['start'])
                    # print(wikifier_entity_occurence['chTo'], spacy_anno['end'])
                    if (
                        wikifier_entity_occurence["chFrom"]
                        < spacy_anno["start"] - char_tolerance
                    ):
                        continue
                    if (
                        wikifier_entity_occurence["chTo"]
                        > spacy_anno["end"] + char_tolerance
                    ):
                        continue
                    # apply very low threshold to get rid of annotation with very low confidence
                    if wikifier_entity_occurence["pageRank"] < threshold:
                        continue
                    temp_entity["support"] = wikifier_entity_occurence
                    aligned_candidates.append(
                        {
                            **temp_entity,
                            **{
                                "pageRank_occurence": wikifier_entity_occurence[
                                    "pageRank"
                                ]
                            },
                        }
                    )
            return aligned_candidates

        def get_response(url, params):
            i = 0
            try:
                r = requests.get(
                    url, params=params, headers={"User-agent": "your bot 0.1"}
                )
                return r.json()
            except KeyboardInterrupt:
                raise
            except:
                logging.error(
                    f"Got no response from wikidata. Retry {i}"
                )  # TODO include reason r
                return {}

        def get_wikidata_entries(entity_string, limit_entities=7, language="en"):
            params = {
                "action": "wbsearchentities",
                "format": "json",
                "language": language,
                "search": entity_string,
                "limit": limit_entities,
            }
            response = get_response("https://www.wikidata.org/w/api.php", params=params)
            if response:
                return response["search"]
            else:
                return []

        def get_wikifier_annotations(
            proc_text, language="de", wikifier_key="dqmaycxjptujqkdwsjojeblwjdiovu"
        ):
            threshold = 1.0
            endpoint = "http://www.wikifier.org/annotate-article"
            language = language
            wikiDataClasses = "false"
            wikiDataClassIds = "true"
            includeCosines = "false"
            all_annotations = []
            data = urllib.parse.urlencode(
                [
                    ("text", proc_text),
                    ("lang", language),
                    ("userKey", wikifier_key),
                    ("pageRankSqThreshold", "%g" % threshold),
                    ("applyPageRankSqThreshold", "true"),
                    ("nTopDfValuesToIgnore", "200"),
                    ("nWordsToIgnoreFromList", "200"),
                    ("wikiDataClasses", wikiDataClasses),
                    ("wikiDataClassIds", wikiDataClassIds),
                    ("support", "true"),
                    ("ranges", "false"),
                    ("includeCosines", includeCosines),
                    ("maxMentionEntropy", "3"),
                ]
            )

            req = urllib.request.Request(
                endpoint, data=data.encode("utf8"), method="POST"
            )
            with urllib.request.urlopen(req, timeout=60) as f:
                response = f.read()
                response = json.loads(response.decode("utf8"))
                if "annotations" in response:
                    for annot in response["annotations"]:
                        all_annotations.append(annot)
                else:
                    print(f"No valid response: {response}")
            return all_annotations

        def link_annotations(spacy_annotations, wikifier_annotations):
            POSSIBLE_SPACY_TYPES = ["PER", "ORG", "LOC", "MISC"]
            linked_entities = []
            for spacy_anno in spacy_annotations:
                # skip all entities with 0 or 1 characters or not in selected spacy types
                if (
                    len(spacy_anno["text"]) < 2
                    or spacy_anno["type"] not in POSSIBLE_SPACY_TYPES
                ):
                    continue
                related_wikifier_entries = get_related_wikifier_entry(
                    spacy_anno, wikifier_annotations
                )
                # if no valid wikifier entities were found, try to find entity based on string using <wbsearchentities>
                if len(related_wikifier_entries) < 1:
                    # get wikidata id for extrated text string from spaCy NER
                    entity_candidates = get_wikidata_entries(
                        entity_string=spacy_anno["text"],
                        limit_entities=1,
                        language="de",
                    )
                    # if also no match continue with next entity
                    if len(entity_candidates) < 1:
                        entity_candidate = {
                            **{
                                "wd_id": "unk",
                                "wd_label": "unk",
                                "disambiguation": "unk",
                                "url": "unk",
                            },
                            **spacy_anno,
                        }
                        linked_entities.append(entity_candidate)
                        continue
                    # take the first entry in wbsearchentities (most likely one)
                    entity_candidate = {
                        **{
                            "wd_id": entity_candidates[0]["id"],
                            "wd_label": entity_candidates[0]["label"],
                            "disambiguation": "wbsearchentities",
                            "url": (
                                entity_candidates[0]["url"]
                                if "http" in entity_candidates[0]["url"]
                                else "http:" + entity_candidates[0]["url"]
                            ),
                        },
                        **spacy_anno,
                    }
                    linked_entities.append(entity_candidate)
                else:
                    highest_PR = -1
                    best_wikifier_candidate = related_wikifier_entries[0]
                    for related_wikifier_entry in related_wikifier_entries:
                        # print(related_wikifier_entry['title'], related_wikifier_entry['pageRank_occurence'])
                        if related_wikifier_entry["pageRank_occurence"] > highest_PR:
                            best_wikifier_candidate = related_wikifier_entry
                            highest_PR = related_wikifier_entry["pageRank_occurence"]
                    entity_candidate = {
                        **{
                            "wd_id": best_wikifier_candidate["wikiDataItemId"],
                            "wd_label": best_wikifier_candidate["secTitle"],
                            "disambiguation": "wikifier",
                            "url": best_wikifier_candidate["url"],
                        },
                        **spacy_anno,
                    }
                    linked_entities.append(entity_candidate)
            return linked_entities

        def select_best_binding(entity, bindings, org_list, event_list):
            entity_id = (
                entity["wd_id"].split("/")[-1]
                if entity["wd_id"].startswith("http")
                else entity["wd_id"]
            )

            def check_instance(binding, check_list=None, check_suffix=None):
                if "instance" in binding and "value" in binding["instance"]:
                    instance_id = binding["instance"]["value"].split("/")[-1]
                    if check_list and (
                        instance_id in check_list or entity_id in check_list
                    ):
                        return True
                    if check_suffix and instance_id.endswith(check_suffix):
                        return True
                return False

            def has_notable_properties(bindings):
                notable_properties = [
                    "P106",  # occupation
                    "P27",  # country of citizenship
                    "P69",  # educated at
                    "P166",  # award received
                    "P800",  # notable work
                    "P1412",  # languages spoken, written or signed
                    "P19",  # place of birth
                    "P570",  # date of death
                    "P735",  # given name
                    "P734",  # family name
                ]
                for b in bindings:
                    for prop, value in b.items():
                        if any(
                            notable_prop in str(value)
                            for notable_prop in notable_properties
                        ):
                            return True
                return False

            for b in bindings:
                # Check for EVENT first
                if entity_id in event_list or check_instance(b, check_list=event_list):
                    entity["type"] = "EVENT"
                    return b, entity
                # Check for ORG
                if check_instance(b, check_list=org_list):
                    entity["type"] = "ORG"
                    return b, entity
                # Check for PER/EPER
                if check_instance(b, check_suffix="/Q5"):
                    if has_notable_properties(bindings):
                        entity["type"] = "EPER"
                    else:
                        entity["type"] = "LPER"
                    return b, entity
                # Check for LOC
                if "coordinate" in b and "value" in b["coordinate"]:
                    entity["type"] = "LOC"
                    return b, entity
            # If no matching binding found, keep the original type or default to MISC
            if entity["type"] == "PER":
                entity["type"] = "LPER"
            elif entity["type"] not in ["ORG", "LOC", "EVENT", "EPER", "LPER"]:
                entity["type"] = "MISC"
            return None, entity

        def get_entity_response(wikidata_id):
            query = (
                """
                    prefix schema: <http://schema.org/>
                    PREFIX wikibase: <http://wikiba.se/ontology#>
                    PREFIX wd: <http://www.wikidata.org/entity/>
                    PREFIX wdt: <http://www.wikidata.org/prop/direct/>
                    # SELECT ?entity ?entityLabel ?entityDescription ?instance ?coordinate ?wikipedia_url ?wdimage
                    SELECT ?entity ?entityLabel ?entityDescription ?instance ?coordinate ?wikipedia_url
                    WHERE {
                    VALUES (?entity) {(wd:%s)}
                    OPTIONAL { ?entity wdt:P31 ?instance . }
                    OPTIONAL { ?entity wdt:P625 ?coordinate . }
                    #   OPTIONAL { ?entity wdt:P18 ?wdimage . }
                    OPTIONAL {
                        ?wikipedia_url schema:about ?entity .
                        ?wikipedia_url schema:inLanguage "de" .
                        ?wikipedia_url schema:isPartOf <https://en.wikipedia.org/> .
                    }
                    SERVICE wikibase:label {bd:serviceParam wikibase:language "de" .}
                    }"""
                % wikidata_id
            )
            res = get_response(
                "https://query.wikidata.org/sparql",
                params={"format": "json", "query": query},
            )
            if res:
                return res["results"]
            else:
                return {"bindings": []}

        def fix_entity_types(all_linked_entities, org_list, event_list):
            entity_info = {}
            for linked_entity in all_linked_entities:
                wd_id = linked_entity["wd_id"]
                etype = linked_entity["type"]
                if wd_id not in entity_info:
                    entity_info[wd_id] = get_entity_response(wikidata_id=wd_id)
                binding, entity = select_best_binding(
                    linked_entity, entity_info[wd_id]["bindings"], org_list, event_list
                )
                # print("After select_best_binding call:", binding, entity)
                # information = ["wikipedia_url", "entityDescription", "wdimage"]
                # information = ["url", "entityDescription"]
                if (
                    binding is None and linked_entity["wd_id"] != "unk"
                ):  ##Restore original entity type if no binding found but entity was linked before
                    if (
                        etype == "PER"
                        and linked_entity["disambiguation"] != "unk"
                        and len(linked_entity["wd_label"].split()) > 1
                    ):
                        linked_entity["type"] = "EPER"
                    elif (
                        etype == "PER"
                        and linked_entity["disambiguation"] != "unk"
                        and len(linked_entity["wd_label"].split()) == 1
                    ):
                        linked_entity["type"] = "LPER"
                    elif etype == "PER" and linked_entity["disambiguation"] == "unk":
                        linked_entity["type"] = "LPER"
                    else:
                        linked_entity["type"] = etype
                    continue
                elif (
                    binding is None and linked_entity["wd_id"] == "unk"
                ):  ##If no binding found and entity was not linked before, set type to MISC
                    linked_entity["wd_id"] = "unk"
                    linked_entity["wd_label"] = "unk"
                    linked_entity["disambiguation"] = "unk"
                    linked_entity["entityDescription"] = "unk"
                    linked_entity["url"] = "unk"
                else:
                    linked_entity["url"] = (
                        binding["entity"]["value"]
                        if entity["url"] == "unk"
                        else entity["url"]
                    )
                    linked_entity["entityDescription"] = (
                        binding["entityDescription"]["value"]
                        if "entityDescription" in binding
                        else ""
                    )
            return all_linked_entities

        def get_models(
            language_code: str,
        ) -> Tuple[stanza.Pipeline, List[str], List[str]]:
            logging.error(f"{language_code=}")
            nlp = stanza.Pipeline(
                lang=language_code,
                dir=str(self.config.get("save_dir")),
                processors="tokenize,ner",
                use_gpu=True,
            )

            with open(self.config.get("save_dir") / "organization.json", "r") as f:
                org_list = json.load(f)

            with open(self.config.get("save_dir") / "occurrence_event.json", "r") as f:
                event_list = json.load(f)
            return nlp, org_list, event_list

        def classify_segments(
            segments: List[Annotation], speaker_name: str | None = None
        ) -> List[Annotation]:
            """
            Takes Speaker Turn Segments and performs NER on them

            Args:
                segments (List[Annotation]): List of segments with text annotations and start and end times
                speaker_name (str): Name of speaker

            Returns:
                List[Annotation]: List of segment predictions
            """
            segment_predictions = []

            for segment in segments:
                ner_vector = np.zeros(len(self.ner_dict))

                stanza_nes = get_stanza_ner_annotations(
                    self.nlp_model(segment.labels[0][:24999])
                )
                wikifier_nes = get_wikifier_annotations(
                    segment.labels[0][:24999]
                )  # TODO pass language parameter?
                linked_entities = link_annotations(stanza_nes, wikifier_nes)
                linked_entities = fix_entity_types(
                    linked_entities, self.org_list, self.event_list
                )

                for ent in linked_entities:
                    ner_vector[self.ner_dict[ent["type"]]] += 1

                segment_predictions.append(
                    Annotation(
                        start=segment.start,
                        end=segment.end,
                        labels=[
                            {
                                # "text": segment.labels[0],
                                "speaker": speaker_name,
                                "tags": linked_entities,
                                "vector": ner_vector.tolist(),
                            }
                        ],
                    )
                )

            return segment_predictions

        if None in [self.nlp_model, self.org_list, self.event_list]:
            self.nlp_model, self.org_list, self.event_list = get_models(
                parameters.get("language_code")
            )

        with (
            inputs["annotations"] as input_annotations,
            data_manager.create_data("AnnotationData") as output_data,
        ):
            output_data.name = "Named Entity Recognition and Disambiguation"
            for _, speaker_data in input_annotations:
                with speaker_data as speaker_data:
                    predictions = classify_segments(
                        speaker_data.annotations, speaker_data.name
                    )
                    output_data.annotations.extend(predictions)

            self.update_callbacks(callbacks, progress=1.0)
            return {
                "annotations": output_data,
            }
