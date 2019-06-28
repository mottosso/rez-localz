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
import itertools
import contextlib

from rez.config import config
from rez.resolved_context import ResolvedContext
from rez.packages_ import Package
from rez.exceptions import PackageFamilyNotFoundError
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
Localize packages from one location to another, to improve
performance or facilitate remote collaboration on software
or content.
"""

epilog = """\
examples:
  Latest available version of Maya
  $ rez env localz -- localize maya

  Version of Maya, required by Alita
  $ rez env localz -- localize maya --requires alita

  Series of requests, all compatible with each other
  $ rez env localz -- localize six-1 maya-2018 python-3.7

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
    "Localize request, fulfilling these requirements"))
parser.add_argument("--all-variants", action="store_true", help=(
    "Copy not just the resolved variant, but all of them"))
parser.add_argument("--paths", nargs="+", metavar="PATH", help=(
    "Override package search path"))
parser.add_argument("-f", "--force", action="store_true", help=(
    "Copy package even if it isn't relocatable (use at your own risk)"))
parser.add_argument("-v", "--verbose", default=0, action="count")
parser.add_argument("--full", action="store_true", help=(
    "Localize requests and requirements of requests. "
    "Use this to create a fully localized context"))


opts = parser.parse_args()
log = logging.getLogger(__name__)

logginglevel = {
    0: logging.INFO,
    1: logging.DEBUG,
    2: logging.DEBUG,
}.get(opts.verbose, logging.INFO)
log.setLevel(logginglevel)


def tell(msg, newlines=1):
    if log.level > logging.INFO:
        return

    sys.stdout.write("%s%s" % (msg, "\n" * newlines))

    if sys.stdout.isatty():
        # Give the user some time to react
        time.sleep(0.01)


def warn(msg, newlines=1):
    if log.level > logging.WARNING:
        return

    sys.stderr.write("WARNING: %s%s" % (msg, "\n" * newlines))


def abort(msg):
    sys.stderr.write("ABORTED: %s\n" % msg)
    exit(1)


if opts.version:
    tell("localz-%s" % version)
    exit(0)

if not opts.request:
    parser.print_help()
    warn("At least one request is required")
    exit(1)


def cleanup():
    if not os.path.exists(tempdir):
        return

    try:
        sys.stdout.write("Cleaning up temporary files.. ")
        shutil.rmtree(tempdir)
        sys.stdout.write("ok\n")
    except OSError as e:
        # It may already have been cleaned-up
        if e.errno not in (errno.ENOENT, errno.EEXIST, errno.ENOTDIR):
            sys.stdout.write("fail\n")
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


class Animation(object):
    frames = itertools.cycle(r"\|/-")

    def __init__(self, template="{frame}", count=10):
        self._template = template
        self._length = len(template)
        self._count = count

    def __next__(self):
        self.tell(next(self.frames))

    def step(self):
        next(self)

    def tell(self, frame):
        message = self._template.format(frame=frame)
        message = "\r%s" % message

        sys.stdout.write(message)
        sys.stdout.flush()

    def finish(self):
        self.tell("")


@contextlib.contextmanager
def stage(msg, count=0):
    t0 = time.time()

    if count:
        msg = "%s {frame}" % msg

    bar = Animation(msg, count)

    try:
        next(bar)
        yield bar

    except Exception as e:
        bar.finish()
        tell("fail")

        if opts.verbose == 1:
            tell(e)

        elif opts.verbose > 1:
            traceback.print_exc()

        else:
            tell("Pass --verbose for more details")

        exit(1)

    else:
        bar.finish()
        tell("ok - %.2fs" % (time.time() - t0))


# Keep it tidy
tempdir = tempfile.mkdtemp()
sys.excepthook = excepthook
atexit.register(cleanup)


tell("Using %s-%s" % (__project__, rez_version))

# Find local packages path
variants = list()
nonlocal_packages_path = opts.paths or config.nonlocal_packages_path
localized_packages_path = config.local_packages_path

tell("Packages requested: %s" % " ".join(opts.request))
tell("Packages will be localized to %s" % localized_packages_path)
tell("Packages are discovered from these paths:")
for path in nonlocal_packages_path:
    tell("  %s" % path, 1)

with stage("Resolving requested packages.."):
    try:
        context = ResolvedContext(opts.request + opts.requires)

    # Handle common errors here
    # The rest goes to the handler in stage()
    except PackageFamilyNotFoundError as e:
        sys.stdout.write("fail\n")

        # Ideally wouldn't have to parse the string-output of
        # this exception, but there isn't anything else we can do.
        try:
            _, package = str(e).split(":", 1)
            package, _ = package.split("(", 1)
            package = package.strip()

        except Exception as e:
            # In case the string value changes
            abort(str(e))

        else:
            abort(
                "Package '%s' wasn't found in any of your "
                "non-local package paths" % package
            )

    # Sort out relevant packages
    for variant in context.resolved_packages:

        if not opts.full:
            # Include only requested packages
            if variant.name not in opts.request:
                continue

        variants += [variant]


count = len(variants)
copied = list()
skipped = list()
with stage("Preparing packages..", count) as bar:
    for var in variants:

        # Don't want to localise already-localised packages
        if var.is_local:
            skipped += [var.resource]
            continue

        result = package_copy.copy_package(
            package=var.parent,

            # Copy only this one variant, unless explicitly overridden
            variants=None if opts.all_variants else [var.index],

            dest_repository=tempdir,
            shallow=False,
            follow_symlinks=True,

            # Make localized packages as similar
            # to their original as possible
            keep_timestamp=True,

            force=opts.force,

            # Only for emergencies
            verbose=opts.verbose > 2,
        )

        for source, destination in result["copied"]:
            copied += [destination]

        # As we're copying into a staging area, there isn't any
        # risk of packages getting skipped. However make it assert,
        # to ensure it doesn't proceed under false pretenses.
        assert not result["skipped"], (tempdir, result["skipped"])

        bar.step()


with stage("Determining relocatability.."):
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


if not copied:
    tell("All requested packages were already localized")
    shutil.rmtree(tempdir)
    exit(0)


tell("The following NEW packages will be localized:")
for variant in copied:
    tell("  %s-%s" % (variant.name, variant.version))

if skipped:
    tell("The following packages were already available locally:")
    for variant in skipped:
        tell("  %s-%s" % (variant.name, variant.version))

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
        dest_repository=localized_packages_path,
        shallow=False,
        follow_symlinks=True,
        keep_timestamp=True,
        force=True,
        verbose=opts.verbose,
    )

    if result["skipped"]:
        print("These were already localized")

tell("Success")

# Cleanup
tell("Cleaning up temporary files..")
shutil.rmtree(tempdir)
