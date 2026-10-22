#include "conformance/include/FrameProbe.hh"

#include <algorithm>
#include <cmath>
#include <ctime>

namespace
{

    double now_s()
    {
        struct timespec ts;
        clock_gettime(CLOCK_MONOTONIC, &ts);
        return ts.tv_sec + ts.tv_nsec * 1e-9;
    }

    double percentile(const std::vector<double>& sorted, double p)
    {
        if (sorted.empty())
        {
            return 0.0;
        }
        size_t i = static_cast<size_t>(std::ceil(p * sorted.size())) - 1;
        return sorted[std::min(i, sorted.size() - 1)];
    }

} // namespace

FrameProbe::FrameProbe()
    : expected_period(0.01)
    , count(0)
    , mean(0)
    , stdev(0)
    , p50(0)
    , p99(0)
    , max(0)
    , max_late(0)
    , late_1ms(0)
    , last(0)
    , have_last(false)
{
    periods.reserve(1 << 20);
}

int FrameProbe::sample()
{
    double t = now_s();
    if (have_last && periods.size() < periods.capacity())
    {
        periods.push_back(t - last);
    }
    last      = t;
    have_last = true;
    return 0;
}

int FrameProbe::reset()
{
    periods.clear();
    have_last = false;
    count     = 0;
    mean = stdev = p50 = p99 = max = max_late = 0.0;
    late_1ms                                  = 0;
    return 0;
}

int FrameProbe::compute()
{
    std::vector<double> sorted(periods);
    std::sort(sorted.begin(), sorted.end());
    count = static_cast<long long>(sorted.size());
    if (sorted.empty())
    {
        return 0;
    }
    double sum = 0.0;
    late_1ms   = 0;
    for (double p : sorted)
    {
        sum += p;
        if (p - expected_period > 0.001)
        {
            late_1ms++;
        }
    }
    mean       = sum / sorted.size();
    double var = 0.0;
    for (double p : sorted)
    {
        var += (p - mean) * (p - mean);
    }
    stdev    = std::sqrt(var / sorted.size());
    p50      = percentile(sorted, 0.50);
    p99      = percentile(sorted, 0.99);
    max      = sorted.back();
    max_late = max - expected_period;
    return 0;
}
