--------------------------- MODULE MC_broken ---------------------------
(***************************************************************************)
(* Model-checking harness for the BROKEN variant (BROKEN = TRUE).          *)
(*                                                                         *)
(* Identical to MC_safe except the model reorders so that ALL candidates   *)
(* are retrieved into the LLM context regardless of the policy decision —  *)
(* i.e. "filter after retrieval". This is the anti-pattern ADR-0002        *)
(* rejects. TLC is EXPECTED to find a counterexample violating INV2 (and   *)
(* INV1/INV7): an over-fetched, denied resource reaches the LLM context.   *)
(*                                                                         *)
(* This is the 60-second Demo 5 payoff: same spec, one flag flipped, and   *)
(* the model checker exhibits the exact unsafe trace.                      *)
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
         BROKEN <- TRUE
=========================================================================
