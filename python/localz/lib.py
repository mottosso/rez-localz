import os
import sys
import shutil
import itertools

from . import _rezapi as rez


def resolve(request, requires=None, full=False):
    requires = requires or []

    if not isinstance(request, (tuple, list)):
        request = [request]

    if not isinstance(requires, (tuple, list)):
        requires = [requires]

    try:
        context = rez.env(request + requires)

    # Handle common errors here
    # The rest goes to the handler in stage()
    except rez.PackageFamilyNotFoundError as e:
        sys.stdout.write("fail\n")

        # Ideally wouldn't have to parse the string-output of
        # this exception, but there isn't anything else we can do.
        try:
            _, package = str(e).split(":", 1)
            package, _ = package.split("(", 1)
            package = package.strip()

        except Exception:
            # In case the string value changes
            raise

        else:
            raise rez.PackageFamilyNotFoundError(
                "Package '%s' wasn't found in any of your "
                "non-local, non-localised package paths" % package
            )

    # Sort out relevant packages
    variants = []
    for variant in context.resolved_packages:

        if not full:
            # Include only requested packages
            if variant.name not in request:
                continue

        variants += [variant]
    return variants


def exists(variant, location=None):
    """Determine whether `variant` is already localised

    A variant is localised if it's coming from the localized_packages_path
    or if an identical variant therein is already present.

    """

    location = location or localized_packages_path()

    if variant.resource.repository_type != "filesystem":
        return False

    # Package path
    package = variant.parent
    current_path = package.resource.path
    current_path = os.path.abspath(current_path)
    current_path = os.path.normpath(current_path)

    # The package we're asking about resides in the localised
    # packages path already.
    if current_path.startswith(location):

        # Memcached isn't smart about when packages are *deleted*
        if rez.config.memcached_uri and os.path.exists(current_path):
            return True

    # The variant is already localised
    it = rez.find(variant.name,
                  str(variant.version),
                  paths=[location])

    existing = list(it)

    if not existing:
        return False

    # Multiple matches are possible
    # E.g. mypackage-1.1.2, mypackage-1.1.2.beta
    for pkg in existing:
        for var in pkg.iter_variants():
            if var.name != variant.name:
                continue
            if var.version != variant.version:
                continue
            if var.index != variant.index:
                continue
            if rez.config.memcached_uri and not os.path.exists(variant.root):
                continue

            return True

    return False


def localized_packages_path():
    path = os.getenv(
        "REZ_LOCALIZED_PACKAGES_PATH",

        # Default
        os.path.expanduser("~/.packages")
    )

    # Sanitise path, protect against e.g. \//\ and ../../
    path = os.path.abspath(path)
    path = os.path.normpath(path)

    return path


def prepare(variant,
            tempdir,
            all_variants=False,
            force=False,
            verbose=0):

    result = rez.copy_package(
        package=variant.parent,

        # Copy only this one variant, unless explicitly overridden
        variants=None if all_variants else [variant.index],

        dest_repository=tempdir,
        shallow=False,
        follow_symlinks=True,

        # Make localized packages as similar
        # to their original as possible
        keep_timestamp=True,

        force=force,

        # Only for emergencies
        verbose=verbose > 2,
    )

    copied = []
    for source, destination in result["copied"]:
        copied += [destination]

    # As we're copying into a staging area, there isn't any
    # risk of packages getting skipped. However make it assert,
    # to ensure it doesn't proceed under false pretenses.
    assert not result["skipped"], (tempdir, result["skipped"])

    return copied


class Animation(object):
    frames = itertools.cycle(r"\|/-")

    def __init__(self, template="{frame}", count=10):
        self._template = template
        self._length = len(template)
        self._count = count

    def __next__(self):
        return self.tell(next(self.frames))

    # Python 2
    def next(self):
        yield self.__next__()

    def step(self):
        next(self)

    def tell(self, frame):
        message = self._template.format(frame=frame)
        message = "\r%s" % message

        sys.stdout.write(message)
        sys.stdout.flush()

    def finish(self):
        self.tell("")


def localize(variant, path=None, verbose=0):
    path = path or localized_packages_path()
    pkg = rez.Package(variant.parent)
    result = rez.copy_package(
        package=pkg,
        dest_repository=path,
        shallow=False,
        follow_symlinks=True,
        keep_timestamp=True,
        force=True,
        verbose=verbose > 2,
    )

    return result


def delocalize(variant, path=None, verbose=0):
    if variant.resource.repository_type != "filesystem":
        raise TypeError(
            "Cannot delocalize a variant "
            "that isn't of repository_type == filesystem"
        )

    path = path or localized_packages_path()
    shutil.rmtree(variant.root)


def is_relocatable(pkg):
    if pkg.relocatable is None:
        return rez.config.default_relocatable
    else:
        return pkg.relocatable


def dirsize(path):
    return sum(
        os.path.getsize(os.path.join(dirpath, filename))
        for dirpath, dirnames, filenames in os.walk(path)
        for filename in filenames
    )
