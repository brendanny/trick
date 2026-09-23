# Python C API compatibility test

`PythonUnicode.cpp` checks UTF-8 and wide-string conversions on both Python
majors, including embedded NULs, a non-BMP character, empty strings and type
errors. It needs only a C++17 compiler and matching Python development files;
it does not require configuring or building Trick or generating SWIG wrappers.

From the repository root, for Python 2.7 or Python 3.6:

```sh
c++ -std=c++17 -Iinclude $(python2-config --includes) \
  trick_source/trick_swig/tests/PythonUnicode.cpp \
  $(python2-config --ldflags) -o /tmp/trick-python-unicode
/tmp/trick-python-unicode
```

Use the selected interpreter's config command. For Python 3.8 and newer, use
`python3-config --ldflags --embed` for the library flags. The standalone CI job
uses Rocky Linux 8's Python 2.7.18 and Python 3.6.8 with GCC 8.5.0.

The UTF-8 conversion intentionally preserves embedded NULs in `std::string`.
The earlier Python 3 implementation constructed from a NUL-terminated pointer
and truncated such strings. Wide-string conversion already preserved lengths.
