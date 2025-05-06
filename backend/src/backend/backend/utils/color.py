import random
import numpy as np


def random_rgb():
    h = random.random() * 359 / 360
    s = 0.6
    v = 0.6
    return hsv_to_rgb(h, s, v)


def rgb_to_hex(rgb):
    rgb_string = "".join(hex(round(255 * x))[-2:] for x in rgb)
    return f"#{rgb_string}"


def hsv_to_rgb(h, s, v):
    if s == 0.0:
        return (v, v, v)
    i = int(h * 6.0)  # assume int() truncates!
    f = (h * 6.0) - i
    p, q, t = v * (1.0 - s), v * (1.0 - s * f), v * (1.0 - s * (1.0 - f))
    i %= 6
    if i == 0:
        return (v, t, p)
    if i == 1:
        return (q, v, p)
    if i == 2:
        return (p, v, t)
    if i == 3:
        return (p, q, v)
    if i == 4:
        return (t, p, v)
    if i == 5:
        return (v, p, q)


def get_closest_color(color):
    color_dict = np.asarray(
        [
            [0,0,0],
            [1.0,1.0,1.0],
            [1.0,0,0],
            [0,1.0,0],
            [0,0,1.0],
            [1.0,1.0,0],
            [0,1.0,1.0],
            [1.0,0,1.0],
            [192/255.0,192/255.0,192/255.0],
            [128/255.0,128/255.0,128/255.0],
            [128/255.0,0,0],
            [128/255.0,128/255.0,0],
            [0,128/255.0,0],
            [128/255.0,0,128/255.0],
            [0,128/255.0,128/255.0],
            [0,0,128/255.0]
        ]
    )
    color_index = np.argmin(np.abs(np.sum(np.subtract(color_dict, color), axis=1)))
    result = [
        "Black",
        "White",
        "Red",
        "Lime",
        "Blue",
        "Yellow",
        "Cyan",
        "Magenta",
        "Silver",
        "Gray",
        "Maroon",
        "Olive",
        "Green",
        "Purple",
        "Teal",
        "Navy"
    ][color_index]
    # print(
    #     f"rgb({255*color[0]},{255*color[1]},{255*color[2]})",
    #     result,
    # )
    return result

