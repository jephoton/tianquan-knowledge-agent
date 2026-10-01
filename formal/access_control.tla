-------------------------- MODULE access_control --------------------------
(***************************************************************************)
(* Tianquan 天权 — formal model of permission-aware retrieval.                 *)
(*                                                                         *)
(* Models the lifecycle of a single user query over a small universe of    *)
(* users and resources:                                                    *)
(*                                                                         *)
(*   submit query                                                          *)
(*     -> search candidates                                                *)
(*     -> policy-decide each candidate (allow / deny, audited)             *)
(*     -> retrieve authorized candidates into the LLM context              *)
(*     -> answer with citations                                            *)
(*   with permission revocation possible before the decision.             *)
(*                                                                         *)
(* The key safety claim (ADR-0002) is that filtering happens BEFORE the    *)
(* LLM: the context contains only authorized content. A BROKEN mode        *)
(* reorders retrieval before the policy decision so TLC can exhibit a      *)
(* counterexample to INV2 (Demo 5).                                        *)
(*                                                                         *)
(* Invariants encoded: INV1, INV2, INV3, INV4, INV6, INV7.                 *)
(* INV5 (NoPrivilegeEscalation / delegation) is out of scope — the action   *)
(* agent was removed from the roadmap.                                      *)
(***************************************************************************)
EXTENDS Naturals, FiniteSets

CONSTANTS
    Users,        \* set of user ids, e.g. {"alice", "bob"}
    Resources,    \* set of resource ids, e.g. {"r1", "r2"}
    Authorized,   \* Authorized[u] = set of resources user u may read (baseline ACL)
    Asker,        \* the user submitting the query
    BROKEN        \* TRUE => retrieve-before-decide (deliberately unsafe variant)

VARIABLES
    phase,        \* "init" -> "searched" -> "decided" -> "retrieved" -> "answered"
    acl,          \* acl[r] = current set of users allowed to read r (mutable, revocable)
    revoked,      \* set of <<user, resource>> pairs revoked this run
    candidates,   \* set of candidate resources from search (may over-fetch)
    decisions,    \* [r -> {"allow","deny","none"}] policy decision per candidate
    context,      \* set of resources placed in the LLM context
    citations,    \* set of resources cited in the answer
    audit         \* set of <<resource, decision>> audit records

vars == << phase, acl, revoked, candidates, decisions, context, citations, audit >>

(***************************************************************************)
(* Whether the asker is currently authorized for r, per the LIVE acl.      *)
(* This mirrors the implementation: the permission filter reads the live   *)
(* ACL, never a stale snapshot.                                            *)
(***************************************************************************)
LiveAllowed(r) == Asker \in acl[r]

TypeOK ==
    /\ phase \in {"init", "searched", "decided", "retrieved", "answered"}
    /\ acl \in [Resources -> SUBSET Users]
    /\ revoked \subseteq (Users \X Resources)
    /\ candidates \subseteq Resources
    /\ decisions \in [Resources -> {"allow", "deny", "none"}]
    /\ context \subseteq Resources
    /\ citations \subseteq Resources
    /\ audit \subseteq (Resources \X {"allow", "deny"})

Init ==
    /\ phase = "init"
    /\ acl = [r \in Resources |-> Authorized[r]]
    /\ revoked = {}
    /\ candidates = {}
    /\ decisions = [r \in Resources |-> "none"]
    /\ context = {}
    /\ citations = {}
    /\ audit = {}

(***************************************************************************)
(* Revocation: at any time before the decision, remove the asker from some *)
(* resource's ACL. Bumps nothing but the live ACL — the model abstracts    *)
(* ACL versions as "the live acl set".                                     *)
(***************************************************************************)
Revoke(r) ==
    /\ phase \in {"init", "searched"}
    /\ Asker \in acl[r]
    /\ acl' = [acl EXCEPT ![r] = acl[r] \ {Asker}]
    /\ revoked' = revoked \cup { <<Asker, r>> }
    /\ UNCHANGED << phase, candidates, decisions, context, citations, audit >>

(***************************************************************************)
(* Search: produce a candidate set. Modeled as an arbitrary non-empty      *)
(* subset of resources to capture over-fetching (candidates may include    *)
(* resources the asker is not authorized to see).                          *)
(***************************************************************************)
Search ==
    /\ phase = "init"
    /\ \E cand \in (SUBSET Resources) \ {{}} :
         candidates' = cand
    /\ phase' = "searched"
    /\ UNCHANGED << acl, revoked, decisions, context, citations, audit >>

(***************************************************************************)
(* Decide: for every candidate, record an allow/deny decision from the     *)
(* LIVE acl, and write an audit record for each. This is the policy gate.  *)
(***************************************************************************)
Decide ==
    /\ phase = "searched"
    /\ decisions' = [ r \in Resources |->
                        IF r \in candidates
                        THEN IF LiveAllowed(r) THEN "allow" ELSE "deny"
                        ELSE "none" ]
    /\ audit' = { <<r, IF LiveAllowed(r) THEN "allow" ELSE "deny">>
                    : r \in candidates }
    /\ phase' = "decided"
    /\ UNCHANGED << acl, revoked, candidates, context, citations >>

(***************************************************************************)
(* Retrieve into context.                                                  *)
(*                                                                         *)
(* SAFE (BROKEN = FALSE): only candidates decided "allow" enter context.   *)
(* BROKEN (BROKEN = TRUE): all candidates enter context regardless of the  *)
(*   decision — i.e. filtering happens after retrieval. This is the        *)
(*   deliberately unsafe variant that violates INV2.                       *)
(***************************************************************************)
Retrieve ==
    /\ phase = "decided"
    /\ context' = IF BROKEN
                    THEN candidates
                    ELSE { r \in candidates : decisions[r] = "allow" }
    /\ phase' = "retrieved"
    /\ UNCHANGED << acl, revoked, candidates, decisions, citations, audit >>

(***************************************************************************)
(* Answer: cite a subset of what is in context. Citations can only come    *)
(* from the context (the answer agent grounds on assembled content).       *)
(***************************************************************************)
Answer ==
    /\ phase = "retrieved"
    /\ \E cited \in SUBSET context :
         citations' = cited
    /\ phase' = "answered"
    /\ UNCHANGED << acl, revoked, candidates, decisions, context, audit >>

Next ==
    \/ Search
    \/ Decide
    \/ Retrieve
    \/ Answer
    \/ \E r \in Resources : Revoke(r)
    \/ (phase = "answered" /\ UNCHANGED vars)   \* stutter at end

Spec == Init /\ [][Next]_vars

(***************************************************************************)
(* Invariants.                                                             *)
(***************************************************************************)

\* INV1: nothing retrieved is outside the asker's live permission set.
INV1_RetrievedOnlyIfAuthorized ==
    \A r \in context : LiveAllowed(r)

\* INV2: the LLM (context) never contains unauthorized content.
\* (Same shape as INV1 here because context IS what the LLM sees; kept
\*  separate to name the property the broken variant violates.)
INV2_LLMSeesOnlyRetrievedContent ==
    \A r \in context : LiveAllowed(r)

\* INV3: a revoked <<asker,r>> is never present in the context.
INV3_RevokedAccessNotReusable ==
    \A r \in Resources :
        (<<Asker, r>> \in revoked) => (r \notin context)

\* INV4: once decided, every candidate has an audit record.
INV4_EveryDecisionAudited ==
    (phase \in {"decided", "retrieved", "answered"})
        => \A r \in candidates :
             \E d \in {"allow", "deny"} : <<r, d>> \in audit

\* INV6: every citation corresponds to an authorized, in-context resource.
INV6_NoUnauthorizedCitation ==
    \A r \in citations : (r \in context) /\ LiveAllowed(r)

\* INV7: denied content never leaks into context or citations.
INV7_NoMetadataLeakOnDeny ==
    \A r \in Resources :
        (decisions[r] = "deny") => (r \notin context /\ r \notin citations)

=============================================================================
