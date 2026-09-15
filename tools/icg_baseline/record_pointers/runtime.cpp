// Independent record pointer identity and cyclic checkpoint restoration.
#include "metadata.cpp"
#include "native_probe.hh"

#include "trick/MemoryManager.hh"

#include <clocale>
#include <fstream>
#include <sstream>
#include <tuple>

namespace
{
    using record_pointer::Node;
    using record_pointer::Peer;
    template <class T> auto members(T& r)
    {
        if constexpr (std::is_same<std::remove_cv_t<T>, RecordPointerModel>::value)
            return std::tie(r.lead, r.head, r.peer, r.alias, r.nodes, r.matrix, r.tail);
        else if constexpr (std::is_same<std::remove_cv_t<T>, Node>::value)
            return std::tie(r.value, r.next, r.peer);
        else
            return std::tie(r.value, r.owner);
    }
    template <class T> bool equal(const T& a, const T& b)
    {
        if constexpr (std::is_array<T>::value)
        {
            for (size_t i = 0; i < std::extent<T>::value; ++i)
                if (!equal(a[i], b[i]))
                    return false;
            return true;
        }
        else
            return a == b;
    }
    template <class T, size_t... I> bool same(const T& a, const T& b, std::index_sequence<I...>)
    {
        return (equal(std::get<I>(members(a)), std::get<I>(members(b))) && ...);
    }
    template <class T> bool same(const T& a, const T& b)
    {
        return same(a, b, std::make_index_sequence<std::tuple_size<decltype(members(a))>::value> { });
    }
    template <class T> bool different(const T& a, const T& b)
    {
        if constexpr (std::is_array<T>::value)
        {
            for (size_t i = 0; i < std::extent<T>::value; ++i)
                if (!different(a[i], b[i]))
                    return false;
            return true;
        }
        else
            return a != b;
    }
    template <class T, size_t... I> bool all_changed(const T& a, const T& b, std::index_sequence<I...>)
    {
        return (different(std::get<I>(members(a)), std::get<I>(members(b))) && ...);
    }
    template <class T> bool all_changed(const T& a, const T& b)
    {
        return all_changed(a, b, std::make_index_sequence<std::tuple_size<decltype(members(a))>::value> { });
    }
    template <class T> void print(const T& value, const Node (&nodes)[3], const Peer (&peers)[2])
    {
        if constexpr (std::is_array<T>::value)
        {
            std::cout << '[';
            for (size_t i = 0; i < std::extent<T>::value; ++i)
            {
                if (i)
                    std::cout << ',';
                print(value[i], nodes, peers);
            }
            std::cout << ']';
        }
        else if constexpr (std::is_pointer<T>::value)
        {
            if (!value)
            {
                std::cout << -1;
                return;
            }
            if constexpr (std::is_same<T, Node*>::value)
            {
                for (int i = 0; i < 3; ++i)
                    if (value == &nodes[i])
                    {
                        std::cout << i;
                        return;
                    }
            }
            else
            {
                for (int i = 0; i < 2; ++i)
                    if (value == &peers[i])
                    {
                        std::cout << i;
                        return;
                    }
            }
            throw std::runtime_error("unknown restored record target");
        }
        else
            std::cout << value;
    }
}
int main()
{
    try
    {
        std::setlocale(LC_ALL, "C");
        RecordPointerModel model { };
        Node nodes[3] { };
        Peer peers[2] { };
        Trick::MemoryManager mm;
        probe::require(mm.declare_extern_var(&model, "RecordPointerModel model") == &model, "model registration");
        probe::require(mm.declare_extern_var(nodes, "record_pointer__Node nodes[3]") == nodes, "node registration");
        probe::require(mm.declare_extern_var(peers, "record_pointer__Peer peers[2]") == peers, "peer registration");
        mm.set_reduced_checkpoint(false);
        mm.set_hexfloat_checkpoint(false);
        mm.set_hexfloat_decimal_comment_checkpoint(false);
        std::cout << "{\"round_trips\":[";
        for (int pass = 0; pass < 2; ++pass)
        {
            mm.set_expanded_arrays(pass != 0);
            nodes[0] = { 101 + pass, &nodes[0], &peers[0] }; // self and mutual cycles
            nodes[1] = { 201 + pass, &nodes[2], &peers[1] };
            nodes[2] = { 301 + pass, &nodes[1], nullptr };
            peers[0] = { 1.25 + pass, &nodes[0] };
            peers[1] = { 2.5 + pass, &nodes[2] };
            model    = {
                11 + pass, pass ? nullptr : &nodes[1],        &peers[1],
                &nodes[1], { &nodes[0], nullptr, &nodes[1] },
                 { { &nodes[2], &nodes[1] }, { nullptr, &nodes[2] } },
                21 + pass
            };
            const auto expected_model   = model;
            const Node expected_nodes[] = { nodes[0], nodes[1], nodes[2] };
            const Peer expected_peers[] = { peers[0], peers[1] };
            std::ostringstream checkpoint;
            mm.write_checkpoint(checkpoint);
            std::ofstream("checkpoint-" + std::to_string(pass) + ".txt") << checkpoint.str();
            model = {
                -1,
                &nodes[0],
                nullptr,
                nullptr,
                { nullptr, &nodes[0], nullptr },
                { { nullptr, nullptr }, { &nodes[0], nullptr } },
                -1
            };
            for (int i = 0; i < 3; ++i)
                nodes[i] = { -1, nullptr, i == 0 ? &peers[1] : &peers[0] };
            for (auto& peer : peers)
                peer = { -1, nullptr };
            bool changed = all_changed(model, expected_model);
            for (int i = 0; i < 3; ++i)
                changed = changed && all_changed(nodes[i], expected_nodes[i]);
            for (int i = 0; i < 2; ++i)
                changed = changed && all_changed(peers[i], expected_peers[i]);
            probe::require(changed, "record pointer control did not mutate every location");
            const int restored = mm.read_checkpoint_from_string(checkpoint.str().c_str());
            probe::require(restored == 0, "record pointer checkpoint restore failed");
            bool matches = same(model, expected_model);
            for (int i = 0; i < 3; ++i)
                matches = matches && same(nodes[i], expected_nodes[i]);
            for (int i = 0; i < 2; ++i)
                matches = matches && same(peers[i], expected_peers[i]);
            probe::require(matches, "record pointer checkpoint values did not round trip");
            if (pass)
                std::cout << ',';
            std::cout << '[';
            bool first = true;
            auto item  = [&](const auto& value)
            {
                if (!first)
                    std::cout << ',';
                first = false;
                print(value, nodes, peers);
            };
            std::apply([&](const auto&... field) { (item(field), ...); }, members(model));
            const int values[]     = { nodes[0].value, nodes[1].value, nodes[2].value };
            Node* next[]           = { nodes[0].next, nodes[1].next, nodes[2].next };
            Peer* links[]          = { nodes[0].peer, nodes[1].peer, nodes[2].peer };
            const double weights[] = { peers[0].value, peers[1].value };
            Node* owners[]         = { peers[0].owner, peers[1].owner };
            item(values);
            item(next);
            item(links);
            item(weights);
            item(owners);
            std::cout << ']';
        }
        std::cout << "]}\n";
        return 0;
    }
    catch (const std::exception& error)
    {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
