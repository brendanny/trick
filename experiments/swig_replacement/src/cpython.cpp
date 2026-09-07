// A small, manual CPython binding over the C++ fixture, independent of the C ABI.
#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include "poc.hh"
#include <exception>
struct Object { PyObject_HEAD void* value; int kind; };
static PyTypeObject *model_type, *allocated_type, *view_type;
#define CATCH catch(const std::exception& e) { PyErr_SetString(PyExc_RuntimeError, e.what()); return nullptr; }
static PyObject* construct(PyTypeObject* type, PyObject* args, PyObject*) {
    double value = 1; const char* name;
    int kind = type == model_type ? 0 : type == allocated_type ? 1 : 2;
    if (kind == 2) { if (!PyArg_ParseTuple(args, "s", &name)) return nullptr; }
    else if (!PyArg_ParseTuple(args, "d", &value)) return nullptr;
    auto self = reinterpret_cast<Object*>(type->tp_alloc(type, 0)); if (!self) return nullptr;
    self->kind = kind;
    try {
        if (kind == 0) self->value = new POCModel(value);
        else if (kind == 1) self->value = new POCAllocated(value);
        else self->value = new POCView(name);
    } catch(const std::exception& e) { Py_DECREF(self); PyErr_SetString(PyExc_RuntimeError, e.what()); return nullptr; }
    return reinterpret_cast<PyObject*>(self);
}
static void destroy(Object* self) {
    if (self->kind == 0) delete static_cast<POCModel*>(self->value);
    else if (self->kind == 1) delete static_cast<POCAllocated*>(self->value);
    else delete static_cast<POCView*>(self->value);
    auto type = Py_TYPE(self);
    type->tp_free(reinterpret_cast<PyObject*>(self));
    Py_DECREF(type);
}
static PyObject* mass_get(Object* self, void*) { return PyFloat_FromDouble(static_cast<POCModel*>(self->value)->mass); }
static int mass_set(Object* self, PyObject* value, void*) {
    if (!value) { PyErr_SetString(PyExc_TypeError, "cannot delete mass"); return -1; }
    double number = PyFloat_AsDouble(value); if (PyErr_Occurred()) return -1;
    static_cast<POCModel*>(self->value)->mass = number; return 0;
}
static PyObject* adjust(Object* self, PyObject* value) {
    auto m = static_cast<POCModel*>(self->value);
    if (PyLong_Check(value)) { long n = PyLong_AsLong(value); if (PyErr_Occurred()) return nullptr; return PyFloat_FromDouble(m->adjust(static_cast<int>(n))); }
    double n = PyFloat_AsDouble(value); if (PyErr_Occurred()) return nullptr; return PyFloat_FromDouble(m->adjust(n));
}
static PyObject* position_get(Object* self, PyObject* args) { int i; if (!PyArg_ParseTuple(args,"i",&i)) return nullptr; try { return PyFloat_FromDouble(static_cast<POCModel*>(self->value)->position_get(i)); } CATCH }
static PyObject* position_set(Object* self, PyObject* args) { int i; double n; if (!PyArg_ParseTuple(args,"id",&i,&n)) return nullptr; try { static_cast<POCModel*>(self->value)->position_set(i,n); Py_RETURN_NONE; } CATCH }
static PyObject* sample_get(Object* self, PyObject* args) { int i; if (!PyArg_ParseTuple(args,"i",&i)) return nullptr; try { return PyFloat_FromDouble(static_cast<POCModel*>(self->value)->sample_get(i)); } CATCH }
static PyObject* sample_push(Object* self, PyObject* args) { double n; if (!PyArg_ParseTuple(args,"d",&n)) return nullptr; try { static_cast<POCModel*>(self->value)->sample_push(n); Py_RETURN_NONE; } CATCH }
static PyObject* registered(Object* self, PyObject*) { return PyBool_FromLong(static_cast<POCAllocated*>(self->value)->registered()); }
static PyObject* get(Object* self, PyObject* args) { int i; if (!PyArg_ParseTuple(args,"i",&i)) return nullptr; try { return PyFloat_FromDouble(static_cast<POCView*>(self->value)->get(i)); } CATCH }
static PyObject* set(Object* self, PyObject* args) { int i; double n; if (!PyArg_ParseTuple(args,"id",&i,&n)) return nullptr; try { static_cast<POCView*>(self->value)->set(i,n); Py_RETURN_NONE; } CATCH }
static PyObject* size(Object* self, PyObject*) { try { return PyLong_FromLong(static_cast<POCView*>(self->value)->size()); } CATCH }
static PyObject* field_get(Object* self, PyObject* args) { const char* s; if (!PyArg_ParseTuple(args,"s",&s)) return nullptr; try { return PyFloat_FromDouble(static_cast<POCView*>(self->value)->field_get(s)); } CATCH }
static PyObject* field_set(Object* self, PyObject* args) { const char* s; double n; if (!PyArg_ParseTuple(args,"sd",&s,&n)) return nullptr; try { static_cast<POCView*>(self->value)->field_set(s,n); Py_RETURN_NONE; } CATCH }
static PyObject* call_adjust(Object* self, PyObject* args) { double n; if (!PyArg_ParseTuple(args,"d",&n)) return nullptr; try { return PyFloat_FromDouble(static_cast<POCView*>(self->value)->call_adjust(n)); } CATCH }
#define METHOD(name, flags) {#name, reinterpret_cast<PyCFunction>(name), flags, nullptr}
static PyMethodDef model_methods[] = {METHOD(adjust,METH_O), METHOD(position_get,METH_VARARGS), METHOD(position_set,METH_VARARGS), METHOD(sample_get,METH_VARARGS), METHOD(sample_push,METH_VARARGS), {nullptr}};
static PyMethodDef allocated_methods[] = {METHOD(registered,METH_NOARGS), {nullptr}};
static PyMethodDef view_methods[] = {METHOD(get,METH_VARARGS), METHOD(set,METH_VARARGS), METHOD(size,METH_NOARGS), METHOD(field_get,METH_VARARGS), METHOD(field_set,METH_VARARGS), METHOD(call_adjust,METH_VARARGS), {nullptr}};
static PyGetSetDef properties[] = {{"mass", reinterpret_cast<getter>(mass_get), reinterpret_cast<setter>(mass_set), nullptr, nullptr}, {nullptr}};
static PyObject* dispatch(PyObject*, PyObject* args) {
    int op, index = 0; const char *text = "", *second = ""; double n = 0; PyObject* handle = Py_None;
    if (!PyArg_ParseTuple(args,"i|Ossid",&op,&handle,&text,&second,&index,&n)) return nullptr;
    try {
        switch(op) {
        case 0: poc_initialize(text); break;
        case 1: poc_array(text,index); break;
        case 2: poc_managed(text,n); break;
        case 3: poc_resize(text,index); break;
        case 4: poc_erase(text); break;
        case 5: poc_restore(text); break;
        case 6: return PyFloat_FromDouble(poc_convert(n,text,second));
        case 7: return PyLong_FromLong(poc_live_models());
        case 8: return PyLong_FromLong(poc_live_allocated());
        case 9: return PyLong_FromLong(poc_allocations());
        case 19: case 20: case 21: {
            if (!PyObject_TypeCheck(handle, model_type)) { PyErr_SetString(PyExc_TypeError,"Model required"); return nullptr; }
            auto m = static_cast<POCModel*>(reinterpret_cast<Object*>(handle)->value);
            return PyLong_FromLong(op == 19 ? poc_left(m) : op == 20 ? poc_right(m) : poc_right_offset(m));
        }
        case 30: return PyUnicode_FromString(poc_checkpoint());
        default: PyErr_SetString(PyExc_ValueError,"unknown operation"); return nullptr;
        }
        Py_RETURN_NONE;
    } CATCH
}
static PyMethodDef module_methods[] = {METHOD(dispatch,METH_VARARGS), {nullptr}};
static PyModuleDef module = {PyModuleDef_HEAD_INIT,"poc_cpython",nullptr,-1,module_methods};
PyMODINIT_FUNC PyInit_poc_cpython() {
    auto m = PyModule_Create(&module); if (!m) return nullptr;
    PyType_Slot model_slots[] = {{Py_tp_new,reinterpret_cast<void*>(construct)}, {Py_tp_dealloc,reinterpret_cast<void*>(destroy)}, {Py_tp_methods,model_methods}, {Py_tp_getset,properties}, {0,nullptr}};
    PyType_Slot allocated_slots[] = {{Py_tp_new,reinterpret_cast<void*>(construct)}, {Py_tp_dealloc,reinterpret_cast<void*>(destroy)}, {Py_tp_methods,allocated_methods}, {0,nullptr}};
    PyType_Slot view_slots[] = {{Py_tp_new,reinterpret_cast<void*>(construct)}, {Py_tp_dealloc,reinterpret_cast<void*>(destroy)}, {Py_tp_methods,view_methods}, {0,nullptr}};
    PyType_Spec specs[] = {{"poc_cpython.Model",sizeof(Object),0,Py_TPFLAGS_DEFAULT,model_slots}, {"poc_cpython.Allocated",sizeof(Object),0,Py_TPFLAGS_DEFAULT,allocated_slots}, {"poc_cpython.View",sizeof(Object),0,Py_TPFLAGS_DEFAULT,view_slots}};
    PyTypeObject** types[] = {&model_type,&allocated_type,&view_type}; const char* names[] = {"Model","Allocated","View"};
    for (int i=0;i<3;++i) { auto t=PyType_FromSpec(&specs[i]); if(!t) {Py_DECREF(m);return nullptr;} *types[i]=reinterpret_cast<PyTypeObject*>(t); if(PyModule_AddObject(m,names[i],t)<0){Py_DECREF(t);Py_DECREF(m);return nullptr;} }
    return m;
}
