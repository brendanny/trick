# distutils: language = c++
cdef extern from "poc.hh":
    cdef cppclass POCLeft:
        pass
    cdef cppclass POCRight:
        pass
    cdef cppclass POCModel(POCLeft, POCRight):
        POCModel(double) except +
        double mass
        double adjust(int) except +
        double adjust(double) except +
        double position_get(int) except +
        void position_set(int, double) except +
        void sample_push(double) except +
        double sample_get(int) except +
    cdef cppclass POCAllocated:
        POCAllocated(double) except +
        bint registered() except +
    cdef cppclass POCView:
        POCView(const char*) except +
        double get(int) except +
        void set(int, double) except +
        int size() except +
        double field_get(const char*) except +
        void field_set(const char*, double) except +
        double call_adjust(double) except +
    void poc_initialize(const char*) except +
    void poc_array(const char*, int) except +
    void poc_managed(const char*, double) except +
    void poc_resize(const char*, int) except +
    void poc_erase(const char*) except +
    const char* poc_checkpoint() except +
    void poc_restore(const char*) except +
    double poc_convert(double, const char*, const char*) except +
    int poc_live_models()
    int poc_live_allocated()
    int poc_allocations()
    int poc_left(POCLeft*)
    int poc_right(POCRight*)
    long poc_right_offset(POCModel*)

cdef class Model:
    cdef POCModel* ptr
    def __cinit__(self, double value): self.ptr = new POCModel(value)
    def __dealloc__(self): del self.ptr
    property mass:
        def __get__(self): return self.ptr.mass
        def __set__(self, double value): self.ptr.mass = value
    def adjust(self, value):
        if isinstance(value, int): return self.ptr.adjust(<int>value)
        return self.ptr.adjust(<double>value)
    def position_get(self, int index): return self.ptr.position_get(index)
    def position_set(self, int index, double value): self.ptr.position_set(index, value)
    def sample_push(self, double value): self.ptr.sample_push(value)
    def sample_get(self, int index): return self.ptr.sample_get(index)

cdef class Allocated:
    cdef POCAllocated* ptr
    def __cinit__(self, double value): self.ptr = new POCAllocated(value)
    def __dealloc__(self): del self.ptr
    def registered(self): return self.ptr.registered()

cdef class View:
    cdef POCView* ptr
    def __cinit__(self, name): self.ptr = new POCView(name.encode())
    def __dealloc__(self): del self.ptr
    def get(self, int index): return self.ptr.get(index)
    def set(self, int index, double value): self.ptr.set(index, value)
    def size(self): return self.ptr.size()
    def field_get(self, name): return self.ptr.field_get(name.encode())
    def field_set(self, name, double value): self.ptr.field_set(name.encode(), value)
    def call_adjust(self, double value): return self.ptr.call_adjust(value)

def initialize(path): poc_initialize(path.encode())
def array(name, int count): poc_array(name.encode(), count)
def managed(name, double value): poc_managed(name.encode(), value)
def resize(name, int count): poc_resize(name.encode(), count)
def erase(name): poc_erase(name.encode())
def checkpoint(): return poc_checkpoint().decode()
def restore(text): poc_restore(text.encode())
def convert(double value, source, target): return poc_convert(value, source.encode(), target.encode())
def live_models(): return poc_live_models()
def live_allocated(): return poc_live_allocated()
def allocations(): return poc_allocations()
def left(Model value): return poc_left(value.ptr)
def right(Model value): return poc_right(value.ptr)
def right_offset(Model value): return poc_right_offset(value.ptr)
def new_allocated(double value): return Allocated(value)
