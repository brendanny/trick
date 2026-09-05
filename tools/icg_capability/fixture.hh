#pragma once

#define TRICK_ANNOTATE(value) __attribute__((annotate(value)))

struct Root
{
        int root;
};

struct Left : virtual Root
{
        int left;
};

struct Right : virtual Root
{
        int right;
};

struct Diamond : Left, Right
{
        int own;
};

struct ImplicitSpecial
{
        int value;
};

struct DeletedDefault
{
        DeletedDefault() = delete;
};

struct DefaultedDefault
{
        DefaultedDefault() = default;
};

struct Abstract
{
        virtual ~Abstract() = default;
        virtual void run()  = 0;
};

struct FriendTarget
{
    private:
        int hidden;
        friend struct Inspector;
};

template <typename T, int Extent> struct Box
{
        T values[Extent];
};

template <typename T> struct Box<T*, 4>
{
        T* values[4];
};

template <typename... Ts> struct Pack
{
};

template <unsigned Width> struct DependentBits
{
        unsigned value : Width;
};

struct Facts
{
        /** trick_units(m) field documentation */
        int documented TRICK_ANNOTATE("trick:io=io");
        unsigned fixed_bits : 3;
        struct
        {
                int value;
        } anonymous_record;
};

Box<int*, 4> box_use;
Pack<int, double> pack_use;
DependentBits<5> bits_use;
