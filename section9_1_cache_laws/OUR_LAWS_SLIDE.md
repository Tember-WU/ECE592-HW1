# Our Laws — lab evidence, predictions, and scaling limits

**Patel–Wu L2 Capacity Growth Law**  
C_L2(t) = 2048 × 2^[0.414286(t−2023)] KiB/core; doubling ≈ 2.41 years.  
Eight pooled lab hosts; sampled plateaus and jumps, with a strong server/desktop confound.  
Likely wall: area, energy and physical access delay; expect piecewise growth.  
Show `figures/law_1.pdf`.

**Patel–Wu Relative Cache Latency Law**  
R(t) = median(T_L2/T_L1) ≈ 2.918; descriptive envelope 2.588–3.333.  
Eight pooled hosts; weak chronological trend, not an absolute-cycle latency claim.  
Likely change: pipeline or topology steps; hiding latency does not shorten dependency latency.  
Show `figures/law_2.pdf`.

**Planned held-out logic (not executed):** eight lab observations → GitHub-frozen laws and predictions → Hazel measurement stars/diamonds → unchanged-model error and verdict.  
**Experimental limitation:** We did not complete the Hazel experiments because we ran out of time. Both laws use lab evidence only; the Hazel predictions are untested and neither law has a held-out verdict. A GitHub pre-experiment freeze is not verified.

Speaker note: Both figures compare Intel, AMD and Ampere/Arm with distinct markers. The 2028 scenario is conditional and lab-only. Hazel validation and a subsequent post-Hazel forecast were not completed because the team ran out of time.
