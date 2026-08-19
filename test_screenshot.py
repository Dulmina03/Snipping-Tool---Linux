import asyncio

from capture.screenshot import ScreenshotCapture


async def main():

    print("Starting screenshot...")

    capture = ScreenshotCapture()

    path = await capture.capture_full_screen()

    print()
    print("Screenshot saved!")
    print(path)


asyncio.run(main())