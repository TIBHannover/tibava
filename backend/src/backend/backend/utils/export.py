import csv

import pandas as pd


def json_to_csv(json_obj, sep: str = None, quotechar: str = None):
    if sep is None:
        sep = "\t"

    df = pd.DataFrame(json_obj)
    return df.to_csv(index=False, sep="\t", quotechar="'", quoting=csv.QUOTE_NONE)


def time_to_string(sec, loc="en"):
    sec, sec_frac = divmod(sec, 1)
    min, sec = divmod(sec, 60)
    hours, min = divmod(min, 60)

    sec_frac = round(1000 * sec_frac)
    hours = (2 - len(str(int(hours)))) * "0" + str(int(hours))
    min = (2 - len(str(int(min)))) * "0" + str(int(min))
    sec = (2 - len(str(int(sec)))) * "0" + str(int(sec))

    if loc == "de":
        return f"{hours}:{min}:{sec},{sec_frac}"
    return f"{hours}:{min}:{sec}.{sec_frac}"
