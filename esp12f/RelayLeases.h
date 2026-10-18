#ifndef SMART_LIFT_RELAY_LEASES_H
#define SMART_LIFT_RELAY_LEASES_H

#include <stdint.h>
#include <string.h>
#include "ProtocolText.h"

// No Arduino dependencies: the same state machine runs in the firmware and host tests.
// A session must be accepted before reset or movement. Boot starts STOP-latched;
// disconnect clears leases and session approval while preserving the STOP latch.
// Each lift has at most one active direction and one command ID. Only that exact
// press can renew or release it, and expiry closes the press without latching STOP.
// Accepted resets remember the last reset ID across STOP and reconnect, but not
// across power cycles. This is bounded replay protection, not a full ID history.
class RelayLeases {
 public:
  static constexpr uint8_t count = 5;
  static constexpr uint32_t leaseMs = 750;
  static constexpr uint8_t maxCommandLength = ProtocolText::maxIdentifierLength;

  struct Lease {
    bool active;
    uint8_t direction;
    uint32_t renewedAt;
    char commandId[maxCommandLength + 1];
  };

  enum class Result { Accepted, Invalid, NotReady, Stopped, Conflict, Stale };
  enum class ResetResult { Accepted, Duplicate, Invalid, NotReady, NotStopped, Stale };

  RelayLeases() : ready_(false), stopped_(true) { clear(); lastResetId_[0] = '\0'; }

  bool ready() const { return ready_; }
  bool stopped() const { return stopped_; }
  // Callers iterate count entries or validate the index before requesting a lease.
  const Lease& at(uint8_t index) const { return leases_[index]; }
  void disconnect() { ready_ = false; clear(); }
  void acceptSession() {
    if (!ready_) { clear(); ready_ = true; }
  }
  void stop() { stopped_ = true; clear(); }

  ResetResult resetStop(const char* resetId) {
    if (!ProtocolText::isIdentifier(resetId)) return ResetResult::Invalid;
    if (!ready_) return ResetResult::NotReady;
    if (strcmp(lastResetId_, resetId) == 0)
      return stopped_ ? ResetResult::Stale : ResetResult::Duplicate;
    if (!stopped_) return ResetResult::NotStopped;
    clear();
    strcpy(lastResetId_, resetId);
    stopped_ = false;
    return ResetResult::Accepted;
  }

  bool anyActive() const {
    for (uint8_t i = 0; i < count; ++i) if (leases_[i].active) return true;
    return false;
  }

  bool expired(uint8_t index, uint32_t now) const {
    return index < count && leases_[index].active &&
           static_cast<uint32_t>(now - leases_[index].renewedAt) >= leaseMs;
  }

  // Keep the closed command ID so a late renewal/start cannot revive this press.
  void expire(uint8_t index) {
    if (index < count) leases_[index].active = false;
  }

  Result execute(uint8_t index, uint8_t direction, uint8_t toggle,
                 const char* commandId, bool renew, uint32_t now) {
    if (index >= count || direction > 2 || toggle > 1 ||
        !ProtocolText::isIdentifier(commandId)) return Result::Invalid;
    if (!ready_) return Result::NotReady;
    if (stopped_) return Result::Stopped;
    Lease& lease = leases_[index];
    // Defensive check even when a caller has not serviced expiry yet.
    if (expired(index, now)) lease.active = false;
    const bool matches = lease.direction == direction && strcmp(lease.commandId, commandId) == 0;
    if (!toggle) {
      if (!matches) return Result::Stale;
      lease.active = false;
      return Result::Accepted;
    }
    if (renew) {
      if (!lease.active || !matches) return Result::Stale;
      lease.renewedAt = now;
      return Result::Accepted;
    }
    // All three outputs of a lift are mutually exclusive. Switching requires release.
    if (lease.active) return Result::Conflict;
    if (strcmp(lease.commandId, commandId) == 0) return Result::Stale;
    lease.active = true;
    lease.direction = direction;
    lease.renewedAt = now;
    strcpy(lease.commandId, commandId);
    return Result::Accepted;
  }

 private:
  void clear() { memset(leases_, 0, sizeof(leases_)); }
  Lease leases_[count];
  char lastResetId_[maxCommandLength + 1];
  bool ready_;
  bool stopped_;
};

#endif
