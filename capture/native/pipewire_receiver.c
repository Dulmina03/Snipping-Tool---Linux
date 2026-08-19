#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <fcntl.h>
#include <errno.h>

#include <pipewire/pipewire.h>


static int check_fd(int fd)
{
    if (fd < 0)
    {
        fprintf(
            stderr,
            "Invalid FD: %d\n",
            fd
        );

        return -1;
    }

    if (fcntl(fd, F_GETFD) == -1)
    {
        fprintf(
            stderr,
            "FD %d is not valid: ",
            fd
        );

        perror("");

        return -1;
    }

    return 0;
}


int main(int argc, char *argv[])
{
    if (argc != 2)
    {
        fprintf(
            stderr,
            "Usage: %s <pipewire-fd>\n",
            argv[0]
        );

        return 1;
    }


    int fd = atoi(argv[1]);


    printf(
        "Received FD: %d\n",
        fd
    );


    if (check_fd(fd) != 0)
    {
        return 1;
    }


    printf(
        "FD is valid!\n"
    );


    int saved_argc = argc;
    char **saved_argv = argv;


    pw_init(
        &saved_argc,
        &saved_argv
    );


    printf(
        "PipeWire initialized.\n"
    );


    printf(
        "PipeWire headers: %s\n",
        pw_get_headers_version()
    );


    printf(
        "PipeWire library: %s\n",
        pw_get_library_version()
    );


    /*
     * We are intentionally not creating a PipeWire
     * context yet.
     *
     * This stage verifies that the FD received from
     * the ScreenCast portal can safely reach the
     * native PipeWire component.
     */


    printf(
        "PipeWire FD handoff test successful!\n"
    );


    pw_deinit();


    return 0;
}
