# audio.cpp Tests

Independent validation repository for [audio.cpp](https://github.com/0xShug0/audio.cpp).
It hosts focused reproductions, A/B comparisons, and platform-specific tests
without changing the upstream repository or its workflows.

Each test should document its pinned source revision, inputs, expected behavior,
and validation scope. Keep unrelated tests independent and retain logs and results
as workflow artifacts. Correctness checks and performance benchmarks should be
identified separately.

## Available Tests

### Linux x64 CUDA Release Packaging

Select **Linux x64 CUDA release packaging** in Actions and provide an audio.cpp
source revision and artifact version. This workflow is manual-only. It uploads
test artifacts but never creates tags or publishes a GitHub release.

The CUDA 12.8 and 13.3 builds use audio.cpp's existing release architecture lists,
full model set, portable CPU backend variants, and library-relative backend
discovery. Builds use Release configuration in `build/release`.
NCCL is disabled for CUDA 12.8 only, matching the library release fix.
The native model manager uses system OpenSSL, with `libssl-dev` at build time
and `libssl3` at runtime, following audio.cpp's working Colab CUDA workflow.
The binary and library archives include the build compiler's `libstdc++.so.6`
and `libgcc_s.so.1`, so clean Ubuntu 22.04 hosts do not need GCC 13 installed.
The workflow can be copied unchanged into audio.cpp: in this test repository it
checks out upstream audio.cpp, and elsewhere it checks out the hosting repository.

Each configuration produces three archives using audio.cpp's naming convention:

- `audio-<version>-bin-ubuntu-x64-cuda<toolkit>.tar.gz`: CLI, server, GGUF tool,
  ggml backend libraries, tools, and model specs.
- `audio-<version>-lib-ubuntu-x64-cuda<toolkit>.tar.gz`: `libs/`, `include/`, and
  LICENSE for C API consumers.
- `audio-<version>-cudart-ubuntu-x64-cuda<toolkit>.tar.gz`: linked CUDA runtime
  libraries, including cuFFT. Extract beside the binaries, or into `libs/` for
  the library package. The NVIDIA driver is not bundled.

Separate clean Ubuntu 22.04 containers verify checksums and dependency closure
without a CUDA toolkit or NCCL installed. Existing upstream C API tests and a
logged CLI VAD request verify CPU execution from outside the package directories.
Missing NVIDIA driver libraries are expected on hosted runners; other missing
dependencies fail the test. CUDA inference requires subsequent GPU validation.
This is a packaging and runtime test, not a parity or performance benchmark.

### Windows Unicode Paths

Windows CPU runtime A/B test for [issue #769](https://github.com/0xShug0/audio.cpp/issues/769).

The workflow builds pinned upstream main in Debug mode, tests ASCII and Chinese
paths, applies only the UTF-8 executable manifest patch, and rebuilds in the same
build directory. PulseVAD uses a real public GGUF and the upstream 16 kHz sample
WAV. The successful cases must load the model and produce identical VAD output.
Logs and HTTP responses are uploaded as workflow artifacts.

The manifest patch is extracted from PR #659 by pnnbao (Dr. Puma), originally
commit `7a005e1dcbe94709b7786eaf44db5cfaa976e24c`. Its other changes are excluded.

Select **Windows Unicode paths** in the Actions tab to run this test. This is a correctness test,
not a performance benchmark. A UTF-8 system code page invalidates the baseline
reproduction and fails the test rather than silently passing it.
