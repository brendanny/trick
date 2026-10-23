#include "trick/vs/CommandParser.hh"

#include "trick/vs/CLocale.hh"

#include <cerrno>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <limits>
#include <optional>
#include <type_traits>

namespace Trick
{
    namespace vs
    {

        namespace
        {

            // ------------------------------------------------------------------
            // Literals
            // ------------------------------------------------------------------

            struct Literal
            {
                    enum class Kind
                    {
                        Str,
                        Int,
                        Float,
                        Bool,
                        None
                    };

                    Kind kind = Kind::None;
                    std::string str;          // Str: UTF-8 bytes
                    std::size_t code_points = 0; // Str
                    bool has_nul = false;        // Str
                    int64_t i = 0;               // Int
                    double f = 0.0;              // Float
                    bool b = false;              // Bool
            };

            bool is_ident_start(char c) noexcept
            {
                return (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || c == '_';
            }

            bool is_ident_char(char c) noexcept { return is_ident_start(c) || (c >= '0' && c <= '9'); }

            bool is_space(char c) noexcept { return c == ' ' || c == '\t' || c == '\f' || c == '\r'; }

            int hex_value(char c) noexcept
            {
                if (c >= '0' && c <= '9')
                    return c - '0';
                if (c >= 'a' && c <= 'f')
                    return c - 'a' + 10;
                if (c >= 'A' && c <= 'F')
                    return c - 'A' + 10;
                return -1;
            }

            void append_utf8(std::string& out, uint32_t cp)
            {
                if (cp < 0x80)
                {
                    out += static_cast<char>(cp);
                }
                else if (cp < 0x800)
                {
                    out += static_cast<char>(0xC0 | (cp >> 6));
                    out += static_cast<char>(0x80 | (cp & 0x3F));
                }
                else if (cp < 0x10000)
                {
                    out += static_cast<char>(0xE0 | (cp >> 12));
                    out += static_cast<char>(0x80 | ((cp >> 6) & 0x3F));
                    out += static_cast<char>(0x80 | (cp & 0x3F));
                }
                else
                {
                    out += static_cast<char>(0xF0 | (cp >> 18));
                    out += static_cast<char>(0x80 | ((cp >> 12) & 0x3F));
                    out += static_cast<char>(0x80 | ((cp >> 6) & 0x3F));
                    out += static_cast<char>(0x80 | (cp & 0x3F));
                }
            }

            /** Length of the valid UTF-8 sequence at s[i], or 0 if it is not valid. */
            std::size_t utf8_sequence(std::string_view s, std::size_t i) noexcept
            {
                const unsigned char c0 = static_cast<unsigned char>(s[i]);
                std::size_t n;
                uint32_t cp;
                if (c0 < 0x80)
                    return 1;
                if (c0 >= 0xC2 && c0 <= 0xDF)
                {
                    n  = 2;
                    cp = c0 & 0x1F;
                }
                else if (c0 >= 0xE0 && c0 <= 0xEF)
                {
                    n  = 3;
                    cp = c0 & 0x0F;
                }
                else if (c0 >= 0xF0 && c0 <= 0xF4)
                {
                    n  = 4;
                    cp = c0 & 0x07;
                }
                else
                {
                    return 0;
                }
                if (i + n > s.size())
                    return 0;
                for (std::size_t k = 1; k < n; ++k)
                {
                    const unsigned char c = static_cast<unsigned char>(s[i + k]);
                    if ((c & 0xC0) != 0x80)
                        return 0;
                    cp = (cp << 6) | (c & 0x3F);
                }
                // Overlong forms, surrogates and values past U+10FFFF are not valid.
                if ((n == 3 && cp < 0x800) || (n == 4 && cp < 0x10000) || cp > 0x10FFFF || (cp >= 0xD800 && cp <= 0xDFFF))
                    return 0;
                return n;
            }

            bool valid_utf8(std::string_view s) noexcept
            {
                for (std::size_t i = 0; i < s.size();)
                {
                    const std::size_t n = utf8_sequence(s, i);
                    if (n == 0)
                        return false;
                    i += n;
                }
                return true;
            }

            /** A comment-only line that Python reads as a source encoding declaration (PEP 263). */
            bool is_coding_cookie(std::string_view line) noexcept
            {
                std::size_t i = 0;
                while (i < line.size() && is_space(line[i]))
                    ++i;
                if (i == line.size() || line[i] != '#')
                    return false;
                const std::string_view rest = line.substr(i);
                return rest.find("coding:") != std::string_view::npos || rest.find("coding=") != std::string_view::npos;
            }

            class Lexer
            {
                public:
                    explicit Lexer(std::string_view s)
                        : _s(s)
                    {
                    }

                    void skip_space()
                    {
                        while (_p < _s.size() && is_space(_s[_p]))
                            ++_p;
                    }

                    bool at_end() const { return _p >= _s.size(); }

                    char peek(std::size_t ahead = 0) const { return _p + ahead < _s.size() ? _s[_p + ahead] : '\0'; }

                    bool accept(char c)
                    {
                        if (peek() == c && !at_end())
                        {
                            ++_p;
                            return true;
                        }
                        return false;
                    }

                    std::string_view identifier()
                    {
                        const std::size_t start = _p;
                        if (!is_ident_start(peek()))
                            return {};
                        while (_p < _s.size() && is_ident_char(_s[_p]))
                            ++_p;
                        return _s.substr(start, _p - start);
                    }

                    /** The rest of the line is empty, or only a comment. */
                    bool rest_is_blank()
                    {
                        skip_space();
                        return at_end() || peek() == '#';
                    }

                    /** Parse one literal argument. Returns nullopt if it is anything else. */
                    std::optional<Literal> literal()
                    {
                        // Unary signs: Python allows any run of + and -, with spaces.
                        bool negative = false;
                        bool signed_value = false;
                        while (peek() == '+' || peek() == '-')
                        {
                            negative ^= (peek() == '-');
                            signed_value = true;
                            ++_p;
                            skip_space();
                        }
                        const char c = peek();
                        if ((c >= '0' && c <= '9') || (c == '.' && peek(1) >= '0' && peek(1) <= '9'))
                        {
                            return number(negative);
                        }
                        if (signed_value)
                            return std::nullopt;  // -True, -"x", ... are expressions
                        if (c == '"' || c == '\'')
                        {
                            return string();
                        }
                        if (is_ident_start(c))
                        {
                            const std::string_view id = identifier();
                            if (peek() == '"' || peek() == '\'')
                            {
                                // Only the u prefix means a plain str; r, b, f change it.
                                if (id == "u" || id == "U")
                                    return string();
                                return std::nullopt;
                            }
                            Literal lit;
                            if (id == "True" || id == "False")
                            {
                                lit.kind = Literal::Kind::Bool;
                                lit.b    = (id == "True");
                                return lit;
                            }
                            if (id == "None")
                            {
                                lit.kind = Literal::Kind::None;
                                return lit;
                            }
                        }
                        return std::nullopt;
                    }

                private:
                    std::optional<Literal> string()
                    {
                        const char quote = _s[_p];
                        if (peek(1) == quote && peek(2) == quote)
                            return std::nullopt;  // triple-quoted
                        ++_p;
                        Literal lit;
                        lit.kind = Literal::Kind::Str;
                        while (true)
                        {
                            if (at_end())
                                return std::nullopt;  // unterminated
                            const char c = _s[_p];
                            if (c == quote)
                            {
                                ++_p;
                                break;
                            }
                            if (c == '\\')
                            {
                                if (!escape(lit))
                                    return std::nullopt;
                                continue;
                            }
                            const std::size_t n = utf8_sequence(_s, _p);
                            if (n == 0)
                                return std::nullopt;  // Python refuses source that is not UTF-8
                            lit.str.append(_s.data() + _p, n);
                            lit.code_points++;
                            _p += n;
                        }
                        // "a" "b" concatenates in Python; leave that to Python.
                        const std::size_t save = _p;
                        skip_space();
                        if (peek() == '"' || peek() == '\'')
                            return std::nullopt;
                        _p = save;
                        return lit;
                    }

                    bool escape(Literal& lit)
                    {
                        ++_p;  // backslash
                        if (at_end())
                            return false;
                        const char e = _s[_p++];
                        uint32_t cp = 0;
                        switch (e)
                        {
                            case '\\':
                                cp = '\\';
                                break;
                            case '\'':
                                cp = '\'';
                                break;
                            case '"':
                                cp = '"';
                                break;
                            case 'a':
                                cp = 7;
                                break;
                            case 'b':
                                cp = 8;
                                break;
                            case 'f':
                                cp = 12;
                                break;
                            case 'n':
                                cp = 10;
                                break;
                            case 'r':
                                cp = 13;
                                break;
                            case 't':
                                cp = 9;
                                break;
                            case 'v':
                                cp = 11;
                                break;
                            case 'x':
                            {
                                const int h = hex_value(peek());
                                const int l = hex_value(peek(1));
                                if (h < 0 || l < 0)
                                    return false;
                                _p += 2;
                                cp = static_cast<uint32_t>(h * 16 + l);
                                break;
                            }
                            case 'u':
                            case 'U':
                            {
                                const int digits = (e == 'u') ? 4 : 8;
                                for (int k = 0; k < digits; ++k)
                                {
                                    const int h = hex_value(peek());
                                    if (h < 0)
                                        return false;
                                    cp = cp * 16 + static_cast<uint32_t>(h);
                                    ++_p;
                                }
                                // Past U+10FFFF is a SyntaxError; a surrogate cannot become UTF-8 for SWIG.
                                if (cp > 0x10FFFF || (cp >= 0xD800 && cp <= 0xDFFF))
                                    return false;
                                break;
                            }
                            case 'N':
                                return false;  // \N{name}: leave to Python
                            default:
                                if (e >= '0' && e <= '7')
                                {
                                    cp = static_cast<uint32_t>(e - '0');
                                    for (int k = 0; k < 2 && peek() >= '0' && peek() <= '7'; ++k)
                                        cp = cp * 8 + static_cast<uint32_t>(_s[_p++] - '0');
                                    break;
                                }
                                // An unknown escape keeps the backslash (Python warns, but accepts it).
                                --_p;
                                lit.str += '\\';
                                lit.code_points++;
                                return true;
                        }
                        if (cp == 0)
                            lit.has_nul = true;
                        append_utf8(lit.str, cp);
                        lit.code_points++;
                        return true;
                    }

                    static bool digits(std::string_view s, std::size_t& p, bool (*is_digit)(char), std::string& out)
                    {
                        // digit (_? digit)*
                        if (p >= s.size() || !is_digit(s[p]))
                            return false;
                        out += s[p++];
                        while (p < s.size())
                        {
                            if (s[p] == '_')
                            {
                                if (p + 1 >= s.size() || !is_digit(s[p + 1]))
                                    return false;
                                ++p;
                            }
                            else if (!is_digit(s[p]))
                            {
                                break;
                            }
                            out += s[p++];
                        }
                        return true;
                    }

                    static bool dec(char c) { return c >= '0' && c <= '9'; }

                    static bool hex(char c) { return hex_value(c) >= 0; }

                    static bool oct(char c) { return c >= '0' && c <= '7'; }

                    static bool bin(char c) { return c == '0' || c == '1'; }

                    std::optional<Literal> number(bool negative)
                    {
                        Literal lit;
                        std::string text;
                        std::size_t p = _p;

                        // Prefixed integers
                        if (_s[p] == '0' && p + 1 < _s.size()
                            && (_s[p + 1] == 'x' || _s[p + 1] == 'X' || _s[p + 1] == 'o' || _s[p + 1] == 'O'
                                || _s[p + 1] == 'b' || _s[p + 1] == 'B'))
                        {
                            const char kind = static_cast<char>(_s[p + 1] | 0x20);
                            p += 2;
                            if (p < _s.size() && _s[p] == '_')
                                ++p;  // 0x_1f is valid
                            bool (*is_digit)(char) = kind == 'x' ? hex : kind == 'o' ? oct : bin;
                            if (!digits(_s, p, is_digit, text))
                                return std::nullopt;
                            if (p < _s.size() && (is_ident_char(_s[p]) || _s[p] == '.'))
                                return std::nullopt;
                            const int base = kind == 'x' ? 16 : kind == 'o' ? 8 : 2;
                            if (!to_int(text, base, negative, lit.i))
                                return std::nullopt;
                            lit.kind = Literal::Kind::Int;
                            _p       = p;
                            return lit;
                        }

                        bool is_float = false;
                        std::string intpart;
                        if (dec(_s[p]) && !digits(_s, p, dec, intpart))
                            return std::nullopt;
                        text = intpart;
                        if (p < _s.size() && _s[p] == '.')
                        {
                            is_float = true;
                            text += '.';
                            ++p;
                            if (p < _s.size() && dec(_s[p]))
                            {
                                std::string frac;
                                if (!digits(_s, p, dec, frac))
                                    return std::nullopt;
                                text += frac;
                            }
                            else if (intpart.empty())
                            {
                                return std::nullopt;
                            }
                        }
                        if (p < _s.size() && (_s[p] == 'e' || _s[p] == 'E'))
                        {
                            is_float = true;
                            text += 'e';
                            ++p;
                            if (p < _s.size() && (_s[p] == '+' || _s[p] == '-'))
                                text += _s[p++];
                            std::string exp;
                            if (!digits(_s, p, dec, exp))
                                return std::nullopt;
                            text += exp;
                        }
                        // 1j is complex, 1x and 1.2.3 are not numbers.
                        if (p < _s.size() && (is_ident_char(_s[p]) || _s[p] == '.'))
                            return std::nullopt;

                        if (is_float)
                        {
                            ScopedCLocale c_locale;
                            errno          = 0;
                            char* end      = nullptr;
                            const double v = std::strtod(text.c_str(), &end);
                            if (end != text.c_str() + text.size())
                                return std::nullopt;
                            // ERANGE: Python also rounds to inf or 0.
                            lit.kind = Literal::Kind::Float;
                            lit.f    = negative ? -v : v;
                        }
                        else
                        {
                            // Decimal: "0", "00", "0_0" are zero; any other leading zero is a SyntaxError.
                            if (text.size() > 1 && text[0] == '0' && text.find_first_not_of('0') != std::string::npos)
                                return std::nullopt;
                            if (!to_int(text, 10, negative, lit.i))
                                return std::nullopt;
                            lit.kind = Literal::Kind::Int;
                        }
                        _p = p;
                        return lit;
                    }

                    /** Digits (no underscores) to int64. False if out of range. */
                    static bool to_int(const std::string& digits_text, int base, bool negative, int64_t& out)
                    {
                        // Accumulate the magnitude as unsigned; allow 2^63 for negative values.
                        const uint64_t limit = negative ? (uint64_t(1) << 63) : uint64_t(std::numeric_limits<int64_t>::max());
                        uint64_t v           = 0;
                        for (char ch : digits_text)
                        {
                            const uint64_t d = static_cast<uint64_t>(hex_value(ch));
                            if (v > (limit - d) / static_cast<uint64_t>(base))
                                return false;
                            v = v * static_cast<uint64_t>(base) + d;
                        }
                        if (negative)
                            out = (v == (uint64_t(1) << 63)) ? std::numeric_limits<int64_t>::min() : -static_cast<int64_t>(v);
                        else
                            out = static_cast<int64_t>(v);
                        return true;
                    }

                    std::string_view _s;
                    std::size_t _p = 0;
            };

            // ------------------------------------------------------------------
            // Argument conversion, as SWIG and Trick's typemaps do it
            // ------------------------------------------------------------------

            using Args = std::vector<Literal>;

            /** A std::string parameter: only a str (SWIG_AsPtr_std_string). */
            std::optional<std::string> as_string(const Literal& a)
            {
                if (a.kind != Literal::Kind::Str || a.has_nul)
                    return std::nullopt;
                return a.str;
            }

            /**
             * A scalar parameter through Trick's typemap_in_scalar<T>: a float is
             * cast, an int goes through C long, a one-character str gives its
             * first byte. A float outside T's range is undefined behavior in C,
             * so it stays with Python.
             */
            template <class T> std::optional<T> as_scalar(const Literal& a)
            {
                switch (a.kind)
                {
                    case Literal::Kind::Int:
                        return static_cast<T>(static_cast<long>(a.i));
                    case Literal::Kind::Bool:
                        return static_cast<T>(a.b ? 1 : 0);
                    case Literal::Kind::Float:
                        if constexpr (std::is_floating_point<T>::value)
                        {
                            return static_cast<T>(a.f);
                        }
                        else
                        {
                            if (!std::isfinite(a.f))
                                return std::nullopt;
                            const double t = std::trunc(a.f);
                            if (t < static_cast<double>(std::numeric_limits<T>::min())
                                || t > static_cast<double>(std::numeric_limits<T>::max()))
                                return std::nullopt;
                            return static_cast<T>(t);
                        }
                    case Literal::Kind::Str:
                        if (a.code_points != 1)
                            return std::nullopt;  // the typemap leaves the value unset
                        return static_cast<T>(static_cast<char>(a.str[0]));
                    case Literal::Kind::None:
                        break;
                }
                return std::nullopt;
            }

            /** A bool parameter through typemap_in_scalar<bool>: no strings. */
            std::optional<bool> as_bool(const Literal& a)
            {
                switch (a.kind)
                {
                    case Literal::Kind::Int:
                        return static_cast<long>(a.i) != 0;
                    case Literal::Kind::Bool:
                        return a.b;
                    case Literal::Kind::Float:
                        return a.f != 0.0;  // NaN is true, as in C
                    default:
                        return std::nullopt;
                }
            }

            /** An int in an overloaded function (SWIG_AsVal_int): an int or a bool, in range. */
            std::optional<int> as_strict_int(const Literal& a)
            {
                if (a.kind == Literal::Kind::Bool)
                    return a.b ? 1 : 0;
                if (a.kind != Literal::Kind::Int || a.i < std::numeric_limits<int>::min()
                    || a.i > std::numeric_limits<int>::max())
                    return std::nullopt;
                return static_cast<int>(a.i);
            }

            template <class C> Command no_args(const Args& args, const std::string& line)
            {
                if (!args.empty())
                    return cmd::Fallback { line };
                return C {};
            }

            Command build(std::string_view name, const Args& args, const std::string& line)
            {
                const auto fallback = [&]() -> Command { return cmd::Fallback { line }; };
                const std::size_t n = args.size();

                // Zero-argument commands
                if (name == "var_clear")
                    return no_args<cmd::VarClear>(args, line);
                if (name == "var_send")
                    return no_args<cmd::VarSend>(args, line);
                if (name == "var_send_list_size")
                    return no_args<cmd::VarSendListSize>(args, line);
                if (name == "var_pause")
                    return no_args<cmd::VarPause>(args, line);
                if (name == "var_unpause")
                    return no_args<cmd::VarUnpause>(args, line);
                if (name == "var_exit")
                    return no_args<cmd::VarExit>(args, line);
                if (name == "var_ascii")
                    return no_args<cmd::VarAscii>(args, line);
                if (name == "var_binary")
                    return no_args<cmd::VarBinary>(args, line);
                if (name == "var_binary_nonames")
                    return no_args<cmd::VarBinaryNoNames>(args, line);
                if (name == "send_sie_resource")
                    return no_args<cmd::SendSieResource>(args, line);
                if (name == "send_sie_class")
                    return no_args<cmd::SendSieClass>(args, line);
                if (name == "send_sie_enum")
                    return no_args<cmd::SendSieEnum>(args, line);
                if (name == "send_sie_top_level_objects")
                    return no_args<cmd::SendSieTopLevelObjects>(args, line);
                if (name == "var_server_log_on" || name == "var_server_log_off")
                {
                    if (n != 0)
                        return fallback();
                    return cmd::VarServerLog { name == "var_server_log_on" };
                }

                // One std::string
                const auto str1 = [&]() -> std::optional<std::string> { return n == 1 ? as_string(args[0]) : std::nullopt; };
                if (name == "var_remove")
                {
                    if (auto s = str1())
                        return cmd::VarRemove { *s };
                    return fallback();
                }
                if (name == "var_exists")
                {
                    if (auto s = str1())
                        return cmd::VarExists { *s };
                    return fallback();
                }
                if (name == "var_get_stl_size")
                {
                    if (auto s = str1())
                        return cmd::VarGetStlSize { *s };
                    return fallback();
                }
                if (name == "var_set_client_tag")
                {
                    if (auto s = str1())
                        return cmd::VarSetClientTag { *s };
                    return fallback();
                }
                if (name == "send_file")
                {
                    if (auto s = str1())
                        return cmd::SendFile { *s };
                    return fallback();
                }

                // Two std::string
                if (name == "var_units")
                {
                    if (n != 2)
                        return fallback();
                    auto a = as_string(args[0]);
                    auto b = as_string(args[1]);
                    if (!a || !b)
                        return fallback();
                    return cmd::VarUnits { *a, *b };
                }

                // Overloaded: (string) | (string, string)
                if (name == "var_add")
                {
                    if (n == 1)
                    {
                        if (auto a = as_string(args[0]))
                            return cmd::VarAdd { *a, std::nullopt };
                    }
                    else if (n == 2)
                    {
                        auto a = as_string(args[0]);
                        auto b = as_string(args[1]);
                        if (a && b)
                            return cmd::VarAdd { *a, *b };
                    }
                    return fallback();
                }

                // Overloaded: (string) | (string, int)
                if (name == "var_send_once")
                {
                    if (n == 1)
                    {
                        if (auto a = as_string(args[0]))
                            return cmd::VarSendOnce { *a, std::nullopt };
                    }
                    else if (n == 2)
                    {
                        auto a = as_string(args[0]);
                        auto c = as_strict_int(args[1]);
                        if (a && c)
                            return cmd::VarSendOnce { *a, *c };
                    }
                    return fallback();
                }

                // One scalar through Trick's typemap
                if (n == 1)
                {
                    const Literal& a = args[0];
                    if (name == "var_cycle")
                    {
                        if (auto v = as_scalar<double>(a))
                            return cmd::VarCycle { *v };
                        return fallback();
                    }
                    if (name == "var_debug")
                    {
                        if (auto v = as_scalar<int>(a))
                            return cmd::VarDebug { *v };
                        return fallback();
                    }
                    if (name == "var_validate_address")
                    {
                        if (auto v = as_scalar<int>(a))
                            return cmd::VarValidateAddress { *v != 0 };
                        return fallback();
                    }
                    if (name == "var_set_copy_mode")
                    {
                        if (auto v = as_scalar<int>(a))
                            return cmd::VarSetCopyMode { *v };
                        return fallback();
                    }
                    if (name == "var_set_write_mode")
                    {
                        if (auto v = as_scalar<int>(a))
                            return cmd::VarSetWriteMode { *v };
                        return fallback();
                    }
                    if (name == "var_set_send_stdio")
                    {
                        if (auto v = as_scalar<int>(a))
                            return cmd::VarSetSendStdio { *v != 0 };
                        return fallback();
                    }
                    if (name == "var_sync")
                    {
                        if (auto v = as_scalar<int>(a))
                            return cmd::VarSync { *v };
                        return fallback();
                    }
                    if (name == "var_set_frame_multiple")
                    {
                        if (auto v = as_scalar<unsigned int>(a))
                            return cmd::VarSetFrameMultiple { *v };
                        return fallback();
                    }
                    if (name == "var_set_frame_offset")
                    {
                        if (auto v = as_scalar<unsigned int>(a))
                            return cmd::VarSetFrameOffset { *v };
                        return fallback();
                    }
                    if (name == "var_set_freeze_frame_multiple")
                    {
                        if (auto v = as_scalar<unsigned int>(a))
                            return cmd::VarSetFreezeFrameMultiple { *v };
                        return fallback();
                    }
                    if (name == "var_set_freeze_frame_offset")
                    {
                        if (auto v = as_scalar<unsigned int>(a))
                            return cmd::VarSetFreezeFrameOffset { *v };
                        return fallback();
                    }
                    if (name == "var_byteswap")
                    {
                        if (auto v = as_bool(a))
                            return cmd::VarByteswap { *v };
                        return fallback();
                    }
                    if (name == "var_send_ip_errors")
                    {
                        if (auto v = as_bool(a))
                            return cmd::VarSendIpErrors { *v };
                        return fallback();
                    }
                }

                if (name == "var_write_stdio")
                {
                    if (n != 2)
                        return fallback();
                    auto stream = as_scalar<int>(args[0]);
                    auto text   = as_string(args[1]);
                    if (!stream || !text)
                        return fallback();
                    return cmd::VarWriteStdio { *stream, *text };
                }

                // var_set(const char*, double | long long | const char* | void*, const char* = NULL).
                // SWIG tries the void* overload first (None), then long long (int or
                // bool), then double (float), then const char* (str).
                if (name == "var_set")
                {
                    if (n != 2 && n != 3)
                        return fallback();
                    auto var = as_string(args[0]);
                    if (!var)
                        return fallback();
                    cmd::SetValue value;
                    const Literal& v = args[1];
                    switch (v.kind)
                    {
                        case Literal::Kind::None:
                            value = cmd::NoneValue {};
                            break;
                        case Literal::Kind::Int:
                            value = static_cast<long long>(v.i);
                            break;
                        case Literal::Kind::Bool:
                            value = static_cast<long long>(v.b ? 1 : 0);
                            break;
                        case Literal::Kind::Float:
                            value = v.f;
                            break;
                        case Literal::Kind::Str:
                            if (v.has_nul)
                                return fallback();
                            value = v.str;
                            break;
                    }
                    std::optional<std::string> units;
                    if (n == 3)
                    {
                        const Literal& u = args[2];
                        if (u.kind == Literal::Kind::Str && !u.has_nul)
                            units = u.str;
                        else if (u.kind != Literal::Kind::None)
                            return fallback();
                    }
                    return cmd::VarSet { *var, value, units };
                }

                return fallback();
            }

            // ------------------------------------------------------------------
            // to_python
            // ------------------------------------------------------------------

            std::string py_string(const std::string& s)
            {
                std::string out = "\"";
                for (unsigned char c : s)
                {
                    switch (c)
                    {
                        case '\\':
                            out += "\\\\";
                            break;
                        case '"':
                            out += "\\\"";
                            break;
                        case '\n':
                            out += "\\n";
                            break;
                        case '\t':
                            out += "\\t";
                            break;
                        case '\r':
                            out += "\\r";
                            break;
                        default:
                            if (c < 0x20 || c == 0x7F)
                            {
                                char buf[8];
                                std::snprintf(buf, sizeof buf, "\\x%02x", c);
                                out += buf;
                            }
                            else
                            {
                                out += static_cast<char>(c);
                            }
                    }
                }
                out += '"';
                return out;
            }

            std::string py_float(double v)
            {
                if (std::isnan(v))
                    return "float('nan')";
                if (std::isinf(v))
                    return v < 0 ? "-1e999" : "1e999";
                ScopedCLocale c_locale;
                char buf[40];
                std::snprintf(buf, sizeof buf, "%.17g", v);
                std::string s = buf;
                if (s.find_first_of(".en") == std::string::npos)
                    s += ".0";
                return s;
            }

            std::string py_bool(bool b) { return b ? "True" : "False"; }

            std::string call(const char* name, const std::string& args = "")
            {
                return std::string("trick.") + name + "(" + args + ")";
            }

            struct ToPython
            {
                    std::string operator()(const cmd::VarAdd& c) const
                    {
                        return call("var_add", py_string(c.name) + (c.units ? ", " + py_string(*c.units) : ""));
                    }
                    std::string operator()(const cmd::VarRemove& c) const { return call("var_remove", py_string(c.name)); }
                    std::string operator()(const cmd::VarUnits& c) const
                    {
                        return call("var_units", py_string(c.name) + ", " + py_string(c.units));
                    }
                    std::string operator()(const cmd::VarSendOnce& c) const
                    {
                        return call("var_send_once",
                                    py_string(c.names) + (c.count ? ", " + std::to_string(*c.count) : ""));
                    }
                    std::string operator()(const cmd::VarExists& c) const { return call("var_exists", py_string(c.name)); }
                    std::string operator()(const cmd::VarGetStlSize& c) const
                    {
                        return call("var_get_stl_size", py_string(c.name));
                    }
                    std::string operator()(const cmd::VarCycle& c) const { return call("var_cycle", py_float(c.seconds)); }
                    std::string operator()(const cmd::VarSetCopyMode& c) const
                    {
                        return call("var_set_copy_mode", std::to_string(c.mode));
                    }
                    std::string operator()(const cmd::VarSetWriteMode& c) const
                    {
                        return call("var_set_write_mode", std::to_string(c.mode));
                    }
                    std::string operator()(const cmd::VarSync& c) const { return call("var_sync", std::to_string(c.mode)); }
                    std::string operator()(const cmd::VarSetFrameMultiple& c) const
                    {
                        return call("var_set_frame_multiple", std::to_string(c.multiple));
                    }
                    std::string operator()(const cmd::VarSetFrameOffset& c) const
                    {
                        return call("var_set_frame_offset", std::to_string(c.offset));
                    }
                    std::string operator()(const cmd::VarSetFreezeFrameMultiple& c) const
                    {
                        return call("var_set_freeze_frame_multiple", std::to_string(c.multiple));
                    }
                    std::string operator()(const cmd::VarSetFreezeFrameOffset& c) const
                    {
                        return call("var_set_freeze_frame_offset", std::to_string(c.offset));
                    }
                    std::string operator()(const cmd::VarByteswap& c) const { return call("var_byteswap", py_bool(c.on)); }
                    std::string operator()(const cmd::VarSendIpErrors& c) const
                    {
                        return call("var_send_ip_errors", py_bool(c.on));
                    }
                    std::string operator()(const cmd::VarValidateAddress& c) const
                    {
                        return call("var_validate_address", py_bool(c.on));
                    }
                    std::string operator()(const cmd::VarDebug& c) const { return call("var_debug", std::to_string(c.level)); }
                    std::string operator()(const cmd::VarSetClientTag& c) const
                    {
                        return call("var_set_client_tag", py_string(c.tag));
                    }
                    std::string operator()(const cmd::VarSetSendStdio& c) const
                    {
                        return call("var_set_send_stdio", py_bool(c.on));
                    }
                    std::string operator()(const cmd::VarWriteStdio& c) const
                    {
                        return call("var_write_stdio", std::to_string(c.stream) + ", " + py_string(c.text));
                    }
                    std::string operator()(const cmd::VarServerLog& c) const
                    {
                        return call(c.on ? "var_server_log_on" : "var_server_log_off");
                    }
                    std::string operator()(const cmd::SendFile& c) const { return call("send_file", py_string(c.path)); }
                    std::string operator()(const cmd::VarSet& c) const
                    {
                        std::string value;
                        if (auto d = std::get_if<double>(&c.value))
                            value = py_float(*d);
                        else if (auto i = std::get_if<long long>(&c.value))
                            value = std::to_string(*i);
                        else if (auto s = std::get_if<std::string>(&c.value))
                            value = py_string(*s);
                        else
                            value = "None";
                        return call("var_set", py_string(c.name) + ", " + value + (c.units ? ", " + py_string(*c.units) : ""));
                    }
                    std::string operator()(const cmd::Fallback& c) const { return c.text; }

                    // Commands with no arguments
                    template <class C> std::string operator()(const C& c) const { return call(command_name(Command(c))); }
            };

        } // namespace

        namespace
        {
            /**
             * Parse one line of `trick.<name>(<literals>)` calls separated by ';'
             * (Python's simple statements). Appends the commands to `out` and
             * returns true only if every statement is typed.
             */
            bool parse_statements(std::string_view line_view, std::vector<Command>& out)
            {
                // Python refuses source that is not UTF-8, and stops at NUL. It reads
                // '\r' as a line break, also inside a comment or a string.
                if (line_view.find_first_of(std::string_view("\0\n\r", 3)) != std::string_view::npos
                    || !valid_utf8(line_view))
                    return false;
                // Indentation is a Python block; leave it to Python.
                if (line_view.empty() || is_space(line_view[0]))
                    return false;

                const std::string line(line_view);
                Lexer lx(line_view);
                while (true)
                {
                    if (lx.identifier() != "trick")
                        return false;
                    lx.skip_space();
                    if (!lx.accept('.'))
                        return false;
                    lx.skip_space();
                    const std::string_view name = lx.identifier();
                    if (name.empty())
                        return false;
                    lx.skip_space();
                    if (!lx.accept('('))
                        return false;

                    Args args;
                    lx.skip_space();
                    if (!lx.accept(')'))
                    {
                        while (true)
                        {
                            lx.skip_space();
                            auto lit = lx.literal();
                            if (!lit)
                                return false;
                            args.push_back(std::move(*lit));
                            lx.skip_space();
                            if (lx.accept(')'))
                                break;
                            if (!lx.accept(','))
                                return false;
                            lx.skip_space();
                            if (lx.accept(')'))
                                break; // trailing comma
                        }
                    }
                    Command c = build(name, args, line);
                    if (is_fallback(c))
                        return false;
                    out.push_back(std::move(c));

                    // ';' then another statement, or a final ';', then only a comment.
                    lx.skip_space();
                    const bool semicolon = lx.accept(';');
                    if (lx.rest_is_blank())
                        return true;
                    if (!semicolon)
                        return false;
                }
            }
        } // namespace

        Command parse_line(std::string_view line)
        {
            std::vector<Command> commands;
            if (parse_statements(line, commands) && commands.size() == 1)
                return std::move(commands.front());
            return cmd::Fallback { std::string(line) };
        }

        std::vector<Command> parse_batch(std::string_view text)
        {
            std::vector<Command> out;
            // Python stops reading a C string at NUL, refuses source that is not
            // UTF-8, and reads an encoding declaration in the first two lines.
            // Leave all of those to Python.
            bool unsafe = text.find('\0') != std::string_view::npos || !valid_utf8(text);
            {
                const std::size_t nl1 = text.find('\n');
                unsafe                = unsafe || is_coding_cookie(text.substr(0, nl1));
                if (nl1 != std::string_view::npos)
                {
                    const std::string_view second = text.substr(nl1 + 1);
                    unsafe                        = unsafe || is_coding_cookie(second.substr(0, second.find('\n')));
                }
            }
            if (unsafe)
            {
                out.push_back(cmd::Fallback { std::string(text) });
                return out;
            }
            std::size_t start = 0;
            while (start <= text.size())
            {
                std::size_t end = text.find('\n', start);
                if (end == std::string_view::npos)
                    end = text.size();
                std::string_view line = text.substr(start, end - start);
                while (!line.empty() && is_space(line.back()))
                    line.remove_suffix(1);

                std::size_t first = 0;
                while (first < line.size() && is_space(line[first]))
                    ++first;
                const bool blank = first == line.size() || line[first] == '#';
                if ((blank && line.find('\r') != std::string_view::npos) || (!blank && !parse_statements(line, out)))
                {
                    out.clear();
                    out.push_back(cmd::Fallback { std::string(text) });
                    return out;
                }
                if (end == text.size())
                    break;
                start = end + 1;
            }
            return out;
        }

        std::string to_python(const Command& command) { return std::visit(ToPython {}, command); }

        std::vector<std::string> split_send_once_names(std::string_view names)
        {
            std::vector<std::string> out;
            if (names.empty())
                return out;
            std::size_t start = 0;
            while (true)
            {
                const std::size_t comma = names.find(',', start);
                if (comma == std::string_view::npos)
                {
                    out.emplace_back(names.substr(start));
                    break;
                }
                out.emplace_back(names.substr(start, comma - start));
                start = comma + 1;
            }
            // std::getline produces no token after a final delimiter.
            if (names.back() == ',')
                out.pop_back();
            return out;
        }

    } // namespace vs
} // namespace Trick
