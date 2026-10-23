/******************************TRICK HEADER*************************************
PURPOSE: ( Types for the variable server adapter test (rewrite Phase 4). VsConfObject
           holds the conformance SIM's ConfVars, so names read "conf.vars.i32" as they
           do in SIM_vs_conformance. )
*******************************************************************************/

#ifndef VS_ADAPTER_TYPES_HH
#define VS_ADAPTER_TYPES_HH

#include "conformance/include/ConfVars.hh"

class VsConfObject
{
    public:
        ConfVars vars; /* -- the conformance SIM's variables */
};

#endif
