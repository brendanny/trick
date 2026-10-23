#include "trick/vs/Packetizer.hh"

#include "trick/vs/AsciiEncoder.hh"
#include "trick/vs/BinaryEncoder.hh"

#include <charconv>
#include <stdexcept>

namespace Trick
{
    namespace vs
    {

        namespace
        {

            void check_sizes(const Snapshot& snapshot, const std::vector<VarFormat>& formats)
            {
                if (snapshot.size() != formats.size())
                    throw std::invalid_argument("variable server: one VarFormat is needed for each snapshot value");
            }

            std::string number(std::size_t n)
            {
                char buf[24];
                const auto r = std::to_chars(buf, buf + sizeof buf, n);
                return std::string(buf, r.ptr);
            }

        } // namespace

        void encode_ascii(Packets& out, const Snapshot& snapshot, const std::vector<VarFormat>& formats,
                          MessageType type)
        {
            check_sizes(snapshot, formats);
            if (formats.empty())
                return;

            char buf[16];
            const auto r = std::to_chars(buf, buf + sizeof buf, static_cast<int32_t>(type));
            std::string message(buf, r.ptr);
            // As the old server, `size` counts the type and each value plus its
            // tab, but restarts at 0 for a continued message.
            std::size_t size = message.size();
            std::string value;

            for (std::size_t i = 0; i < formats.size(); ++i)
            {
                message += '\t';

                value.clear();
                const StagedValue& staged = snapshot.value(i);
                append_ascii_value(value, staged.desc, snapshot.data(i), formats[i].conversion, formats[i].units);

                if (value.size() + 2 > max_message)
                {
                    out.warnings.push_back("Variable Server buffer[" + number(max_message) + "] too small for symbol "
                                           + std::string(formats[i].name) + ", TRUNCATED IT.");
                    value.resize(max_message - 2);
                }

                if (size + value.size() + 2 > max_message)
                {
                    out.messages.push_back(std::move(message));
                    message.clear();
                    size = 0;
                }

                message += value;
                size += value.size() + 1;
            }

            message += '\n';
            out.messages.push_back(std::move(message));
        }

        void encode_binary(Packets& out, const Snapshot& snapshot, const std::vector<VarFormat>& formats,
                           MessageType type, bool nonames, bool byteswap)
        {
            check_sizes(snapshot, formats);
            if (formats.empty())
                return;

            constexpr std::size_t header_size = 12;

            // First decide which values go in which message, as the old server did.
            struct Message
            {
                    std::size_t size;
                    std::vector<std::size_t> values;
            };
            std::vector<Message> plan;
            plan.push_back({ header_size, {} });

            for (std::size_t i = 0; i < formats.size(); ++i)
            {
                const std::size_t var_size = binary_var_size(formats[i].name, snapshot.value(i).desc, nonames);
                if (header_size + var_size > max_message)
                {
                    out.warnings.push_back("Variable Server buffer[" + number(max_message) + "] too small (need "
                                           + number(header_size + var_size) + ") for symbol "
                                           + std::string(formats[i].name) + ", SKIPPING IT.");
                    continue;
                }
                if (plan.back().size + var_size > max_message)
                    plan.push_back({ header_size, {} });
                plan.back().size += var_size;
                plan.back().values.push_back(i);
            }

            for (const Message& m : plan)
            {
                std::string message;
                message.reserve(m.size);
                append_int32(message, static_cast<int32_t>(type), byteswap);
                append_int32(message, static_cast<int32_t>(m.size - 4), byteswap);
                append_int32(message, static_cast<int32_t>(m.values.size()), byteswap);
                for (std::size_t i : m.values)
                    append_binary_var(message, formats[i].name, snapshot.value(i).desc, snapshot.data(i), nonames,
                                      byteswap);
                out.messages.push_back(std::move(message));
            }
        }

    } // namespace vs
} // namespace Trick
