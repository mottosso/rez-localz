
try:
    # The __version__ module is written into the built Python
    # project, such that we can forward the package version
    from . import __version__ as localz_version
    version = localz_version.version

except ImportError:
    # If none exists, then it's safe to assume this version
    # hasn't been built.
    version = "dev"
