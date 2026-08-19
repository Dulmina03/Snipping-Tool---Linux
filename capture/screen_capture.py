import asyncio
import os
import subprocess
import uuid

from dbus_next import Message, MessageType, Variant
from dbus_next.aio import MessageBus


PORTAL_BUS = "org.freedesktop.portal.Desktop"
PORTAL_PATH = "/org/freedesktop/portal/desktop"

SCREENCAST = "org.freedesktop.portal.ScreenCast"
REQUEST = "org.freedesktop.portal.Request"


class ScreenCapture:

    def __init__(self):
        self.bus = None
        self.session_handle = None
        self.pipewire_fd = None
        self.receiver = None

    async def connect(self):

        self.bus = await MessageBus(
            negotiate_unix_fd=True
        ).connect()

        print("Connected to portal.")

    async def portal_request(
        self,
        interface,
        member,
        signature,
        body,
    ):

        reply = await self.bus.call(
            Message(
                destination=PORTAL_BUS,
                path=PORTAL_PATH,
                interface=interface,
                member=member,
                signature=signature,
                body=body,
            )
        )

        if reply.message_type == MessageType.ERROR:

            raise RuntimeError(
                f"{member} failed: "
                f"{reply.error_name}"
            )

        request_path = reply.body[0]

        future = (
            asyncio.get_running_loop()
            .create_future()
        )

        def handler(message):

            if message.message_type != MessageType.SIGNAL:
                return

            if message.interface != REQUEST:
                return

            if message.member != "Response":
                return

            if message.path != request_path:
                return

            if not future.done():

                future.set_result(
                    message.body
                )

        self.bus.add_message_handler(
            handler
        )

        try:

            response, results = (
                await asyncio.wait_for(
                    future,
                    timeout=120,
                )
            )

        finally:

            self.bus.remove_message_handler(
                handler
            )

        if response != 0:

            raise RuntimeError(
                f"{member} failed. "
                f"Portal response: {response}"
            )

        return results

    async def create_session(self):

        print(
            "Creating ScreenCast session..."
        )

        options = {

            "handle_token": Variant(
                "s",
                "snippingtool_"
                + uuid.uuid4().hex,
            ),

            "session_handle_token": Variant(
                "s",
                "session_"
                + uuid.uuid4().hex,
            ),
        }

        results = await self.portal_request(
            SCREENCAST,
            "CreateSession",
            "a{sv}",
            [
                options
            ],
        )

        self.session_handle = (
            results[
                "session_handle"
            ].value
        )

        print(
            "CreateSession SUCCESS!"
        )

        print(
            "Session:"
        )

        print(
            self.session_handle
        )

    async def select_sources(self):

        print()
        print(
            "Selecting screen source..."
        )

        options = {

            "types": Variant(
                "u",
                1,
            ),

            "multiple": Variant(
                "b",
                False,
            ),

            "handle_token": Variant(
                "s",
                "sources_"
                + uuid.uuid4().hex,
            ),
        }

        await self.portal_request(
            SCREENCAST,
            "SelectSources",
            "oa{sv}",
            [
                self.session_handle,
                options,
            ],
        )

        print(
            "SelectSources SUCCESS!"
        )

    async def start(self):

        print()
        print(
            "Starting ScreenCast..."
        )

        results = await self.portal_request(
            SCREENCAST,
            "Start",
            "osa{sv}",
            [
                self.session_handle,
                "",
                {
                    "handle_token": Variant(
                        "s",
                        "start_"
                        + uuid.uuid4().hex,
                    )
                },
            ],
        )

        streams = results[
            "streams"
        ].value

        print(
            "Start SUCCESS!"
        )

        print()
        print(
            "Streams:"
        )

        print(
            streams
        )

        return streams

    async def open_pipewire_remote(self):

        print()
        print(
            "Opening PipeWire remote..."
        )

        reply = await self.bus.call(
            Message(
                destination=PORTAL_BUS,
                path=PORTAL_PATH,
                interface=SCREENCAST,
                member="OpenPipeWireRemote",
                signature="oa{sv}",
                body=[
                    self.session_handle,
                    {},
                ],
            )
        )

        if reply.message_type == MessageType.ERROR:

            raise RuntimeError(
                "OpenPipeWireRemote failed: "
                + str(
                    reply.error_name
                )
            )

        print()
        print(
            "OpenPipeWireRemote SUCCESS!"
        )

        print(
            "D-Bus signature:",
            reply.signature
        )

        print(
            "D-Bus body:",
            reply.body
        )

        print(
            "Unix FDs:",
            reply.unix_fds
        )

        fd_index = reply.body[0]

        self.pipewire_fd = (
            reply.unix_fds[fd_index]
        )

        print()
        print(
            "Actual PipeWire FD:",
            self.pipewire_fd
        )

        os.fstat(
            self.pipewire_fd
        )

        print(
            "PipeWire FD is valid!"
        )

        return self.pipewire_fd

    def start_native_receiver(self):

        if self.pipewire_fd is None:

            raise RuntimeError(
                "PipeWire FD has not been created."
            )

        receiver_path = (
            "capture/native/"
            "pipewire_receiver"
        )

        print()
        print(
            "Starting native PipeWire receiver..."
        )

        print(
            "Passing FD:",
            self.pipewire_fd
        )

        self.receiver = subprocess.Popen(
            [
                receiver_path,
                str(self.pipewire_fd),
            ],
            pass_fds=(
                self.pipewire_fd,
            ),
        )

        print(
            "Native receiver started."
        )

    async def close(self):

        if self.receiver is not None:

            if self.receiver.poll() is None:

                print()
                print(
                    "Stopping native receiver..."
                )

                self.receiver.terminate()

                try:

                    self.receiver.wait(
                        timeout=3
                    )

                except subprocess.TimeoutExpired:

                    self.receiver.kill()

            self.receiver = None

        if self.pipewire_fd is not None:

            try:

                os.close(
                    self.pipewire_fd
                )

            except OSError:

                pass

            self.pipewire_fd = None

        if self.bus is not None:

            self.bus.disconnect()


async def main():

    capture = ScreenCapture()

    try:

        await capture.connect()

        await capture.create_session()

        await capture.select_sources()

        await capture.start()

        await capture.open_pipewire_remote()

        print()
        print(
            "PipeWire remote opened successfully!"
        )

        capture.start_native_receiver()

        print()
        print(
            "Everything is running!"
        )

        print(
            "Press Ctrl+C to stop."
        )

        while True:

            await asyncio.sleep(1)

    except KeyboardInterrupt:

        print()
        print(
            "Stopping..."
        )

    except Exception as error:

        print()
        print(
            "ScreenCast test failed:"
        )

        print(
            error
        )

    finally:

        await capture.close()


if __name__ == "__main__":

    asyncio.run(main())