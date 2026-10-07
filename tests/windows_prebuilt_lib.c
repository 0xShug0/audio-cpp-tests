#include "audiocpp.h"
#include <windows.h>
#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static double now(void) {
    LARGE_INTEGER counter, frequency;
    QueryPerformanceCounter(&counter);
    QueryPerformanceFrequency(&frequency);
    return (double)counter.QuadPart / frequency.QuadPart;
}

#define CHECK(call) do { \
    audiocpp_status status = (call); \
    if (status != AUDIOCPP_OK) { \
        fprintf(stderr, "%s failed (%d): %s\n", #call, status, audiocpp_last_error()); \
        failed = 1; goto cleanup; \
    } \
} while (0)

int main(int argc, char **argv) {
    int failed = 0;
    audiocpp_registry *registry = NULL;
    audiocpp_model *model = NULL;
    audiocpp_session *session = NULL;
    audiocpp_request *request = NULL;
    audiocpp_result *result = NULL;
    float *pcm = NULL;
    FILE *file;
    long bytes;
    audiocpp_model_config config = {0};
    audiocpp_backend_config backend = {"cpu", 0, 2};
    if (argc != 3) return 2;
    setvbuf(stdout, NULL, _IONBF, 0);
    printf("version=%s ABI=%u\n", audiocpp_build_version(), audiocpp_abi_version());
    file = fopen(argv[2], "rb");
    if (!file) return 2;
    fseek(file, 0, SEEK_END);
    bytes = ftell(file);
    rewind(file);
    if (bytes <= 0 || bytes % sizeof(float)) { fclose(file); return 2; }
    pcm = malloc((size_t)bytes);
    if (!pcm || fread(pcm, 1, bytes, file) != (size_t)bytes) {
        fclose(file); free(pcm); return 2;
    }
    fclose(file);
    CHECK(audiocpp_registry_create(NULL, &registry));
    printf("families=%zu\n", audiocpp_registry_family_count(registry));
    config.family_hint = "parakeet_tdt";
    CHECK(audiocpp_model_load(registry, argv[1], &config, NULL, &model));
    CHECK(audiocpp_session_create(model, "asr", "offline", &backend, NULL, &session));
    request = audiocpp_request_create();
    if (!request) { failed = 1; goto cleanup; }
    CHECK(audiocpp_request_set_audio(request, pcm, bytes / sizeof(float), 16000, 1));
    for (int i = 0; i < 2; ++i) {
        const char *text = NULL;
        char normalized[1024];
        size_t n = 0;
        double start = now();
        CHECK(audiocpp_session_run(session, request, &result));
        double elapsed = now() - start;
        CHECK(audiocpp_result_text(result, &text, NULL));
        printf("run=%d seconds=%.6f RTF=%.6f text=%s\n", i + 1, elapsed,
               elapsed / (bytes / sizeof(float) / 16000.0), text);
        for (const unsigned char *p = (const unsigned char *)text; *p && n + 1 < sizeof(normalized); ++p) {
            if (isalnum(*p) || *p == ' ') normalized[n++] = (char)tolower(*p);
        }
        normalized[n] = 0;
        if (strcmp(normalized, "concord returned to its place amidst the tents") != 0) {
            fprintf(stderr, "Ground-truth mismatch: %s\n", normalized);
            failed = 1;
        }
        audiocpp_result_free(result);
        result = NULL;
    }
cleanup:
    audiocpp_result_free(result);
    audiocpp_request_free(request);
    audiocpp_session_free(session);
    audiocpp_model_free(model);
    audiocpp_registry_free(registry);
    free(pcm);
    puts(failed ? "FAIL" : "PASS: inference, transcript, repeated request, cleanup");
    return failed;
}
