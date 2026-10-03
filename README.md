# audio.cpp Tests

Independent validation repository for [audio.cpp](https://github.com/0xShug0/audio.cpp).
It hosts focused reproductions, A/B comparisons, and platform-specific tests
without changing the upstream repository or its workflows.

Each test should document its pinned source revision, inputs, expected behavior,
and validation scope. Keep unrelated tests independent and retain logs and results
as workflow artifacts. Correctness checks and performance benchmarks should be
identified separately.

## Available Tests

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
