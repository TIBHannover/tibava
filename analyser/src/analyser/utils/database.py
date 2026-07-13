def get_features_from_db_entry(entry, return_collection=False):
    data_dict = {"id": entry["id"], "feature": []}

    if return_collection:
        if "collection" in entry:
            data_dict["collection"] = entry["collection"]
        else:
            data_dict["collection"] = {"id": "", "name": "", "is_public": False}

    # TODO
    if "feature" not in entry:
        return data_dict
    for feature in entry["feature"]:
        for annotation in feature["annotations"]:
            if "value" in annotation:
                value = annotation["value"]
            data_dict["feature"].append(
                {"plugin": feature["plugin"], "type": annotation["type"], "version": feature["version"], "value": value}
            )

    return data_dict


def get_classifier_from_db_entry(entry):

    if "classifier" not in entry:
        return {"id": entry["id"], "classifier": []}
    data_dict = {"id": entry["id"], "classifier": entry["classifier"]}
    return data_dict


# TODO
def get_features_from_db_plugins(entry):
    data_dict = {"id": entry["id"], "feature": []}
    # TODO
    if "feature" not in entry:
        return data_dict
    for feature in entry["feature"]:
        for annotation in feature["annotations"]:
            if "value" in annotation:
                value = annotation["value"]
            data_dict["feature"].append({"plugin": feature["plugin"], "type": annotation["type"], "value": value})

    return data_dict
