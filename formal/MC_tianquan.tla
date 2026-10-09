--------------------------- MODULE MC_tianquan ---------------------------
(***************************************************************************)
(* LIVE DEMO HARNESS — one file, flip one flag.                            *)
(*                                                                         *)
(* This is the single spec to drive the formal-verification demo. Run it   *)
(* once as-is (BROKEN = FALSE) and TLC reports NO error — the pipeline is  *)
(* proven safe across every interleaving of search / decide / retrieve /   *)
(* answer / revoke.                                                        *)
(*                                                                         *)
(* Then, LIVE, change the one line below to `BROKEN <- TRUE` and re-run.   *)
(* TLC finds a counterexample and prints the exact unsafe trace: an admin  *)
(* revokes access AFTER the policy decision but BEFORE retrieval, and the  *)
(* naive implementation (which trusts the decide-time snapshot instead of  *)
(* re-checking the live ACL) leaks the now-unauthorized resource into the  *)
(* LLM context. This is the time-of-check / time-of-use race — a bug unit  *)
(* tests cannot exhaustively cover, caught here by exhaustive state-space  *)
(* exploration.                                                            *)
(*                                                                         *)
(* Baseline ACL: alice may read r1 only; bob may read r2 only. Asker=alice *)
(***************************************************************************)
CONSTANTS alice, bob, r1, r2

VARIABLES phase, acl, revoked, candidates, decisions, context, citations, audit

AuthorizedDef == [ r \in {r1, r2} |->
                     CASE r = r1 -> {alice}
                       [] r = r2 -> {bob} ]

INSTANCE access_control
    WITH Users <- {alice, bob},
         Resources <- {r1, r2},
         Authorized <- AuthorizedDef,
         Asker <- alice,
         \* ====== FLIP THIS LINE LIVE IN THE DEMO ======
         \*   FALSE = safe (re-checks live ACL at retrieval)  -> no error
         \*   TRUE  = naive (trusts stale decide-time snapshot) -> leak
         BROKEN <- FALSE
=========================================================================
