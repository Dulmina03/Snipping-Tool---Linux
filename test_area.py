import asyncio

from capture.screenshot import ScreenshotCapture


async def main():

    print("Starting area capture...")

    capture = ScreenshotCapture()

    path = await capture.capture_area()

    print()
    print("Area screenshot saved!")
    print(path)


asyncio.run(main())