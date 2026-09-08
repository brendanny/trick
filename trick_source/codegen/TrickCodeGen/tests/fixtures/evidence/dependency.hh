#pragma once
// Dependency facts are distinct from user-file selection roots.
namespace evidence {
struct Dependency { int value; };
struct UnusedDependency { int value; };
class InputProcessor { static int unsupported; };
}
