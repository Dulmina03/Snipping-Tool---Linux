#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <unistd.h>
#include <fcntl.h>
#include <errno.h>

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

    /*
     * Listener hook.
     *
     * This is important because it connects
     * our callbacks to the PipeWire stream.
     */
    struct spa_hook stream_listener;

    struct spa_video_info format;
};


/*
 * ============================================================
 * FRAME CALLBACK
 * ============================================================
 *
 * PipeWire calls this function whenever a video
 * buffer is available.
 */
static void on_process(void *userdata)
{
    struct app_data *data =
        userdata;

    struct pw_buffer *pw_buffer =
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
        fprintf(
            stderr,
            "PipeWire buffer contains no SPA buffer\n"
        );

        pw_stream_queue_buffer(
            data->stream,
            pw_buffer
        );

        return;
    }


    if (buffer->n_datas == 0)
    {
        fprintf(
            stderr,
            "PipeWire buffer contains no data\n"
        );

        pw_stream_queue_buffer(
            data->stream,
            pw_buffer
        );

        return;
    }


    struct spa_data *spa_data =
        &buffer->datas[0];


    if (spa_data->data == NULL)
    {
        fprintf(
            stderr,
            "PipeWire buffer data pointer is NULL\n"
        );

        pw_stream_queue_buffer(
            data->stream,
            pw_buffer
        );

        return;
    }


    uint32_t size = 0;


    if (spa_data->chunk != NULL)
    {
        size =
            spa_data->chunk->size;
    }


    printf(
        "FRAME RECEIVED! size=%u bytes\n",
        size
    );

    fflush(stdout);


    /*
     * IMPORTANT:
     *
     * The actual video pixels are available at:
     *
     *     spa_data->data
     *
     * Later we will copy this data into an image.
     */


    pw_stream_queue_buffer(
        data->stream,
        pw_buffer
    );
}


/*
 * ============================================================
 * FORMAT CALLBACK
 * ============================================================
 *
 * PipeWire calls this when the video format has
 * been negotiated.
 */
static void on_param_changed(
    void *userdata,
    uint32_t id,
    const struct spa_pod *param
)
{
    struct app_data *data =
        userdata;


    if (param == NULL)
        return;


    if (id != SPA_PARAM_Format)
        return;


    if (spa_format_parse(
            param,
            &data->format.media_type,
            &data->format.media_subtype
        ) < 0)
    {
        fprintf(
            stderr,
            "Could not parse media format\n"
        );

        return;
    }


    if (data->format.media_type !=
            SPA_MEDIA_TYPE_video)
    {
        fprintf(
            stderr,
            "Received non-video media type\n"
        );

        return;
    }


    if (data->format.media_subtype !=
            SPA_MEDIA_SUBTYPE_raw)
    {
        fprintf(
            stderr,
            "Received non-raw video format\n"
        );

        return;
    }


    if (spa_format_video_raw_parse(
            param,
            &data->format.info.raw
        ) < 0)
    {
        fprintf(
            stderr,
            "Could not parse raw video format\n"
        );

        return;
    }


    printf("\n");
    printf(
        "====================================\n"
    );

    printf(
        "VIDEO FORMAT RECEIVED!\n"
    );


    const char *format_name =
        spa_debug_type_find_name(
            spa_type_video_format,
            data->format.info.raw.format
        );


    if (format_name != NULL)
    {
        printf(
            "Format: %s\n",
            format_name
        );
    }
    else
    {
        printf(
            "Format ID: %u\n",
            data->format.info.raw.format
        );
    }


    printf(
        "Size: %u x %u\n",
        data->format.info.raw.size.width,
        data->format.info.raw.size.height
    );


    printf(
        "Framerate: %u/%u\n",
        data->format.info.raw.framerate.num,
        data->format.info.raw.framerate.denom
    );


    printf(
        "====================================\n"
    );

    printf("\n");

    fflush(stdout);
}


/*
 * ============================================================
 * STATE CALLBACK
 * ============================================================
 *
 * Tells us when the PipeWire stream changes state.
 */
static void on_state_changed(
    void *userdata,
    enum pw_stream_state old,
    enum pw_stream_state state,
    const char *error
)
{
    (void)old;


    struct app_data *data =
        userdata;


    printf(
        "Stream state: %s\n",
        pw_stream_state_as_string(
            state
        )
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


    if (state ==
            PW_STREAM_STATE_ERROR)
    {
        fprintf(
            stderr,
            "PipeWire stream entered ERROR state\n"
        );


        pw_main_loop_quit(
            data->loop
        );
    }
}


/*
 * ============================================================
 * PIPEWIRE CALLBACK TABLE
 * ============================================================
 */
static const struct pw_stream_events stream_events =
{
    PW_VERSION_STREAM_EVENTS,

    .state_changed =
        on_state_changed,

    .param_changed =
        on_param_changed,

    .process =
        on_process,
};


/*
 * ============================================================
 * FD VALIDATION
 * ============================================================
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


    if (fcntl(
            fd,
            F_GETFD
        ) == -1)
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
 * ============================================================
 * MAIN
 * ============================================================
 */
int main(
    int argc,
    char *argv[]
)
{
    /*
     * We expect:
     *
     * argv[1] = PipeWire FD
     * argv[2] = ScreenCast node ID
     */

    if (argc != 3)
    {
        fprintf(
            stderr,
            "Usage: %s <pipewire-fd> <node-id>\n",
            argv[0]
        );

        return 1;
    }


    int fd =
        atoi(
            argv[1]
        );


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


    if (check_fd(fd) != 0)
    {
        return 1;
    }


    printf(
        "FD is valid!\n"
    );


    /*
     * ========================================================
     * INITIALIZE PIPEWIRE
     * ========================================================
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
     * ========================================================
     * CREATE MAIN LOOP
     * ========================================================
     */

    struct app_data data =
    {
        0
    };


    data.loop =
        pw_main_loop_new(
            NULL
        );


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
     * ========================================================
     * CREATE CONTEXT
     * ========================================================
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
     * ========================================================
     * CONNECT USING PORTAL FD
     * ========================================================
     *
     * This is the special PipeWire connection supplied
     * by xdg-desktop-portal.
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
            "Could not connect to PipeWire using FD\n"
        );

        perror(
            "pw_context_connect_fd"
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
     * ========================================================
     * CREATE STREAM PROPERTIES
     * ========================================================
     */

    struct pw_properties *props =
        pw_properties_new(
            PW_KEY_MEDIA_TYPE,
            "Video",

            PW_KEY_MEDIA_CATEGORY,
            "Capture",

            PW_KEY_MEDIA_ROLE,
            "Screen",

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
     * ========================================================
     * SET TARGET NODE
     * ========================================================
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
     * ========================================================
     * CREATE STREAM
     * ========================================================
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
     * ========================================================
     * REGISTER CALLBACKS
     * ========================================================
     *
     * THIS IS THE IMPORTANT PART.
     *
     * Without this, PipeWire can connect the stream,
     * but our on_param_changed() and on_process()
     * functions will never be called.
     */

    pw_stream_add_listener(
        data.stream,
        &data.stream_listener,
        &stream_events,
        &data
    );


    printf(
        "PipeWire stream callbacks registered!\n"
    );


    /*
     * ========================================================
     * BUILD VIDEO FORMAT
     * ========================================================
     */

    uint8_t pod_buffer[2048];


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
            ),

            SPA_FORMAT_mediaSubtype,
            SPA_POD_Id(
                SPA_MEDIA_SUBTYPE_raw
            ),

            SPA_FORMAT_VIDEO_format,
            SPA_POD_CHOICE_ENUM_Id(
                4,

                SPA_VIDEO_FORMAT_BGRA,
                SPA_VIDEO_FORMAT_BGRA,
                SPA_VIDEO_FORMAT_RGBA,
                SPA_VIDEO_FORMAT_BGRx
            ),

            SPA_FORMAT_VIDEO_size,
            SPA_POD_CHOICE_RANGE_Rectangle(
                &SPA_RECTANGLE(
                    1920,
                    1080
                ),

                &SPA_RECTANGLE(
                    1,
                    1
                ),

                &SPA_RECTANGLE(
                    4096,
                    4096
                )
            )
        );


    /*
     * ========================================================
     * CONNECT STREAM
     * ========================================================
     */

    int result =
        pw_stream_connect(
            data.stream,

            PW_DIRECTION_INPUT,

            PW_ID_ANY,

            PW_STREAM_FLAG_AUTOCONNECT |
            PW_STREAM_FLAG_MAP_BUFFERS,

            params,
            1
        );


    if (result < 0)
    {
        fprintf(
            stderr,
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
        "PipeWire video stream connected!\n"
    );

    printf(
        "Waiting for video frames...\n"
    );

    printf("\n");


    /*
     * ========================================================
     * RUN PIPEWIRE EVENT LOOP
     * ========================================================
     */

    pw_main_loop_run(
        data.loop
    );


    /*
     * ========================================================
     * CLEANUP
     * ========================================================
     */

    printf(
        "Stopping PipeWire receiver...\n"
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


    return 0;
}