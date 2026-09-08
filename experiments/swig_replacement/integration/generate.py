#!/usr/bin/env python3
"""Extract a bounded declaration model, then emit metadata and checked bindings.

This experiment deliberately rejects unsupported selected declarations. It does
not replace TrickCodeGen or implement the full legacy ICG selection/IO policy.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

from clang import cindex as cx


def compiler_includes(compiler):
    result = subprocess.run([compiler, "-E", "-x", "c++", "-", "-v"], input="",
                            text=True, capture_output=True, check=True)
    section = result.stderr.split("#include <...> search starts here:", 1)[1].split("End of search list.", 1)[0]
    return [line.strip() for line in section.splitlines() if line.strip()]


def units(field):
    # Parse only the unit token, including legacy /* *i m ... */ comments. IO
    # flags and the rest of Trick's annotation language are outside this lane.
    source = Path(field.location.file.name).read_text()
    line = source[field.extent.end.offset:].split("\n", 1)[0]
    comment = re.search(r"/\*(.*?)\*/", line)
    text = comment[1].strip("*< ") if comment else ""
    explicit = re.search(r"trick_units\(([^)]+)\)", text)
    if explicit:
        return explicit[1]
    tokens = text.split()
    if tokens and tokens[0] in ("i", "o", "io", "*i", "*o", "*io"):
        tokens.pop(0)
    return tokens[0] if tokens else "--"


def extract(header, policy, args):
    if policy.get("version") != 1:
        raise ValueError("unsupported policy version")
    tu = cx.Index.create().parse(str(header), args=args)
    errors = [str(d) for d in tu.diagnostics if d.severity >= cx.Diagnostic.Error]
    if errors:
        raise ValueError("Clang rejected the translation unit:\n" + "\n".join(errors))
    selected = {p["name"]: p for p in policy["records"]}
    if len(selected) != len(policy["records"]):
        raise ValueError("duplicate selected record")
    definitions = {}
    for cursor in tu.cursor.walk_preorder():
        if cursor.kind in (cx.CursorKind.STRUCT_DECL, cx.CursorKind.CLASS_DECL) and cursor.is_definition() and cursor.spelling in selected:
            if cursor.semantic_parent.kind != cx.CursorKind.TRANSLATION_UNIT:
                raise ValueError("namespaced/nested records not supported in this lane: " + cursor.spelling)
            definitions[cursor.spelling] = cursor
    records = []
    for name, entry in selected.items():
        if name not in definitions:
            raise ValueError("selected record not found: " + name)
        cursor = definitions[name]
        source = Path(cursor.location.file.name)
        record = {"name": name, "allocation": entry["allocation"],
                  "source": source.name, "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                  "fields": [], "constructors": [], "methods": []}
        found_methods = set()
        for item in cursor.get_children():
            if item.kind == cx.CursorKind.CXX_BASE_SPECIFIER:
                raise ValueError("inheritance generation is not implemented: " + name)
            if item.kind in (cx.CursorKind.CXX_METHOD, cx.CursorKind.DESTRUCTOR) and item.is_virtual_method():
                raise ValueError("virtual records are outside the standard-layout lane: " + name)
            if item.access_specifier != cx.AccessSpecifier.PUBLIC:
                continue
            if item.kind == cx.CursorKind.FIELD_DECL:
                typ = item.type.get_canonical()
                if item.is_bitfield() or typ.is_const_qualified():
                    raise ValueError("unsupported field: " + name + "." + item.spelling)
                field = {"name": item.spelling, "type": typ.spelling, "units": units(item)}
                if typ.kind == cx.TypeKind.DOUBLE:
                    field["kind"] = "double"
                elif typ.kind == cx.TypeKind.CONSTANTARRAY and typ.element_type.kind == cx.TypeKind.DOUBLE:
                    field.update(kind="array", count=typ.element_count)
                elif typ.spelling in selected:
                    field["kind"] = "record"
                elif typ.spelling == "std::vector<double>":
                    field["kind"] = "vector"
                else:
                    raise ValueError(f"unsupported field {name}.{item.spelling}: {typ.spelling}")
                record["fields"].append(field)
            elif item.kind == cx.CursorKind.CONSTRUCTOR:
                if item.is_copy_constructor() or item.is_move_constructor():
                    continue
                arguments = [{"name": a.spelling or f"arg{i}", "type": a.type.spelling}
                             for i, a in enumerate(item.get_arguments())]
                if item.is_deleted_method() or any(a["type"] != "double" for a in arguments):
                    raise ValueError("unsupported selected constructor: " + item.displayname)
                record["constructors"].append(arguments)
            elif item.kind == cx.CursorKind.CXX_METHOD and item.spelling in entry["methods"]:
                arguments = [{"name": a.spelling or f"arg{i}", "type": a.type.spelling}
                             for i, a in enumerate(item.get_arguments())]
                if item.result_type.spelling not in ("int", "double", "void") or any(a["type"] not in ("double", "int", name + " &") for a in arguments):
                    raise ValueError("unsupported selected method: " + item.displayname)
                record["methods"].append({"name": item.spelling, "result": item.result_type.spelling,
                                          "static": item.is_static_method(), "arguments": arguments})
                found_methods.add(item.spelling)
        missing = set(entry["methods"]) - found_methods
        if missing:
            raise ValueError(f"missing methods for {name}: {sorted(missing)}")
        if not record["constructors"]:
            record["constructors"] = [[]]  # aggregates in this bounded lane
        if [] not in record["constructors"]:
            raise ValueError("checkpoint generation requires a default constructor: " + name)
        if record["allocation"] not in ("new", "trick_malloc"):
            raise ValueError("unknown allocation recipe: " + record["allocation"])
        records.append(record)
    # A by-value member's class must be registered before its enclosing class.
    ordered = []
    while records:
        ready = [r for r in records if all(f["type"] in {x["name"] for x in ordered}
                 for f in r["fields"] if f["kind"] == "record")]
        if not ready:
            raise ValueError("cyclic/unknown record dependency")
        for record in ready:
            ordered.append(record); records.remove(record)
    return {"version": 1, "records": ordered,
            "header_sha256": hashlib.sha256(header.read_bytes()).hexdigest(),
            "policy_sha256": hashlib.sha256(json.dumps(policy, sort_keys=True).encode()).hexdigest()}


def emit(model, header_name):
    declarations = ['#pragma once', f'#include "{header_name}"', 'extern "C" {']
    metadata = ['#include "generated.hh"', '#include "trick/checkpoint_stl.hh"', '#include <cstdlib>', '#include <new>', '#include <type_traits>']
    bindings = ['#include "generated.hh"', '#include "bindings.hh"', 'namespace binding {', 'void bind_generated(py::module_& m) {']
    for record in model["records"]:
        name = record["name"]
        fields = record["fields"]
        declarations += [f'extern ATTRIBUTES attr{name}[{len(fields)+1}];', f'void init_attr{name}_c_intf();', f'void destroy_python_{name}(void*);']
        metadata += ['extern "C" {', f'ATTRIBUTES attr{name}[{len(fields)+1}] = {{}};', f'void init_attr{name}_c_intf() {{',
                     '  static bool done = false; if (done) return; done = true;', f'  static_assert(std::is_standard_layout_v<{name}>, "this generator requires standard-layout records");']
        for i, field in enumerate(fields):
            member, kind, typ = field["name"], field["kind"], field["type"]
            a = f'attr{name}[{i}]'
            trick_type = {"double": "TRICK_DOUBLE", "array": "TRICK_DOUBLE", "record": "TRICK_STRUCTURED", "vector": "TRICK_STL"}[kind]
            size = "sizeof(double)" if kind in ("double", "array") else f"sizeof(decltype({name}::{member}))"
            type_name = "double" if kind == "array" else typ
            metadata += [f'  {a}.name = "{member}"; {a}.type_name = "{type_name}";',
                         f'  {a}.units = {json.dumps(field["units"])}; {a}.io = 15; {a}.language = Language_CPP;',
                         f'  {a}.type = {trick_type}; {a}.size = {size};',
                         f'  {a}.offset = offsetof({name}, {member});']
            if kind == "record":
                metadata += [f'  init_attr{typ}_c_intf(); {a}.attr = attr{typ};']
            elif kind == "array":
                metadata += [f'  {a}.num_index = 1; {a}.index[0].size = {field["count"]};']
            elif kind == "vector":
                metadata += [f'  {a}.stl_type = TRICK_STL_VECTOR; {a}.stl_elem_type = TRICK_DOUBLE; {a}.stl_elem_type_name = "double";',
                             f'  {a}.get_stl_size = [](void* p) {{ return static_cast<std::vector<double>*>(p)->size(); }};',
                             f'  {a}.get_stl_element = [](void* p, size_t i) -> void* {{ return &static_cast<std::vector<double>*>(p)->at(i); }};']
                for slot, fn in (("checkpoint_stl", "checkpoint_stl"), ("post_checkpoint_stl", "delete_stl"), ("restore_stl", "restore_stl")):
                    metadata += [f'  {a}.{slot} = [](void* p, const char* object, const char* field) {{ {fn}(*static_cast<std::vector<double>*>(p), object, field); }};']
                metadata += [f'  {a}.clear_stl = [](void* p) {{ static_cast<std::vector<double>*>(p)->clear(); }};']
        metadata += [f'  attr{name}[{len(fields)}].name = "";', '}', f'size_t io_src_sizeof_{name}() {{ return sizeof({name}); }};',
                     f'void* io_src_allocate_{name}(int count) {{',
                     f'  auto p = static_cast<{name}*>(std::calloc(count, sizeof({name}))); if (!p) throw std::bad_alloc();',
                     '  int i = 0; try {', f'    for (; i < count; ++i) ::new (static_cast<void*>(&p[i])) {name}();',
                     f'  }} catch (...) {{ while (i) p[--i].~{name}(); std::free(p); throw; }}', '  return p;', '}',
                     f'void io_src_destruct_{name}(void* p, int count) {{ for (int i=0; i<count; ++i) static_cast<{name}*>(p)[i].~{name}(); }}',
                     f'void destroy_python_{name}(void* p) {{']
        metadata += ([f'  static_cast<{name}*>(p)->~{name}(); std::free(p);'] if record["allocation"] == "trick_malloc" else [f'  delete static_cast<{name}*>(p);'])
        metadata += ['}', f'void io_src_delete_{name}(void* p) {{ destroy_python_{name}(p); }}', '}']

        bindings += [f'  auto cls_{name} = py::class_<Handle<{name}>>(m, "{name}");']
        allocation = "TRICK_ALLOC_MALLOC" if record["allocation"] == "trick_malloc" else "TRICK_ALLOC_NEW"
        for ctor in record["constructors"]:
            signature = ', '.join([f'double {a["name"]}' for a in ctor] + ['py::object TMMName'])
            arguments = ''.join(', ' + a["name"] for a in ctor)
            annotations = ''.join(', py::arg("' + a["name"] + '")' for a in ctor)
            bindings += [f'  cls_{name}.def(py::init([]({signature}) {{ return construct<{name}>("{name}", {allocation}, &destroy_python_{name}, TMMName{arguments}); }}){annotations}, py::arg("TMMName") = py::none());']
        bindings += [f'  cls_{name}.def_property_readonly("thisown", &Handle<{name}>::owns);',
                     f'  m.def("TMMName", [](const Handle<{name}>& object, const std::string& name) {{ adopt(object, "{name}", name); }});',
                     f'  m.def("castAs{name}", [](std::uintptr_t address) {{ return borrow<{name}>(reinterpret_cast<void*>(address), "{name}"); }});',
                     f'  m.def("find_{name}", [](const std::string& name) {{ return borrow<{name}>(named(name)->start, "{name}"); }});']
        for field in fields:
            member, kind, typ = field["name"], field["kind"], field["type"]
            unit = json.dumps(field["units"])
            if kind == "double":
                bindings += [f'  cls_{name}.def_property("{member}", [](const Handle<{name}>& h) {{ return h.get()->{member}; }}, [](const Handle<{name}>& h, py::object value) {{ auto n = number(value, {unit}); h.get()->{member} = n; }});']
            elif kind == "record":
                bindings += [f'  cls_{name}.def_property_readonly("{member}", [](const Handle<{name}>& h) {{ return h.child(&h.get()->{member}); }});']
            else:
                count = field.get("count", 0)
                view = f'view(h, &h.get()->{member}, {count}, {unit})'
                bindings += [f'  cls_{name}.def_property("{member}", [](const Handle<{name}>& h) {{ return {view}; }}, [](const Handle<{name}>& h, py::iterable values) {{ {view}.assign(values); }});']
        for method in record["methods"]:
            params, call = [], []
            if not method["static"]:
                params.append(f'const Handle<{name}>& self')
            for arg in method["arguments"]:
                if arg["type"] == name + " &":
                    params.append(f'const Handle<{name}>& {arg["name"]}')
                    call.append('*' + arg["name"] + '.get()')
                else:
                    params.append(arg["type"] + ' ' + arg["name"]); call.append(arg["name"])
            target = name + '::' if method["static"] else 'self.get()->'
            definition = 'def_static' if method["static"] else 'def'
            bindings += [f'  cls_{name}.{definition}("{method["name"]}", []({", ".join(params)}) {{ return {target}{method["name"]}({", ".join(call)}); }});']
    declarations += ['}']
    bindings += ['}', '}']
    return {"generated.hh": '\n'.join(declarations)+'\n', "metadata.cpp": '\n'.join(metadata)+'\n', "bindings.cpp": '\n'.join(bindings)+'\n'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--header", type=Path, required=True)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--compiler", default="c++")
    parser.add_argument("-I", dest="includes", action="append", default=[])
    opts = parser.parse_args()
    args = ['-x', 'c++', '-std=c++17', '-fparse-all-comments']
    args += ['-I'+str(Path(p).resolve()) for p in opts.includes]
    for directory in compiler_includes(opts.compiler):
        args += ['-isystem', directory]
    try:
        model = extract(opts.header.resolve(), json.loads(opts.policy.read_text()), args)
        generated = emit(model, opts.header.name)
    except ValueError as error:
        print(error, file=sys.stderr)
        return 1
    opts.output.mkdir(parents=True, exist_ok=True)
    # Emit only after extraction and validation succeed.
    generated['declarations.json'] = json.dumps(model, indent=2)+'\n'
    for name, contents in generated.items():
        (opts.output/name).write_text(contents)
    print(f'Generated {len(model["records"])} records from Clang declarations')
    return 0

if __name__ == '__main__':
    sys.exit(main())
