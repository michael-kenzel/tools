#!/usr/bin/env python3
import winreg
import subprocess
import argparse
from pathlib import Path

def distros():
	with winreg.OpenKeyEx(winreg.HKEY_CURRENT_USER, "Software\\Microsoft\\Windows\\CurrentVersion\\Lxss") as Lxss:
		num_distros, _, _ = winreg.QueryInfoKey(Lxss)
		for i in range(0, num_distros):
			distro_subkey = winreg.EnumKey(Lxss, i)
			with winreg.OpenKey(Lxss, distro_subkey) as distro:
				name, type = winreg.QueryValueEx(distro, "DistributionName")
				path, type = winreg.QueryValueEx(distro, "BasePath")
				yield name, Path(path)/"ext4.vhdx"

def main(args):
	for name, path in distros():
		if args.distro and name not in args.distro:
			print("skipping", name)
			continue
		print(name, "at", path)
		print(path.stat().st_size/(1024**3), "GiB")
		p = subprocess.Popen(["diskpart"], stdin=subprocess.PIPE)
		p.communicate(f"select vdisk file={path}\r\ncompact vdisk\r\nexit".encode())
		if p.returncode != 0:
			raise Exception("diskpart failed")
		print(path.stat().st_size/(1024**3), "GiB")


if __name__ == "__main__":
	argparser = argparse.ArgumentParser()
	argparser.add_argument("-d", "--distro", action="append", help="specify distro to compact")
	main(argparser.parse_args())
