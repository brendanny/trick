// Standalone subsystem tests have no Executive/MessagePublisher. Capture their
// diagnostic boundary here; production targets keep the real runtime boundary.
#include <cstdarg>
#include <cstdio>

extern "C" int message_publish(int, const char* format, ...)
{
    va_list args;
    va_start(args, format);
    const int result = std::vfprintf(stderr, format, args);
    va_end(args);
    return result;
}
