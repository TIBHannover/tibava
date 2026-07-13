import imageio
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


def image_pad(image):
    height, width = image.shape[:2]  # WHC

    pad_x = max(0, (height - width) // 2)
    pad_y = max(0, (width - height) // 2)

    return np.pad(image, ((pad_y, pad_y), (pad_x, pad_x), (0, 0)), "constant", constant_values=0)


def image_crop(image, size=None):
    image = PIL.Image.fromarray(image)
    width, height = image.size  # Get dimensions

    left = (width - size[0]) / 2
    top = (height - size[1]) / 2
    right = (width + size[0]) / 2
    bottom = (height + size[1]) / 2

    # Crop the center of the image
    image = image.crop((left, top, right, bottom))
    return np.array(image)


def image_from_proto(image_proto):
    image_field = image_proto.WhichOneof("image")
    if image_field == "path":
        image = imageio.imread(image_proto.path)
    if image_field == "encoded":
        image = imageio.imread(image_proto.encoded)

    image = image_normalize(image)

    if image_proto.roi.width > 0 and image_proto.roi.height > 0:
        y = int(image_proto.roi.y * image.shape[0])
        height = int(image_proto.roi.height * image.shape[0])
        x = int(image_proto.roi.x * image.shape[1])
        width = int(image_proto.roi.width * image.shape[1])

        image = image[y : y + height, x : x + width]

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
        scale = max(1, min_dim / short_dim)
        new_shape = np.asarray(shape * scale, dtype=np.int32)
    elif size is not None:
        new_shape = size
    else:
        return image

    PIL.Image.MAX_IMAGE_PIXELS = 10000 * 10000
    img = PIL.Image.fromarray(image)
    img = img.resize(size=new_shape[::-1])
    return np.array(img)
