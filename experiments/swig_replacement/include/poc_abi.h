#pragma once
#ifdef __cplusplus
extern "C" {
#endif
// All exceptions are caught at this boundary; error text is thread-local and
// valid until the next call. Handles are owned by the caller until destroy.
const char* poc_error(void);
void* poc_create(int kind, const char* name, double value);
void poc_destroy(int kind, void* handle);
double poc_call(int operation, void* handle, const char* text, const char* second, int index, double value);
const char* poc_text(void);
#ifdef __cplusplus
}
#endif
