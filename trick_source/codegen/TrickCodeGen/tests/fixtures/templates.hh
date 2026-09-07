#pragma once

namespace templates
{
    template <class T, int N = 3> struct Array
    {
            T values[N];
            T get() const;
    };
    template <class T> struct Choice
    {
            T value;
    };
    template <class T> struct Choice<T*>
    {
            T* value;
            unsigned flag : 1;
    };
    template <> struct Choice<bool>
    {
            int flag;
    };
    template <class... T> struct Pack
    {
            int count;
    };
    template <int... V> struct Numbers
    {
    };
    template <template <class> class C, class T> struct Apply
    {
            C<T> value;
    };
    template <int* P> struct Null
    {
    };
    template <class T> struct Opaque;
    using Int   = int;
    using Alias = Array<Int>;
    struct Model
    {
            Alias array;
            Choice<int*> partial;
            Choice<bool> explicit_choice;
            Pack<> empty;
            Pack<int, const double*> pack;
            Numbers<-2, 0, 7> numbers;
            Apply<Choice, int> apply;
            Null<nullptr> null_pointer;
            Opaque<int>* opaque;
    };
    extern template struct Array<short, 2>;
    template struct Array<long, 4>;
}
