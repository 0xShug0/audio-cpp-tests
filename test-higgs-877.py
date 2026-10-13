import json
import os
from pathlib import Path
import subprocess
import time
import wave

root = Path.cwd()
artifacts = root / 'artifacts'
artifacts.mkdir(exist_ok=True)
model = root / 'models/higgs-audio-v3-tts-4b-q8_0.gguf'
results = []
for kind in ('cpu', 'cpu-portable'):
    cli = next((root / 'prebuilt' / kind).rglob('audiocpp_cli.exe'))
    out = artifacts / (kind + '.wav')
    command = [str(cli), '--task', 'tts', '--family', 'higgs_audio_tts',
               '--model', str(model), '--backend', 'cpu', '--text', 'Hello test.',
               '--out', str(out), '--log', '--metrics']
    (artifacts / (kind + '-command.json')).write_text(json.dumps(command, indent=2))
    start = time.monotonic()
    print('RUN', subprocess.list2cmdline(command), flush=True)
    with (artifacts / (kind + '-stdout.log')).open('wb') as stdout, (artifacts / (kind + '-stderr.log')).open('wb') as stderr:
        try:
            p = subprocess.run(command, cwd=cli.parent, stdout=stdout, stderr=stderr, timeout=900)
            code = p.returncode
        except subprocess.TimeoutExpired:
            code = 'timeout after 900 seconds'
    result = {'kind': kind, 'exit': code, 'wall_seconds': time.monotonic() - start}
    if out.exists():
        try:
            with wave.open(str(out), 'rb') as wav:
                result['audio_seconds'] = wav.getnframes() / wav.getframerate()
        except Exception as error:
            result['wav_error'] = str(error)
    results.append(result)
    (artifacts / 'results.json').write_text(json.dumps(results, indent=2))
    print(json.dumps(result), flush=True)
    for log in (artifacts / (kind + '-stdout.log'), artifacts / (kind + '-stderr.log')):
        lines = log.read_text(errors='replace').splitlines()
        print('\n'.join(lines[-45:]), flush=True)
