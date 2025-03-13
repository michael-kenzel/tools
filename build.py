#!/usr/bin/env python3

import subprocess
import argparse
from pathlib import Path


def cmd(*args, **kwargs):
	print(args, kwargs)
	p = subprocess.Popen(args, **kwargs)
	return p.wait()

def git(*args, **kwargs):
	if cmd("git", *args, **kwargs) != 0:
		raise Exception(f"git command failed: {' '.join(args)} {kwargs}")

def pull_git_dependency(dir, url, *, branch = "main"):
	if dir.exists():
		git("fetch", cwd=dir)
		git("checkout", branch, cwd=dir)
		git("merge", f"origin/{branch}", "--ff-only", cwd=dir)
	else:
		git("clone", url, dir, "-b", branch)

def cmake_var_def_args(vars):
	for name, value in vars.items():
		match value:
			case Path(): yield f"-D{name}:PATH={value}" # necessary so that cmake deals with \ correctly
			case _: yield f"-D{name}={value}"

def cmake_configure(build_dir, source_dir, configs, **vars):
	if cmd("cmake", "-G", "Ninja", "-DCMAKE_BUILD_TYPE=Release", *tuple(cmake_var_def_args(vars)), source_dir, cwd=build_dir) != 0:
		raise Exception(f"cmake command failed: {build_dir} {source_dir} {configs} {vars}")

def ninja(build_dir, *targets):
	from time import monotonic_ns
	t_start = monotonic_ns()
	if cmd("ninja", *targets, cwd=build_dir) != 0:
		raise Exception(f"ninja failed: {build_dir} {targets}")
	t_end = monotonic_ns()
	print(f"time elapsed: {(t_end - t_start) / 1e9} s")


tools = dict()
def tool(cls):
	global tools
	tools[cls.__name__.lower()] = cls
	return cls


@tool
class Ninja:
	def __init__(self, dir):
		dir.mkdir(exist_ok=True)
		self.source_dir = dir/"src"
		self.build_dir = dir

	def pull(self):
		pull_git_dependency(self.source_dir, "https://github.com/ninja-build/ninja.git", branch="master")

	def configure(self, configs):
		pass

	def build(self, configs):
		cmd("python", self.source_dir/"configure.py", "--bootstrap", cwd=self.build_dir)

	def artifacts(self):
		yield self.build_dir/"ninja.exe"


@tool
class LLVM:
	def __init__(self, dir):
		dir.mkdir(exist_ok=True)
		self.source_dir = dir/"src"
		self.build_dir = dir/"build"
		self.install_dir = dir

	def pull(self):
		pull_git_dependency(self.source_dir, "https://github.com/llvm/llvm-project.git")

	def configure(self, configs):
		self.build_dir.mkdir(exist_ok=True)

		cmake_configure(self.build_dir, self.source_dir/"llvm", configs,
			CMAKE_C_COMPILER="clang-cl",
			CMAKE_CXX_COMPILER="clang-cl",
			CMAKE_INSTALL_PREFIX=self.install_dir,
			LLVM_OPTIMIZED_TABLEGEN=True,
			LLVM_ENABLE_LLD=True,
			LLVM_TARGETS_TO_BUILD="X86;AArch64;NVPTX",
			LLVM_ENABLE_PROJECTS="clang;clang-tools-extra;lld",
			LLVM_ENABLE_BINDINGS=False,
			LLVM_INCLUDE_TOOLS=True,
			LLVM_INCLUDE_TESTS=False,
			LLVM_INCLUDE_BENCHMARKS=False,
			LLVM_INCLUDE_EXAMPLES=False,
			LLVM_INCLUDE_DOCS=False,
			CLANG_INCLUDE_TESTS=False,
			CLANG_INCLUDE_DOCS=False,
		)

	def build(self, configs):
		ninja(self.build_dir, "install")

	def artifacts(self):
		with open(self.build_dir/"install_manifest.txt") as file:
			for l in file:
				yield Path(l.strip())


def dependencies(this_dir, include):
	if Ninja in include:
		yield Ninja(this_dir/"ninja")

	if LLVM in include:
		yield LLVM(this_dir/"llvm")


def pull(deps):
	for dep in deps:
		dep.pull()


def build(deps, *, configs):
	for dep in deps:
		dep.configure(configs)
		dep.build(configs)


def package(this_dir, deps):
	import tempfile

	for dep in deps:
		dest = (this_dir/type(dep).__name__).with_suffix(".7z")

		if dest.exists():
			dest.unlink()

		with tempfile.NamedTemporaryFile(delete_on_close=False) as listfile:
			for a in dep.artifacts():
				listfile.write(str(a.relative_to(this_dir)).encode())
				listfile.write(b'\n')
			listfile.close()

			cmd("7z", "a", "-t7z", "-spf", f"-ir@{listfile.name}", dest, cwd=this_dir)


def main(args):
	this_dir = Path(__file__).parent

	deps = [d for d in dependencies(this_dir, args.tools)]

	match args.command:
		case "pull": pull(deps)
		case "build": build(deps, configs=args.configs)
		case "package": package(this_dir, deps)


def parse_args():
	global tools

	def lookup_tool(name: str):
		tool = tools.get(name)
		if not tool:
			raise ValueError()
		return tool

	args = argparse.ArgumentParser()
	sub_args = args.add_subparsers(required=True)

	def add_command(name):
		args = sub_args.add_parser(name)
		args.set_defaults(command=name)
		args.add_argument("tools", nargs="*", type=lookup_tool, default=list(tools.values()))
		return args

	pull_cmd = add_command("pull")

	build_cmd = add_command("build")
	build_cmd.add_argument("-cfg", "--config", action="append", dest="configs", default=["Release"])

	build_cmd = add_command("package")

	return args.parse_args()

if __name__ == "__main__":
	main(parse_args())
