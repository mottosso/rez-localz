import os
import sys
import time
import errno
import shutil
import atexit
import logging
import argparse
import tempfile
import traceback
import contextlib

from rez.config import config
from rez.resolved_context import ResolvedContext
from rez.packages_ import Package, Variant, iter_packages
from rez import package_copy, __version__ as rez_version

try:
    from rez import __project__
except ImportError:
    # Vanilla Rez
    __project__ = "rez"

try:
    # The __version__ module is written into the built Python
    # project, such that we can forward the package version
    from . import __version__ as localz_version
    version = localz_version.version

except ImportError:
    # If none exists, then it's safe to assume this version
    # hasn't been built.
    version = "dev"

description = """\
Localise packages from one location to another, to improve
performance or facilitate remote collaboration on software
or content.
"""

epilog = """\
examples:
  Latest available version of Maya
  $ rez env localz -- localise maya

  Version of Maya, required by Alita
  $ rez env localz -- localise maya --requires alita

  Series of requests, all compatible with each other
  $ rez env localz -- localise six-1 maya-2018 python-3.7

"""

parser = argparse.ArgumentParser(
    prog="localz",
    formatter_class=argparse.RawDescriptionHelpFormatter,
    description=description,
    epilog=epilog)
parser.add_argument("request", nargs="*", help=(
    "Packages to localize"), metavar="PKG")
parser.add_argument("--version", action="store_true", help=(
    "Print version and exit"))
parser.add_argument("--requires", nargs="+", default=[], metavar="PKG", help=(
    "Localise request, fulfilling these requirements"))
parser.add_argument("--all-variants", action="store_true", help=(
    "Copy not just the resolved variant, but all of them"))
parser.add_argument("--paths", nargs="+", metavar="PATH", help=(
    "Package search path (ignores --no-local if set)"))
parser.add_argument("-f", "--force", action="store_true", help=(
    "Copy package even if it isn't relocatable (use at your own risk)"))
parser.add_argument("-v", "--verbose", action="count")


log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)
opts = parser.parse_args()


def tell(msg, newlines=1):
    if log.level > logging.INFO:
        return

    sys.stdout.write("%s%s" % (msg, "\n" * newlines))


def warn(msg, newlines=1):
    if log.level > logging.WARNING:
        return

    sys.stderr.write("%s%s" % (msg, "\n" * newlines))


if opts.version:
    tell("localz-%s" % version)
    exit(0)

if not opts.request:
    parser.print_help()
    warn("At least one request is required")
    exit(1)


def cleanup():
    try:
        shutil.rmtree(tempdir)
    except OSError as e:
        # It may already have been cleaned-up
        if e.errno not in (errno.ENOENT, errno.EEXIST, errno.ENOTDIR):
            print("errno: %s" % e.errno)
            traceback.print_exc()


def excepthook(type, value, traceback):
    """Clean up temporary files"""

    cleanup()
    sys.__excepthook__(type, value, traceback)


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


@contextlib.contextmanager
def stage(msg, timing=True):
    verbose = log.level < logging.INFO
    tell(msg, 0)
    t0 = time.time()

    try:
        yield
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


# Keep it tidy
tempdir = tempfile.mkdtemp()
sys.excepthook = excepthook
atexit.register(cleanup)


tell("Using %s-%s" % (__project__, rez_version))

# Find local packages path
variants = list()
paths = opts.paths or config.nonlocal_packages_path

tell("Packages are discovered from these paths:")
for path in paths:
    tell("  %s" % path, 1)

with stage("Resolving requested packages.. "):
    context = ResolvedContext(opts.request + opts.requires)

    # Sort out relevant packages
    for variant in context.resolved_packages:
        if variant.name not in opts.request:
            continue

        variants += [variant]


copied = list()
with stage("Preparing packages.. "):
    for var in variants:
        result = package_copy.copy_package(
            package=var.parent,

            # Copy only this one variant, unless explicitly overridden
            variants=None if opts.all_variants else [var.index],

            dest_repository=tempdir,
            shallow=False,
            follow_symlinks=True,

            # Make localised packages as similar
            # to their original as possible
            keep_timestamp=True,

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
