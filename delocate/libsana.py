""" Analyze libraries in trees

Analyze library dependencies in paths and wheel files
"""

import os
from os.path import basename, dirname, join as pjoin, realpath

import logging
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    Iterator,
    List,
    Mapping,
    Optional,
    Set,
    Text,
    Tuple,
)
import warnings

import six

from .tools import (get_install_names, zip2dir, get_rpaths,
                    get_environment_variable_paths)
from .tmpdirs import TemporaryDirectory


logger = logging.getLogger(__name__)


class DependencyNotFound(Exception):
    """Raised by tree_libs or resolve_rpath if an expected dependency is
    missing.
    """


class DependencyTree(object):
    """Info on a library and all of its dependences.

    Provide the path to the first library and all other information will be
    filled automatically.

    Parameters
    ----------
    path : str
        The path of a library.
    dependencies : mapping of (DependencyTree: str) or None, optional
        The dependencies of a library if known.  If None is given then they
        will be detected automatically.  See attributes section.
    filt_func : None or callable, optional
        If None, inspect all files for library dependencies. If callable,
        accepts filename as argument, returns True if we should inspect the
        file, False otherwise.
    skip_missing : bool, default=False
        Determines if dependency resolution failures are considered a critical
        error to be raised.
        Otherwise missing libraries are shown in error logs.
    cache : dict of str: DependencyTree
        A cache of DependencyTree objects used to detect cyclic dependences.
        The keys are the canonical (``os.path.realpath``) file path of the
        DependencyTree value.

    Attributes
    ----------
    path : str
        The canonical (``os.path.realpath``) file path of this library.
    dependencies : dict of (DependencyTree: str)
        The dependencies of this library, which themselves may have their own
        dependencies.
        The key is the DependencyTree, the value is the install_name which
        resolved to that library.
        Libraries may depend on each other in a cycle.

    Raises
    ------
    DependencyNotFound
        When any dependencies can not be located and `skip_missing` is False.
    """

    def __init__(
        self,
        path,  # type: Text
        dependencies=None,  # type: Optional[Mapping[DependencyTree, Text]]
        filt_func=None,  # type: Optional[Callable[[Text], bool]]
        skip_missing=False,  # type: bool
        cache=None,  # type: Optional[Dict[Text, DependencyTree]]
    ):
        # type: (...) -> None
        self.path = realpath(path)
        if cache is None:
            cache = {}
        cache[self.path] = self
        if not os.path.isfile(self.path):
            if skip_missing:
                # Disable dependencies auto-detection for this library.
                dependencies = dependencies or {}
                logger.error("Missing dependency stubbed: %s", self.path)
            else:
                raise DependencyNotFound(self.path)
        if dependencies is None:  # Auto-detect dependencies recursively.
            self.dependencies = dict(
                self.__find_dependencies(filt_func, skip_missing, cache)
            )
        else:
            self.dependencies = dict(dependencies)

    def __find_dependencies(
        self,
        filt_func,  # type: Optional[Callable[[Text], bool]]
        skip_missing,  # type: bool
        cache,  # type: Dict[Text, DependencyTree]
    ):
        # type: (...) -> Iterator[Tuple[DependencyTree, Text]]
        """Detect and return this libraries dependences.

        Yields
        ------
        DependencyTree
            All direct dependencies of this library which can have dependencies
            themselves.

        Raises
        ------
        DependencyNotFound
            When any dependencies can not be located and `skip_missing` is
            False.
        """
        if filt_func is not None and not filt_func(self.path):
            return
        rpaths = get_rpaths(self.path) + get_environment_variable_paths()
        for install_name in get_install_names(self.path):
            try:
                if install_name.startswith("@"):
                    dependency_path = resolve_rpath(
                        install_name,
                        rpaths,
                        loader_path=dirname(self.path),
                    )
                else:
                    dependency_path = search_environment_for_lib(install_name)
                if not os.path.exists(dependency_path):
                    raise DependencyNotFound(dependency_path)
            except DependencyNotFound:
                error_msg = (
                    "\n{0} not found:"
                    "\n  Needed by: {1}"
                    "\n  Search path:\n    {2}".format(
                        install_name, self.path, "\n    ".join(rpaths)
                    )
                )
                if skip_missing:
                    logger.error(error_msg)
                else:
                    raise DependencyNotFound(error_msg)

            if dependency_path in cache:  # Handle cyclic dependencies.
                yield cache[dependency_path], install_name
                continue
            if dependency_path != install_name:
                logger.debug(
                    "\n%s resolved to:\n%s", install_name, dependency_path
                )
            yield DependencyTree(
                path=dependency_path,
                dependencies=None,  # Recurse into dependencies.
                filt_func=filt_func,
                skip_missing=skip_missing,
                cache=cache,
            ), install_name

    def walk(self, visited=None):
        # type: (Optional[Set[DependencyTree]]) -> Iterator[DependencyTree]
        """Iterate over all of this trees dependencies inclusively.

        Parameters
        ----------
        visited : set of DependencyTree
            This set is updated with new DependencyTree's as they're visited.
            This is used to prevent infinite recursion.

        Yields
        ------
        DependencyTree
            Iterates over each dependency including itself without duplicates.
        """
        if visited is None:
            visited = {self, }
        elif self in visited:
            return
        else:
            visited.add(self)
        yield self
        for dependency in self.dependencies:
            for sub_dependency in dependency.walk(visited=visited):
                yield sub_dependency

    def __eq__(self, other):
        # type: (Any) -> bool
        if not isinstance(other, DependencyTree):
            return False
        return self.path == other.path

    def __hash__(self):
        # type: () -> int
        return hash(self.path)

    def __repr__(self):
        # type: () -> str
        parameters = ["path={0!r}".format(self.path), "dependencies=None"]
        if not os.path.isfile(self.path):
            parameters.append("skip_missing=True")
        return "DependencyTree({0})".format(", ".join(parameters))


def dependency_walk(
    root_path,  # type: Text
    filt_func=None,  # type: Optional[Callable[[Text], bool]]
):
    # type: (...) -> Iterator[DependencyTree]
    """Walk along dependences starting with the libraries within `root_path`.

    Parameters
    ----------
    root_path : str
        root path of tree to search for libraries depending on other libraries.
    filt_func : None or callable, optional
        If None, inspect all files for library dependencies. If callable,
        accepts filename as argument, returns True if we should inspect the
        file, False otherwise.

    Yields
    ------
    DependencyTree
        Iterates over the libraries in `root_path` and each of their
        dependencies without any duplicates.

    Raises
    ------
    DependencyNotFound
        When any dependencies can not be located.
    """
    # This cache is what prevents yielding duplicates.
    cache = {}  # type: Dict[Text, DependencyTree]
    for dirpath, dirnames, basenames in os.walk(root_path):
        for base in basenames:
            depending_libpath = realpath(pjoin(dirpath, base))
            if depending_libpath in cache:
                continue  # A library in root_path was a dependency of another.
            if filt_func and not filt_func(depending_libpath):
                continue
            for library in DependencyTree(
                path=depending_libpath, filt_func=filt_func, cache=cache
            ).walk():
                yield library


def tree_libs(
    start_path,  # type: Text
    filt_func=None,  # type: Optional[Callable[[Text], bool]]
):
    # type: (...) -> Dict[Text, Dict[Text, Text]]
    """ Return analysis of library dependencies within `start_path`

    Parameters
    ----------
    start_path : str
        root path of tree to search for libraries depending on other libraries.
    filt_func : None or callable, optional
        If None, inspect all files for library dependencies. If callable,
        accepts filename as argument, returns True if we should inspect the
        file, False otherwise.
    Returns
    -------
    lib_dict : dict
        dictionary with (key, value) pairs of (``libpath``,
        ``dependings_dict``).

        ``libpath`` is a canonical (``os.path.realpath``) filename of library,
        or library name starting with {'@loader_path'}.


        ``dependings_dict`` is a dict with (key, value) pairs of
        (``depending_libpath``, ``install_name``), where ``dependings_libpath``
        is the canonical (``os.path.realpath``) filename of the library
        depending on ``libpath``, and ``install_name`` is the "install_name" by
        which ``depending_libpath`` refers to ``libpath``.

    Notes
    -----

    See:

    * https://developer.apple.com/library/mac/documentation/Darwin/Reference/ManPages/man1/dyld.1.html  # noqa: E501
    * http://matthew-brett.github.io/pydagogue/mac_runtime_link.html

    .. deprecated:: 0.8
        This function does not support `@loader_path` and only returns the
        direct dependencies of the libraries in `start_path`.

        :class:`DependencyTree` should be used instead.
    """
    warnings.warn(
        "tree_libs doesn't support @loader_path and has been deprecated"
        " in favor of DependencyTree.",
        DeprecationWarning,
        stacklevel=2,
    )
    lib_dict = {}  # type: Dict[Text, Dict[Text, Text]]
    for dirpath, dirnames, basenames in os.walk(start_path):
        for base in basenames:
            depending_libpath = realpath(pjoin(dirpath, base))
            if filt_func is not None and not filt_func(depending_libpath):
                continue
            dep_tree = DependencyTree(
                path=depending_libpath,
                filt_func=filt_func,
                skip_missing=True,
            )
            for depending, install_name in dep_tree.dependencies.items():
                if install_name.startswith("@loader_path/"):
                    # Support for `@loader_path` would break existing callers.
                    logger.debug(
                        "Excluding %s because it has '@loader_path'.",
                        install_name
                    )
                    continue
                lib_dict.setdefault(depending.path, {})
                lib_dict[depending.path][dep_tree.path] = install_name
    return lib_dict


def resolve_rpath(lib_path, rpaths, loader_path, executable_path="."):
    # type: (Text, Iterable[Text], Text, Text) -> Text
    """ Return `lib_path` with any special runtime linking names resolved.

    If `lib_path` has `@rpath` then returns the first `rpaths`/`lib_path`
    combination found.  If the library can't be found in `rpaths` then
    DependencyNotFound is raised.

    `@loader_path` and `@executable_path` are resolved with their respective
    parameters.

    Parameters
    ----------
    lib_path : str
        The path to a library file, which may or may not be a relative path
        starting with `@rpath`, `@loader_path`, or `@executable_path`.
    rpaths : sequence of str
        A sequence of search paths, usually gotten from a call to `get_rpaths`.
    loader_path : str
        The path to be used for `@loader_path`.
        This must be the directory of the library which is loading `lib_path`.
    executable_path : str, optional
        The path to be used for `@executable_path`.
        Assumed to be the working directory by default.

    Returns
    -------
    lib_path : str
        A str with the resolved libraries realpath.

    Raises
    ------
    DependencyNotFound
        When `lib_path` has `@rpath` in it but can not be found on any of the
        provided `rpaths`.
    """
    if lib_path.startswith('@loader_path/'):
        return realpath(pjoin(loader_path, lib_path.split('/', 1)[1]))
    if lib_path.startswith('@executable_path/'):
        return realpath(pjoin(executable_path, lib_path.split('/', 1)[1]))
    if not lib_path.startswith('@rpath/'):
        return realpath(lib_path)

    lib_rpath = lib_path.split('/', 1)[1]
    for rpath in rpaths:
        rpath_lib = resolve_rpath(
            pjoin(rpath, lib_rpath), (), loader_path, executable_path
        )
        if os.path.exists(rpath_lib):
            return realpath(rpath_lib)

    raise DependencyNotFound(lib_path)


def search_environment_for_lib(lib_path):
    # type: (Text) -> Text
    """ Search common environment variables for `lib_path`

    We'll use a single approach here:

        1. Search for the basename of the library on DYLD_LIBRARY_PATH
        2. Search for ``realpath(lib_path)``
        3. Search for the basename of the library on DYLD_FALLBACK_LIBRARY_PATH

    This follows the order that Apple defines for "searching for a
    library that has a directory name in it" as defined in their
    documentation here:

    https://developer.apple.com/library/archive/documentation/DeveloperTools/Conceptual/DynamicLibraries/100-Articles/DynamicLibraryUsageGuidelines.html#//apple_ref/doc/uid/TP40001928-SW10

    See the script "testing_osx_rpath_env_variables.sh" in tests/data
    for a more in-depth explanation. The case where LD_LIBRARY_PATH is
    used is a narrow subset of that, so we'll ignore it here to keep
    things simple.

    Parameters
    ----------
    lib_path : str
        Name of the library to search for

    Returns
    -------
    lib_path : str
        Full path of ``basename(lib_path)``'s location, if it can be found, or
        ``realpath(lib_path)`` if it cannot.
    """
    lib_basename = basename(lib_path)
    potential_library_locations = []

    # 1. Search on DYLD_LIBRARY_PATH
    potential_library_locations += _paths_from_var('DYLD_LIBRARY_PATH',
                                                   lib_basename)

    # 2. Search for realpath(lib_path)
    potential_library_locations.append(realpath(lib_path))

    # 3. Search on DYLD_FALLBACK_LIBRARY_PATH
    potential_library_locations += \
        _paths_from_var('DYLD_FALLBACK_LIBRARY_PATH', lib_basename)

    for location in potential_library_locations:
        if os.path.exists(location):
            return location
    return realpath(lib_path)


def get_prefix_stripper(strip_prefix):
    # type: (Text) -> Callable[[Text], Text]
    """ Return function to strip `strip_prefix` prefix from string if present

    Parameters
    ----------
    strip_prefix : str
        Prefix to strip from the beginning of string if present

    Returns
    -------
    stripper : func
        function such that ``stripper(a_string)`` will strip `prefix` from
        ``a_string`` if present, otherwise pass ``a_string`` unmodified
    """
    n = len(strip_prefix)

    def stripper(path):
        # type: (Text) -> Text
        return path if not path.startswith(strip_prefix) else path[n:]
    return stripper


def get_rp_stripper(strip_path):
    # type: (Text) -> Callable[[Text], Text]
    """ Return function to strip ``realpath`` of `strip_path` from string

    Parameters
    ----------
    strip_path : str
        path to strip from beginning of strings. Processed to ``strip_prefix``
        by ``realpath(strip_path) + os.path.sep``.

    Returns
    -------
    stripper : func
        function such that ``stripper(a_string)`` will strip ``strip_prefix``
        from ``a_string`` if present, otherwise pass ``a_string`` unmodified
    """
    return get_prefix_stripper(realpath(strip_path) + os.path.sep)


def stripped_lib_dict(lib_dict, strip_prefix):
    # type: (Dict[Text, Dict[Text, Text]], Text) -> Dict[Text, Dict[Text, Text]]
    """ Return `lib_dict` with `strip_prefix` removed from start of paths

    Use to give form of `lib_dict` that appears relative to some base path
    given by `strip_prefix`.  Particularly useful for analyzing wheels where we
    unpack to a temporary path before analyzing.

    Parameters
    ----------
    lib_dict : dict
        See :func:`tree_libs` for definition.  All depending and depended paths
        are canonical (therefore absolute)
    strip_prefix : str
        Prefix to remove (if present) from all depended and depending library
        paths in `lib_dict`

    Returns
    -------
    relative_dict : dict
        `lib_dict` with `strip_prefix` removed from beginning of all depended
        and depending library paths.
    """
    relative_dict = {}
    stripper = get_prefix_stripper(strip_prefix)

    for lib_path, dependings_dict in lib_dict.items():
        ding_dict = {}
        for depending_libpath, install_name in dependings_dict.items():
            ding_dict[stripper(depending_libpath)] = install_name
        relative_dict[stripper(lib_path)] = ding_dict
    return relative_dict


def wheel_libs(
    wheel_fname,  # type: Text
    filt_func=None  # type: Optional[Callable[[Text], bool]]
):
    # type: (...) -> Dict[Text, Dict[Text, Text]]
    """ Return analysis of library dependencies with a Python wheel

    Use this routine for a dump of the dependency tree.

    Parameters
    ----------
    wheel_fname : str
        Filename of wheel
    filt_func : None or callable, optional
        If None, inspect all files for library dependencies. If callable,
        accepts filename as argument, returns True if we should inspect the
        file, False otherwise.

    Returns
    -------
    lib_dict : dict
        dictionary with (key, value) pairs of (``libpath``,
        ``dependings_dict``).  ``libpath`` is library being depended on,
        relative to wheel root path if within wheel tree.  ``dependings_dict``
        is (key, value) of (``depending_lib_path``, ``install_name``).  Again,
        ``depending_lib_path`` is library relative to wheel root path, if
        within wheel tree.
    """
    with TemporaryDirectory() as tmpdir:
        zip2dir(wheel_fname, tmpdir)
        lib_dict = tree_libs(tmpdir, filt_func)
    return stripped_lib_dict(lib_dict, realpath(tmpdir) + os.path.sep)


def _paths_from_var(varname, lib_basename):
    # type: (Text, Text) -> List[Text]
    var = os.environ.get(six.ensure_str(varname))
    if var is None:
        return []
    return [pjoin(path, lib_basename) for path in var.split(':')]
