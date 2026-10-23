/*
    PURPOSE:
        (Deprecated. The variable server's session threads are internal to the server since the
         rewrite (Phase 6). This header keeps set_vs_ptr(), which older copies of
         default_trick_sys.sm call, as a function that does nothing.)
*/

#ifndef VARIABLESERVERSESSIONTHREAD_HH
#define VARIABLESERVERSESSIONTHREAD_HH

namespace Trick {

    class VariableServer;

    /** Deprecated: kept so that an S_define written for an older Trick still builds. */
    class VariableServerSessionThread {
        public:
            /** Does nothing. The server finds itself. */
            static void set_vs_ptr(Trick::VariableServer * in_vs) { (void)in_vs; }
    };

}

#endif
