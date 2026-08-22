#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <unistd.h>
#include <fcntl.h>
#include <errno.h>
#include <string.h>

#include <pipewire/pipewire.h>

#include <spa/param/video/format-utils.h>
#include <spa/param/video/type-info.h>
#include <spa/debug/types.h>


struct app_data
{
    struct pw_main_loop *loop;
    struct pw_context *context;
    struct pw_core *core;
    struct pw_stream *stream;

    struct spa_video_info_raw format;

    int format_received;
    int frame_count;
};


/*
 * ------------------------------------------------------------
 * FD CHECK
 * ------------------------------------------------------------
 */

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
            "FD %d is invalid: ",
            fd
        );

        perror("");

        return -1;
    }

    return 0;
}


/*
 * ------------------------------------------------------------
 * STREAM STATE
 * ------------------------------------------------------------
 */

static void on_state_changed(
    void *userdata,
    enum pw_stream_state old,
    enum pw_stream_state state,
    const char *error
)
{
    struct app_data *data = userdata;

    printf(
        "Stream state: %s -> %s\n",
        pw_stream_state_as_string(old),
        pw_stream_state_as_string(state)
    );

    if (error != NULL)
    {
        fprintf(
            stderr,
            "Stream error: %s\n",
            error
        );
    }

    fflush(stdout);

    if (state == PW_STREAM_STATE_ERROR)
    {
        fprintf(
            stderr,
            "\nPipeWire stream entered ERROR state.\n"
        );

        if (data->loop != NULL)
        {
            pw_main_loop_quit(data->loop);
        }
    }
}


/*
 * ------------------------------------------------------------
 * FORMAT NEGOTIATION
 * ------------------------------------------------------------
 */

static void on_param_changed(
    void *userdata,
    uint32_t id,
    const struct spa_pod *param
)
{
    struct app_data *data = userdata;

    if (param == NULL)
    {
        return;
    }

    if (id != SPA_PARAM_Format)
    {
        return;
    }

    printf("\n");
    printf("----------------------------------------\n");
    printf("PIPEWIRE FORMAT NEGOTIATION\n");
    printf("----------------------------------------\n");

    /*
     * Parse the raw video format.
     */

    if (spa_format_video_raw_parse(
            param,
            &data->format) < 0)
    {
        printf(
            "Format is not raw video.\n"
        );

        fflush(stdout);

        return;
    }

    data->format_received = 1;

    printf(
        "Format: %s\n",
        spa_debug_type_find_name(
            spa_type_video_format,
            data->format.format
        )
    );

    printf(
        "Size: %u x %u\n",
        data->format.size.width,
        data->format.size.height
    );

    printf(
        "Framerate: %u/%u\n",
        data->format.framerate.num,
        data->format.framerate.denom
    );

    printf(
        "Max framerate: %u/%u\n",
        data->format.max_framerate.num,
        data->format.max_framerate.denom
    );

    printf(
        "Modifier: %lu\n",
        data->format.modifier
    );

    printf("----------------------------------------\n");

    fflush(stdout);
}


/*
 * ------------------------------------------------------------
 * BUFFER PROCESSING
 * ------------------------------------------------------------
 */

static void on_process(void *userdata)
{
    struct app_data *data = userdata;

    struct pw_buffer *pw_buffer;

    pw_buffer =
        pw_stream_dequeue_buffer(
            data->stream
        );

    if (pw_buffer == NULL)
    {
        fprintf(
            stderr,
            "No PipeWire buffer available\n"
        );

        return;
    }

    struct spa_buffer *buffer =
        pw_buffer->buffer;

    if (buffer == NULL)
    {
        pw_stream_queue_buffer(
            data->stream,
            pw_buffer
        );

        return;
    }

    if (buffer->n_datas == 0)
    {
        pw_stream_queue_buffer(
            data->stream,
            pw_buffer
        );

        return;
    }

    struct spa_data *spa_data =
        &buffer->datas[0];

    if (spa_data->data != NULL)
    {
        uint32_t size = 0;

        if (spa_data->chunk != NULL)
        {
            size =
                spa_data->chunk->size;
        }

        data->frame_count++;

        printf(
            "FRAME RECEIVED! #%d  size=%u bytes\n",
            data->frame_count,
            size
        );

        fflush(stdout);
    }

    pw_stream_queue_buffer(
        data->stream,
        pw_buffer
    );
}


/*
 * ------------------------------------------------------------
 * STREAM EVENTS
 * ------------------------------------------------------------
 */

static const struct pw_stream_events stream_events =
{
    PW_VERSION_STREAM_EVENTS,

    .state_changed =
        on_state_changed,

    .param_changed =
        on_param_changed,

    .process =
        on_process
};


/*
 * ------------------------------------------------------------
 * MAIN
 * ------------------------------------------------------------
 */

int main(
    int argc,
    char *argv[]
)
{
    /*
     * Expected:
     *
     * argv[1] = PipeWire FD
     * argv[2] = ScreenCast node ID
     */

    if (argc != 3)
    {
        fprintf(
            stderr,
            "\nUsage:\n"
            "  %s <pipewire-fd> <node-id>\n\n",
            argv[0]
        );

        return 1;
    }


    int fd =
        atoi(argv[1]);


    uint32_t node_id =
        (uint32_t)strtoul(
            argv[2],
            NULL,
            10
        );


    printf(
        "Received PipeWire FD: %d\n",
        fd
    );

    printf(
        "Received ScreenCast node ID: %u\n",
        node_id
    );


    /*
     * Validate FD.
     */

    if (check_fd(fd) != 0)
    {
        return 1;
    }

    printf(
        "FD is valid!\n"
    );


    /*
     * Initialize PipeWire.
     */

    pw_init(
        &argc,
        &argv
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
     * Create PipeWire main loop.
     */

    struct app_data data;

    memset(
        &data,
        0,
        sizeof(data)
    );


    data.loop =
        pw_main_loop_new(NULL);


    if (data.loop == NULL)
    {
        fprintf(
            stderr,
            "Could not create PipeWire main loop\n"
        );

        pw_deinit();

        return 1;
    }


    /*
     * Create PipeWire context.
     */

    data.context =
        pw_context_new(
            pw_main_loop_get_loop(
                data.loop
            ),
            NULL,
            0
        );


    if (data.context == NULL)
    {
        fprintf(
            stderr,
            "Could not create PipeWire context\n"
        );

        pw_main_loop_destroy(
            data.loop
        );

        pw_deinit();

        return 1;
    }


    /*
     * Connect using the FD received from
     * xdg-desktop-portal.
     */

    data.core =
        pw_context_connect_fd(
            data.context,
            fd,
            NULL,
            0
        );


    if (data.core == NULL)
    {
        fprintf(
            stderr,
            "Could not connect to PipeWire remote\n"
        );

        pw_context_destroy(
            data.context
        );

        pw_main_loop_destroy(
            data.loop
        );

        pw_deinit();

        return 1;
    }


    printf(
        "Connected to portal PipeWire remote!\n"
    );


    /*
     * Create stream properties.
     */

    struct pw_properties *props =
        pw_properties_new(
            PW_KEY_MEDIA_TYPE,
            "Video",

            PW_KEY_MEDIA_CATEGORY,
            "Capture",

            PW_KEY_MEDIA_ROLE,
            "Screen",

            PW_KEY_TARGET_OBJECT,
            NULL,

            NULL
        );


    if (props == NULL)
    {
        fprintf(
            stderr,
            "Could not create stream properties\n"
        );

        pw_core_disconnect(
            data.core
        );

        pw_context_destroy(
            data.context
        );

        pw_main_loop_destroy(
            data.loop
        );

        pw_deinit();

        return 1;
    }


    /*
     * Set target node.
     */

    char target[32];

    snprintf(
        target,
        sizeof(target),
        "%u",
        node_id
    );


    pw_properties_set(
        props,
        PW_KEY_TARGET_OBJECT,
        target
    );


    printf(
        "Target PipeWire node: %s\n",
        target
    );


    /*
     * Create stream.
     */

    data.stream =
        pw_stream_new(
            data.core,
            "ai-snipping-tool-capture",
            props
        );


    if (data.stream == NULL)
    {
        fprintf(
            stderr,
            "Could not create PipeWire stream\n"
        );

        pw_core_disconnect(
            data.core
        );

        pw_context_destroy(
            data.context
        );

        pw_main_loop_destroy(
            data.loop
        );

        pw_deinit();

        return 1;
    }


    /*
     * Register callbacks BEFORE connecting.
     */

    struct spa_hook stream_listener;

    memset(
        &stream_listener,
        0,
        sizeof(stream_listener)
    );


    pw_stream_add_listener(
        data.stream,
        &stream_listener,
        &stream_events,
        &data
    );


    printf(
        "PipeWire stream callbacks registered!\n"
    );


    /*
     * --------------------------------------------------------
     * FORMAT REQUEST
     *
     * IMPORTANT:
     *
     * Do NOT force a specific pixel format here.
     *
     * We only tell PipeWire:
     *
     *     "I want video."
     *
     * PipeWire can then negotiate the format that the
     * portal provides.
     * --------------------------------------------------------
     */

    uint8_t pod_buffer[1024];

    struct spa_pod_builder builder =
        SPA_POD_BUILDER_INIT(
            pod_buffer,
            sizeof(pod_buffer)
        );


    const struct spa_pod *params[1];


    params[0] =
        spa_pod_builder_add_object(
            &builder,

            SPA_TYPE_OBJECT_Format,
            SPA_PARAM_EnumFormat,

            SPA_FORMAT_mediaType,
            SPA_POD_Id(
                SPA_MEDIA_TYPE_video
            )
        );


    /*
     * Connect stream.
     */

    int result =
        pw_stream_connect(
            data.stream,

            PW_DIRECTION_INPUT,

            node_id,

            PW_STREAM_FLAG_AUTOCONNECT |
            PW_STREAM_FLAG_MAP_BUFFERS,

            params,
            1
        );


    if (result < 0)
    {
        fprintf(
            stderr,
            "\n"
            "pw_stream_connect failed: %d\n",
            result
        );

        pw_stream_destroy(
            data.stream
        );

        pw_core_disconnect(
            data.core
        );

        pw_context_destroy(
            data.context
        );

        pw_main_loop_destroy(
            data.loop
        );

        pw_deinit();

        return 1;
    }


    printf("\n");
    printf(
        "PipeWire video stream connection requested!\n"
    );

    printf(
        "Waiting for PipeWire format negotiation...\n"
    );

    printf(
        "Waiting for video frames...\n"
    );

    fflush(stdout);


    /*
     * Run PipeWire event loop.
     */

    pw_main_loop_run(
        data.loop
    );


    /*
     * Cleanup.
     */

    printf("\n");
    printf(
        "PipeWire receiver stopping...\n"
    );


    if (data.stream != NULL)
    {
        pw_stream_disconnect(
            data.stream
        );

        pw_stream_destroy(
            data.stream
        );
    }


    if (data.core != NULL)
    {
        pw_core_disconnect(
            data.core
        );
    }


    if (data.context != NULL)
    {
        pw_context_destroy(
            data.context
        );
    }


    if (data.loop != NULL)
    {
        pw_main_loop_destroy(
            data.loop
        );
    }


    pw_deinit();


    printf(
        "PipeWire receiver stopped.\n"
    );


    return 0;
}