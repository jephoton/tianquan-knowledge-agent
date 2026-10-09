--------------------------- MODULE MC_tianquan ---------------------------
(***************************************************************************)
(* LIVE DEMO HARNESS — one file, flip one flag.                            *)
(*                                                                         *)
(* This is the single spec to drive the formal-verification demo. Run it   *)
(* as-is and TLC reports NO error — the pipeline is proven safe across     *)
(* every interleaving of search / decide / retrieve / answer / revoke.     *)
(*                                                                         *)
(* The DEMO does not flip this flag — it edits the real retrieval logic in *)
(* access_control.tla (see that file's `AdmitToContext` / `Retrieve` and   *)
(* the demo runbook). `BROKEN` is retained only so the automated           *)
(* MC_safe / MC_broken harnesses can select the variant without editing.   *)
(*                                                                         *)
(* The subtle bug the checker catches: an admin revokes access AFTER the   *)
(* policy decision but BEFORE retrieval; a naive implementation that       *)
(* trusts the decide-time snapshot (instead of re-checking the live ACL)   *)
(* leaks the now-unauthorized resource. A time-of-check/time-of-use race   *)
(* unit tests cannot exhaustively cover.                                   *)
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
