from hatchling.builders.hooks.plugin.interface import BuildHookInterface
import os
import re
import shutil
import sys
import logging
import subprocess


def compile_protobufs():
    source_protobufs_directory = os.path.join(
        "src", "steam", "utils", "protobuf_manager", "protobufs")

    if os.path.exists(source_protobufs_directory):
        shutil.rmtree(source_protobufs_directory)

    os.makedirs(source_protobufs_directory)

    with open(os.path.join(source_protobufs_directory, "__init__.py"), "w"):
        pass

    proto_files = [file for file in os.listdir(
        "protobufs") if file.endswith(".proto")]
    cmd = [
        sys.executable, "-m", "grpc_tools.protoc",
        "-I", "protobufs",
        f"--python_out={source_protobufs_directory}",
        f"--mypy_out={source_protobufs_directory}",
    ] + proto_files

    subprocess.run(cmd, check=True)


def generate_emsg_enum():
    input_file = os.path.join("protobufs", "enums_clientserver.proto")
    output_file = os.path.join("src", "steam", "enums", "emsg.py")

    if not os.path.exists(input_file):
        logging.warning(f"{input_file} not found. Skipping EMsg generation.")
        return

    with open(input_file, "r", encoding="utf-8") as f:
        content = f.read()

    match = re.search(r"enum EMsg\s*\{([^}]*)\}", content, re.DOTALL)

    if not match:
        logging.warning("EMsg enum not found in enums_clientserver.proto")
        return

    enum_body = match.group(1)
    members: list[tuple[str, int]] = []
    pattern = re.compile(r"^\s*([a-zA-Z0-9_]+)\s*=\s*(\d+);", re.MULTILINE)

    for match in pattern.finditer(enum_body):
        name = match.group(1)

        for prefix in ["k_emsg", "k_em"]:
            if name.lower().startswith(prefix):
                name = name[len(prefix):]
                break

        value = int(match.group(2))
        members.append((name, value))

    lines = [
        "from enum import IntEnum",
        "",
        "",
        "class EMsg(IntEnum):",
    ]

    for name, value in members:
        lines.append(f"    {name} = {value}")

    lines.append("")

    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    with open(output_file, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


class ProtoBuildHook(BuildHookInterface):
    def initialize(self, version, build_data):
        compile_protobufs()
        generate_emsg_enum()
