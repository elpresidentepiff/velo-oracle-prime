--- src/intelligence/velo_prime_ensemble.py.orig	2026-05-03 17:57:10.071685200 -0700
+++ src/intelligence/velo_prime_ensemble.py.tmp	2026-05-03 17:57:09.980883900 -0700
@@ -184,15 +184,18 @@
     # They are computed and persisted in velo_verdicts for auditing only.
     # See excluded_from_ensemble field on every verdict row for confirmation.
     "improvement_score":     0.12,  # DISABLED — ablation 2026-04-04: hurts top-1 (-0.6 ppts)
-    "release_window_score":  0.10,  # DISABLED — RPD features not wired in live pipeline
-    "comment_intel_score":   0.08,  # DISABLED — RPD features not wired in live pipeline
+    "release_window_score":  0.00,  # DISABLED_FROM_LIVE_WEIGHT — live_sidecar_ablation_audit: harmful ROI
+    "comment_intel_score":   0.00,  # DISABLED_FROM_LIVE_WEIGHT — live_sidecar_ablation_audit: harmful ROI
 }
 
 # ─── Disabled components ────────────────────────────────────────────────────────
 # Components listed here are excluded from the ensemble regardless of weight.
 # Condition for disabling: required input features are not available in the live
-# scoring pipeline, causing the specialist model to return a constant output that
-# adds zero ranking signal while distorting probability scaling.
+# scoring pipeline, or the component demonstrated harmful ROI in live audit.
+#
+# Disabled from live VP weighting after live_sidecar_ablation_audit: 
+# release_day_prob/comment_intel_score showed harmful ROI profile. 
+# Fields remain logged for audit/operator visibility.
 #
 # release_window_score — requires RPD timing features (setup_run_flag,
 #   cash_run_flag, trainer_timing_score, runs_since_win/place …)
@@ -207,8 +210,8 @@
 # Re-enable only when the required feature pipeline is fully wired and
 # the field-level zero-variance kill switch (in predict_race) does NOT fire.
 _DISABLED_COMPONENTS: set[str] = {
-    "release_window_score",
-    "comment_intel_score",
+    "release_window_score", # STORED_ONLY
+    "comment_intel_score",  # STORED_ONLY
     # Ablation backtest (2026-04-04, 647 races): improvement_score hurts top-1
     # (-0.6 ppts vs SQPE+Place) and avgWinP (-0.003). No compensating case.
     # Re-enable only if a retrained model demonstrates lift over SQPE+Place+MktDeception.
@@ -241,6 +244,19 @@
     ABLATION_FULL_MINUS_DEAD:              set(),
 }
 
+# ─── Production Policies ────────────────────────────────────────────────────────
+# Controlled by VELO_ENSEMBLE_POLICY env var.
+POLICY_CURRENT = "current"
+POLICY_NO_RELEASE_COMMENT = "no_release_comment"
+
+_ACTIVE_POLICY = _os.getenv("VELO_ENSEMBLE_POLICY", POLICY_CURRENT).lower()
+
+def _get_policy_exclude() -> set[str]:
+    """Return components to exclude based on the active production policy."""
+    if _ACTIVE_POLICY == POLICY_NO_RELEASE_COMMENT:
+        return {"release_window_score", "comment_intel_score"}
+    return set()
+
 # Macro modifiers — these adjust confidence/weight, don't replace probabilities
 _MACRO_CHAOS_CONFIDENCE_DAMPER    = 0.80  # reduce model confidence in chaos regime
 _MACRO_COMPRESSION_FAV_PENALTY    = 0.05  # subtract from favourite's prob when trap=high
@@ -284,6 +300,15 @@
     doctrines_fired: list = field(default_factory=list)  # list of doctrine names that fired
     g_shadow_flags: list = field(default_factory=list)  # what G did
 
+    # HFS Signal Contract v1 — populated by _compute_hfs_signals() after compute()
+    mpi: Optional[float] = None
+    chaos_bloom: Optional[float] = None
+    mpi_source: Optional[str] = None
+    chaos_bloom_source: Optional[str] = None
+    mpi_block_reason: Optional[str] = None
+    chaos_bloom_block_reason: Optional[str] = None
+    signal_contract_version: str = "hfs_signal_contract_v1"
+
     def compute(self, killed: set[str] | None = None) -> "VeloPrimePrediction":
         """Build VELO_PRIME_prob from all available signals.
 
@@ -291,9 +316,12 @@
             killed: additional components to exclude this race (from field-level
                     zero-variance kill switch in predict_race).
         """
-        excluded = _DISABLED_COMPONENTS | (killed or set())
+        policy_exclude = _get_policy_exclude()
+        excluded = _DISABLED_COMPONENTS | policy_exclude | (killed or set())
         scores = {"sqpe_v17": self.sqpe_v17_prob}
-        # Track for observability (populated after scores dict is built below)
+        
+        # Log active policy
+        self.verdict_flags.append(f"policy:{_ACTIVE_POLICY}")
 
         if "improvement_score" not in excluded and self.improvement_score is not None:
             scores["improvement_score"] = self.improvement_score
@@ -382,8 +410,62 @@
         else:
             self.confidence_level = "low"
 
+        # Compute HFS signal contract fields after velo_prime_prob is finalised
+        self._compute_hfs_signals()
+
         return self
 
+    def _compute_hfs_signals(self) -> None:
+        """
+        Compute mpi and chaos_bloom for the HFS signal contract.
+        Called at the end of compute() so velo_prime_prob is already finalised.
+        Formula version: hfs_signal_contract_v1.1 (hardened against nulls)
+
+        MPI  = market pressure index (model vs market disagreement), bounded [0,1]
+        chaos_bloom = race entropy index (macro context), bounded [0,1]
+        """
+        # ── MPI ───────────────────────────────────────────────────────────────
+        vp = getattr(self, 'velo_prime_prob', self.sqpe_v17_prob)
+        mds = getattr(self, 'market_deception_score', None)
+        
+        if vp is not None and mds is not None:
+            # MPI = blend of model confidence and market deception signal
+            raw = (vp * 0.6) + (mds * 0.4)
+            self.mpi = round(min(1.0, max(0.0, raw)), 4)
+            self.mpi_source = "derived_from_vp_mds"
+        elif vp is not None:
+            # Neutral fallback: use vp directly if mds missing
+            self.mpi = round(min(1.0, max(0.0, vp)), 4)
+            self.mpi_source = "derived_from_vp_only"
+            self.mpi_block_reason = "mds_missing_fallback_applied"
+        else:
+            self.mpi = 0.5  # Absolute fallback
+            self.mpi_source = "neutral_fallback"
+            self.mpi_block_reason = "velo_prime_prob_missing"
+
+        # ── Chaos bloom ───────────────────────────────────────────────────────
+        chaos_mode = None
+        trap_risk = None
+        if self.macro_context:
+            chaos_mode = getattr(self.macro_context, 'chaos_mode', None)
+            trap_risk = getattr(self.macro_context, 'favourite_trap_risk', None)
+
+        # Hardened logic: always return at least 0.3
+        base = 0.3
+        if chaos_mode:
+            base += 0.4
+        if trap_risk in ("high", "HIGH", True, 1):
+            base += 0.3
+        elif trap_risk in ("medium", "MEDIUM"):
+            base += 0.15
+        
+        self.chaos_bloom = round(min(1.0, max(0.0, base)), 4)
+        if not self.macro_context:
+            self.chaos_bloom_source = "neutral_fallback"
+            self.chaos_bloom_block_reason = "macro_context_missing"
+        else:
+            self.chaos_bloom_source = "derived_from_macro_field_trap"
+
     def to_dict(self) -> dict:
         return {
             "horse": self.horse,
@@ -412,6 +494,14 @@
             "g_shadow_flags": self.g_shadow_flags,
             "g_shadow_mode": _G_SHADOW_MODE,
             "doctrines_fired": self.doctrines_fired,
+            # HFS Signal Contract v1
+            "mpi": self.mpi,
+            "chaos_bloom": self.chaos_bloom,
+            "mpi_source": self.mpi_source,
+            "chaos_bloom_source": self.chaos_bloom_source,
+            "mpi_block_reason": self.mpi_block_reason,
+            "chaos_bloom_block_reason": self.chaos_bloom_block_reason,
+            "signal_contract_version": self.signal_contract_version,
         }
 
 
