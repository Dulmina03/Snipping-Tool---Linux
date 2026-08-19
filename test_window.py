import asyncio

from capture.screenshot import ScreenshotCapture


async def main():

    print("Starting window capture...")

    capture = ScreenshotCapture()

    path = await capture.capture_window()

    print()
    print("Window screenshot saved!")
    print(path)


asyncio.run(main())