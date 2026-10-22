/*
    PURPOSE: (Measure frame-start jitter for the variable server benchmark.
              A 100 Hz scheduled job records the wall-clock time between
              calls. The benchmark resets the probe, loads the variable
              server, then reads the statistics.)
    LIBRARY_DEPENDENCIES: (
      (conformance/src/FrameProbe.cpp)
    )
*/

#ifndef FRAMEPROBE_HH
#define FRAMEPROBE_HH

#include <vector>

class FrameProbe
{
    public:
        FrameProbe();

        int sample();  /* scheduled job */
        int reset();   /* clears the samples; the benchmark calls it */
        int compute(); /* fills the statistics below */

        double expected_period; /* s nominal job period */

        long long count;    /* -- periods measured since reset */
        double mean;        /* s mean period */
        double stdev;       /* s standard deviation of the period */
        double p50;         /* s median period */
        double p99;         /* s 99th percentile period */
        double max;         /* s longest period */
        double max_late;    /* s largest (period - expected_period) */
        long long late_1ms; /* -- periods more than 1 ms longer than expected */

    private:
        std::vector<double> periods; /**< trick_io(**) */
        double last;                 /**< trick_io(**) */
        bool have_last;              /**< trick_io(**) */
};

#endif
