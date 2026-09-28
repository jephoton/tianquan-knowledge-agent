---------------------------- MODULE MC_safe ----------------------------
(***************************************************************************)
(* Model-checking harness for the SAFE variant (BROKEN = FALSE).           *)
(* Instantiates concrete constants for access_control and defines the      *)
(* Authorized ACL function that a .cfg literal cannot express directly.    *)
(*                                                                         *)
(* Baseline ACL:                                                           *)
(*   alice may read r1 only.                                               *)
(*   bob   may read r2 only.                                               *)
(* Asker is alice, so r1 is authorized and r2 is not (over-fetch target).  *)
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
         BROKEN <- FALSE
=========================================================================
