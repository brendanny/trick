"""CFFI ABI mode: no C++ parsing; explicit owned handles and a Python facade."""
from cffi import FFI
from adapters import BUILD

ffi = FFI()
ffi.cdef("""
const char* poc_error(void);
void* poc_create(int, const char*, double);
void poc_destroy(int, void*);
double poc_call(int, void*, const char*, const char*, int, double);
const char* poc_text(void);
""")
lib = ffi.dlopen(str(BUILD / "libpoc_abi.so"))

def check():
    error = ffi.string(lib.poc_error())
    if error:
        raise RuntimeError(error.decode())

def call(op, handle=ffi.NULL, text="", second="", index=0, value=0.):
    result = lib.poc_call(op, handle, text.encode(), second.encode(), index, value)
    check()
    return result

class Handle:
    def __init__(self, kind, name="", value=0.):
        raw = lib.poc_create(kind, name.encode(), value)
        check()
        self._ptr = ffi.gc(raw, lambda ptr: lib.poc_destroy(kind, ptr))

class Model(Handle):
    def __init__(self, value): super().__init__(0, value=value)
    @property
    def mass(self): return call(10, self._ptr)
    @mass.setter
    def mass(self, value): call(11, self._ptr, value=value)
    def adjust(self, value):
        return call(12, self._ptr, index=value) if isinstance(value, int) else call(13, self._ptr, value=value)
    def position_get(self, index): return call(14, self._ptr, index=index)
    def position_set(self, index, value): call(15, self._ptr, index=index, value=value)
    def sample_push(self, value): call(16, self._ptr, value=value)
    def sample_get(self, index): return call(17, self._ptr, index=index)

class Allocated(Handle):
    def __init__(self, value): super().__init__(1, value=value)
    def registered(self): return bool(call(18, self._ptr))

class View(Handle):
    def __init__(self, name): super().__init__(2, name=name)
    def get(self, index): return call(22, self._ptr, index=index)
    def set(self, index, value): call(23, self._ptr, index=index, value=value)
    def size(self): return int(call(24, self._ptr))
    def field_get(self, name): return call(25, self._ptr, text=name)
    def field_set(self, name, value): call(26, self._ptr, text=name, value=value)
    def call_adjust(self, value): return call(27, self._ptr, value=value)

def initialize(path): call(0, text=path)
def array(name, count): call(1, text=name, index=count)
def managed(name, value): call(2, text=name, value=value)
def resize(name, count): call(3, text=name, index=count)
def erase(name): call(4, text=name)
def restore(text): call(5, text=text)
def convert(value, source, target): return call(6, text=source, second=target, value=value)
def live_models(): return int(call(7))
def live_allocated(): return int(call(8))
def allocations(): return int(call(9))
def left(model): return int(call(19, model._ptr))
def right(model): return int(call(20, model._ptr))
def right_offset(model): return int(call(21, model._ptr))
def new_allocated(value): return Allocated(value)
def checkpoint():
    text = lib.poc_text()
    check()
    return ffi.string(text).decode()
