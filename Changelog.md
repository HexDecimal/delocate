# Changelog

Matthew Brett (MB) wrote most of the code. Kyle Benesch (KB) did some heroic
refactoring of the dependency tracing and added type hinting. Isuru Fernando
(IF) developed the Universal2 (arm64) support. Min Ragan-Kelley (MinRK) did a
lot of work discussing OSX things with MB, and contributed fixes as well.

See [this Changelog site](https://keepachangelog.com) for helpful
rules on making a good Changelog.

## [Unreleased]

### Changed

- `patch_wheel` function raises `FileNotFoundError` instead of `ValueError` on
  missing patch files.
- `delocate.fuse.fuse_trees` now auto-detects binary files instead of testing
  filename suffixes.

### Deprecated

- `get_rpaths` and `get_install_id` are deprecated due to not supporting
  architectures.
- `unique_by_index` is deprecated. Use more-itertools unique_everseen instead.

### Fixed

- Fixed `NotImplementedError` when libraries depend on differing binaries
  per-architecture.
  [#230](https://github.com/matthew-brett/delocate/pull/230)
- Now checks all architectures instead of an arbitrary default.
  This was causing inconsistent behavior across MacOS versions.
  [#230](https://github.com/matthew-brett/delocate/pull/230)
- `delocate-merge` now supports libraries with missing or unusual extensions.
  [#228](https://github.com/matthew-brett/delocate/issues/228)
- Now supports library files ending in parentheses.
- Fixed `Unknown Mach-O header` error when encountering a fat static library.
  [#229](https://github.com/matthew-brett/delocate/issues/229)

### Removed

- Dropped support for Python 3.7 and Python 3.8.
  [#226](https://github.com/matthew-brett/delocate/pull/226)

## [0.12.0] - 2024-08-29

### Added

- `delocate-wheel` `--lib-sdir` now changes the suffix of the bundled library
  directory.
  [#210](https://github.com/matthew-brett/delocate/pull/210)

### Changed

- Sanitize rpaths (`--sanitize-rpaths`) is now the default behavior.
  Opt-out with the new `--no-sanitize-rpaths` flag.
  [#223](https://github.com/matthew-brett/delocate/pull/223)
- Improved error message for when a MacOS target version is not met.
  [#211](https://github.com/matthew-brett/delocate/issues/211)
- `delocate-fuse` is no longer available and will throw an error when invoked.
  To fuse two wheels together use `delocate-merge`. `delocate-merge` does not
  overwrite the first wheel. It creates a new wheel with an automatically
  determined name. If the old behavior is needed (not recommended), pin the
  version to `delocate==0.11.0`.
  [#215](https://github.com/matthew-brett/delocate/pull/215)

### Deprecated

- `--require-target-macos-version` has been deprecated.
  `MACOSX_DEPLOYMENT_TARGET` should be used instead of this flag.
  [#219](https://github.com/matthew-brett/delocate/pull/219)

### Fixed

- Existing libraries causing DelocationError were not shown due to bad string
  formatting.
  [#216](https://github.com/matthew-brett/delocate/pull/216)
- Wheels for macOS 11 and later were using invalid literal versions in tags
  instead of the macOS release version required by Python packagers.
  [#219](https://github.com/matthew-brett/delocate/pull/219)
- Fixed regression in `intel` platform support.
  [#219](https://github.com/matthew-brett/delocate/pull/219)

## [0.11.0] - 2024-03-22

### Added

- Use `--require-target-macos-version` or the `MACOSX_DEPLOYMENT_TARGET`
  environment variable to ensure that wheels are
  compatible with the specified macOS version. #198

### Changed

- Delocate now uses the binaries of the wheel file to determine a more accurate
  platform tag, this will rename wheels accordingly. #198
- `delocate-wheel` is now more strict with platform tags and will no longer allow
  a wheel to be incompatible with its own tags. #198

### Fixed

- `--sanitize-rpaths` was failing with duplicate rpaths.
  [#208](https://github.com/matthew-brett/delocate/pull/208)

## [0.10.7] - 2023-12-12

### Changed

- Handle glob paths in more cases for `delocate-wheel`, `delocate-path`,
  `delocate-listdeps`, and `delocate-addplat`.
  [#71](https://github.com/matthew-brett/delocate/issues/71)

### Fixed

- No longer picks a random directory when multiple directories end with the
  package name. [#192](https://github.com/matthew-brett/delocate/issues/192)

## [0.10.6] - 2023-11-21

### Added

- Dependencies can be manually excluded with the `--exclude <name>` flag.
  [#106](https://github.com/matthew-brett/delocate/pull/106)
- Non-portable rpaths can be cleaned up using the `--sanitize-rpaths` flag.
  [#164](https://github.com/matthew-brett/delocate/pull/164)

## [0.10.5] - 2023-11-14

### Added

- Honor the `SOURCE_DATE_EPOCH` environment variable to support
  [reproducible builds](https://reproducible-builds.org/docs/source-date-epoch/).
  [#187](https://github.com/matthew-brett/delocate/pull/187)

### Fixed

- Fixed `UnicodeDecodeError` when an archive has non-ASCII characters.
  [#189](https://github.com/matthew-brett/delocate/issues/189)

## [0.10.4] - 2022-12-17

### Fixed

- Dependency paths with `@rpath`, `@loader_path` and `@executable_path`
  will now look at `/usr/local/lib` and `/usr/lib` after the
  rpaths, loader path, or executable path is searched.
  [#167](https://github.com/matthew-brett/delocate/pull/167)

## [0.10.3] - 2022-11-04

- Support for Python 3.6 has been dropped.
- Delocate no longer depends on the `wheel` API.
- Running Delocate on already delocated wheels will no longer corrupt them.
  [#157](https://github.com/matthew-brett/delocate/pull/157)

## [0.10.2] - 2021-12-31

Bugfix and compatibility release.

- Ensured support for versions of wheel beyond 0.37.1. If you are using older
  versions of Delocate then you may need to to pin `wheel==0.37.1`.
  [#135](https://github.com/matthew-brett/delocate/issues/135)
- Fixed crashes when `otool` gives multiple architectures in its output.
  This does not support different dependencies per-architecture.
  [#130](https://github.com/matthew-brett/delocate/pull/130)

## [0.10.1] - 2021-11-23

Bugfix release.

- Delocate will no longer fail when libraries use different install names to
  refer to the same library.
  [#134](https://github.com/matthew-brett/delocate/pull/134)

## [0.10.0] - 2021-09-22

First release that requires Python 3.

- `wheel_libs` now supports recursive dependencies.
- `listdeps` command now supports recursive dependencies.
  [#118](https://github.com/matthew-brett/delocate/pull/118)
- Wheels with top-level extension modules or wheels using namespaces can now
  be delocated.
  [#123](https://github.com/matthew-brett/delocate/pull/123)
- Wheels with multiple packages will no longer copy duplicate libraries.
  [#35](https://github.com/matthew-brett/delocate/issues/35)
- `delocate.tools.back_tick` has been deprecated.
  [#126](https://github.com/matthew-brett/delocate/pull/126)

## [0.9.1] - 2021-09-17

Bugfix release.

- Fixed issue where Delocate would attempt to modify the install names of a
  non-copied library which dynamically links to a copied library.
  [#120](https://github.com/matthew-brett/delocate/pull/120)

## [0.9.0] - 2021-07-17

Refactoring, updating and `arm64` (M1) support.

- Libraries depending on `@loader_path` are now supported (KB).
- `@executable_path` is supported and defaults to the current Python
  executable path. This can be changed with the `--executable-path` flag
  (KB).
- The `--ignore-missing-dependencies` flag can be given to ignore errors and
  delocate as many dependencies as possible (KB).
- Dependencies are now delocated recursively (KB).
- `delocate.delocating.copy_recurse` has been deprecated (KB).
- `delocate.libsana.resolve_rpath` has been deprecated (KB).
- Add required ad-hoc signing for libraries (IF).
- Fix to escape regexp special characters to occur in library names (such as
  `++` in `libc++` (Grzegorz Bokota).
- Support for new `otool` output from arm architecture fat libraries (IF).
- Various CI improvements, including refactoring for test wheel generation,
  replacing `i386` with `arm64` for dual architectures, and start of
  Github workflow tests (MB, KB).
- Various documentation fixes (Brad Solomon, Andrew Murray).

## [0.8.2] - 2020-07-12

Bugfix release.

- Force UTF-8 for import of README file. 0.8.1 introduced non-ascii
  characters, so unguarded `open('README.rst', 'rt').read()` in `setup.py`
  gives an encoding error. See GH issue 81. Thanks to Joshua Haberman for
  the report.

## [0.8.1] - 2020-06-28

Bugfix release.

- Adapt parsing of otool output to Catalina, avoiding crash in delocate
  (thanks to Github use `matham` for the report)
- Adapt to possibility that `wheel` binary is not on PATH.
- Various improvements to documentation, including explanation of Delocate's
  problems in dealing with single module extensions (Brad Solomon)
- PEP8 maintenance by Grzegorz Bokota.

## [0.8.0] - 2019-11-06

Bugfix and new feature release.

- More extensive search for libraries that code depends on, using macOS path
  search algorithm (Forrest Brennen, Ofan Tester).
- Fix for newer XCode messages for "not an object" (Andy Wilson)
- Fixes to Wheel zip file permissions and attributes (Cosimo Lupo and MB).
- Some Windows path compatibility (Isuru Fernando)
- Bugfix for use of undefined variable in `get_install_id` (Anthony
  Sottile).

## [0.7.4] - 2018-10-01

Bugfix release to deal with large number of breaking changes in wheel
0.32.0.

- Refactor to deal with Wheel 0.32.0, with massive refactoring of the API,
  and the use of zero permissions RECORD file.
- Refactor to use Pytest (many thanks to Github user Xoviat).
- Beginning of Windows refactor (Xoviat again).

## [0.7.3] - 2017-12-04

Also deal with xcode 8.3 message from another binary file.

## [0.7.2] - 2017-12-02

Make compatible with latest Xcode error messages.

## [0.7.1] - 2017-06-27

Fix broken tests from 0.7.0.

## [0.7.0] - 2017-06-27

Add ability to deal with rpath. Thanks to Kyle Stewart.

## [0.6.5] - 2017-06-16

More changes for compatibility with newer OSX Xcode messages. Thanks to
Sean Gillies.

- more adaptations to changes to output of `otool`.

## [0.6.4] - 2016-11-23

Changes for compatibility with newer OSX. Thanks to Tommy Sparber.

- adapt to SIP file protections;
- adapt to changes in otool output;
- rebuild testing wheels for OSX 10.6 compatibility.

## [0.6.3] - 2015-07-20

- Inspect all files looking for linked libraries, instead of inspecting only
  files ending in library extensions. This means that you will also pick up
  libraries for executables in the given path to delocate, by default, but
  is slower to execute. Thanks to Marc Abramowitz for the report and
  suggestion;
- Remove silly check for library existence when delocating libraries that
  are in the tree to delocate.

## [0.6.2] - 2014-11-10

- Bugfix for zipfile unpacking losing permissions; This wiped out useful
  permissions like execute permissions for scripts when modifying zip files.

## [0.6.1] - 2014-10-23

- Add some useful flags to `delocate-add-platform`
- Refactoring

## [0.6.0] - 2014-09-13

- Add utility to add platform tags to wheel contents and name
- Add more general wheel context manager
- Some refactoring for neatness

## [0.5.0] - 2014-07-22

- Add utilities and script to apply a patch to a wheel
- Add utilities and script to test for architectures in libraries and
  require named architectures
- Docstring fixes and refactoring

## [0.4.0] - 2014-06-25

- Set `install_name_id` for copied libraries to be unique to this package.
  OSX uses the `install_name_id` to identify a library uniquely on the
  system. If two libraries have the same `install_name_id` when loaded into
  the process, then OSX will raise an error unless their compatibility number
  matches. Delocate now sets the `install_name_id` to be more or less
  unique with a Python process at least. This means OSX won't raise an error
  if you have two different libraries in two different packages (e.g hdf5
  libraries in `h5py` and `pytables`.
- Turn on compression for creating wheel zip files. Previously we were zipping
  without compression (because MB didn't know that was the default).
- Raise an error if delocating attempts to copy two different libraries with
  the same name (therefore overwriting one with the other).
- Add command and functions to do architecture fuse between two different
  wheels. This can be useful when you have to build a 32-bit and 64-bit wheel
  separately. In that case you can fuse the two wheels making fat (combined)
  architecture libraries, using `delocate-fuse`. Add supporting routines
  for detecting architecture of libraries and fusing libraries with different
  architectures.
- Add use of `os.path.expanduser` to specified output wheel directory for `delocate-wheel` script.
  Now flag input like `delocate-wheel -w ~/wheels some_wheel.whl` will correctly output to `$HOME/wheels`.

## [0.3.0] - 2014-05-05

- Switch to using just `@loader_path` rather than a combination of
  `@loader_path` and `@rpath` for pointing to relocated libraries. Using
  `@rpath` was giving some errors of form:

      "install_name_tool: changing install names or rpaths can't be redone
      for: libsomething.dylib (for architecture x86_64) because larger updated
      load commands do not fit (the program must be relinked, and you may need
      to use -headerpad or -headerpad_max_install_names)

  Presumably because `@rpath` had been zero length before we got to the library.

- Add flag to display depending libraries as well as the libraries a tree /
  wheel depends on.
- Use canonical paths for depended and depending library paths, including
  following symbolic links. This means that two links pointing to the same
  file don't appear to be two different libraries, causing an error when
  copying the second into the directory containing the copied libraries.
- Don't raise an error when delocating a wheel that was previously delocated
  (MinRK)

## [0.2.1] - 2014-03-31

Bugfix release

- Rewrite wheel RECORD file when writing wheel. Delocated wheels were
  breaking `wheel unpack` command.

## [0.2.0] - 2014-03-25

First public release
