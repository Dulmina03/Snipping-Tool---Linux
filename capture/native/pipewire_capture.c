#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <fcntl.h>
#include <pipewire/pipewire.h>

int main(int argc, char *argv[])
{
    if (argc != 2)
    {
        fprintf(
            stderr,
            "Usage: %s <fd>\n",
            argv[0]
        );

        return 1;
    }

    int fd = atoi(argv[1]);

    if (fd < 0)
    {
        fprintf(
            stderr,
            "Invalid file descriptor\n"
        );

        return 1;
    }

    printf(
        "Received file descriptor: %d\n",
        fd
    );

    if (fcntl(fd, F_GETFD) == -1)
    {
        perror(
            "fcntl"
        );

        return 1;
    }

    printf(
        "File descriptor is valid!\n"
    );

    pw_init(
        &argc,
        &argv
    );

    printf(
        "PipeWire initialized successfully!\n"
    );

    printf(
        "PipeWire library: %s\n",
        pw_get_library_version()
    );

    pw_deinit();

    return 0;
}
