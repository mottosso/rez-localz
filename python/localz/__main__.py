import os
import sys
import time
import shutil
import logging
import argparse
import tempfile
import contextlib

from rez.config import config
from rez.packages_ import Package, Variant, iter_packages
from rez.utils.formatting import PackageRequest
from rez import package_copy, __version__

try:
    from rez import __project__
except ImportError:
    # Vanilla Rez
    __project__ = "rez"

parser = argparse.ArgumentParser()
parser.add_argument("request", nargs="+", help=(
    "Packages to localize"))
parser.add_argument("--paths", nargs="+", metavar="PATHS", help=(
    "Package search path (ignores --no-local if set)"))
parser.add_argument("-f", "--force", action="store_true", help=(
    "Copy package even if it isn't relocatable (use at your own risk)"))
parser.add_argument("-k", "--keep-timestamp", action="store_true", help=(
    "Keep timestamp of source package. Note that this is ignored if "
    "you're copying variant(s) into an existing package."))
parser.add_argument("-v", "--verbose", action="count")

opts = parser.parse_args()
log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)


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


def tell(msg, newlines=1):
    if log.level == logging.CRITICAL:
        return

    import sys
    sys.stdout.write("%s%s" % (msg, "\n" * newlines))


@contextlib.contextmanager
def stage(msg, timing=True, tempdir=False):
    verbose = log.level < logging.INFO
    tell(msg, 0)
    t0 = time.time()

    if tempdir:
        tempdir = tempfile.mkdtemp()

    try:
        yield tempdir
    except Exception:
        if not verbose:
            tell("fail")
        raise
    else:
        if not verbose:
            return

        if timing:
            tell("ok - %.2fs" % (time.time() - t0))
        else:
            tell("ok")
    finally:
        if tempdir:
            tell("Cleaning up temporary files.")
            shutil.rmtree(tempdir)


tell("Using %s-%s" % (__project__, __version__))

# Find local packages path
packages = list()
paths = opts.paths or config.nonlocal_packages_path

tell("Packages are discovered from these paths:")
for path in paths:
    tell("  %s" % path, 1)

with stage("Resolving requested packages.. "):
    # Resolve request
    for request in opts.request:
        request = PackageRequest(request)
        query = iter_packages(
            name=request.name,
            range_=request.range_,
            paths=paths
        )

        results = list(query)
        if not results:
            sys.stderr.write("\nNo matching packages found.\n")
            sys.exit(1)

        package = list(sorted(results, key=lambda x: x.version))[-1]
        packages += [package]


tempdir = tempfile.mkdtemp()
copied = list()
with stage("Preparing packages.. "):
    for pkg in packages:
        result = package_copy.copy_package(
            package=pkg,
            dest_repository=tempdir,
            shallow=False,
            follow_symlinks=True,
            keep_timestamp=opts.keep_timestamp,
            force=opts.force,
            verbose=opts.verbose,
        )

        for source, destination in result["copied"]:
            copied += [destination]

        # As we're copying into a staging area, there isn't any
        # risk of packages getting skipped. However make it assert,
        # to ensure it doesn't proceed under false pretenses.
        assert not result["skipped"], (tempdir, result["skipped"])

with stage("Determining relocatability.. "):
    def is_relocatable(pkg):
        if pkg.relocatable is None:
            return config.default_relocatable
        else:
            return pkg.relocatable

    unrelocatable = [var for var in copied if not is_relocatable(var)]


if unrelocatable:
    tell("Some packages are unable to be relocated")
    tell("Use --force to forcibly relocate these, note that they may "
         "not function as expected.")

    for variant in unrelocatable:
        tell("  %s-%s" % (variant.name, variant.version))

    shutil.rmtree(tempdir)
    exit(1)

skipped = list()
local_packages_path = config.local_packages_path
with stage("Determining existing packages.."):
    for variant in copied[:]:
        it = iter_packages(variant.name,
                           range_=str(variant.version),
                           paths=[local_packages_path])

        for package in it:
            for existing in package.iter_variants():
                variant = Variant(variant)

                if existing.name != variant.name:
                    continue

                if existing.version != variant.version:
                    continue

                if existing.index != variant.index:
                    continue

                # Already exists!
                skipped += [variant]

    for existing in skipped:
        copied.remove(variant)


if not copied:
    tell("All requested packages were already localised")
    shutil.rmtree(tempdir)
    exit(0)


tell("The following NEW packages will be localised:")
for variant in copied:
    tell("  %s-%s" % (variant.name, variant.version))

if skipped:
    tell("The following packages will be SKIPPED:")
    for variant in skipped:
        tell("  %s-%s" % (variant.name, variant.version))

tell("Packages will be localized to %s" % local_packages_path)

size = sum(
    os.path.getsize(os.path.join(dirpath, filename))
    for dirpath, dirnames, filenames in os.walk(tempdir)
    for filename in filenames
) / (10.0 ** 6)  # mb

tell("After this operation, %.2f mb will be used" % size)

if not ask("Do you want to continue? [Y/n] "):
    tell("Cancelled")
    shutil.rmtree(tempdir)
    exit(0)

# Report
tell("Localizing..")
for variant in copied:
    tell("  %s-%s" % (variant.name, variant.version))

    pkg = Package(variant.parent)
    result = package_copy.copy_package(
        package=pkg,
        dest_repository=local_packages_path,
        shallow=False,
        follow_symlinks=True,
        keep_timestamp=True,
        force=True,
        verbose=opts.verbose,
    )

    if result["skipped"]:
        print("These were already localised")

tell("Success")

# Cleanup
tell("Cleaning up temporary files..")
shutil.rmtree(tempdir)
