// Syntax shared by the two template libraries; all lifetime policies stay in
// their respective translation units.
m.def("initialize", &poc_initialize);
m.def("array", &poc_array);
m.def("managed", &poc_managed);
m.def("resize", &poc_resize);
m.def("erase", &poc_erase);
m.def("checkpoint", &poc_checkpoint);
m.def("restore", &poc_restore);
m.def("convert", &poc_convert);
m.def("live_models", &poc_live_models);
m.def("live_allocated", &poc_live_allocated);
m.def("allocations", &poc_allocations);
m.def("left", &poc_left);
m.def("right", &poc_right);
m.def("right_offset", &poc_right_offset);
b::class_<POCView>(m, "View")
    .def(b::init<const char*>())
    .def("get", &POCView::get).def("set", &POCView::set)
    .def("size", &POCView::size)
    .def("field_get", &POCView::field_get).def("field_set", &POCView::field_set)
    .def("call_adjust", &POCView::call_adjust);
