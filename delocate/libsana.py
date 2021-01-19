""" Analyze libraries in trees

Analyze library dependencies in paths and wheel files
"""

import os
from os.path import basename, dirname, join as pjoin, realpath

import logging
from typing import (
    Callable,
    Dict,
    Iterable,
    Iterator,
    List,
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


def get_dependencies(
    lib_path,  # type: Text
):
    # type: (...) -> Iterator[Tuple[Text, Text]]
    """Iterate over this libraries dependences.

    Parameters
    ----------
    lib_path : str
        The library to fetch dependencies from.  Must be an existing file.

    Yields
    ------
    dependency_path : str
        The direct dependencies of this library which can have dependencies
        themselves.
        If the libaray at `install_name` can not be found then this value will
        not be a valid file path.
        :func:`os.path.isfile` can be used to test if this file exists.
    install_name : str
        The install name of `dependency_path` as if :func:`get_install_names`
        was called.

    Raises
    ------
    DependencyNotFound
        When `lib_path` does not exist.
    """
    if not os.path.isfile(lib_path):
        raise DependencyNotFound(lib_path)
    rpaths = get_rpaths(lib_path) + get_environment_variable_paths()
    for install_name in get_install_names(lib_path):
        try:
            if install_name.startswith("@"):
                dependency_path = resolve_rpath(
                    install_name,
                    rpaths,
                    loader_path=dirname(lib_path),
                )
            else:
                dependency_path = search_environment_for_lib(install_name)
            yield dependency_path, install_name
            if dependency_path != install_name:
                logger.debug(
                    "%s resolved to: %s", install_name, dependency_path
                )
        except DependencyNotFound:
            logger.error(
                "\n{0} not found:"
                "\n  Needed by: {1}"
                "\n  Search path:\n    {2}".format(
                    install_name, lib_path, "\n    ".join(rpaths)
                )
            )
            # At this point install_name is known to be a bad path.
            # Expanding install_name with realpath may be undesirable.
            yield realpath(install_name), install_name


def walk_library(
    lib_path,  # type: Text
    filt_func=lambda filepath: True,  # type: Callable[[Text], bool]
    visited=None,  # type: Optional[Set[Text]]
):
    # type: (...) -> Iterator[Text]
    """Iterate over all of this trees dependencies inclusively.

    Dependencies which can not be resolved will be logged and ignored.

    Parameters
    ----------
    lib_path : str
        The library to start with.
    filt_func : callable, optional
        A callable which accepts filename as argument and returns True if we
        should inspect the file or False otherwise.
        Defaults to inspecting all files for library dependencies. If callable,
        If `filt_func` filters a library it will also exclude all of that
        libraries dependencies as well.
    visited : set of str
        This set is updated with new library_path's as they are visited.
        This is used to prevent infinite recursion and duplicates.

    Yields
    ------
    library_path : str
        The pats of each library including `lib_path` without duplicates.
    """
    if visited is None:
        visited = {lib_path, }
    elif lib_path in visited:
        return
    else:
        visited.add(lib_path)
    if not filt_func(lib_path):
        logger.debug("Ignoring %s and its dependencies.", lib_path)
        return
    yield lib_path
    for dependency_path, _ in get_dependencies(lib_path):
        if not os.path.isfile(dependency_path):
            logger.error(
                "%s not found, requested by %s", dependency_path, lib_path,
            )
            continue
        for sub_dependency in walk_library(
            dependency_path,
            filt_func=filt_func,
            visited=visited,
        ):
            yield sub_dependency


def walk_directory(
    root_path,  # type: Text
    filt_func=lambda filepath: True,  # type: Callable[[Text], bool]
):
    # type: (...) -> Iterator[Text]
    """Walk along dependences starting with the libraries within `root_path`.

    Dependencies which can not be resolved will be logged and ignored.

    Parameters
    ----------
    root_path : str
        The root directory to search for libraries depending on other libraries.
    filt_func : None or callable, optional
        A callable which accepts filename as argument and returns True if we
        should inspect the file or False otherwise.
        Defaults to inspecting all files for library dependencies. If callable,
        If `filt_func` filters a library it will also exclude all of that
        libraries dependencies as well.

    Yields
    ------
    library_path : str
        Iterates over the libraries in `root_path` and each of their
        dependencies without any duplicates.
    """
    visited_paths = set()  # type: Set[Text]
    for dirpath, dirnames, basenames in os.walk(root_path):
        for base in basenames:
            depending_path = realpath(pjoin(dirpath, base))
            if depending_path in visited_paths:
                continue  # A library in root_path was a dependency of another.
            if not filt_func(depending_path):
                continue
            for library_path in walk_library(
                depending_path, filt_func=filt_func, visited=visited_paths
            ):
                yield library_path


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
    """
    warnings.warn(
        "tree_libs doesn't support @loader_path and has been deprecated.",
        DeprecationWarning,
        stacklevel=2,
    )
    lib_dict = {}  # type: Dict[Text, Dict[Text, Text]]
    for dirpath, dirnames, basenames in os.walk(start_path):
        for base in basenames:
            depending_path = realpath(pjoin(dirpath, base))
            if filt_func and not filt_func(depending_path):
                logger.debug("Ignoring dependencies of: %s", depending_path)
                continue
            for dependancy_path, install_name in get_dependencies(
                depending_path
            ):
                if install_name.startswith("@loader_path/"):
                    # Support for `@loader_path` would break existing callers.
                    logger.debug(
                        "Excluding %s because it has '@loader_path'.",
                        install_name
                    )
                    continue
                lib_dict.setdefault(dependancy_path, {})
                lib_dict[dependancy_path][depending_path] = install_name
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
