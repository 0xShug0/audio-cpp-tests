# audio.cpp Windows path test

Independent Windows CPU runtime A/B test for audio.cpp issue #769.
No workflow changes are made to the upstream repository.

The workflow builds pinned upstream main in Debug mode, tests ASCII and Chinese
paths, applies only the UTF-8 executable manifest patch, and rebuilds in the same
build directory. PulseVAD uses a real public GGUF and the upstream 16 kHz sample
WAV. The successful cases must load the model and produce identical VAD output.
Logs and HTTP responses are uploaded as workflow artifacts.

The manifest patch is extracted from PR #659 by pnnbao (Dr. Puma), originally
commit `7a005e1dcbe94709b7786eaf44db5cfaa976e24c`. Its other changes are excluded.

Run **Windows Unicode paths** from the Actions tab. This is a correctness test,
not a performance benchmark. A UTF-8 system code page invalidates the baseline
reproduction and fails the test rather than silently passing it.
