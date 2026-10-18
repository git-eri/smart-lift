#ifndef SMART_LIFT_PROTOCOL_TEXT_H
#define SMART_LIFT_PROTOCOL_TEXT_H

#include <stddef.h>
#include <string.h>

namespace ProtocolText {

constexpr size_t maxIdentifierLength = 64;

// JSON strings carry a length; C strings and Arduino String conversion stop at NUL.
// Reject embedded NUL before conversion so a longer field cannot alias a command,
// controller ID, hostname or credential prefix.
inline bool isText(const char* value, size_t length) {
  return value && memchr(value, '\0', length) == nullptr;
}

inline bool isIdentifierCharacter(char value) {
  return (value >= 'a' && value <= 'z') || (value >= 'A' && value <= 'Z') ||
         (value >= '0' && value <= '9') || value == '-' || value == '_';
}

inline bool isIdentifier(const char* value, size_t length) {
  if (!value || !length || length > maxIdentifierLength) return false;
  for (size_t i = 0; i < length; ++i) {
    if (!isIdentifierCharacter(value[i])) return false;
  }
  return true;
}

// State-machine callers provide a C string. Bound the scan to the wire limit.
inline bool isIdentifier(const char* value) {
  if (!value) return false;
  size_t length = 0;
  while (length <= maxIdentifierLength && value[length]) {
    if (!isIdentifierCharacter(value[length])) return false;
    ++length;
  }
  return length && length <= maxIdentifierLength;
}

}  // namespace ProtocolText

#endif
