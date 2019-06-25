import os
import sys
import errno
import shutil
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--overwrite", action="store_true")
parser.add_argument("--exclude", nargs="+", default=["*.pyc", "__pycache__"])

opts = parser.parse_args()


def ask(msg):

    # Support for being called via script/subprocess
    if not sys.stdout.isatty():
        return False

    try:
        # Python 2 support
        _input = raw_input
    except NameError:
        _input = input

    try:
        value = _input(msg).lower().rstrip()  # account for /n and /r
        return value in ("", "y", "yes", "ok")
    except EOFError:
        return True  # On just hitting enter
    except KeyboardInterrupt:
        return False


build_dir = os.environ["REZ_BUILD_PATH"]
python_dir = os.path.join(build_dir, "python")

print("Building into: %s" % build_dir)

root = os.path.dirname(__file__)
for dirname in ("python", "bin"):
    print("Copying %s/.. (excluding %s)" % (dirname, ", ".join(opts.exclude)))

    shutil.copytree(
        os.path.join(root, dirname),
        os.path.join(build_dir, dirname),
        ignore=shutil.ignore_patterns(*opts.exclude)
    )


if int(os.getenv("REZ_BUILD_INSTALL")):  # e.g. "1"
    install_dir = os.environ["REZ_BUILD_INSTALL_PATH"]
    exists = os.path.exists(install_dir)

    if exists and os.listdir(install_dir):
        print("Previous install found %s" % install_dir)

        if opts.overwrite or ask("Overwrite existing install? [Y/n] "):
            print("Cleaning existing install %s.." % install_dir)
            shutil.rmtree(install_dir)
        else:
            print("Installation directory already exists, try --overwrite")
            exit(1)

    print("Installing into '%s'.." % install_dir)

    try:
        shutil.rmtree(install_dir)  # Created by Rez
    except OSError as e:
        # May not exist
        if e.errno != errno.EEXIST:
            raise

    shutil.copytree(build_dir, install_dir,)
