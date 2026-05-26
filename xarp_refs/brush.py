from xarp.data_models import Hands, Pose
from xarp.entities import Element, DefaultAssets
from xarp.express import SyncXR
from xarp.gestures import pinch, THUMB_TIP
from xarp.server import run, make_qrcode_image
from xarp.spatial import Transform, Vector3

gray = (.5, .5, .5, 1)
red = (1, 0, 0, .5)
green = (0, 1, 0, .5)
blue = (0, 0, 1, .5)

cursor_scale = Transform(scale=Vector3.one() * .02)

brush = Element(
    key="brush",
    asset=DefaultAssets.sphere(),
    transform=cursor_scale,
    color=gray)

paint = Element(
    key="paint",
    asset=DefaultAssets.sphere(),
    transform=cursor_scale,
    color=blue)


def app(xr: SyncXR, *args, **kwargs) -> None:
    xr.say("Brush XR")

    stream = xr.sense(eyes=True)
    for frame in stream:
        eyes: Pose = frame['eyes']
        print(eyes.position)
        print(eyes.rotation)

    stream.close()

if __name__ == '__main__':
    make_qrcode_image()
    run(app)
