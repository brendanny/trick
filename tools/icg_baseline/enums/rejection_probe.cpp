// Compare actual legacy storage with C++ enum values. This case is rejected,
// not normalized into a successful candidate/legacy/native comparison.
#include "legacy.cpp"
#include <iostream>

int main() {
    std::cout << "{\"Byte\":["
              << enumicg_rejected__Byte[1].value << ','
              << static_cast<unsigned>(icg_rejected::Byte::middle) << ','
              << enumicg_rejected__Byte[2].value << ','
              << static_cast<unsigned>(icg_rejected::Byte::maximum)
              << "],\"Word\":["
              << enumicg_rejected__Word[1].value << ','
              << static_cast<unsigned>(icg_rejected::Word::middle) << ','
              << enumicg_rejected__Word[2].value << ','
              << static_cast<unsigned>(icg_rejected::Word::maximum)
              << "],\"Boolean\":[" << enumicg_rejected__Boolean[1].value << ','
              << static_cast<unsigned>(icg_rejected::Boolean::one) << "]}\n";
}
