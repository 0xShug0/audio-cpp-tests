import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess


parser = argparse.ArgumentParser()
parser.add_argument("--source", type=Path, required=True)
parser.add_argument("--artifacts", type=Path, required=True)
parser.add_argument("--base-ref", required=True)
args = parser.parse_args()
source = args.source.resolve()
artifacts = args.artifacts.resolve()
artifacts.mkdir(parents=True, exist_ok=True)
catalogs = ["gguf_converter_model_specs.inc", "native_package_specs.inc", "model_specs.inc"]
cpp = r'''#include <cstdio>
#include <iostream>
#include <string_view>
#include <utility>
#ifdef _WIN32
#include <fcntl.h>
#include <io.h>
#endif
using Entry = std::pair<std::string_view, std::string_view>;
const Entry converter[] = {
#include "gguf_converter_model_specs.inc"
};
const Entry native[] = {
#include "native_package_specs.inc"
};
const Entry builtin[] = {
#include "model_specs.inc"
};
template <size_t N> void dump(const Entry (&entries)[N]) {
    for (const auto & entry : entries) {
        std::cout << entry.first << '\t' << entry.second.size() << '\n';
        std::cout.write(entry.second.data(), entry.second.size());
        std::cout << '\n';
    }
}
int main(int argc, char ** argv) {
#ifdef _WIN32
    _setmode(_fileno(stdout), _O_BINARY);
#endif
    if (argc != 2) return 2;
    if (argv[1][0] == '0') dump(converter);
    else if (argv[1][0] == '1') dump(native);
    else if (argv[1][0] == '2') dump(builtin);
    else return 2;
}
'''
current = (source / "CMakeLists.txt").read_text(encoding="utf-8")
base = subprocess.check_output(["git", "show", args.base_ref + ":CMakeLists.txt"], cwd=source).decode()
results = []
for name, cmake, fixture in [
    ("baseline_oversized", base, "oversized"),
    ("current_catalog", current, "normal"),
    ("oversized", current, "oversized"),
    ("minified_utf8", current, "minified_utf8"),
]:
    root = artifacts / name
    project = root / "source"
    build = root / "build" / "debug"
    specs = project / "model_specs"
    specs.mkdir(parents=True, exist_ok=True)
    for path in (source / "model_specs").glob("*.json"):
        shutil.copyfile(path, specs / path.name)
    if fixture != "normal":
        path = specs / "qwen3_tts.json"
        spec = json.loads(path.read_bytes())
        spec["description"] = ("Large spec with punctuation ; quotes \\\" and backslash \\ . " * 400
                               if fixture == "oversized" else "\u58f0\u97f3\u6d4b\u8bd5" * 2500)
        text = json.dumps(spec, ensure_ascii=False, indent=2 if fixture == "oversized" else None)
        path.write_bytes(text.encode("utf-8"))
    start = cmake.index("# Model specs remain editable")
    end = cmake.index("if (NOT CMAKE_CONFIGURATION_TYPES", start)
    block = cmake[start:end]
    (project / "CMakeLists.txt").write_text(
        "cmake_minimum_required(VERSION 3.20)\nproject(SpecLiteralValidation LANGUAGES CXX)\n"
        "set(AUDIOCPP_DEPLOYMENT_BUILD ON)\n" + block +
        "\nadd_executable(catalog_dump catalog_dump.cpp)\n"
        "target_include_directories(catalog_dump PRIVATE ${CMAKE_BINARY_DIR}/generated)\n"
        "set_target_properties(catalog_dump PROPERTIES CXX_STANDARD 17 CXX_STANDARD_REQUIRED ON CXX_EXTENSIONS OFF)\n"
        "if(MSVC)\n target_compile_options(catalog_dump PRIVATE /utf-8 /permissive-)\nendif()\n",
        encoding="utf-8")
    (project / "catalog_dump.cpp").write_text(cpp, encoding="utf-8")
    configure = subprocess.run(["cmake", "-S", str(project), "-B", str(build), "-DCMAKE_BUILD_TYPE=Debug"],
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    (root / "configure.log").write_bytes(configure.stdout)
    if configure.returncode:
        raise RuntimeError(name + ": configure failed")
    generated = {}
    for catalog in catalogs:
        content = (build / "generated" / catalog).read_bytes()
        import re
        chunks = re.findall(rb'R"AUDIOCPP_SPEC\((.*?)\)AUDIOCPP_SPEC"', content, re.S)
        generated[catalog] = {"chunks": len(chunks), "max_literal_bytes": max(map(len, chunks))}
        if name != "baseline_oversized" and max(map(len, chunks)) > 16000:
            raise RuntimeError(name + ": literal exceeds limit")
    compile_result = subprocess.run(["cmake", "--build", str(build), "--config", "Debug", "--parallel", "4"],
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    (root / "build.log").write_bytes(compile_result.stdout)
    row = {"case": name, "compile_returncode": compile_result.returncode, "catalogs": generated}
    if name == "baseline_oversized" and os.name == "nt":
        row["expected_C2026"] = compile_result.returncode != 0 and b"C2026" in compile_result.stdout
        results.append(row)
        if not row["expected_C2026"]:
            raise RuntimeError("Baseline did not reproduce MSVC C2026")
        continue
    if compile_result.returncode:
        results.append(row)
        (artifacts / "results.json").write_text(json.dumps(results, indent=2))
        raise RuntimeError(name + ": compile failed")
    executable = build / ("Debug/catalog_dump.exe" if os.name == "nt" else "catalog_dump")
    expected = {p.stem: p.read_bytes().replace(b"\r\n", b"\n") for p in specs.glob("*.json")}
    for index, catalog in enumerate(catalogs):
        output = subprocess.check_output([str(executable), str(index)])
        (root / (catalog + ".records")).write_bytes(output)
        position = 0
        actual = {}
        while position < len(output):
            newline = output.index(b"\n", position)
            family, count = output[position:newline].split(b"\t")
            position = newline + 1
            payload = output[position:position + int(count)]
            position += int(count)
            assert output[position:position + 1] == b"\n"
            position += 1
            json.loads(payload)
            key = family.decode("ascii")
            assert key not in actual
            actual[key] = payload
        assert actual == expected, name + ": compiled JSON differs from source"
        row["catalogs"][catalog]["valid_json_and_exact_bytes"] = True
        row["catalogs"][catalog]["families"] = len(actual)
        row["catalogs"][catalog]["sha256"] = hashlib.sha256(output).hexdigest()
    results.append(row)
    (artifacts / "results.json").write_text(json.dumps(results, indent=2))
    print(json.dumps(row), flush=True)
print("PASS: all compiled catalogs contain valid, byte-exact JSON", flush=True)
