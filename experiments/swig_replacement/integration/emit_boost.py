"""Boost.Python consumer of the shared, validated declaration model."""
import json


def emit_boost(model):
    lines = ['#include "generated.hh"', '#include "boost_bindings.hh"',
             'namespace binding {', 'void bind_generated_boost() {']
    for record in model["records"]:
        name = record["name"]
        lines += [f'  bp::class_<Handle<{name}>> cls_{name}("{name}", bp::no_init);']
        allocation = "TRICK_ALLOC_MALLOC" if record["allocation"] == "trick_malloc" else "TRICK_ALLOC_NEW"
        for ctor in record["constructors"]:
            signature = ', '.join([f'double {a["name"]}' for a in ctor] + ['bp::object TMMName'])
            arguments = ''.join(', ' + a["name"] for a in ctor)
            keywords = ', '.join([f'bp::arg("{a["name"]}")' for a in ctor] + ['bp::arg("TMMName") = bp::object()'])
            # Unary + converts captureless lambdas to function pointers, whose
            # signatures Boost.Python can inspect without a custom signature.
            lines += [f'  cls_{name}.def("__init__", bp::make_constructor(+[]({signature}) {{ return construct_boost<{name}>("{name}", {allocation}, &destroy_python_{name}, TMMName{arguments}); }}, bp::default_call_policies(), ({keywords})));']
        lines += [f'  cls_{name}.add_property("thisown", &Handle<{name}>::owns);',
                  f'  bp::def("TMMName", +[](const Handle<{name}>& object, const std::string& name) {{ adopt(object, "{name}", name); }});',
                  f'  bp::def("castAs{name}", +[](std::uintptr_t address) {{ return borrow<{name}>(reinterpret_cast<void*>(address), "{name}"); }});',
                  f'  bp::def("find_{name}", +[](const std::string& name) {{ return borrow<{name}>(named(name)->start, "{name}"); }});']
        for field in record["fields"]:
            member, kind = field["name"], field["kind"]
            units = json.dumps(field["units"])
            if kind == "double":
                lines += [f'  cls_{name}.add_property("{member}", +[](const Handle<{name}>& h) {{ return h.get()->{member}; }}, +[](const Handle<{name}>& h, bp::object value) {{ auto n = number(value, {units}); h.get()->{member} = n; }});']
            elif kind == "record":
                lines += [f'  cls_{name}.add_property("{member}", +[](const Handle<{name}>& h) {{ return h.child(&h.get()->{member}); }});']
            else:
                view = f'view(h, &h.get()->{member}, {field.get("count", 0)}, {units})'
                lines += [f'  cls_{name}.add_property("{member}", +[](const Handle<{name}>& h) {{ return {view}; }}, +[](const Handle<{name}>& h, bp::object values) {{ assign_values({view}, values); }});']
        static_methods = set()
        for method in record["methods"]:
            params, call = [], []
            if not method["static"]:
                params.append(f'const Handle<{name}>& self')
            for arg in method["arguments"]:
                if arg["type"] == name + " &":
                    params.append(f'const Handle<{name}>& {arg["name"]}')
                    call.append('*' + arg["name"] + '.get()')
                else:
                    params.append(arg["type"] + ' ' + arg["name"])
                    call.append(arg["name"])
            target = name + '::' if method["static"] else 'self.get()->'
            lines += [f'  cls_{name}.def("{method["name"]}", +[]({", ".join(params)}) {{ return {target}{method["name"]}({", ".join(call)}); }});']
            if method["static"]:
                static_methods.add(method["name"])
        # Apply only after registering every overload of a static method.
        for method in sorted(static_methods):
            lines += [f'  cls_{name}.staticmethod("{method}");']
    return '\n'.join(lines + ['}', '}']) + '\n'
