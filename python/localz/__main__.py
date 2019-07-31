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
import inspect

from . import lib, version
from . import _rezapi as rez

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
parser.add_argument("-y", "--yes", action="store_true", help=(
    "Do not ask about whether to localise"))
parser.add_argument("--requires", nargs="+", default=[], metavar="PKG", help=(
    "Localize request, fulfilling these requirements"))
parser.add_argument("--all-variants", action="store_true", help=(
    "Copy not just the resolved variant, but all of them"))
parser.add_argument("--prefix", nargs="+", metavar="PATH", help=(
    "Write localised packages to here, instead of "
    "REZ_LOCALIZED_PACKAGES_PATH"))
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
    frameinfo = inspect.currentframe()
    sys.stderr.write("L%s ABORTED: %s\n" % (frameinfo.f_back.f_lineno, msg))
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


@contextlib.contextmanager
def stage(msg, count=0):
    t0 = time.time()

    if count:
        msg = "%s {frame}" % msg

    bar = lib.Animation(msg, count)

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


tell("Using %s-%s" % (rez.project, rez.version))

# Find local packages path
variants = list()
nonlocal_packages_path = opts.paths or rez.config.nonlocal_packages_path
localized_packages_path = opts.prefix or lib.localized_packages_path()

tell("Packages requested: %s" % " ".join(opts.request))
tell("Packages will be localized to %s" % localized_packages_path)
tell("Packages are discovered from these paths:")
for path in nonlocal_packages_path:
    tell("  %s" % path, 1)

with stage("Resolving requested packages.."):
    try:
        variants = lib.resolve(opts.request,
                               opts.requires,
                               opts.full)

    except Exception as e:
        sys.stdout.write("\n")
        abort(traceback.format_exc())

    except rez.PackageFamilyNotFoundError as e:
        sys.stdout.write("\n")
        abort(traceback.format_exc())


count = len(variants)
copied = list()
skipped = list()
with stage("Preparing packages..", count) as bar:
    for var in variants:

        # Don't want to localise already-localised packages
        if lib.exists(var, localized_packages_path):
            skipped += [var.resource]
            continue

        copied += lib.prepare(var,
                              tempdir,
                              opts.all_variants,
                              opts.force,
                              opts.verbose)

        bar.step()


with stage("Determining relocatability.."):
    unrelocatable = [var for var in copied if not lib.is_relocatable(var)]


if unrelocatable:
    tell("Some packages are unable to be relocated")
    tell("Use --force to forcibly relocate these, note that they may "
         "not function as expected.")

    for variant in unrelocatable:
        tell("  %s-%s" % (variant.name, variant.version))

    shutil.rmtree(tempdir)
    exit(1)


if skipped:
    tell("The following packages were already available locally:")
    for variant in skipped:
        tell("  %s-%s  (%s)" % (variant.name, variant.version, variant.uri))

if not copied:
    tell("All requested packages were already localized")
    shutil.rmtree(tempdir)
    exit(0)

tell("The following NEW packages will be localized:")
for variant in copied:
    tell("  %s-%s" % (variant.name, variant.version))

size = lib.dirsize(tempdir) / (10.0 ** 6)  # mb

tell("After this operation, %.2f mb will be used" % size)

if not opts.yes and not ask("Do you want to continue? [Y/n] "):
    tell("Cancelled")
    shutil.rmtree(tempdir)
    exit(0)

# Report
tell("Localizing..")
for variant in copied:
    tell("  %s-%s" % (variant.name, variant.version))
    result = lib.localize(variant, localized_packages_path, opts.verbose)

    if result["skipped"]:
        print("These were already localized")

tell("Success")

# Cleanup
tell("Cleaning up temporary files..")
shutil.rmtree(tempdir)

if localized_packages_path not in map(os.path.normpath,
                                      rez.config.packages_path):
    tell("WARNING: Localised packages currently not in your Rez search path")
    tell("         Add '%s' to your REZ_PACKAGES_PATH"
         % localized_packages_path)
