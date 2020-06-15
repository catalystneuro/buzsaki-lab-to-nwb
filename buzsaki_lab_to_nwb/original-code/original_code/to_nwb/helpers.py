import cv2


def read_video(fname):
    """

    Parameters
    ----------
    fname

    Returns
    -------

    """

    cap = cv2.VideoCapture(fname)

    frames = []
    it = 0
    while True:
        retval, image = cap.read()
        if image is not None:
            frames.append(image)
            it += 1
            if not it % 1000:
                print('Processed %d frames so far' % it)
        if not retval:
            break

    return frames