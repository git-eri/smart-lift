// g++ -std=c++11 -Wall -Wextra -Werror esp12f/tests/relay_leases_test.cpp -o relay-leases-test
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include "../RelayLeases.h"

using Result = RelayLeases::Result;
using ResetResult = RelayLeases::ResetResult;

static void arm(RelayLeases& state) {
  state.acceptSession();
  assert(state.resetStop("initial-reset") == ResetResult::Accepted);
}

static void test_boot_and_session_gate() {
  RelayLeases state;
  assert(state.stopped() && !state.ready() && !state.anyActive());
  assert(state.resetStop("initial-reset") == ResetResult::NotReady);
  assert(state.execute(0, 0, 1, "press", false, 0) == Result::NotReady);
  state.acceptSession();
  assert(state.stopped());
  assert(state.execute(0, 0, 1, "press", false, 0) == Result::Stopped);
  assert(state.resetStop("initial-reset") == ResetResult::Accepted);
  assert(!state.anyActive());
  assert(state.execute(0, 0, 1, "press", false, 0) == Result::Accepted);
}

static void test_all_three_directions_interlock() {
  for (uint8_t active = 0; active < 3; ++active) {
    RelayLeases state;
    arm(state);
    assert(state.execute(0, active, 1, "a", false, 0) == Result::Accepted);
    for (uint8_t next = 0; next < 3; ++next) {
      assert(state.execute(0, next, 1, "b", false, 1) == Result::Conflict);
      assert(state.at(0).active && state.at(0).direction == active);
    }
    assert(state.execute(0, active, 0, "a", false, 2) == Result::Accepted);
    assert(state.execute(0, (active + 1) % 3, 1, "b", false, 3) == Result::Accepted);
  }
}

static void test_expiry_and_late_renewal() {
  RelayLeases state;
  arm(state);
  assert(state.execute(0, 0, 1, "a", false, 100) == Result::Accepted);
  assert(!state.expired(0, 849));
  assert(state.expired(0, 850));
  state.expire(0);
  assert(!state.at(0).active);
  assert(state.execute(0, 0, 1, "a", true, 851) == Result::Stale);
  assert(state.execute(0, 0, 1, "a", false, 852) == Result::Stale);
  assert(state.execute(0, 0, 1, "b", false, 853) == Result::Accepted);
}

static void test_expiry_checked_inside_command() {
  RelayLeases state;
  arm(state);
  assert(state.execute(0, 0, 1, "a", false, 0) == Result::Accepted);
  assert(state.execute(0, 0, 1, "a", true, 750) == Result::Stale);
  assert(!state.anyActive());
}

static void test_renewal_requires_exact_press_and_direction() {
  RelayLeases state;
  arm(state);
  assert(state.execute(0, 0, 1, "a", false, 0) == Result::Accepted);
  assert(state.execute(0, 1, 1, "a", true, 500) == Result::Stale);
  assert(state.execute(0, 0, 1, "b", true, 500) == Result::Stale);
  assert(state.at(0).renewedAt == 0);
  assert(state.execute(0, 0, 1, "a", true, 500) == Result::Accepted);
  assert(!state.expired(0, 1249));
  assert(state.expired(0, 1250));
}

static void test_late_release_cannot_stop_another_press() {
  RelayLeases state;
  arm(state);
  assert(state.execute(0, 0, 1, "a", false, 0) == Result::Accepted);
  assert(state.execute(0, 1, 0, "a", false, 10) == Result::Stale);
  assert(state.at(0).active);
  assert(state.execute(0, 0, 0, "a", false, 20) == Result::Accepted);
  assert(state.execute(0, 1, 1, "b", false, 30) == Result::Accepted);
  assert(state.execute(0, 0, 0, "a", false, 40) == Result::Stale);
  assert(state.at(0).active && state.at(0).direction == 1);
}

static void test_independent_lifts_and_expiry() {
  RelayLeases state;
  arm(state);
  assert(state.execute(0, 0, 1, "a", false, 0) == Result::Accepted);
  assert(state.execute(4, 2, 1, "b", false, 500) == Result::Accepted);
  assert(state.expired(0, 750) && !state.expired(4, 750));
  state.expire(0);
  assert(state.anyActive() && state.at(4).active);
}

static void test_stop_latch_survives_reconnection() {
  RelayLeases state;
  arm(state);
  assert(state.execute(0, 0, 1, "a", false, 0) == Result::Accepted);
  state.stop();
  assert(state.stopped() && !state.anyActive());
  state.disconnect();
  assert(!state.ready() && state.stopped());
  assert(state.resetStop("second-reset") == ResetResult::NotReady);
  state.acceptSession();
  assert(state.stopped());
  assert(state.execute(0, 0, 1, "b", false, 10) == Result::Stopped);
  assert(state.resetStop("second-reset") == ResetResult::Accepted);
  assert(!state.anyActive());
  assert(state.execute(0, 0, 1, "a", true, 20) == Result::Stale);
  assert(state.execute(0, 0, 1, "b", false, 30) == Result::Accepted);
}

static void test_disconnect_clears_movements_without_changing_latch() {
  RelayLeases state;
  arm(state);
  assert(state.execute(0, 0, 1, "a", false, 0) == Result::Accepted);
  state.disconnect();
  assert(!state.anyActive() && !state.ready() && !state.stopped());
  assert(state.execute(0, 0, 1, "b", false, 10) == Result::NotReady);
  state.acceptSession();
  assert(state.execute(0, 0, 1, "a", true, 20) == Result::Stale);
  assert(!state.anyActive());
}

static void test_millis_wraparound() {
  RelayLeases state;
  arm(state);
  const uint32_t start = UINT32_MAX - 200;
  assert(state.execute(0, 0, 1, "a", false, start) == Result::Accepted);
  assert(!state.expired(0, static_cast<uint32_t>(start + 749)));
  assert(state.expired(0, static_cast<uint32_t>(start + 750)));
  assert(state.execute(0, 0, 1, "a", true, static_cast<uint32_t>(start + 749)) == Result::Accepted);
  assert(!state.expired(0, static_cast<uint32_t>(start + 1498)));
  assert(state.expired(0, static_cast<uint32_t>(start + 1499)));
}

static void test_invalid_fields_and_command_length() {
  RelayLeases state;
  arm(state);
  char tooLong[66];
  memset(tooLong, 'a', 65); tooLong[65] = 0;
  assert(state.execute(5, 0, 1, "a", false, 0) == Result::Invalid);
  assert(state.execute(0, 3, 1, "a", false, 0) == Result::Invalid);
  assert(state.execute(0, 0, 2, "a", false, 0) == Result::Invalid);
  assert(state.execute(0, 0, 1, "", false, 0) == Result::Invalid);
  assert(state.execute(0, 0, 1, nullptr, false, 0) == Result::Invalid);
  assert(state.execute(0, 0, 1, tooLong, false, 0) == Result::Invalid);
  tooLong[64] = 0;
  assert(state.execute(0, 0, 1, tooLong, false, 0) == Result::Accepted);
}

static void test_duplicate_reset_preserves_live_press() {
  RelayLeases state;
  arm(state);
  assert(state.execute(0, 0, 1, "press", false, 100) == Result::Accepted);
  assert(state.resetStop("initial-reset") == ResetResult::Duplicate);
  assert(!state.stopped() && state.at(0).active && state.at(0).renewedAt == 100);
  assert(state.execute(0, 0, 1, "press", true, 500) == Result::Accepted);
}

static void test_previous_reset_cannot_clear_later_stop() {
  RelayLeases state;
  arm(state);
  state.stop();
  assert(state.resetStop("initial-reset") == ResetResult::Stale);
  assert(state.stopped());
  state.disconnect();
  state.acceptSession();
  assert(state.resetStop("initial-reset") == ResetResult::Stale);
  assert(state.stopped());
  assert(state.resetStop("fresh-reset") == ResetResult::Accepted);
  assert(!state.stopped() && !state.anyActive());
}

static void test_different_reset_while_clear_preserves_live_press() {
  RelayLeases state;
  arm(state);
  assert(state.execute(0, 1, 1, "press", false, 100) == Result::Accepted);
  assert(state.resetStop("unrelated-reset") == ResetResult::NotStopped);
  assert(state.at(0).active && !state.stopped());
  assert(state.execute(0, 1, 1, "press", true, 500) == Result::Accepted);
}

static void test_invalid_reset_does_not_clear_stop() {
  RelayLeases state;
  state.acceptSession();
  assert(state.resetStop("") == ResetResult::Invalid);
  assert(state.resetStop(nullptr) == ResetResult::Invalid);
  assert(state.resetStop("not a valid ID") == ResetResult::Invalid);
  char tooLong[66];
  memset(tooLong, 'a', 65); tooLong[65] = 0;
  assert(state.resetStop(tooLong) == ResetResult::Invalid);
  assert(state.stopped());
  assert(state.resetStop("fresh-reset") == ResetResult::Accepted);
}

static void test_duplicate_session_approval_preserves_live_press() {
  RelayLeases state;
  arm(state);
  assert(state.execute(0, 2, 1, "press", false, 100) == Result::Accepted);
  state.acceptSession();
  assert(state.at(0).active && state.ready() && !state.stopped());
}

static void test_expiry_helpers_reject_out_of_range_indices() {
  RelayLeases state;
  arm(state);
  assert(state.execute(0, 0, 1, "press", false, 0) == Result::Accepted);
  assert(!state.expired(RelayLeases::count, 1000));
  assert(!state.expired(255, 1000));
  state.expire(RelayLeases::count);
  state.expire(255);
  assert(state.at(0).active);
}

static void test_text_validation_rejects_embedded_nul_aliases() {
  const char command[] = "reset_stop\0extra";
  const char server[] = "server.lan\0.other";
  assert(!ProtocolText::isText(command, sizeof(command) - 1));
  assert(!ProtocolText::isText(server, sizeof(server) - 1));
  assert(ProtocolText::isText("", 0));
  assert(ProtocolText::isText("reset_stop", 10));
  assert(!ProtocolText::isText(nullptr, 0));
}

static void test_identifier_validation_matches_wire_rules() {
  const char embeddedNul[] = "valid\0suffix";
  assert(!ProtocolText::isIdentifier(embeddedNul, sizeof(embeddedNul) - 1));
  assert(!ProtocolText::isIdentifier("has space"));
  assert(!ProtocolText::isIdentifier("contains.dot"));
  assert(!ProtocolText::isIdentifier("unicode-\xc3\xa4"));
  assert(ProtocolText::isIdentifier("Press_123-next"));
  char boundary[66];
  memset(boundary, 'a', 65); boundary[65] = 0;
  assert(!ProtocolText::isIdentifier(boundary));
  boundary[64] = 0;
  assert(ProtocolText::isIdentifier(boundary));
}

int main() {
  test_boot_and_session_gate();
  test_all_three_directions_interlock();
  test_expiry_and_late_renewal();
  test_expiry_checked_inside_command();
  test_renewal_requires_exact_press_and_direction();
  test_late_release_cannot_stop_another_press();
  test_independent_lifts_and_expiry();
  test_stop_latch_survives_reconnection();
  test_disconnect_clears_movements_without_changing_latch();
  test_millis_wraparound();
  test_invalid_fields_and_command_length();
  test_duplicate_reset_preserves_live_press();
  test_previous_reset_cannot_clear_later_stop();
  test_different_reset_while_clear_preserves_live_press();
  test_invalid_reset_does_not_clear_stop();
  test_duplicate_session_approval_preserves_live_press();
  test_expiry_helpers_reject_out_of_range_indices();
  test_text_validation_rejects_embedded_nul_aliases();
  test_identifier_validation_matches_wire_rules();
  puts("19 relay lease and protocol text tests passed");
}
