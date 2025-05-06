import numpy as np

import PIL


def image_normalize(image):
    if len(image.shape) == 2:

        return np.stack([image] * 3, -1)

    if len(image.shape) == 3:
        if image.shape[-1] == 4:
            return image[..., 0:3]
        if image.shape[-1] == 1:
            return np.concatenate([image] * 3, -1)

    if len(image.shape) == 4:
        return image_normalize(image[0, ...])

    return image


def image_resize(image, max_dim=None, min_dim=None, size=None):
    if max_dim is not None:
        shape = np.asarray(image.shape[:2], dtype=np.float32)

        long_dim = max(shape)
        scale = min(1, max_dim / long_dim)
        new_shape = np.asarray(shape * scale, dtype=np.int32)

    elif min_dim is not None:
        shape = np.asarray(image.shape[:2], dtype=np.float32)

        short_dim = min(shape)
        scale = min(1, min_dim / short_dim)
        new_shape = np.asarray(shape * scale, dtype=np.int32)
    elif size is not None:
        new_shape = size
    else:
        return image
    img = PIL.Image.fromarray(image)
    img = img.resize(size=new_shape[::-1])
    return np.array(img)
