#pragma once

#define ICG_DEFAULT_COUNT (2 + 3)
namespace callable_model
{
    using Count = unsigned;
    struct Plain
    {
            int value;
    };
    struct Reference
    {
            int& value;
    };
    struct Constant
    {
            const int value;
    };
    struct NoDefault
    {
            explicit NoDefault(int);
    };
    struct MoveOnly
    {
            MoveOnly()                           = default;
            MoveOnly(const MoveOnly&)            = delete;
            MoveOnly(MoveOnly&&)                 = default;
            MoveOnly& operator=(const MoveOnly&) = delete;
            MoveOnly& operator=(MoveOnly&&)      = default;
    };
    struct UserDtor
    {
            ~UserDtor();
    };
    struct DeletedDtor
    {
            ~DeletedDtor() = delete;
    };
    class InaccessibleCtor
    {
            InaccessibleCtor() = default;

        public:
            void run();
    };
    struct Base
    {
            virtual ~Base()                                 = default;
            virtual int step(int value = 2) const& noexcept = 0;
    };
    struct Derived : Base
    {
            int step(int value) const& noexcept final;
    };
    struct Methods
    {
            Methods();
            explicit Methods(Count initial);
            Methods(const Methods&)            = default;
            ~Methods()                         = default;
            Methods& operator=(const Methods&) = default;
            explicit operator bool() const noexcept;
            double value() const&;
            double value() &&;
            int watch() volatile;
            static int scale(int first, int second = ICG_DEFAULT_COUNT);
            constexpr int twice(int n) const { return 2 * n; }
    };
    void free(int value = ICG_DEFAULT_COUNT);
    void free(int renamed);
    int free(double value) noexcept;
    void arrays(const int values[3], Count size = 3);
    void varargs(const char* format, ...);
    struct Late
    {
            Late();
    };
    inline Late::Late() = default;
    struct Throws
    {
            Throws() noexcept(false);
    };
    struct ContainsThrows
    {
            Throws value;
    };
}
