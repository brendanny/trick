/**
 * Trick's SWIG interface code uses a handful of Python C API calls the Python 2 way.
 * Through SWIG 4.4 those names were supplied for Python 3 builds by compatibility macros in SWIG.
 * SWIG 4.5.0 removed them (swig commit 79f7a2b), so Trick defines them here instead.
 *
 * Only the macros Trick uses are defined.
 */

#ifndef SWIG_PYTHON_COMPAT_HH
#define SWIG_PYTHON_COMPAT_HH

#include <Python.h>

#include <string>

inline std::string trick_python_unicode_string(PyObject* value)
{
    PyObject* encoded = PyUnicode_AsUTF8String(value);
    if (!encoded)
    {
        return std::string();
    }
    char* bytes     = nullptr;
    Py_ssize_t size = 0;
#if PY_MAJOR_VERSION >= 3
    const int status = PyBytes_AsStringAndSize(encoded, &bytes, &size);
#else
    const int status = PyString_AsStringAndSize(encoded, &bytes, &size);
#endif
    std::string result;
    if (status == 0)
    {
        result.assign(bytes, size);
    }
    Py_DECREF(encoded);
    return result;
}

inline std::wstring trick_python_unicode_wstring(PyObject* value)
{
#if PY_MAJOR_VERSION >= 3
    Py_ssize_t size;
    wchar_t* wide = PyUnicode_AsWideCharString(value, &size);
    if (!wide)
    {
        return std::wstring();
    }
    std::wstring result(wide, size);
    PyMem_Free(wide);
    return result;
#else
    const Py_ssize_t size = PyUnicode_GetSize(value);
    if (size <= 0)
    {
        return std::wstring();
    }
    std::wstring result(size, L'\0');
    const Py_ssize_t written = PyUnicode_AsWideChar(reinterpret_cast<PyUnicodeObject*>(value), &result[0], size);
    if (written < 0)
    {
        return std::wstring();
    }
    result.resize(written);
    return result;
#endif
}

/* Under Python 2 these are the real C API names and must not be redefined. */
#if PY_VERSION_HEX >= 0x03000000

#ifndef PyInt_Check
#define PyInt_Check(x) PyLong_Check(x)
#endif

#ifndef PyInt_AsLong
#define PyInt_AsLong(x) PyLong_AsLong(x)
#endif

#ifndef PyInt_FromLong
#define PyInt_FromLong(x) PyLong_FromLong(x)
#endif

#ifndef PyString_FromString
#define PyString_FromString(x) PyUnicode_FromString(x)
#endif

#endif

#endif
