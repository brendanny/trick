#include "trick/swig/swig_python_compat.hh"

int main()
{
    Py_Initialize();
    // Exercise non-ASCII, an embedded NUL, and a non-BMP code point on both ABIs.
    const char utf8[]    = "a\0\xc3\xa9\xf0\x9f\x9a\x80";
    const wchar_t wide[] = L"a\0\u00e9\U0001f680";
    PyObject* text       = PyUnicode_DecodeUTF8(utf8, sizeof(utf8) - 1, "strict");
    if (!text || trick_python_unicode_string(text) != std::string(utf8, sizeof(utf8) - 1)
        || trick_python_unicode_wstring(text) != std::wstring(wide, sizeof(wide) / sizeof(wchar_t) - 1))
    {
        return 1;
    }
    Py_DECREF(text);
    text = PyUnicode_FromString("");
    if (!text || !trick_python_unicode_string(text).empty() || !trick_python_unicode_wstring(text).empty()
        || PyErr_Occurred())
    {
        return 2;
    }
    Py_DECREF(text);
    text = PyLong_FromLong(42);
    trick_python_unicode_string(text);
    if (!PyErr_Occurred())
    {
        return 3;
    }
    PyErr_Clear();
    trick_python_unicode_wstring(text);
    if (!PyErr_Occurred())
    {
        return 4;
    }
    PyErr_Clear();
    Py_DECREF(text);
    Py_Finalize();
    return 0;
}
